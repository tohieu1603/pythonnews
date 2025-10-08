
from typing import List, Dict, Any
from apps.stock.repositories import repositories as repo
from apps.stock.utils.safe import to_datetime

class CompanyService:
    def list_companies_payload(self) -> List[Dict[str, Any]]:
        """
        Trả về list[CompanyOut] – gồm nested shareholders, news, events, officers.
        """
        companies = repo.qs_companies_with_related()
        data: List[Dict[str, Any]] = []

        for c in companies:
            shareholders = [{
                "id": sh.id,
                "share_holder": sh.share_holder,
                "quantity": sh.quantity,
                "share_own_percent": float(sh.share_own_percent) if sh.share_own_percent is not None else None,
                "update_date": to_datetime(sh.update_date),
            } for sh in c.shareholders.all()[:10]]  # Giới hạn 10 shareholder đầu

            news_list = [{
                "id": n.id,
                "title": n.title,
                "image_url": n.news_image_url,
                "source_link": n.news_source_link,
                "price_change_pct": float(n.price_change_pct) if n.price_change_pct is not None else None,
                "public_date": to_datetime(n.public_date), 
            } for n in c.news.all()[:5]]  # Giới hạn 5 news đầu

            events_list = [{
                "id": e.id,
                "event_title": e.event_title,
                "public_date": to_datetime(e.public_date),
                "issue_date": to_datetime(e.issue_date),
                "source_url": e.source_url,
            } for e in c.events.all()[:5]]

            officers_list = [{
                "id": o.id,
                "officer_name": o.officer_name,
                "officer_position": o.officer_position,
                "position_short_name": o.position_short_name,
                "officer_owner_percent": float(o.officer_owner_percent) if o.officer_owner_percent is not None else None,
                "updated_at": to_datetime(o.updated_at),
            } for o in c.officers.all()[:5]]

            company_data = {
                "id": c.id,
                "company_profile": c.company_profile,
                "history": c.history,
                "issue_share": c.issue_share,
                "financial_ratio_issue_share": c.financial_ratio_issue_share,
                "charter_capital": c.charter_capital,
                "updated_at": to_datetime(c.updated_at),
                "shareholders": shareholders,
                "news": news_list,
                "events": events_list,
                "officers": officers_list,
            }
            data.append(company_data)

        return data
