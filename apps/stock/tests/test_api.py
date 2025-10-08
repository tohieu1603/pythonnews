from django.test import TestCase
from django.urls import reverse
from django.test import Client

from .factories import create_company_bundle


class TestStockAPI(TestCase):
    def setUp(self):
        self.client = Client()

    def test_get_symbol_success(self):
        company, symbol = create_company_bundle("AAA")

        resp = self.client.get(f"/api/stocks/symbols/{symbol.name}")
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(data["name"], symbol.name)
        self.assertEqual(data["exchange"], symbol.exchange)
        # company nested object is present with id
        self.assertIn("company", data)
        self.assertEqual(data["company"]["id"], company.id)

    def test_get_symbol_not_found(self):
        resp = self.client.get("/api/stocks/symbols/ZZZZ")
        self.assertEqual(resp.status_code, 404)
