import pytest
import numpy as np
import pandas as pd

from src.ml.trainer import DemandTrainer
from src.ml.predictor import DemandPredictor
from src.ml.evaluation import ModelEvaluator
from src.features.feature_engineering import FeatureEngineer


class TestDemandTrainer:
    """Testes do treinador do modelo."""

    def test_train_model(self, sample_sales_data):
        """Verifica treinamento do modelo."""
        engineer = FeatureEngineer()
        features_df = engineer.create_sales_features(sample_sales_data)
        X, y = engineer.prepare_for_model(features_df, target_col="quantity_sold")
        
        trainer = DemandTrainer()
        metrics = trainer.train(X, y)
        
        assert "train_rmse" in metrics
        assert "test_rmse" in metrics
        assert "test_r2" in metrics
        assert trainer.model is not None

    def test_feature_importance(self, sample_sales_data):
        """Verifica importância das features."""
        engineer = FeatureEngineer()
        features_df = engineer.create_sales_features(sample_sales_data)
        X, y = engineer.prepare_for_model(features_df, target_col="quantity_sold")
        
        trainer = DemandTrainer()
        trainer.train(X, y)
        importance = trainer.get_feature_importance()
        
        assert len(importance) > 0
        assert all(isinstance(v, float) for v in importance.values())

    def test_save_and_load_model(self, sample_sales_data, tmp_path):
        """Verifica salvar e carregar modelo."""
        engineer = FeatureEngineer()
        features_df = engineer.create_sales_features(sample_sales_data)
        X, y = engineer.prepare_for_model(features_df, target_col="quantity_sold")
        
        trainer = DemandTrainer()
        trainer.train(X, y)
        
        model_path = str(tmp_path / "model.json")
        trainer.save_model(model_path)
        
        # Carregar modelo
        new_trainer = DemandTrainer()
        new_trainer.load_model(model_path)
        assert new_trainer.model is not None


class TestDemandPredictor:
    """Testes do preditor de demanda."""

    def test_predict(self, sample_sales_data):
        """Verifica previsão de demanda."""
        engineer = FeatureEngineer()
        features_df = engineer.create_sales_features(sample_sales_data)
        X, y = engineer.prepare_for_model(features_df, target_col="quantity_sold")
        
        trainer = DemandTrainer()
        trainer.train(X, y)
        
        predictor = DemandPredictor(trainer)
        predictions = predictor.predict(X.head(10))
        
        assert len(predictions) == 10
        assert all(p >= 0 for p in predictions)

    def test_analyze_prediction(self):
        """Verifica análise de previsões."""
        predictor = DemandPredictor()
        predictions = np.array([10, 20, 30, 40, 50])
        analysis = predictor.analyze_prediction(predictions)
        
        assert analysis["mean_demand"] == 30.0
        assert analysis["min_demand"] == 10.0
        assert analysis["max_demand"] == 50.0
        assert analysis["n_predictions"] == 5


class TestModelEvaluator:
    """Testes do avaliador de modelos."""

    def test_evaluate(self):
        """Verifica métricas de avaliação."""
        y_true = np.array([10, 20, 30, 40, 50])
        y_pred = np.array([12, 18, 33, 38, 52])
        
        metrics = ModelEvaluator.evaluate(y_true, y_pred)
        
        assert "rmse" in metrics
        assert "mae" in metrics
        assert "r2" in metrics
        assert metrics["r2"] > 0.9  # Should be high for close predictions

    def test_generate_report(self):
        """Verifica geração de relatório."""
        y_true = np.array([10, 20, 30])
        y_pred = np.array([12, 18, 33])
        
        report = ModelEvaluator.generate_report(y_true, y_pred)
        assert "RELATÓRIO" in report
        assert "RMSE" in report
        assert "R²" in report