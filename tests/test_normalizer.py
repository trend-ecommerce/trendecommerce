import pytest
import pandas as pd

from src.normalization.normalizer import DataNormalizer


class TestDataNormalizer:
    """Testes de normalização de dados."""

    def setup_method(self):
        self.normalizer = DataNormalizer()

    def test_normalize_products(self, sample_product_data):
        """Verifica normalização de produtos."""
        result = self.normalizer.normalize_products(
            sample_product_data, platform="mercadolivre"
        )
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "external_id" in result.columns
        assert "platform" in result.columns
        assert "title" in result.columns

    def test_normalize_trends(self, sample_trends_data):
        """Verifica normalização de tendências."""
        raw = sample_trends_data.to_dict("records")
        result = self.normalizer.normalize_trends(raw)
        assert isinstance(result, pd.DataFrame)
        assert "keyword" in result.columns
        assert "interest_score" in result.columns

    def test_normalize_empty_data(self):
        """Verifica tratamento de dados vazios."""
        result = self.normalizer.normalize_products([], "test")
        assert result.empty

    def test_price_normalization(self):
        """Verifica normalização de preço."""
        assert DataNormalizer._normalize_price(100) == 100.0
        assert DataNormalizer._normalize_price("99.99") == 99.99
        assert DataNormalizer._normalize_price(None) is None
        assert DataNormalizer._normalize_price("invalid") is None