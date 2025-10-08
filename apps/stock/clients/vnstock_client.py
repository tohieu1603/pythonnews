import time
from typing import Dict, Generator, Optional, Tuple

import pandas as pd
from vnstock import Company as VNCompany
from vnstock import Listing
from vnstock.explorer.vci.company import Company as VCIExplorerCompany
from apps.stock.services.rate_limiter import get_rate_limiter
from apps.stock.utils.pandas_compat import suppress_pandas_warnings
from core.db_utils import close_db_connections

# Suppress pandas warnings
suppress_pandas_warnings()


class VNStockClient:
    """
    Đóng gói calls tới vnstock, có retry/backoff khi dính rate-limit (SystemExit).
    Cung cấp helper để iterate symbols và fetch thông tin công ty.
    """

    def __init__(self, max_retries: int = 3, wait_seconds: int = 45):
        self.max_retries = max_retries
        self.wait_seconds = wait_seconds
        self.rate_limiter = get_rate_limiter()

    def _df_or_empty(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        """
        Helper to safely return a DataFrame or an empty one if the input is None.
        """
        if df is None:
            return pd.DataFrame()
        return df

    def _normalize_shareholder_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        rename_map = {}
        if "owner_full_name" in df.columns and "share_holder" not in df.columns:
            rename_map["owner_full_name"] = "share_holder"
        if "percentage" in df.columns and "share_own_percent" not in df.columns:
            rename_map["percentage"] = "share_own_percent"
        if rename_map:
            df = df.rename(columns=rename_map)

        drop_cols = [col for col in ("__typename", "ticker", "en__owner_full_name") if col in df.columns]
        if drop_cols:
            df = df.drop(columns=drop_cols)

        if "update_date" in df.columns:
            df["update_date"] = pd.to_datetime(df["update_date"], errors="coerce")
            df["update_date"] = df["update_date"].dt.strftime("%Y-%m-%d")

        for col in ("share_holder", "share_own_percent", "quantity", "update_date"):
            if col not in df.columns:
                df[col] = None

        return df[["share_holder", "quantity", "share_own_percent", "update_date"]]

    def _fetch_vci_shareholders_direct(self, symbol: str) -> pd.DataFrame:
        try:
            explorer = VCIExplorerCompany(symbol=symbol, random_agent=False, to_df=True, show_log=False)
            df = explorer._process_data(explorer.raw_data, "OrganizationShareHolders")
        except Exception as exc:
            print(f"Error fetching VCI shareholders for {symbol}: {exc}")
            return pd.DataFrame()

        return self._normalize_shareholder_df(df)

    def _fetch_shareholders(self, symbol: str, *companies: VNCompany) -> pd.DataFrame:
        direct_df = self._fetch_vci_shareholders_direct(symbol)
        if not direct_df.empty:
            return direct_df

        for company in companies:
            if company is None:
                continue
            try:
                df = company.shareholders()
            except SystemExit:
                raise
            except NotImplementedError:
                continue
            except Exception as exc:
                print(f"Error fetching shareholders from provider for {symbol}: {exc}")
                continue

            normalized = self._normalize_shareholder_df(self._df_or_empty(df))
            if not normalized.empty:
                return normalized

        return pd.DataFrame()

    def iter_all_symbols(
        self, exchange: Optional[str] = "HSX"
    ) -> Generator[Tuple[str, str], None, None]:
        """
        Lấy danh sách các mã ở sàn HSX (mặc định). Nếu truyền sàn khác,
        sẽ lọc theo sàn đó.
        """
        listing = Listing()
        df = listing.symbols_by_exchange()
        exch = (exchange or "HSX").upper()
        df = df[df["exchange"] == exch]
        df = df[df["symbol"].str.isalpha()]
        
        for _, row in df.iterrows():
            yield str(row.get("symbol")), str(row.get("exchange"))

    def fetch_company_bundle(
        self, symbol: str
    ) -> Tuple[Dict[str, pd.DataFrame], bool]:
        """
        Lấy bundle thông tin công ty từ cả 2 nguồn TCBS và VCI với rate limiting.
        """
        retries = 0
        while retries <= self.max_retries:
            vn_company_tcbs = None
            vn_company_vci = None
            listing = None

            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed(f"company_bundle_{symbol}")

                vn_company_tcbs = VNCompany(symbol=symbol, source="TCBS")
                vn_company_vci = VNCompany(symbol=symbol, source="VCI")
                listing = Listing()

                bundle = {
                    "overview_df_TCBS": self._df_or_empty(vn_company_tcbs.overview()),
                    "overview_df_VCI": self._df_or_empty(vn_company_vci.overview()),
                    "profile_df": self._df_or_empty(vn_company_tcbs.profile()),
                    "shareholders_df": self._fetch_shareholders(symbol, vn_company_vci, vn_company_tcbs),
                    "industries_icb_df": listing.industries_icb(),
                    "symbols_by_industries_df": listing.symbols_by_industries(),
                    "news_df": self._df_or_empty(vn_company_vci.news()),
                    "officers_df": self._df_or_empty(vn_company_vci.officers()),
                    "events_df": self._df_or_empty(vn_company_vci.events()),
                    "subsidiaries": self._df_or_empty(vn_company_tcbs.subsidiaries()),
                }

                return bundle, True

            except SystemExit:
                retries += 1
                wait_time = self.wait_seconds * (2 ** (retries - 1))
                print(
                    f"⚠️ Rate limit hit for {symbol}. Retry {retries}/{self.max_retries} after {wait_time}s..."
                )
                time.sleep(wait_time)

            except Exception as e:
                print(f"Error {symbol}: {e}")
                return {}, False

            finally:
                # Close DB connections
                close_db_connections(vn_company_tcbs, vn_company_vci, listing)

        return {}, False


    def fetch_company_bundle_safe(
        self, symbol: str
    ) -> Tuple[Dict[str, pd.DataFrame], bool]:
        """
        Safe/robust variant of fetch_company_bundle với rate limiting.
        - Wraps each VNStock call in its own try/except.
        - Returns partial bundle; ok=True if TCBS overview is available.
        """
        retries = 0
        while retries <= self.max_retries:
            listing = None
            vn_company_tcbs = None
            vn_company_vci = None

            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed(f"company_bundle_safe_{symbol}")

                listing = Listing()
                vn_company_tcbs = VNCompany(symbol=symbol, source="TCBS")
                vn_company_vci = VNCompany(symbol=symbol, source="VCI")

                # TCBS
                try:
                    overview_tcbs = self._df_or_empty(vn_company_tcbs.overview())
                except Exception:
                    overview_tcbs = pd.DataFrame()
                try:
                    profile_df = self._df_or_empty(vn_company_tcbs.profile())
                except Exception:
                    profile_df = pd.DataFrame()
                try:
                    news_df = self._df_or_empty(vn_company_vci.news())
                except Exception:
                    news_df = pd.DataFrame()
                try:
                    subs_df = self._df_or_empty(vn_company_tcbs.subsidiaries())
                except Exception:
                    subs_df = pd.DataFrame()

                # VCI
                try:
                    overview_vci = self._df_or_empty(vn_company_vci.overview())
                except Exception:
                    overview_vci = pd.DataFrame()
                shareholders_df = self._fetch_shareholders(symbol, vn_company_vci, vn_company_tcbs)
                try:
                    officers_df = self._df_or_empty(vn_company_vci.officers())
                except Exception:
                    officers_df = pd.DataFrame()
                try:
                    events_df = self._df_or_empty(vn_company_vci.events())
                except Exception:
                    events_df = pd.DataFrame()

                # Listing datasets
                try:
                    industries_icb_df = listing.industries_icb()
                except Exception:
                    industries_icb_df = pd.DataFrame()
                try:
                    symbols_by_industries_df = listing.symbols_by_industries()
                except Exception:
                    symbols_by_industries_df = pd.DataFrame()

                bundle = {
                    "overview_df_TCBS": overview_tcbs,
                    "overview_df_VCI": overview_vci,
                    "profile_df": profile_df,
                    "shareholders_df": shareholders_df,
                    "industries_icb_df": industries_icb_df,
                    "symbols_by_industries_df": symbols_by_industries_df,
                    "news_df": news_df,
                    "officers_df": officers_df,
                    "events_df": events_df,
                    "subsidiaries": subs_df,
                }

                ok = overview_tcbs is not None and not overview_tcbs.empty
                return bundle, bool(ok)

            except SystemExit:
                retries += 1
                wait_time = self.wait_seconds * (2 ** (retries - 1))
                print(
                    f"⚠️ Rate limit hit for {symbol}. Retry {retries}/{self.max_retries} after {wait_time}s..."
                )
                time.sleep(wait_time)

            except Exception as e:
                print(f"Error {symbol}: {e}")
                return {}, False

            finally:
                # Close DB connections
                close_db_connections(vn_company_tcbs, vn_company_vci, listing)

        return {}, False

