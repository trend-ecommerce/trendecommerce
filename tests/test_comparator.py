import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.ml.comparator import DemandComparator, ValidationReport, ValidationRow
from src.database.connection import DatabaseManager
from src.database.models import Base, Product, SalesHistory, PredictionLog


@pytest.fixture
def mock_db_manager(tmp_path):
    """DatabaseManager temporário em memória para testes."""
    db_file = tmp_path / "test_comparator.db"
    manager = DatabaseManager(database_url=f"sqlite:///{db_file}")
    Base.metadata.create_all(manager.engine)
    return manager


@pytest.fixture
def sample_dataset():
    """Gera dataset de produtos e vendas para validação."""
    products_df = pd.DataFrame([
        {"product_id": 1, "title": "Produto Teste A", "category": "Eletrônicos", "price": 100.0, "platform": "mercadolivre"},
        {"product_id": 2, "title": "Produto Teste B", "category": "Celulares", "price": 500.0, "platform": "mercadolivre"},
    ])
    
    dates = pd.date_range(start="2026-01-01", periods=45, freq="D")
    sales_rows = []
    
    np.random.seed(42)
    for p_id in [1, 2]:
        base = 20 if p_id == 1 else 40
        for dt in dates:
            sales_rows.append({
                "product_id": p_id,
                "date": dt,
                "quantity_sold": int(max(0, base + np.random.randint(-5, 6))),
                "price_at_date": 100.0 if p_id == 1 else 500.0,
                "available_quantity": 100,
                "platform": "mercadolivre"
            })
            
    sales_df = pd.DataFrame(sales_rows)
    return products_df, sales_df


class TestDemandComparator:
    """Testes do comparador Real vs Previsto."""

    def test_run_backtest_validation(self, sample_dataset, mock_db_manager):
        """Verifica se o comparador calcula os erros e percentuais corretamente."""
        products_df, sales_df = sample_dataset
        comparator = DemandComparator(db_manager=mock_db_manager)
        
        report = comparator.run_backtest_validation(
            products_df=products_df,
            sales_df=sales_df,
            test_days=5
        )
        
        assert isinstance(report, ValidationReport)
        assert report.total_predictions > 0
        assert report.hit_rate_pct >= 0.0
        assert report.mean_accuracy_pct >= 0.0
        assert report.rmse >= 0.0
        assert report.mae >= 0.0
        assert len(report.rows) == report.total_predictions
        
        # Verificar estrutura de cada linha
        first_row = report.rows[0]
        assert isinstance(first_row, ValidationRow)
        assert hasattr(first_row, "actual_demand")
        assert hasattr(first_row, "predicted_demand")
        assert hasattr(first_row, "error")
        assert hasattr(first_row, "hit_interval")

    def test_format_terminal_table(self, sample_dataset, mock_db_manager):
        """Verifica formatação em texto da tabela de auditoria."""
        products_df, sales_df = sample_dataset
        comparator = DemandComparator(db_manager=mock_db_manager)
        
        report = comparator.run_backtest_validation(
            products_df=products_df,
            sales_df=sales_df,
            test_days=3
        )
        
        table_str = comparator.format_terminal_table(report)
        assert "RELATÓRIO DE AUDITORIA" in table_str
        assert "Taxa de Acerto na Faixa" in table_str
        assert "Produto Teste A" in table_str