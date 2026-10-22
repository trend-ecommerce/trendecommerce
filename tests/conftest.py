import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_sales_data():
    """Dados de vendas simulados para testes."""
    dates = pd.date_range(start="2026-01-01", periods=90, freq="D")
    np.random.seed(42)
    
    data = []
    for product_id in [1, 2, 3]:
        base_sales = np.random.randint(5, 50)
        base_price = np.random.uniform(50, 500)
        
        for date in dates:
            sales = max(0, base_sales + np.random.randint(-10, 15))
            price = round(base_price * np.random.uniform(0.9, 1.1), 2)
            data.append({
                "product_id": product_id,
                "date": date,
                "quantity_sold": sales,
                "price": price,
            })
    
    return pd.DataFrame(data)


@pytest.fixture
def sample_trends_data():
    """Dados de tendências simulados para testes."""
    dates = pd.date_range(start="2026-01-01", periods=30, freq="D")
    np.random.seed(42)
    
    data = []
    for keyword in ["notebook", "smartphone", "tablet"]:
        for date in dates:
            interest = np.random.randint(10, 100)
            data.append({
                "keyword": keyword,
                "date": date,
                "interest_score": interest,
                "source": "mock",
                "is_mock": True,
            })
    
    return pd.DataFrame(data)


@pytest.fixture
def sample_product_data():
    """Dados de produtos simulados para testes."""
    return [
        {
            "source": "mercadolivre",
            "product_id": "MLB123456",
            "title": "Notebook Dell Inspiron 15",
            "price": 3500.00,
            "currency": "BRL",
            "category_id": "MLB1648",
            "sold_quantity": 150,
            "available_quantity": 50,
            "condition": "new",
        },
        {
            "source": "mercadolivre",
            "product_id": "MLB789012",
            "title": "iPhone 15 Pro 256GB",
            "price": 7999.00,
            "currency": "BRL",
            "category_id": "MLB1055",
            "sold_quantity": 300,
            "available_quantity": 20,
            "condition": "new",
        },
    ]


@pytest.fixture
def temp_python_file(tmp_path):
    """Cria um arquivo Python temporário para testes."""
    def _create(content: str, filename: str = "test_script.py"):
        file_path = tmp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return str(file_path)
    return _create