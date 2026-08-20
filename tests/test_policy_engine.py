import unittest
from api_guardian.policy_engine import PolicyEngine


class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PolicyEngine()

    def test_ml_search_allow(self):
        url = "https://api.mercadolivre.com/sites/MLB/search?q=notebook"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_ml_search_missing_param_block(self):
        url = "https://api.mercadolivre.com/sites/MLB/search"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "BLOCK")

    def test_ml_trends_allow(self):
        url = "https://api.mercadolivre.com/trends/MLB"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_ml_trends_missing_auth_block(self):
        url = "https://api.mercadolivre.com/trends/MLB"
        res = self.engine.evaluate("GET", url, headers={})
        self.assertEqual(res.status, "ALLOW")

    def test_ml_highlights_allow(self):
        url = "https://api.mercadolivre.com/highlights/MLB/category/MLB1648"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_ml_items_allow(self):
        url = "https://api.mercadolivre.com/items/MLB123456"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_ml_categories_allow(self):
        url = "https://api.mercadolivre.com/sites/MLB/categories"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    # Tests for 2 NEW Authorized APIs
    def test_ml_item_description_allow(self):
        url = "https://api.mercadolivre.com/items/MLB123456/description"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_ml_seller_reputation_allow(self):
        url = "https://api.mercadolivre.com/users/99887766"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "ALLOW")

    def test_amazon_catalog_allow(self):
        url = "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items?keywords=laptop"
        headers = {"x-amz-access-token": "valid_lwa_token"}
        res = self.engine.evaluate("GET", url, headers=headers)
        self.assertEqual(res.status, "ALLOW")

    def test_amazon_catalog_missing_auth_block(self):
        url = "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items?keywords=laptop"
        res = self.engine.evaluate("GET", url, headers={})
        self.assertEqual(res.status, "BLOCK")

    def test_amazon_product_types_allow(self):
        url = "https://sellingpartnerapi-na.amazon.com/definitions/2020-09-01/productTypes/LUGGAGE"
        headers = {"x-amz-access-token": "valid_lwa_token"}
        res = self.engine.evaluate("GET", url, headers=headers)
        self.assertEqual(res.status, "ALLOW")

    def test_unknown_api_block(self):
        url = "https://api.unknown-service.com/data"
        res = self.engine.evaluate("GET", url)
        self.assertEqual(res.status, "BLOCK")

    def test_wrong_method_block(self):
        url = "https://api.mercadolivre.com/sites/MLB/search?q=notebook"
        res = self.engine.evaluate("POST", url)
        self.assertEqual(res.status, "BLOCK")


if __name__ == "__main__":
    unittest.main()
