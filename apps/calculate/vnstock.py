import logging
import re
import time
from typing import Callable, Dict, Generator, List, Optional, Tuple

import pandas as pd
from vnstock import Company, Finance, Listing

from apps.stock.services.rate_limiter import get_rate_limiter
from core.db_utils import close_db_connections

logger = logging.getLogger(__name__)


class VNStock:

    def __init__(self, max_retries: int = 5, wait_seconds: int = 60):
        self.max_retries = max_retries
        self.wait_seconds = wait_seconds
        self.rate_limiter = get_rate_limiter()

    def _compute_wait_seconds(self, exc: Optional[SystemExit], retries: int) -> float:
        """
        Determine how long we should wait before retrying.
        - Try to respect the "try again after X seconds" hint from VCI.
        - Fall back to exponential backoff using `wait_seconds`.
        """
        base_wait = self.wait_seconds * max(1, 2 ** (retries - 1))

        if exc is None:
            return base_wait

        message = ""
        if isinstance(exc, SystemExit):
            if isinstance(exc.code, str):
                message = exc.code
            elif exc.code is not None:
                message = str(exc.code)
        else:
            message = str(exc)

        match = re.search(r"(\d+)\s*(?:giây|s|sec)", message)
        if match:
            suggested = int(match.group(1))
            # Add a small buffer to be safe
            return max(base_wait, suggested + 5)

        return base_wait

    def _df_or_empty(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()
        return df

    def _fetch_dataframe(
        self,
        endpoint: str,
        fetcher: Callable[[], Optional[pd.DataFrame]],
        error_context: str,
    ) -> pd.DataFrame:
        """
        Helper để gọi các method trả về DataFrame với rate limiting + error handling.
        """
        self.rate_limiter.wait_if_needed(endpoint)
        try:
            return self._df_or_empty(fetcher())
        except SystemExit:
            raise
        except Exception as exc:
            logger.warning("%s: %s", error_context, exc, exc_info=True)
            return pd.DataFrame()

    def iter_all_symbols(self, exchange: Optional[str] = "HSX") -> Generator[Tuple[str, str], None, None]:
        listing = None
        try:
            listing = Listing()
            self.rate_limiter.wait_if_needed("calculate_listing_symbols")
            df = listing.symbols_by_exchange()
            exch = (exchange or "HSX").upper()
            df = df[df["exchange"] == exch]

            for _, row in df.iterrows():
                yield str(row.get("symbol")), str(row.get("exchange"))
        finally:
            close_db_connections(listing)

    def inter_all_symbols(self, exchange: Optional[str] = "HSX") -> Generator[Tuple[str, str], None, None]:
        """
        Backwards-compatible alias (giữ lại tên cũ inter_all_symbols).
        """
        yield from self.iter_all_symbols(exchange)

    def fetch_bundle(
        self, symbol: str
    ) -> Tuple[Dict[str, pd.DataFrame], bool]:
        retries = 0
        while retries <= self.max_retries:
            finance: Optional[Finance] = None
            ratio_companies: List[Company] = []
            try:
                print(f"Trying to fetch data for {symbol}, attempt {retries + 1}")
                logger.info(
                    "Fetching finance bundle for %s (attempt %d/%d)",
                    symbol,
                    retries + 1,
                    self.max_retries,
                )

                # Rate limit trước khi tạo instance Finance (thường trigger network call)
                self.rate_limiter.wait_if_needed("calculate_finance_init")
                finance = Finance(symbol=symbol, source="VCI")

                bs_df = self._fetch_dataframe(
                    "calculate_finance_balance_sheet",
                    finance.balance_sheet,
                    f"Error fetching balance sheet for {symbol}",
                )
                inc_df = self._fetch_dataframe(
                    "calculate_finance_income_statement",
                    finance.income_statement,
                    f"Error fetching income statement for {symbol}",
                )
                cf_df = self._fetch_dataframe(
                    "calculate_finance_cash_flow",
                    finance.cash_flow,
                    f"Error fetching cash flow for {symbol}",
                )
                ratios_df = pd.DataFrame()
                try:
                    ratio_methods = [
                        "ratios",
                        "ratio",
                        "financial_ratios",
                        "financial_ratio",
                        "ratios_quarterly",
                        "ratios_ttm",
                    ]
                    for method_name in ratio_methods:
                        if not hasattr(finance, method_name):
                            continue
                        tmp = self._fetch_dataframe(
                            f"calculate_finance_{method_name}",
                            getattr(finance, method_name),
                            f"Error fetching finance.{method_name} for {symbol}",
                        )
                        if not tmp.empty:
                            ratios_df = tmp
                            break

                    if ratios_df.empty:
                        for src in ["VCI", "TCBS"]:
                            # Rate limit việc tạo Company vì constructor có thể call API
                            self.rate_limiter.wait_if_needed(f"calculate_company_init_{src}")
                            try:
                                comp = Company(symbol=symbol, source=src)
                            except SystemExit:
                                raise
                            except Exception as exc:
                                print(f"Error initialising Company({src}) for {symbol}: {exc}")
                                logger.warning(
                                    "Error initialising Company(%s) for %s: %s",
                                    src,
                                    symbol,
                                    exc,
                                    exc_info=True,
                                )
                                continue
                            ratio_companies.append(comp)
                            for method_name in ratio_methods:
                                if not hasattr(comp, method_name):
                                    continue
                                tmp = self._fetch_dataframe(
                                    f"calculate_company_{src}_{method_name}",
                                    getattr(comp, method_name),
                                    f"Error fetching Company({src}).{method_name} for {symbol}",
                                )
                                if not tmp.empty:
                                    ratios_df = tmp
                                    raise StopIteration
                except StopIteration:
                    pass
                except Exception:
                    ratios_df = pd.DataFrame()

                bundle = {
                    "balance_sheet_df": bs_df,
                    "income_statement_df": inc_df,
                    "cash_flow_df": cf_df,
                    "ratios_df": ratios_df,
                    "profile_df": pd.DataFrame(),
                }
                print(f"Successfully fetched data for {symbol}")
                logger.info("Fetched finance bundle for %s successfully", symbol)
                return bundle, True

            except SystemExit as exc:
                retries += 1
                if retries > self.max_retries:
                    logger.error(
                        "SystemExit for %s exceeded max retries (%d). Last message: %r",
                        symbol,
                        self.max_retries,
                        exc.code if isinstance(exc, SystemExit) else exc,
                    )
                    break

                wait_for = self._compute_wait_seconds(exc, retries)
                print(
                    f"SystemExit occurred for {symbol}, retrying after {wait_for:.0f}s "
                    f"({retries}/{self.max_retries})"
                )
                logger.warning(
                    "SystemExit encountered for %s (attempt %d/%d). Message=%r. Sleeping %.1fs before retry.",
                    symbol,
                    retries,
                    self.max_retries,
                    exc.code if isinstance(exc, SystemExit) else exc,
                    wait_for,
                )
                time.sleep(wait_for)

            except Exception as e:
                print(f"Exception occurred for {symbol}: {e}")
                logger.exception("Unhandled exception when fetching finance bundle for %s", symbol)
                return {}, False

            finally:
                close_db_connections(finance, *ratio_companies)

        print(f"Max retries exceeded for {symbol}")
        logger.error("Max retries exceeded for %s. Giving up.", symbol)
        return {}, False

    def get_full_financial_data(self, symbol: str) -> Tuple[bool, Dict]:
        """Alias for fetch_bundle to match service expectations."""
        bundle, success = self.fetch_bundle(symbol)
        return success, bundle
                
