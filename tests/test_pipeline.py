import os
import unittest
from datetime import date
from db.connection import set_mock_mode
from api_guardian.runtime_guard import set_network_executor
from pipeline.validators import PayloadValidator
from pipeline.schema_drift import SchemaDriftDetector
from pipeline.transformers import DataTransformer
from pipeline.repository import DataRepository
from pipeline.data_quality import DataQualityChecker
from pipeline.feature_engineering import FeatureEngineer
from pipeline.execution_tracker import PipelineTracker
from pipeline.collectors.mercadolivre_collector import MercadoLivreSearchCollector
from pipeline.collectors.amazon_collector import AmazonCatalogCollector


def mock_network_executor(method, url, headers=None, **kwargs):
    if "mercadolibre.com" in url:
        return {
            "results": [
                {
                    "id": "MLB1001",
                    "title": "Smartphone Test",
                    "price": 1500.0,
                    "original_price": 1800.0,
                    "currency_id": "BRL",
                    "available_quantity": 10,
                    "category_id": "MLB1051",
                    "seller": {"id": "SELLER01"}
                }
            ]
        }
    elif "sellingpartnerapi-na.amazon.com" in url:
        return {
            "items": [
                {
                    "asin": "B08N5WRWNW",
                    "summaries": [{"itemName": "Laptop Test", "brand": "TestBrand"}]
                }
            ]
        }
    return {}


class TestPipeline(unittest.TestCase):
    def setUp(self):
        set_mock_mode(True)
        set_network_executor(mock_network_executor)

    def test_payload_validator_valid_and_invalid(self):
        payload = {
            "results": [
                {"id": "MLB001", "title": "Valid Item", "price": 100.0},
                {"id": "MLB002", "title": "Invalid Price Item", "price": -50.0}
            ]
        }
        valid, quarantined = PayloadValidator.validate_ml_search(payload)
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(valid[0]["id"], "MLB001")

    def test_schema_drift_detector(self):
        payload_v1 = {"results": [{"id": "MLB001", "price": 100.0}]}
        payload_v2 = {"results": [{"id": "MLB001", "price": 100.0, "new_field": "test"}]}

        hash1 = SchemaDriftDetector.compute_schema_hash(payload_v1)
        hash2 = SchemaDriftDetector.compute_schema_hash(payload_v2)
        self.assertNotEqual(hash1, hash2)

    def test_data_transformer(self):
        raw_item = {
            "id": "MLB999",
            "title": "Notebook Gamer",
            "price": 4500.0,
            "category_id": "MLB1648",
            "available_quantity": 5
        }
        transformed = DataTransformer.transform_ml_item(raw_item)
        self.assertEqual(transformed["product"]["product_id"], "MLB999")
        self.assertEqual(transformed["price_history"]["price"], 4500.0)

    def test_repository_upsert_and_history(self):
        product_dim = {
            "product_id": "MLB999",
            "site_id": "MLB",
            "title": "Notebook Gamer",
            "category_id": "MLB1648",
            "currency_id": "BRL"
        }
        price_entry = {
            "product_id": "MLB999",
            "price": 4500.0,
            "currency_id": "BRL"
        }

        self.assertTrue(DataRepository.upsert_product(product_dim))
        self.assertTrue(DataRepository.insert_price_history(price_entry))

    def test_data_quality_checker(self):
        self.assertFalse(DataQualityChecker.check_volume_anomaly("exec-01", fetched_count=0, expected_min=1))
        self.assertTrue(DataQualityChecker.check_volume_anomaly("exec-01", fetched_count=10, expected_min=1))
        anomalies = DataQualityChecker.check_item_quality("exec-01", [{"price": -10.0}])
        self.assertEqual(anomalies, 1)

    def test_feature_engineer_calculation(self):
        feats = FeatureEngineer.calculate_daily_features("MLB999", date.today())
        self.assertEqual(feats["product_id"], "MLB999")
        self.assertIn("rolling_avg_price_7d", feats)

    def test_execution_tracker_context(self):
        with PipelineTracker("Test_Pipeline", "ML", "/test") as tracker:
            tracker.increment_fetched(5)
            tracker.increment_inserted(3)
        self.assertEqual(tracker.records_fetched, 5)

    def test_mercadolivre_collector_run(self):
        collector = MercadoLivreSearchCollector()
        result = collector.run(query="smartphone")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreater(result["fetched"], 0)

    def test_amazon_collector_run(self):
        os.environ["LWA_TOKEN"] = "mock_lwa_token_val"
        collector = AmazonCatalogCollector()
        result = collector.run(keywords="laptop")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreater(result["fetched"], 0)


if __name__ == "__main__":
    unittest.main()
