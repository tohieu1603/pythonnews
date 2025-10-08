# apps/stock/services/fetch_service.py
import time
from typing import Dict, List, Optional
import pandas as pd
from vnstock import Company as VNCompany
from apps.stock.clients.vnstock_client import VNStockClient


class FetchService:
    """Class chuyên fetch data từ external APIs"""
    
    def __init__(self, max_retries: int = 5, wait_seconds: int = 60, vn_client: Optional[VNStockClient] = None):
        self.max_retries = max_retries
        self.wait_seconds = wait_seconds
        self.vn_client = vn_client or VNStockClient(max_retries=max_retries, wait_seconds=wait_seconds)
    
    def fetch_shareholders_df(self, symbol_name: str) -> pd.DataFrame:
        """Fetch shareholders DataFrame with retry/backoff."""
        retries = 0
        while retries <= self.max_retries:
            try:
                df = self.vn_client.get_shareholders_df(symbol_name)
                if df is not None and not df.empty:
                    return df
                return pd.DataFrame()
            except SystemExit:
                retries += 1
                print(
                    f"Rate limit when fetching shareholders for {symbol_name}. "
                    f"Retry {retries}/{self.max_retries} after {self.wait_seconds}s"
                )
                time.sleep(self.wait_seconds)
            except Exception as e:
                print(f"Error fetching shareholders for {symbol_name}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def fetch_events_df(self, symbol_name: str) -> pd.DataFrame:
        """Fetch events DataFrame with retry/backoff."""
        retries = 0
        while retries <= self.max_retries:
            try:
                vn_company = VNCompany(symbol=symbol_name, source="VCI")
                df: Optional[pd.DataFrame] = vn_company.events()
                return df if df is not None else pd.DataFrame()
            except SystemExit:
                retries += 1
                print(
                    f"Rate limit when fetching events for {symbol_name}. "
                    f"Retry {retries}/{self.max_retries} after {self.wait_seconds}s"
                )
                time.sleep(self.wait_seconds)
            except Exception as e:
                print(f"Error fetching events for {symbol_name}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def fetch_officers_df(self, symbol_name: str) -> pd.DataFrame:
        """Fetch officers DataFrame with retry/backoff."""
        retries = 0
        while retries <= self.max_retries:
            try:
                vn_company = VNCompany(symbol=symbol_name, source="VCI")
                df: Optional[pd.DataFrame] = vn_company.officers()
                return df if df is not None else pd.DataFrame()
            except SystemExit:
                retries += 1
                print(
                    f"Rate limit when fetching officers for {symbol_name}. "
                    f"Retry {retries}/{self.max_retries} after {self.wait_seconds}s"
                )
                time.sleep(self.wait_seconds)
            except Exception as e:
                print(f"Error fetching officers for {symbol_name}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()
