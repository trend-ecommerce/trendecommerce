"""Testes Unitários de Núcleo (Core Unit Tests) - TrendCommerce AI.

Valida funções puras, regras matemáticas, criptografia de senhas, tokens JWT,
validação de domínios de e-mail, normalização textual (Unicode), saneamento de
séries temporais e cálculos isolados do motor preditivo e de oportunidades.
"""

from datetime import timedelta
import numpy as np
import pandas as pd
import pytest
from jose import jwt

from src.api.dependencies import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
)
from src.api.routers.products_router import _strip_accents
from src.api.services.supabase_service import validate_real_email
from src.features.feature_engineering import FeatureEngineer
from src.ml.future_forecaster import FutureForecaster
from src.ml.opportunity_recommender import OpportunityRecommender


class TestSecurityAndHashingUnit:
    """Testes unitários de segurança, hashing Bcrypt e geração de JWT."""

    def test_password_hash_and_verification(self):
        """UT-01: Verifica geração de hash Bcrypt e validação positiva/negativa de senha."""
        raw_pwd = "TrendCommerce@2026"
        hashed = get_password_hash(raw_pwd)

        assert hashed != raw_pwd
        assert hashed.startswith("$2")
        assert verify_password(raw_pwd, hashed) is True
        assert verify_password("SenhaIncorreta123", hashed) is False

    def test_jwt_access_token_creation_and_claims(self):
        """UT-02: Verifica codificação e decodificação de claims no token JWT."""
        payload = {"sub": "qa.tester@trendecommerce.com", "user_id": 99}
        token = create_access_token(data=payload, expires_delta=timedelta(minutes=30))

        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "qa.tester@trendecommerce.com"
        assert decoded["user_id"] == 99
        assert "exp" in decoded


class TestEmailValidationUnit:
    """Testes unitários de validação de e-mail e bloqueio de domínios descartáveis."""

    def test_valid_corporate_and_system_emails(self):
        """UT-03: E-mails reais e contas administrativas permitidas devem ser aceitos."""
        ok_admin, msg_admin = validate_real_email("admin@trendecommerce.com")
        assert ok_admin is True
        assert msg_admin == ""

        ok_gmail, msg_gmail = validate_real_email("cliente.loja@gmail.com")
        assert ok_gmail is True
        assert msg_gmail == ""

    def test_reject_invalid_and_disposable_emails(self):
        """UT-04: E-mails malformados ou de domínios temporários/bloqueados devem ser rejeitados."""
        ok_fmt, _ = validate_real_email("email_sem_arroba.com")
        assert ok_fmt is False

        ok_disp, msg_disp = validate_real_email("fake@mailinator.com")
        assert ok_disp is False
        assert "permitido" in msg_disp.lower() or "verdadeiro" in msg_disp.lower()


class TestTextNormalizationAndForecasterUnit:
    """Testes unitários de normalização textual, saneamento de outliers e cálculos do FutureForecaster."""

    def test_strip_accents_normalization(self):
        """UT-05: Verifica remoção de acentuação e conversão para minúsculas na busca."""
        assert _strip_accents("Estação de Musculação Pró") == "estacao de musculacao pro"
        assert _strip_accents("Câmera Fotográfica 4K") == "camera fotografica 4k"

    def test_sanitize_sales_series_outlier_removal(self):
        """UT-06: Verifica se zeros isolados e agulhas extremas são saneados preservando a mediana."""
        raw_series = pd.Series([50, 52, 48, 0, 51, 49, 50, 300, 51, 50], dtype=float)
        cleaned = FeatureEngineer.sanitize_sales_series(raw_series, product_id=1)

        assert len(cleaned) == len(raw_series)
        assert cleaned.iloc[3] >= 35.0  # Zero isolado corrigido para patamar da mediana
        assert cleaned.iloc[7] <= 90.0  # Agulha isolada de 300 amortecida

    def test_forecaster_feature_row_and_trend_stats(self):
        """UT-07: Verifica construção do vetor de 23 features e cálculo de tendência (slope/anchor)."""
        forecaster = FutureForecaster(model_path="nao_existe.json")
        history = [20 + i for i in range(30)]
        curr_date = pd.Timestamp("2026-11-15")

        row = forecaster._build_feature_row(price=199.90, history=history, curr_date=curr_date)
        assert len(row) == 23
        assert row["eh_fim_semana"] == 1  # 15/11/2026 é domingo
        assert row["price"] == pytest.approx(199.90, rel=1e-3)

        slope, anchor = forecaster._compute_trend_stats(history)
        assert slope > 0.0
        assert anchor >= 40.0

    def test_opportunity_quadrant_classification(self):
        """UT-08: Verifica classificação nos 4 quadrantes estratégicos da Matriz POI."""
        recommender = OpportunityRecommender()
        products_df = pd.DataFrame([
            {"product_id": 1, "title": "Prod Explosivo", "category": "Tech", "platform": "api_vendas", "price": 200.0},
            {"product_id": 2, "title": "Prod Estável", "category": "Tech", "platform": "api_vendas", "price": 200.0},
            {"product_id": 3, "title": "Prod Moderado", "category": "Tech", "platform": "api_vendas", "price": 200.0},
            {"product_id": 4, "title": "Prod Baixo", "category": "Tech", "platform": "api_vendas", "price": 200.0},
        ])
        forecasts = {
            1: {"predicted_units": 50, "growth_pct": 15.0},   # score >= 75 e growth > 8 -> OPORTUNIDADE_EXPLOSIVA
            2: {"predicted_units": 30, "growth_pct": 2.0},    # score = 69 -> ALTA_RENTABILIDADE
            3: {"predicted_units": 10, "growth_pct": -2.0},   # score = 51 -> DEMANDA_MODERADA
            4: {"predicted_units": 2, "growth_pct": -15.0},   # score = 21 -> BAIXA_PRIORIDADE
        }

        items = recommender.evaluate_opportunities(products_df, forecasts, horizon_days=14)
        by_id = {item.product_id: item for item in items}

        assert by_id[1].quadrant == OpportunityRecommender.QUADRANT_EXPLOSIVE
        assert by_id[2].quadrant == OpportunityRecommender.QUADRANT_STABILITY
        assert by_id[3].quadrant == OpportunityRecommender.QUADRANT_MODERATE
        assert by_id[4].quadrant == OpportunityRecommender.QUADRANT_LOW
