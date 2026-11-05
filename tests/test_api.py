import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """Testa endpoint de health check."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_auth_login_and_me(client):
    """Testa login com credenciais válidas e obtenção do usuário autenticado."""
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@trendecommerce.com",
        "password": "admin123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@trendecommerce.com"

    token = data["access_token"]
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@trendecommerce.com"


def test_auth_google_login_and_register(client):
    """Testa cadastro e login via Google OAuth2 endpoint."""
    # 1. Cadastro / Login com novo usuário via Google
    google_email = "novo.google.user@gmail.com"
    response = client.post("/api/v1/auth/google", json={
        "email": google_email,
        "name": "Google Test User"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == google_email
    assert data["user"]["name"] == "Google Test User"

    # 2. Login com usuário já existente via Google
    response_existing = client.post("/api/v1/auth/google", json={
        "email": "admin@trendecommerce.com"
    })
    assert response_existing.status_code == 200
    assert response_existing.json()["user"]["email"] == "admin@trendecommerce.com"


def test_auth_google_otp_request_and_verify(client):
    """Testa fluxo completo de OTP do Google: solicitação de código e validação."""
    test_email = "usuario.verificado.google@gmail.com"

    # 1. Solicitar código de verificação
    req_resp = client.post("/api/v1/auth/google/request-code", json={
        "email": test_email,
        "name": "Usuario Verificado"
    })
    assert req_resp.status_code == 200
    assert req_resp.json()["success"] is True

    # 2. Tentar código inválido
    err_resp = client.post("/api/v1/auth/google/verify-code", json={
        "email": test_email,
        "code": "0000"
    })
    assert err_resp.status_code == 400

    # 3. Validar com código de teste aceito
    verify_resp = client.post("/api/v1/auth/google/verify-code", json={
        "email": test_email,
        "code": "1234",
        "name": "Usuario Verificado"
    })
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == test_email
    assert data["user"]["name"] == "Usuario Verificado"



def test_auth_register_duplicate(client):
    """Testa tentativa de cadastro duplicado."""
    response = client.post("/api/v1/auth/register", json={
        "email": "admin@trendecommerce.com",
        "password": "outrasenha123",
        "name": "Admin Duplicado"
    })
    assert response.status_code == 400


def test_auth_forgot_and_reset_password(client):
    """Testa fluxo de recuperação de senha com código OTP."""
    req_resp = client.post("/api/v1/auth/forgot-password", json={
        "email": "admin@trendecommerce.com"
    })
    assert req_resp.status_code == 200
    assert req_resp.json()["success"] is True
    assert "admin@trendecommerce.com" in req_resp.json()["message"]

    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "code": "1234",
        "new_password": "novasenhaforte123"
    })
    assert reset_resp.status_code == 200

    # Restaurar senha admin
    client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "code": "1234",
        "new_password": "admin123"
    })


def test_products_list_and_categories(client):
    """Testa listagem paginada e categorias de produtos."""
    response = client.get("/api/v1/products?page=1&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["page"] == 1
    assert len(data["items"]) > 0

    cat_resp = client.get("/api/v1/products/categories")
    assert cat_resp.status_code == 200
    assert isinstance(cat_resp.json(), list)


def test_top_selling_products(client):
    """Testa ranking dos produtos mais vendidos."""
    response = client.get("/api/v1/products/top-sales?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["rank"] == 1
    assert "quantity_sold" in data[0]


def test_product_detail_and_history(client):
    """Testa obtenção de detalhes e histórico temporal de um produto."""
    prod_resp = client.get("/api/v1/products/1")
    assert prod_resp.status_code == 200
    assert prod_resp.json()["id"] == 1

    hist_resp = client.get("/api/v1/products/1/history?days=14")
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) > 0
    assert "quantity_sold" in history[0]


def test_forecast_predict_xgboost(client):
    """Testa execução do modelo de Machine Learning (XGBoost) para previsão futura."""
    response = client.post("/api/v1/forecast/predict", json={
        "product_id": 1,
        "horizon_days": 7
    })
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == 1
    assert data["horizon_days"] == 7
    assert len(data["days"]) == 7
    assert data["total_predicted_units"] > 0
    assert data["total_projected_revenue"] > 0
    assert "confidence_min" in data["days"][0]
    assert "confidence_max" in data["days"][0]
    # Testar Explicabilidade IA
    assert "explanation" in data
    assert data["explanation"] is not None
    assert "summary" in data["explanation"]
    assert "primary_driver" in data["explanation"]
    assert len(data["explanation"]["factors"]) == 4


def test_forecast_ranking(client):
    """Testa ranking preditivo de 30 dias com explicabilidade."""
    response = client.get("/api/v1/forecast/ranking?horizon_days=30")
    assert response.status_code == 200
    data = response.json()
    assert len(data["top_overall"]) <= 7
    assert isinstance(data["top_by_category"], dict)
    if data["top_overall"]:
        first_item = data["top_overall"][0]
        assert "rank_reason" in first_item
        assert "key_driver" in first_item
        assert first_item["rank"] == 1


def test_forecast_compare_endpoint(client):
    """Testa comparador preditivo lado a lado (Produto A vs B)."""
    response = client.post("/api/v1/forecast/compare", json={
        "product_id_a": 1,
        "product_id_b": 2,
        "horizon_days": 14
    })
    assert response.status_code == 200
    data = response.json()
    assert data["horizon_days"] == 14
    assert data["product_a"]["product_id"] == 1
    assert data["product_b"]["product_id"] == 2
    assert "verdict" in data
    assert "demand_leader" in data
    assert "revenue_leader" in data
    assert data["demand_difference"] >= 0
    assert data["revenue_difference"] >= 0


def test_discover_live_products(client):
    """Testa busca no catálogo oficial e tratamento de produto não cadastrado."""
    response = client.post("/api/v1/products/discover-live", json={
        "query": "Monitor Gamer 144Hz",
        "limit": 3
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] > 0
    assert len(data["products"]) > 0
    assert "Monitor" in data["products"][0]["title"] or "Gamer" in data["products"][0]["title"]
    assert all(p["id"] is not None for p in data["products"])

    # Produto inexistente não cadastrado deve retornar 404
    resp_404 = client.post("/api/v1/products/discover-live", json={
        "query": "produto_totalmente_inexistente_xyz_999",
        "limit": 3
    })
    assert resp_404.status_code == 404
    assert "não encontrado" in resp_404.json()["detail"].lower()


def test_send_otp_email_service(monkeypatch):
    """Testa geração de e-mail OTP com logo, remetente oficial e aviso de segurança."""
    import email
    from src.api.services.email_service import send_otp_email
    import smtplib

    # Sem senha configurada deve retornar mensagem de configuração
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_USER", "trendeccomerceai@gmail.com")
    success, msg = send_otp_email("user@example.com", "9842")
    assert success is False
    assert "SMTP_PASSWORD" in msg

    # Com senha mockada deve tentar envio via SMTP
    monkeypatch.setenv("SMTP_PASSWORD", "mockapppassword123")
    monkeypatch.setenv("SMTP_USER", "trendeccomerceai@gmail.com")

    sent_messages = []
    class MockSMTP:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def login(self, user, pwd):
            assert user == "trendeccomerceai@gmail.com"
        def sendmail(self, sender, recipients, msg_str):
            sent_messages.append((sender, recipients, msg_str))

    monkeypatch.setattr(smtplib, "SMTP_SSL", MockSMTP)
    success, msg = send_otp_email("testuser@gmail.com", "7412")
    assert success is True
    assert len(sent_messages) == 1
    sender, recipients, msg_str = sent_messages[0]
    assert sender == "trendeccomerceai@gmail.com"
    assert "testuser@gmail.com" in recipients

    parsed_msg = email.message_from_string(msg_str)
    decoded_body = ""
    for part in parsed_msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            payload = part.get_payload(decode=True)
            if payload:
                decoded_body += payload.decode("utf-8")

    assert "NUNCA COMPARTILHE ESTE CÓDIGO COM NINGUÉM" in decoded_body
    assert "7412" in decoded_body
    assert "trendecommerce_logo" in msg_str


def test_products_autocomplete(client):
    """Testa endpoint de autocompletar e recomendações com caracteres parecidos."""
    # Busca de produto existente ou sugestões ao digitar
    resp = client.get("/api/v1/products/autocomplete?q=creatina&limit=5")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0
    first = items[0]
    assert "title" in first
    assert "price" in first
    assert "category" in first
    assert all(item["id"] is not None for item in items)

    # Busca com termo de pesquisa (recomenda produtos cadastrados com caracteres parecidos)
    resp_cor = client.get("/api/v1/products/autocomplete?q=camisa%20corinthians&limit=5")
    assert resp_cor.status_code == 200
    cor_items = resp_cor.json()
    assert isinstance(cor_items, list)
    assert len(cor_items) > 0
    assert any("camis" in item["title"].lower() for item in cor_items)
    assert all(item["id"] is not None for item in cor_items)

    # Busca com erro de digitação (typo 'notbook') deve recomendar 'Notebook' cadastrado
    resp_typo = client.get("/api/v1/products/autocomplete?q=notbook&limit=5")
    assert resp_typo.status_code == 200
    typo_items = resp_typo.json()
    assert len(typo_items) > 0
    assert any("notebook" in item["title"].lower() for item in typo_items)
    assert all(item["id"] is not None for item in typo_items)

    # Termo proibido deve retornar lista vazia
    resp_prohibited = client.get("/api/v1/products/autocomplete?q=cocaina&limit=5")
    assert resp_prohibited.status_code == 200
    assert resp_prohibited.json() == []

    # Produto inexistente não cadastrado deve retornar lista vazia
    resp_unreg = client.get("/api/v1/products/autocomplete?q=produto_inexistente_xyz_999&limit=5")
    assert resp_unreg.status_code == 200
    assert resp_unreg.json() == []