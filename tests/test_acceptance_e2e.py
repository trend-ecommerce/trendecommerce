"""Testes de Aceitação (User Acceptance & E2E Journey Tests) - TrendCommerce AI.

Valida os Critérios de Aceitação (BDD - Dado / Quando / Então) sob a ótica do usuário final:
- CA-01: Jornada de Autenticação, Sessão do Usuário e Acesso às Páginas Web (/app/*)
- CA-02: Jornada do Painel IA Preditiva (Linha do Tempo Híbrida, Horizontes 7/14/30d, KPIs e Mais Vendidos)
- CA-03: Jornada do Ranking Preditivo (Top 7 Geral 30 dias e Top 5 por Categoria com PTI)
- CA-04: Jornada de Análise Específica (Busca Inteligente com Tolerância a Erros de Digitação e Bloqueio de Inexistentes)
- CA-05: Jornada de Comparação Estratégica Lado a Lado e Recomendações da Matriz de Oportunidades (POI)
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_acceptance_ca01_frontend_pages_and_auth_journey(client):
    """CA-01: Dado um gestor comercial, quando acessa a plataforma e realiza login, então obtém acesso completo às telas."""
    # 1. Verificar entrega das páginas HTML do frontend
    for page in ["login.html", "ia-preditiva.html", "ranking.html", "analise-especifica.html", "cadastro.html"]:
        resp_page = client.get(f"/app/{page}")
        assert resp_page.status_code == 200
        assert "<!DOCTYPE html>" in resp_page.text or "<html" in resp_page.text

    # 2. Realizar login como Administrador e validar perfil na sessão
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "admin@trendecommerce.com",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert token_data["token_type"] == "bearer"

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_data['access_token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["is_active"] is True


def test_acceptance_ca02_ia_preditiva_dashboard_journey(client):
    """CA-02: Dado o painel IA Preditiva, quando o usuário alterna horizontes (7, 14, 30 dias), então os KPIs e curvas atualizam."""
    # Obter Top 5 mais vendidos no mês
    top_resp = client.get("/api/v1/products/top-sales?limit=5&days=30")
    assert top_resp.status_code == 200
    top_items = top_resp.json()
    assert len(top_items) == 5
    leader_id = top_items[0]["id"]

    # Simular seleção de horizontes 7, 14 e 30 dias para o produto líder
    totals = {}
    for horizon in (7, 14, 30):
        tl_resp = client.get(f"/api/v1/forecast/timeline/{leader_id}?history_range=6m&horizon_days={horizon}")
        assert tl_resp.status_code == 200
        tl = tl_resp.json()
        assert len(tl["forecast_points"]) == horizon
        assert tl["metrics"]["forecast_total"] > 0
        assert tl["metrics"]["forecast_revenue"] > 0
        assert tl["metrics"]["recommended_buffer"] >= tl["metrics"]["forecast_total"]
        totals[horizon] = tl["metrics"]["forecast_total"]

    # Demanda acumulada de 30 dias deve ser maior que a de 14 dias, e 14 maior que 7 dias
    assert totals[30] > totals[14] > totals[7]


def test_acceptance_ca03_ranking_30d_and_categories_journey(client):
    """CA-03: Dado a tela de Ranking de Produtos, quando carregada, então exibe Top 7 Geral e Top 5 por Categoria."""
    rank_resp = client.get("/api/v1/forecast/ranking?horizon_days=30")
    assert rank_resp.status_code == 200
    rank_data = rank_resp.json()

    assert len(rank_data["top_overall"]) == 7
    assert "GERAIS" in rank_data["top_by_category"]
    for cat in ["Eletrônicos", "Moda e acessórios", "Casa e decoração", "Esportes e fitness", "Beleza e cuidados pessoais"]:
        assert cat in rank_data["top_by_category"]
        assert len(rank_data["top_by_category"][cat]) == 5
        assert rank_data["top_by_category"][cat][0]["rank"] == 1


def test_acceptance_ca04_specific_analysis_fuzzy_search_journey(client):
    """CA-04: Dado a Análise Específica, quando o usuário pesquisa com erro de digitação, então recebe sugestões válidas e gera projeção."""
    # 1. Digitar 'notbook' (com erro de grafia) no autocomplete
    auto_resp = client.get("/api/v1/products/autocomplete?q=notbook&limit=5")
    assert auto_resp.status_code == 200
    suggestions = auto_resp.json()
    assert len(suggestions) > 0
    selected_prod = suggestions[0]
    assert "notebook" in selected_prod["title"].lower()

    # 2. Carregar análise preditiva e XAI para o produto selecionado
    pred_resp = client.post("/api/v1/forecast/predict", json={
        "product_id": selected_prod["id"],
        "horizon_days": 14
    })
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()
    assert pred_data["product_id"] == selected_prod["id"]
    assert len(pred_data["days"]) == 14
    assert len(pred_data["explanation"]["factors"]) == 4


def test_acceptance_ca05_strategic_comparison_and_poi_matrix_journey(client):
    """CA-05: Dado dois produtos concorrentes, quando comparados, então o sistema emite veredito estratégico e classifica oportunidades."""
    comp_resp = client.post("/api/v1/forecast/compare", json={
        "product_id_a": 1,
        "product_id_b": 124,
        "horizon_days": 30
    })
    assert comp_resp.status_code == 200
    comp = comp_resp.json()
    assert comp["horizon_days"] == 30
    assert len(comp["verdict"]) > 20

    rec_resp = client.get("/api/v1/recommendations/top-products?days=14&limit=10")
    assert rec_resp.status_code == 200
    rec = rec_resp.json()
    assert rec["total_analyzed"] >= 500
    assert len(rec["items"]) == 10
    assert rec["items"][0]["opportunity_score"] >= rec["items"][-1]["opportunity_score"]
