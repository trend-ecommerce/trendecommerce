import pytest
import numpy as np
import pandas as pd

from src.features.feature_engineering import FeatureEngineer


class TestFeatureEngineer:
    """Testes de criação de features."""

    def setup_method(self):
        self.engineer = FeatureEngineer()

    def test_sales_features_created(self, sample_sales_data):
        """Verifica criação de features de vendas."""
        result = self.engineer.create_sales_features(sample_sales_data)
        assert "vendas_7_dias" in result.columns
        assert "vendas_30_dias" in result.columns
        assert "media_vendas_7_dias" in result.columns
        assert "crescimento_vendas" in result.columns
        assert "preco_medio_7_dias" in result.columns
        assert "variacao_preco" in result.columns

    def test_temporal_features_created(self, sample_sales_data):
        """Verifica criação de features temporais."""
        result = self.engineer.create_temporal_features(sample_sales_data)
        assert "dia_semana" in result.columns
        assert "mes" in result.columns
        assert "eh_fim_semana" in result.columns
        assert "dia_semana_sin" in result.columns

    def test_prepare_for_model(self, sample_sales_data):
        """Verifica preparação dos dados para o modelo."""
        features_df = self.engineer.create_sales_features(sample_sales_data)
        X, y = self.engineer.prepare_for_model(features_df, target_col="quantity_sold")
        assert len(X) == len(y)
        assert "quantity_sold" not in X.columns
        assert "product_id" not in X.columns
        assert not X.isnull().any().any()

    def test_empty_dataframe(self):
        """Verifica tratamento de DataFrame vazio."""
        empty_df = pd.DataFrame()
        result = self.engineer.create_sales_features(empty_df)
        assert result.empty
