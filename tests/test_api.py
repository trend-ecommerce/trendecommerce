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

    # Login com usuario ja existente via Google
    response_existing = client.post("/api/v1/auth/google", json={
        "email": "admin@trendecommerce.com"
    })
    assert response_existing.status_code == 200
    assert response_existing.json()["user"]["email"] == "admin@trendecommerce.com"


def test_auth_google_otp_request_and_verify(client):
    """Testa fluxo completo de OTP do Google: solicitacao de codigo e validacao."""
    test_email = "usuario.verificado.google@gmail.com"

    # 1. Solicitar codigo de verificacao
    req_resp = client.post("/api/v1/auth/google/request-code", json={
        "email": test_email,
        "name": "Usuario Verificado"
    })
    assert req_resp.status_code == 200
    assert req_resp.json()["success"] is True

    # 2. Tentar codigo invalido
    err_resp = client.post("/api/v1/auth/google/verify-code", json={
        "email": test_email,
        "code": "0000"
    })
    assert err_resp.status_code == 400

    # 3. Validar com codigo de teste aceito
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


def test_auth_forgot_and_reset_password(client, monkeypatch):
    """Testa fluxo completo de recuperacao de senha com OTP de 6 digitos do Supabase e ticket temporario."""
    import importlib
    auth_router = importlib.import_module("src.api.routers.auth_router")

    recovery_calls = []
    pw_update_calls = []

    monkeypatch.setattr(auth_router, "supabase_ensure_auth_user_for_recovery", lambda email, name=None: "exists")

    def fake_send_recovery(email, redirect_to=None):
        recovery_calls.append(email)
        return True, "Código enviado!"

    def fake_verify_otp(email, token):
        if email == "admin@trendecommerce.com" and token == "654321":
            return True, "ok", "sb_recovery_access_token_xyz"
        return False, "Código de verificação incorreto ou expirado.", None

    def fake_update_sb_pw(access_token, new_password):
        pw_update_calls.append((access_token, new_password))
        return True

    monkeypatch.setattr(auth_router, "supabase_send_password_recovery", fake_send_recovery)
    monkeypatch.setattr(auth_router, "supabase_verify_recovery_otp", fake_verify_otp)
    monkeypatch.setattr(auth_router, "supabase_update_auth_password", fake_update_sb_pw)
    monkeypatch.setattr(auth_router, "supabase_sync_user_row", lambda *args, **kwargs: True)

    # 0. Email nao cadastrado deve retornar 404
    not_found_resp = client.post("/api/v1/auth/forgot-password", json={
        "email": "naoexiste.usuario.xyz@gmail.com"
    })
    assert not_found_resp.status_code == 404

    # 1. Solicitar envio via Supabase Auth
    req_resp = client.post("/api/v1/auth/forgot-password", json={
        "email": "admin@trendecommerce.com"
    })
    assert req_resp.status_code == 200
    assert req_resp.json()["success"] is True
    assert "admin@trendecommerce.com" in recovery_calls

    # 2. Codigo mestre antigo '1234' deve ser rejeitado (422 pelo schema de 6 digitos)
    legacy_verify = client.post("/api/v1/auth/verify-reset-code", json={
        "email": "admin@trendecommerce.com",
        "code": "1234"
    })
    assert legacy_verify.status_code == 422

    # 3. Codigo incorreto de 6 digitos deve retornar 400
    err_verify = client.post("/api/v1/auth/verify-reset-code", json={
        "email": "admin@trendecommerce.com",
        "code": "000000"
    })
    assert err_verify.status_code == 400

    # 4. Codigo correto de 6 digitos deve retornar ticket JWT stateless (reset_token)
    assert not hasattr(auth_router, "_reset_tickets")
    ok_verify = client.post("/api/v1/auth/verify-reset-code", json={
        "email": "admin@trendecommerce.com",
        "code": "654321"
    })
    assert ok_verify.status_code == 200
    verify_data = ok_verify.json()
    assert verify_data["success"] is True
    reset_token = verify_data.get("reset_token")
    assert reset_token and len(reset_token.split(".")) == 3

    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from src.api.dependencies import SECRET_KEY, ALGORITHM

    decoded_ticket = jwt.decode(reset_token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_ticket["purpose"] == "password_reset"
    assert decoded_ticket["sub"] == "admin@trendecommerce.com"
    assert decoded_ticket["sb_access_token"] == "sb_recovery_access_token_xyz"
    assert decoded_ticket.get("pwd_fp")

    # 4b. Token expirado deve retornar HTTP 400
    expired_payload = dict(decoded_ticket)
    expired_payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired_jwt = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
    expired_resp = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "reset_token": expired_jwt,
        "new_password": "novasenhaforte123"
    })
    assert expired_resp.status_code == 400
    assert "expirou" in expired_resp.json()["detail"].lower()

    # 5. Tentativa de reset com '1234' ou ticket invalido deve ser bloqueada (400)
    bad_reset = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "reset_token": "1234",
        "new_password": "novasenhaforte123"
    })
    assert bad_reset.status_code == 400

    # 6. Redefinir senha com ticket valido
    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "reset_token": reset_token,
        "new_password": "novasenhaforte123"
    })
    assert reset_resp.status_code == 200
    assert ("sb_recovery_access_token_xyz", "novasenhaforte123") in pw_update_calls

    # 7. Ticket nao pode ser reutilizado (uso unico)
    reuse_resp = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "reset_token": reset_token,
        "new_password": "outrasenhaforte123"
    })
    assert reuse_resp.status_code == 400

    # 8. Validar login com a nova senha
    login_new = client.post("/api/v1/auth/login", json={
        "email": "admin@trendecommerce.com",
        "password": "novasenhaforte123"
    })
    assert login_new.status_code == 200

    # 9. Restaurar senha admin para os testes subsequentes usando novo ticket
    restore_verify = client.post("/api/v1/auth/verify-reset-code", json={
        "email": "admin@trendecommerce.com",
        "code": "654321"
    })
    assert restore_verify.status_code == 200
    restore_token = restore_verify.json()["reset_token"]
    restore_resp = client.post("/api/v1/auth/reset-password", json={
        "email": "admin@trendecommerce.com",
        "code": restore_token,
        "new_password": "admin123"
    })
    assert restore_resp.status_code == 200

    # 10. Rate limit do Supabase no envio deve retornar HTTP 429 com mensagem em portugues
    monkeypatch.setattr(
        auth_router,
        "supabase_send_password_recovery",
        lambda email, redirect_to=None: (False, "Limite temporário de envio de e-mails atingido."),
    )
    rl_resp = client.post("/api/v1/auth/forgot-password", json={"email": "admin@trendecommerce.com"})
    assert rl_resp.status_code == 429
    assert "limite" in rl_resp.json()["detail"].lower()


