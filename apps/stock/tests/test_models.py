from django.test import TestCase

from apps.stock.models import Industry, Company, Symbol, ShareHolder, News, Events, Officers
from .factories import create_company_bundle, create_industry, create_company, create_symbol


class TestStockModels(TestCase):
    def test_str_methods(self):
        industry = create_industry("Finance")
        company = create_company(full_name="Fin Corp", industry=industry)
        symbol = create_symbol(name="FIN", company=company, exchange="HNX")
        shareholder = ShareHolder.objects.create(share_holder="Owner", share_own_percent=10.0, company=company)
        news = News.objects.create(title="Headline", public_date=1704067200, company=company)
        event = Events.objects.create(event_title="Earnings", company=company)
        officer = Officers.objects.create(
            officer_name="John Smith",
            officer_position="CFO",
            position_short_name="CFO",
            officer_owner_percent=2.5,
            company=company,
        )

        self.assertEqual(str(industry), "Finance")
        self.assertEqual(str(company), "Fin Corp")
        self.assertEqual(str(symbol), "FIN (HNX)")
        self.assertEqual(str(shareholder), "Owner - 10.0%")
        self.assertEqual(str(news), "Headline")
        self.assertEqual(str(event), "Earnings")
        self.assertEqual(str(officer), "John Smith - CFO")

    def test_relationships(self):
        company, symbol = create_company_bundle("ACM")

        self.assertEqual(symbol.company, company)
        self.assertEqual(company.symbols.count(), 1)
        self.assertEqual(company.shareholders.count(), 1)
        self.assertEqual(company.news.count(), 1)
        self.assertEqual(company.events.count(), 1)
        self.assertEqual(company.officers.count(), 1)
