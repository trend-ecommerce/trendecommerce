import pytest
import pandas as pd
import numpy as np


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
def sample_product_data():
    """Dados de produtos simulados para testes (formato API_Historico_Vendas)."""
    return [
        {
            "source": "api_vendas",
            "product_id": "VENDAS_1",
            "title": "Notebook Dell Inspiron 15",
            "price": 3500.00,
            "currency": "BRL",
            "category_id": "Informática",
            "sold_quantity": 150,
            "available_quantity": 50,
            "condition": "new",
        },
        {
            "source": "api_vendas",
            "product_id": "VENDAS_2",
            "title": "iPhone 15 Pro 256GB",
            "price": 7999.00,
            "currency": "BRL",
            "category_id": "Smartphones",
            "sold_quantity": 300,
            "available_quantity": 20,
            "condition": "new",
        },
    ]
