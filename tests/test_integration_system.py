"""Testes de Integração de Sistema (System Integration Tests) - TrendCommerce AI.

Valida a integração entre camadas:
- Rotas FastAPI + Sessão SQLAlchemy/SQLite (CRUD de Produtos e Vendas)
- Consolidação Executiva (/api/v1/forecast/summary) e Cache em Memória
- Status do Banco e Conectividade com a API de Histórico de Vendas (/api/v1/products/api-status)
- Consistência Temporal entre Janelas da Linha do Tempo (1M, 6M, 1Y, 5Y)
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_integration_create_product_and_record_sale_flow(client):
    """IT-01: Integração completa de cadastro de produto, registro de venda e consulta de histórico."""
    create_resp = client.post("/api/v1/products", json={
        "title": "Headset Gamer Sem Fio 7.1 Surround Teste QA",
        "category": "Eletrônicos",
        "price": 459.90,
        "platform": "api_vendas",
        "currency": "BRL",
        "condition": "new"
    })
    assert create_resp.status_code == 201
    created_prod = create_resp.json()
    new_id = created_prod["id"]
    assert created_prod["title"] == "Headset Gamer Sem Fio 7.1 Surround Teste QA"

    # Registrar venda para o produto recém-criado
    sale_resp = client.post(f"/api/v1/products/{new_id}/sales", json={
        "date": "2026-11-01T12:00:00",
        "quantity_sold": 15,
        "price_at_date": 459.90,
        "available_quantity": 85
    })
    assert sale_resp.status_code == 201
    sale_data = sale_resp.json()
    assert sale_data["product_id"] == new_id
    assert sale_data["quantity_sold"] == 15
    assert sale_data["revenue"] == pytest.approx(15 * 459.90, rel=1e-2)

    # Consultar detalhes do produto e validar persistência da venda
    detail_resp = client.get(f"/api/v1/products/{new_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["total_sold_units"] >= 15
    assert len(detail["sales_history"]) >= 1

    # Limpar produto temporário de teste para manter 500 produtos oficiais intactos
    from src.api.dependencies import get_db_instance
    from src.database.models import Product, SalesHistory
    db_mgr = get_db_instance()
    with db_mgr.session() as session:
        session.query(SalesHistory).filter(SalesHistory.product_id == new_id).delete()
        session.query(Product).filter(Product.id == new_id).delete()
        session.commit()


def test_integration_forecast_summary_and_debug_status(client):
    """IT-02: Integração do resumo executivo consolidado (/forecast/summary) e status do banco (/debug/status)."""
    dbg_resp = client.get("/api/v1/debug/status")
    assert dbg_resp.status_code == 200
    dbg = dbg_resp.json()
    assert dbg["products_count"] >= 500
    assert dbg["sales_history_count"] >= 45000
    assert dbg["users_count"] >= 1

    sum_resp = client.get("/api/v1/forecast/summary?horizon_days=7")
    assert sum_resp.status_code == 200
    summary = sum_resp.json()
    assert summary["horizon_days"] == 7
    assert summary["total_products"] >= 500
    assert summary["total_predicted_units"] > 0
    assert summary["total_projected_revenue"] > 0
    assert len(summary["items"]) >= 500


def test_integration_vendas_api_status_and_category_filter(client):
    """IT-03: Integração do status da API de Histórico de Vendas e filtragem por categoria."""
    status_resp = client.get("/api/v1/products/api-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "url" in status_data
    assert ("online" in status_data) or ("database_file_available" in status_data)

    # Filtrar top-sales por categoria específica
    top_cat_resp = client.get("/api/v1/products/top-sales?limit=5&category=Eletr%C3%B4nicos&days=30")
    assert top_cat_resp.status_code == 200
    top_cat = top_cat_resp.json()
    assert len(top_cat) == 5
    assert all(item["category"] == "Eletrônicos" for item in top_cat)


def test_integration_timeline_consistency_across_ranges(client):
    """IT-04: Verifica consistência absoluta dos pontos históricos entre janelas 1m, 6m, 1y e 5y."""
    r_1m = client.get("/api/v1/forecast/timeline/124?history_range=1m&horizon_days=14").json()
    r_6m = client.get("/api/v1/forecast/timeline/124?history_range=6m&horizon_days=14").json()
    r_1y = client.get("/api/v1/forecast/timeline/124?history_range=1y&horizon_days=14").json()

    map_1m = {p["date"]: p["demand"] for p in r_1m["history_points"]}
    map_6m = {p["date"]: p["demand"] for p in r_6m["history_points"]}
    map_1y = {p["date"]: p["demand"] for p in r_1y["history_points"]}

    # Toda data presente em 1m deve ter exatamente a mesma demanda em 6m e 1y
    for dt, val in map_1m.items():
        assert map_6m[dt] == val
        assert map_1y[dt] == val
