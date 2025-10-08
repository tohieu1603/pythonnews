# apps/stock/services/payload_builder.py
from typing import Any, Dict
from apps.stock.utils.safe import to_datetime


class PayloadBuilder:
    """Class chuyên xây dựng response payload"""
    
    @staticmethod
    def build_symbol_payload(symbol: Any, company: Any) -> Dict[str, Any]:
        """Build the response payload for a symbol."""
        company_payload = {
            "id": company.id,
            "company_name": company.company_name,
            "company_profile": company.company_profile,
            "history": company.history,
            "issue_share": company.issue_share,
            "financial_ratio_issue_share": company.financial_ratio_issue_share,
            "charter_capital": company.charter_capital,
            "outstanding_share": company.outstanding_share,
            "foreign_percent": company.foreign_percent,
            "established_year": company.established_year,
            "no_employees": company.no_employees,
            "stock_rating": company.stock_rating,
            "website": company.website,
            "updated_at": to_datetime(company.updated_at),
        }

        return {
            "id": symbol.id,
            "name": symbol.name,
            "exchange": symbol.exchange,
            "company": company_payload,
        }