# apps/stock/services/mappers.py
from typing import Any, Dict, List
import pandas as pd

from apps.stock.utils.safe import (
    safe_date_passthrough,
    safe_decimal,
    safe_int,
    safe_str,
    to_epoch_seconds,
    to_datetime,
)


class DataMappers:
    """Class chứa các method mapping data từ vnstock DataFrames sang dict format"""
    
    @staticmethod
    def map_shareholders(df: pd.DataFrame) -> List[Dict]:
        """Map shareholders DataFrame to list of dicts"""
        if df is None or df.empty:
            return []
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "share_holder": safe_str(r.get("share_holder")),
                    "quantity": safe_int(r.get("quantity")),
                    "share_own_percent": safe_decimal(r.get("share_own_percent")),
                    "update_date": safe_date_passthrough(r.get("update_date")),
                }
            )
        return rows

    @staticmethod
    def map_news(df: pd.DataFrame) -> List[Dict]:
        """Map news DataFrame to list of dicts"""
        if df is None or df.empty:
            return []

        # DataFrame.applymap is deprecated in pandas 3.x; DataFrame.map is the
        # new element-wise helper. We normalise NaN/NaT values here before
        # iterating to avoid passing them to Django model fields.
        clean_df = df.map(lambda value: None if pd.isna(value) else value)

        rows: List[Dict] = []
        for _, r in clean_df.iterrows():
            raw_public_date = r.get("public_date")

            if isinstance(raw_public_date, pd.Timestamp):
                public_date = safe_int(raw_public_date.timestamp(), None)
            else:
                # Values coming from vnstock are epoch milliseconds. Convert to
                # seconds when the magnitude suggests milliseconds.
                if isinstance(raw_public_date, (int, float)):
                    public_date_candidate = raw_public_date / 1000 if raw_public_date and raw_public_date > 1e12 else raw_public_date
                    public_date = safe_int(public_date_candidate, None)
                else:
                    public_date = safe_int(to_epoch_seconds(raw_public_date), None)

            rows.append(
                {
                    "title": safe_str(r.get("news_title", "No Title")),
                    "news_image_url": safe_str(r.get("news_image_url"), None),
                    "news_source_link": safe_str(r.get("news_source_link"), None),
                    "price_change_pct": safe_decimal(r.get("price_change_pct"), None),
                    "public_date": public_date,
                }
            )
        return rows

    @staticmethod
    def map_events(df: pd.DataFrame) -> List[Dict]:
        """Map events DataFrame to list of dicts"""
        if df is None or df.empty:
            return []
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "event_title": safe_str(r.get("event_title", "No Title")),
                    "source_url": safe_str(r.get("source_url")),
                    "issue_date": to_datetime(r.get("issue_date")),
                    "public_date": to_datetime(r.get("public_date")),
                }
            )
        return rows

    @staticmethod
    def map_sub_company(df: pd.DataFrame) -> List[Dict]:
        """Map subsidiaries DataFrame to list of dicts"""
        if df is None or df.empty:
            return []
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "company_name": safe_str(r.get("sub_company_name", "No Name")),
                    "sub_own_percent": safe_decimal(r.get("sub_own_percent"), None),
                }
            )
        return rows

    @staticmethod
    def map_officers(df: pd.DataFrame) -> List[Dict]:
        """Map officers DataFrame to list of dicts"""
        if df is None or df.empty:
            return []
        rows = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "officer_name": safe_str(r.get("officer_name", "No Name")),
                    "officer_position": safe_str(r.get("officer_position")),
                    "position_short_name": safe_str(r.get("position_short_name")),
                    "officer_owner_percent": safe_decimal(r.get("officer_own_percent")),
                }
            )
        return rows

    @staticmethod
    def build_shareholder_rows(company_obj, df: pd.DataFrame) -> List[Dict]:
        """Build shareholder rows with company object for database insert"""
        if df is None or df.empty:
            return []
        rows: List[Dict] = []
        for _, r in df.iterrows():
            rows.append(
                {
                    "share_holder": safe_str(r.get("share_holder") or "").strip(),
                    "quantity": safe_int(r.get("quantity")),
                    "share_own_percent": safe_decimal(r.get("share_own_percent") or 0),
                    "update_date": safe_date_passthrough(r.get("update_date")),
                    "company": company_obj,
                }
            )
        return rows