def test_supabase_recovery_service_helpers(monkeypatch):
    """Testa helpers de verificacao OTP e atualizacao de senha no supabase_service."""
    from src.api.services import supabase_service

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.content = b"json" if payload is not None else b""

        def json(self):
            return self._payload

    captured = []

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        captured.append(("POST", url, headers, json, params))
        if url.endswith("/auth/v1/verify"):
            if json.get("token") == "654321":
                return FakeResp(200, {"access_token": "tok_abc"})
            return FakeResp(403, {"error_code": "otp_expired", "msg": "Token has expired or is invalid"})
        if url.endswith("/auth/v1/recover"):
            return FakeResp(429, {"error_code": "over_email_send_rate_limit", "msg": "rate limit"})
        return FakeResp(200, {})

    def fake_put(url, headers=None, json=None, timeout=None):
        captured.append(("PUT", url, headers, json, None))
        return FakeResp(200, {"id": "user-1"})

    monkeypatch.setattr(supabase_service.requests, "post", fake_post)
    monkeypatch.setattr(supabase_service.requests, "put", fake_put)
    monkeypatch.delenv("AUTH_RESET_REDIRECT_URL", raising=False)

    ok, msg, token = supabase_service.supabase_verify_recovery_otp("user@gmail.com", "654321")
    assert ok is True
    assert msg == "ok"
    assert token == "tok_abc"

    bad_ok, bad_msg, bad_tok = supabase_service.supabase_verify_recovery_otp("user@gmail.com", "000000")
    assert bad_ok is False
    assert "6 dígitos" in bad_msg
    assert bad_tok is None

    assert supabase_service.supabase_update_auth_password("tok_abc", "NewPass#123") is True
    assert any(c[0] == "PUT" and c[1].endswith("/auth/v1/user") and c[2]["Authorization"] == "Bearer tok_abc" for c in captured)

    rec_ok, rec_msg = supabase_service.supabase_send_password_recovery("user@gmail.com")
    assert rec_ok is False
    assert "limite" in rec_msg.lower()
    recover_calls = [c for c in captured if c[1].endswith("/auth/v1/recover")]
    assert recover_calls[0][4]["redirect_to"] == "https://trendecommerce.onrender.com/app/novasenha.html"


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
    assert "TrendEcommerce AI" in decoded_body
    assert "TrendCommerce AI" not in decoded_body


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

