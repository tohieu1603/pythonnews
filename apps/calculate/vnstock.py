
from typing import Optional, Generator, Tuple, Dict
from vnstock import Listing, Finance, Company
import pandas as pd
from core.db_utils import close_db_connections


class VNStock:
    
    def __init__(self, max_retries = 5, wait_seconds: int = 60):
        self.max_retries = max_retries
        self.wait_seconds = wait_seconds
    
    def _df_or_empty(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()
        return df
    def inter_all_symbols(self, exchange: Optional[str] = "HSX") -> Generator[Tuple[str, str], None, None]:
        listing = None
        try:
            listing = Listing()
            df = listing.symbols_by_exchange()
            exch = (exchange or "HSX").upper()
            df = df[df["exchange"] == exch]

            for _, row in df.iterrows():
                yield str(row.get("symbol")), str(row.get("exchange"))
        finally:
            close_db_connections(listing)
    
    def fetch_bundle(
        self, symbol: str
    ) -> Tuple[Dict[str, pd.DataFrame], bool]:
        retries = 0
        while retries <= self.max_retries:
            try:
                print(f"Trying to fetch data for {symbol}, attempt {retries + 1}")
                finance = Finance(symbol=symbol, source="VCI")
                
                bs_df = self._df_or_empty(finance.balance_sheet())
                inc_df = self._df_or_empty(finance.income_statement())
                cf_df = self._df_or_empty(finance.cash_flow())
                ratios_df = pd.DataFrame()
                try:
                    ratio_methods = [
                        'ratios',
                        'ratio',
                        'financial_ratios',
                        'financial_ratio',
                        'ratios_quarterly',
                        'ratios_ttm',
                    ]
                    for m in ratio_methods:
                        if hasattr(finance, m):
                            fn = getattr(finance, m)
                            try:
                                tmp = fn()
                                tmp = self._df_or_empty(tmp)
                                if not tmp.empty:
                                    ratios_df = tmp
                                    break
                            except Exception:
                                continue
                    if ratios_df.empty:
                        for src in ["VCI", "TCBS"]:
                            try:
                                comp = Company(symbol=symbol, source=src)
                            except Exception:
                                continue
                            for m in ratio_methods:
                                if hasattr(comp, m):
                                    try:
                                        tmp = getattr(comp, m)()
                                        tmp = self._df_or_empty(tmp)
                                        if not tmp.empty:
                                            ratios_df = tmp
                                            raise StopIteration
                                    except Exception:
                                        continue
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
                return bundle, True
                
            except SystemExit:
                print(f"SystemExit occurred for {symbol}, retrying...")
                retries += 1
                
            except Exception as e:
                print(f"Exception occurred for {symbol}: {e}")
                return {}, False
                
        print(f"Max retries exceeded for {symbol}")
        return {}, False

    def get_full_financial_data(self, symbol: str) -> Tuple[bool, Dict]:
        """Alias for fetch_bundle to match service expectations."""
        bundle, success = self.fetch_bundle(symbol)
        return success, bundle
                
