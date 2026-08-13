import unittest
from ml.dataset_builder import MLDatasetBuilder
from ml.model_trainer import XGBoostTrendTrainer
from ml.predictor import TrendPredictor
from db.connection import set_mock_mode


class TestMLPipeline(unittest.TestCase):
    def setUp(self):
        set_mock_mode(True)

    def test_dataset_builder_structure(self):
        X, y_reg, y_clf = MLDatasetBuilder.build_training_sample()
        self.assertIsInstance(X, list)
        self.assertIsInstance(y_reg, list)
        self.assertIsInstance(y_clf, list)

    def test_xgboost_trainer(self):
        trainer = XGBoostTrendTrainer()
        metrics = trainer.train_models()
        self.assertEqual(metrics["status"], "SUCCESS")

    def test_trend_predictor(self):
        predictor = TrendPredictor()
        predictions = predictor.predict_trends(category_keyword="notebook")
        self.assertEqual(predictions["status"], "SUCCESS")
        self.assertIn("top_10_best_products", predictions)
        self.assertIn("trend_aumentar", predictions)
        self.assertIn("trend_diminuir", predictions)
        self.assertIn("trend_estagnar", predictions)


if __name__ == "__main__":
    unittest.main()