def test_protected_admin_routes(client):
    """Testa que rotas administrativas exigem token JWT valido."""
    # 1. Tentativa sem token deve retornar 401
    resp_reseed_anon = client.post("/api/v1/admin/reseed")
    assert resp_reseed_anon.status_code == 401

    # 2. Login como admin para obter token
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "admin@trendecommerce.com",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Com token valido, rota administrativa deve permitir acesso
    resp_reseed_auth = client.post("/api/v1/admin/reseed", headers=headers)
    assert resp_reseed_auth.status_code == 200
    assert resp_reseed_auth.json()["status"] == "success"


def test_recommendations_top_products_with_real_ml(client):
    """Testa endpoint de recomendações conectado ao motor preditivo real."""
    resp = client.get("/api/v1/recommendations/top-products?days=14&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_analyzed" in data
    assert "items" in data
    if data["items"]:
        first = data["items"][0]
        assert "opportunity_score" in first
        assert "predicted_units" in first
        assert "estimated_revenue" in first
        assert "quadrant" in first
        assert first["predicted_units"] > 0


def test_forecast_timeline_endpoint(client):
    """Testa endpoint da Linha do Tempo Híbrida (histórico real + projeção XGBoost)."""
    # 1. Testar range padrão (6m, 14d) para produto existente
    resp = client.get("/api/v1/forecast/timeline/1?history_range=6m&horizon_days=14")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == 1
    assert "product_title" in data
    assert "current_date" in data
    assert data["history_range"] == "6m"
    assert data["horizon_days"] == 14
    assert len(data["history_points"]) > 0
    assert len(data["forecast_points"]) == 14
    assert "metrics" in data
    assert data["metrics"]["historical_avg"] >= 0
    assert data["metrics"]["historical_peak"] >= data["metrics"]["historical_avg"]
    assert data["metrics"]["forecast_total"] > 0
    assert data["metrics"]["forecast_avg"] > 0
    assert all(p["is_real"] is True for p in data["history_points"])
    assert all("confidence_min" in p and "confidence_max" in p for p in data["forecast_points"])

    # 2. Testar range de 1 mês com 7 dias
    resp_1m = client.get("/api/v1/forecast/timeline/1?history_range=1m&horizon_days=7")
    assert resp_1m.status_code == 200
    d_1m = resp_1m.json()
    assert len(d_1m["history_points"]) <= 32
    assert len(d_1m["forecast_points"]) == 7

    # 3. Testar range de 5 anos com 30 dias (deve conter ~60 pontos mensais)
    resp_5y = client.get("/api/v1/forecast/timeline/1?history_range=5y&horizon_days=30")
    assert resp_5y.status_code == 200
    d_5y = resp_5y.json()
    assert len(d_5y["history_points"]) >= 50
    assert len(d_5y["forecast_points"]) == 30

    # 4. Testar produto inexistente (deve retornar 404)
    resp_404 = client.get("/api/v1/forecast/timeline/999999?history_range=6m&horizon_days=14")
    assert resp_404.status_code == 404
