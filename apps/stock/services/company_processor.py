# apps/stock/services/company_processor.py
from typing import Any, Dict
import pandas as pd

from apps.stock.repositories import repositories as repo
from apps.stock.services.mappers import DataMappers
from apps.stock.utils.safe import safe_decimal, safe_int, safe_str


class CompanyProcessor:
    """Class chuyên xử lý company data và related data"""
    
    @staticmethod
    def process_company_data(bundle: Dict, overview_data: pd.Series) -> Any:
        """Extract and process company data from bundle."""
        profile_df = bundle.get("profile_df")
        company_name = (
            safe_str(profile_df.iloc[0].get("company_name"))
            if profile_df is not None and not profile_df.empty
            else "Unknown Company"
        )

        overview_df_vci = bundle.get("overview_df_VCI")
        if overview_df_vci is not None and not overview_df_vci.empty:
            vci_data = overview_df_vci.iloc[0]
            company_profile = safe_str(vci_data.get("company_profile"))
            history = safe_str(vci_data.get("history"))
            fin_ratio_share = safe_int(vci_data.get("financial_ratio_issue_share"))
            charter_cap = safe_int(vci_data.get("charter_capital"))
        else:
            company_profile = ""
            history = ""
            fin_ratio_share = None
            charter_cap = None

        return repo.upsert_company(
            company_name,
            defaults={
                "company_profile": company_profile,
                "history": history,
                "issue_share": safe_int(overview_data.get("issue_share")),
                "stock_rating": safe_decimal(overview_data.get("stock_rating"), None),
                "website": safe_str(overview_data.get("website", "")),
                "financial_ratio_issue_share": fin_ratio_share,
                "charter_capital": charter_cap,
                "outstanding_share": safe_int(overview_data.get("outstanding_shares", 0)),
                "foreign_percent": safe_decimal(overview_data.get("foreign_percent", 0)),
                "established_year": safe_int(overview_data.get("established_year", 0)),
                "delta_in_week": safe_decimal(overview_data.get("delta_in_week", 0)),
                "delta_in_month": safe_decimal(overview_data.get("delta_in_month", 0)),
                "delta_in_year": safe_decimal(overview_data.get("delta_in_year", 0)),
                "no_employees": safe_int(overview_data.get("no_employees", 0)),
            },
        )

    @staticmethod
    def process_related_data(company: Any, bundle: Dict) -> None:
        """Process shareholders, events, officers, and subsidiaries."""
        try:
            # Process shareholders
            shareholders_df = bundle.get("shareholders_df")
            if shareholders_df is not None and not shareholders_df.empty:
                repo.upsert_shareholders(
                    company, DataMappers.map_shareholders(shareholders_df)
                )
            news_df = bundle.get("news_df")

            if news_df is not None and not news_df.empty:
                repo.upsert_news(
                    company, DataMappers.map_news(news_df)
                )
            events_df = bundle.get("events_df")
            if events_df is not None and not events_df.empty:
                repo.upsert_events(
                    company, DataMappers.map_events(events_df)
                )

            # Process officers
            officers_df = bundle.get("officers_df")
            if officers_df is not None and not officers_df.empty:
                repo.upsert_officers(
                    company, DataMappers.map_officers(officers_df)
                )

            # Process subsidiaries
            subsidiaries_df = bundle.get("subsidiaries")
            if subsidiaries_df is not None and not subsidiaries_df.empty:
                repo.upsert_sub_company(
                    DataMappers.map_sub_company(subsidiaries_df), company
                )
        except Exception as e:
            print(f"Error processing related data for company {company.id}: {e}")