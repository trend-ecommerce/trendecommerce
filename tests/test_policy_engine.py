import unittest
import os
from api_guardian.policy_engine import PolicyEngine
from api_guardian.config import GuardianConfig


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.config = GuardianConfig()
        self.engine = PolicyEngine(self.config)

    # --- 1. AMAZON CATALOG ITEMS ---
    def test_amazon_catalog_allow(self):
        res = self.engine.evaluate({
            'url': 'https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items',
            'method': 'GET',
            'headers': {'x-amz-access-token': 'valid_lwa_token'}
        })
        self.assertEqual(res['decision'], 'ALLOW')

    def test_amazon_catalog_missing_auth_block(self):
        res = self.engine.evaluate({
            'url': 'https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items',
            'method': 'GET',
            'headers': {}
        })
        # If os.getenv LWA_TOKEN is missing, should BLOCK
        if not os.getenv("LWA_TOKEN"):
            self.assertEqual(res['decision'], 'BLOCK')
            self.assertIn("Autenticação", res['reason'])

    # --- 2. AMAZON PRODUCT TYPE DEFINITIONS ---
    def test_amazon_product_types_allow(self):
        res = self.engine.evaluate({
            'url': 'https://sellingpartnerapi-na.amazon.com/definitions/2020-09-01/productTypes/LUGGAGE',
            'method': 'GET',
            'headers': {'x-amz-access-token': 'valid_token'}
        })
        self.assertEqual(res['decision'], 'ALLOW')

    # --- 3. MERCADO LIVRE SEARCH ---
    def test_ml_search_allow(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/sites/MLB/search',
            'method': 'GET',
            'params': {'q': 'notebook'}
        })
        self.assertEqual(res['decision'], 'ALLOW')

    def test_ml_search_missing_param_block(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/sites/MLB/search',
            'method': 'GET',
            'params': {}
        })
        self.assertEqual(res['decision'], 'BLOCK')
        self.assertIn("q", res['reason'])

    # --- 4. MERCADO LIVRE ITEMS ---
    def test_ml_items_allow(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/items/MLB12345678',
            'method': 'GET'
        })
        self.assertEqual(res['decision'], 'ALLOW')

    # --- 5. MERCADO LIVRE CATEGORIES ---
    def test_ml_categories_allow(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/sites/MLB/categories',
            'method': 'GET'
        })
        self.assertEqual(res['decision'], 'ALLOW')

    # --- 6. MERCADO LIVRE TRENDS ---
    def test_ml_trends_allow(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/trends/MLB',
            'method': 'GET',
            'headers': {'Authorization': 'Bearer test_token'}
        })
        self.assertEqual(res['decision'], 'ALLOW')

    def test_ml_trends_missing_auth_block(self):
        if not os.getenv("ACCESS_TOKEN"):
            res = self.engine.evaluate({
                'url': 'https://api.mercadolibre.com/trends/MLB',
                'method': 'GET',
                'headers': {}
            })
            self.assertEqual(res['decision'], 'BLOCK')

    # --- 7. MERCADO LIVRE HIGHLIGHTS ---
    def test_ml_highlights_allow(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/highlights/MLB/category/MLB1430',
            'method': 'GET',
            'headers': {'Authorization': 'Bearer test_token'}
        })
        self.assertEqual(res['decision'], 'ALLOW')

    # --- BLOCK CASES: UNKNOWN API, WRONG METHOD ---
    def test_unknown_api_block(self):
        res = self.engine.evaluate({
            'url': 'https://example.com/api',
            'method': 'GET'
        })
        self.assertEqual(res['decision'], 'BLOCK')
        self.assertIn("não autorizada", res['reason'])

    def test_wrong_method_block(self):
        res = self.engine.evaluate({
            'url': 'https://api.mercadolibre.com/sites/MLB/search',
            'method': 'POST',
            'params': {'q': 'notebook'}
        })
        self.assertEqual(res['decision'], 'BLOCK')
        self.assertIn("Método HTTP 'POST' não permitido", res['reason'])


if __name__ == '__main__':
    unittest.main()
