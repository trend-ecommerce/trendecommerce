import unittest
import os
from ml.dataset_builder import MLDatasetBuilder
from ml.model_trainer import XGBoostTrendTrainer
from ml.predictor import TrendPredictor
from db.connection import set_mock_mode


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        set_mock_mode(True)

    def test_dataset_builder_structure(self):
        X, y_30d, y_60d = MLDatasetBuilder.build_training_sample()
        self.assertIsInstance(X, list)
        self.assertIsInstance(y_30d, list)
        self.assertIsInstance(y_60d, list)

    def test_xgboost_trainer(self):
        trainer = XGBoostTrendTrainer()
        metrics = trainer.train_models()
        self.assertEqual(metrics["status"], "SUCCESS")

    def test_trend_predictor(self):
        predictor = TrendPredictor()
        predictions = predictor.predict_trends(category_keyword="notebook")
        self.assertEqual(predictions["status"], "SUCCESS")
        self.assertIn("current_trends_now", predictions)
        self.assertIn("forecast_1_month_30d", predictions)
        self.assertIn("forecast_2_months_60d", predictions)


if __name__ == "__main__":
    unittest.main()
