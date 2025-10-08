from typing import List, Dict, Any
from apps.stock.repositories import repositories as repo
from apps.stock.utils.safe import to_datetime, iso_str_or_none

class IndustryService:
    def list_industries_payload(self) -> List[Dict[str, Any]]:
        """
        Trả về list[IndustryOut] (có mảng symbols).
        Các field không có trong model (description, created_at) -> None.
        """
        industries = repo.qs_industries_with_symbols()
        payload: List[Dict[str, Any]] = []

        for ind in industries:
            syms = []
            for s in ind.symbols.all():
                comp = s.company
                company_payload = None
                if comp:
                    company_payload = {
                        "id": comp.id,
                        "company_profile": comp.company_profile,
                        "history": comp.history,
                        "issue_share": comp.issue_share,
                        "financial_ratio_issue_share": comp.financial_ratio_issue_share,
                        "charter_capital": comp.charter_capital,
                        "updated_at": to_datetime(comp.updated_at),
                        "company_name": comp.company_name,
                        "established_year": comp.established_year,
                        "foreign_percent": comp.foreign_percent,
                        "outstanding_share": comp.outstanding_share,
                        "no_employees": comp.no_employees,
                        "stock_rating": float(comp.stock_rating) if comp.stock_rating is not None else None,
                        "website": comp.website,
                        "shareholders": [],
                        "news": [],
                        "events": [],
                        "officers": [],
                    }
                syms.append({
                    "id": s.id,
                    "name": s.name,
                    "exchange": s.exchange,
                    "updated_at": to_datetime(s.updated_at),
                    "company": company_payload,
                })

            payload.append({
                "id": ind.id,
                "name": ind.name,
                "description": None,
                "created_at": None,
                "updated_at": to_datetime(ind.updated_at),
                "symbols": syms,
            })

        return payload
