"""Carregador e verificador de calibragem dos bancos (Seed Data).

Garante automaticamente na inicialização que tanto o banco da API
(historico_vendas.db, quando presente) quanto o banco local/Render
(data/trendcommerce_dev.db ou PostgreSQL via DATABASE_URL) contenham
exatamente os 500 produtos oficiais e cobertura histórica 2020-01-01..2026-11-30
calibrada deterministicamente. Nunca carrega catálogos fictícios legados.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import Product, SalesHistory
from src.services.vendas_api_client import vendas_client

logger = logging.getLogger(__name__)

TARGET_MIN_DATE = "2020-01-01"
TARGET_MAX_DATE = "2026-11-30"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_JSON_PATH = PROJECT_ROOT / "data" / "catalog_500_products.json"
EXACT_CALIBRATION_SIGNATURES = (
    (1, "2026-11-30", 68),
    (1, "2026-11-27", 251),
    (124, "2026-10-29", 1133),
    (1, "2020-01-25", 46),
)
OFFICIAL_ANCHOR_PRODUCTS = {
    1: ("Notebook Dell Inspiron 15 i5 8GB SSD 256GB", 4107.23),
    124: ("Pisca-pisca de Natal LED 14 Lâmpadas 8 Funções", 61.37),
}


def _load_expected_catalog_signatures() -> dict[int, tuple[str, float]]:
    """Carrega mapa (id -> (titulo, preco_base)) oficial a partir de data/catalog_500_products.json."""
    expected: dict[int, tuple[str, float]] = dict(OFFICIAL_ANCHOR_PRODUCTS)
    if CATALOG_JSON_PATH.exists():
        try:
            with open(CATALOG_JSON_PATH, "r", encoding="utf-8") as f:
                items = json.load(f)
            if isinstance(items, list):
                for item in items:
                    pid = int(item["id"])
                    expected[pid] = (
                        str(item.get("nome") or ""),
                        round(float(item.get("preco_base") or 0.0), 2),
                    )
        except Exception as err:
            logger.warning(f"[SeedLoader] Falha ao ler assinaturas de {CATALOG_JSON_PATH}: {err}")
    return expected


def _is_api_db_calibrated(api_db_path: Optional[Path]) -> bool:
    """Verifica em poucos milissegundos se historico_vendas.db possui cobertura até 2026-11-30 e assinatura calibrada."""
    if not api_db_path or not api_db_path.exists():
        return False
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(api_db_path), timeout=10.0)
        max_row = conn.execute("SELECT MAX(data_venda) FROM vendas_historicas").fetchone()
        if not max_row or not max_row[0] or str(max_row[0])[:10] != TARGET_MAX_DATE:
            return False

        for pid, date_str, expected_qty in EXACT_CALIBRATION_SIGNATURES:
            row = conn.execute(
                "SELECT vendas FROM vendas_historicas WHERE produto_id = ? AND data_venda = ?",
                (pid, date_str),
            ).fetchone()
            if not row or int(row[0]) != expected_qty:
                return False
        return True
    except Exception as err:
        logger.warning(f"[SeedLoader] Falha ao verificar assinatura em {api_db_path}: {err}")
        return False
    finally:
        if conn is not None:
            conn.close()


def _is_local_db_calibrated(session: Session, exact_api_signatures: bool = True) -> bool:
    """Verifica se o banco local/Render possui exatamente os 500 produtos oficiais (títulos, preços e plataforma)
    e cobertura histórica calibrada 2020-01-01..2026-11-30.
    """
    try:
        prod_rows = session.query(Product.id, Product.title, Product.price, Product.platform).all()
        min_expected_prods = 500 if (exact_api_signatures or CATALOG_JSON_PATH.exists()) else 1
        if len(prod_rows) < min_expected_prods:
            return False

        if any(str(r[3]) != "api_vendas" for r in prod_rows):
            return False

        # Rejeita imediatamente catálogos fictícios/divergentes (ex: Produto 124 != Pisca-pisca de Natal)
        existing_by_id = {int(r[0]): (str(r[1]), round(float(r[2] or 0.0), 2)) for r in prod_rows}
        expected_catalog = _load_expected_catalog_signatures()
        for pid, exp_pair in expected_catalog.items():
            if existing_by_id.get(pid) != exp_pair:
                logger.warning(
                    f"[SeedLoader] Produto divergente detectado (id={pid}: atual={existing_by_id.get(pid)} vs oficial={exp_pair}). Recalibração será executada."
                )
                return False

        date_bounds = session.query(
            func.min(SalesHistory.date),
            func.max(SalesHistory.date),
        ).first()
        if not date_bounds or not date_bounds[0] or not date_bounds[1]:
            return False
        if str(date_bounds[0])[:10] != TARGET_MIN_DATE or str(date_bounds[1])[:10] != TARGET_MAX_DATE:
            return False

        for pid, date_str, expected_qty in EXACT_CALIBRATION_SIGNATURES:
            target_dt = datetime.strptime(date_str, "%Y-%m-%d")
            qty = (
                session.query(SalesHistory.quantity_sold)
                .filter(
                    SalesHistory.product_id == pid,
                    SalesHistory.date >= (target_dt - timedelta(days=1)),
                    SalesHistory.date < (target_dt + timedelta(days=1)),
                    func.date(SalesHistory.date) == date_str,
                )
                .scalar()
            )
            if qty is None or int(qty) != expected_qty:
                return False

        # Verifica que o último produto oficial (500) também recebeu a ponta final (evita carga truncada)
        if min_expected_prods >= 500:
            tail_dt = datetime.strptime(TARGET_MAX_DATE, "%Y-%m-%d")
            p500_tail = (
                session.query(SalesHistory.id)
                .filter(
                    SalesHistory.product_id == 500,
                    SalesHistory.date >= (tail_dt - timedelta(days=1)),
                    SalesHistory.date < (tail_dt + timedelta(days=1)),
                    func.date(SalesHistory.date) == TARGET_MAX_DATE,
                )
                .first()
            )
            if p500_tail is None:
                return False

        return True
    except Exception as err:
        logger.warning(f"[SeedLoader] Falha ao verificar assinatura no banco local: {err}")
        return False


def ensure_calibrated_databases(db_manager=None) -> bool:
    """Verifica na inicialização se historico_vendas.db (se disponível) e o banco local/Render
    contêm o catálogo oficial completo e a série calibrada até 2026-11-30. Caso contrário,
    limpa registros divergentes e executa scripts.update_historical_data_to_nov30.main().
    """
    if db_manager is None:
        from src.api.dependencies import get_db_instance
        db_manager = get_db_instance()

    api_db_path = vendas_client.get_database_path()
    api_ok = _is_api_db_calibrated(api_db_path) if api_db_path else True
    use_exact = bool(api_db_path or CATALOG_JSON_PATH.exists())

    local_ok = False
    with db_manager.session() as check_session:
        local_ok = _is_local_db_calibrated(
            check_session,
            exact_api_signatures=use_exact,
        )
        # Se houver produtos sintéticos ou catálogo divergente do oficial, limpar antes de sincronizar/recriar
        if not local_ok:
            try:
                has_stale = check_session.query(Product.id).first() is not None
                if has_stale:
                    non_api_count = check_session.query(Product).filter(Product.platform != "api_vendas").count()
                    p124_row = check_session.query(Product.title, Product.price).filter(Product.id == 124).first()
                    p124_bad = (not p124_row) or (str(p124_row[0]) != OFFICIAL_ANCHOR_PRODUCTS[124][0])
                    if non_api_count > 0 or p124_bad:
                        logger.warning("[SeedLoader] Removendo produtos antigos/fictícios para restaurar catálogo oficial de 500 produtos...")
                        check_session.query(SalesHistory).delete()
                        check_session.query(Product).delete()
                        check_session.commit()
            except Exception:
                check_session.rollback()

    if api_ok and local_ok:
        return True

    can_calibrate = bool(
        api_db_path
        or CATALOG_JSON_PATH.exists()
        or (PROJECT_ROOT / "data" / "trendcommerce_dev.db").exists()
    )
    if can_calibrate:
        print(
            "[SeedLoader] Catálogo oficial ou assinatura calibrada (2026-11-30 / P1=68 / P124=1133) "
            "ausente ou divergente. Executando recalibração e sincronização automática..."
        )
        try:
            from scripts.update_historical_data_to_nov30 import main as run_update_nov30
            run_update_nov30()
            return True
        except Exception as err:
            logger.error(f"[SeedLoader] Erro na recalibração automática: {err}")
            return False

    return False


def _seed_contingency_catalog(session: Session):
    """Fallback de contingência com catálogo básico calibrado caso o seed JSON não seja encontrado."""
    import numpy as np
    products = [
        Product(external_id="PROD_101", platform="api_vendas", title="Notebook Dell Inspiron 15 Intel Core i7 16GB 512GB SSD", category="Eletrônicos", price=3499.99),
        Product(external_id="PROD_102", platform="api_vendas", title="MacBook Air M2 13.6 Polegadas 8GB RAM 256GB SSD", category="Eletrônicos", price=6899.00),
        Product(external_id="PROD_103", platform="api_vendas", title="Smartphone Samsung Galaxy S23 5G 256GB", category="Eletrônicos", price=3199.00),
        Product(external_id="PROD_104", platform="api_vendas", title="Creatina Monohidratada Pura Micronizada 300g", category="Esportes e fitness", price=119.90),
        Product(external_id="PROD_105", platform="api_vendas", title="Whey Protein Concentrado 100% Pouch 900g", category="Esportes e fitness", price=149.90),
        Product(external_id="PROD_106", platform="api_vendas", title="Tênis Esportivo Running Amortecimento Pro", category="Moda e acessórios", price=289.90),
        Product(external_id="PROD_107", platform="api_vendas", title="Batom Líquido Matte Longa Duração Efeito Aveludado", category="Beleza e cuidados pessoais", price=39.90),
        Product(external_id="PROD_108", platform="api_vendas", title="Cafeteira Elétrica Programável Jarra Inox 1.5L", category="Casa e decoração", price=229.90),
    ]
    session.add_all(products)
    session.flush()

    base_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    for product in products:
        for day in range(90):
            sale_date = base_date - timedelta(days=89 - day)
            weekend_factor = 1.3 if sale_date.weekday() in [5, 6] else 1.0
            qty = max(2, int(np.random.poisson(20) * weekend_factor))
            sale = SalesHistory(
                product_id=product.id,
                date=sale_date,
                quantity_sold=qty,
                price_at_date=product.price,
                available_quantity=100,
                platform=product.platform
            )
            session.add(sale)
    session.commit()
    print("[SeedLoader] Catálogo de contingência carregado com sucesso (8 produtos).")


def seed_database_if_empty(session: Session):
    """Garante catálogo oficial dos 500 produtos e histórico calibrado até 2026-11-30 (sem fallback fictício)."""
    try:
        api_db_path = vendas_client.get_database_path()
        api_ok = _is_api_db_calibrated(api_db_path) if api_db_path else True
        use_exact = bool(api_db_path or CATALOG_JSON_PATH.exists())
        local_ok = _is_local_db_calibrated(session, exact_api_signatures=use_exact)

        if api_ok and local_ok:
            return

        # Se o banco contiver catálogo divergente/fictício antigo, limpar antes de reconstruir
        has_products = session.query(Product.id).first() is not None
        if has_products:
            non_api_count = session.query(Product).filter(Product.platform != "api_vendas").count()
            p124_row = session.query(Product.title, Product.price).filter(Product.id == 124).first()
            p124_bad = (not p124_row) or (str(p124_row[0]) != OFFICIAL_ANCHOR_PRODUCTS[124][0])
            if non_api_count > 0 or p124_bad:
                session.query(SalesHistory).delete()
                session.query(Product).delete()
                session.commit()
            else:
                session.rollback()
        else:
            # Libera qualquer transação de leitura aberta no SQLite antes de gravar em lote
            session.rollback()

        can_calibrate = bool(
            api_db_path
            or CATALOG_JSON_PATH.exists()
            or (PROJECT_ROOT / "data" / "trendcommerce_dev.db").exists()
        )
        if can_calibrate:
            try:
                from scripts.update_historical_data_to_nov30 import main as run_update_nov30
                run_update_nov30()
                session.expire_all()
                return
            except Exception as err:
                logger.warning(f"[SeedLoader] Falha ao executar update_historical_data_to_nov30: {err}")
        else:
            logger.error("[SeedLoader] Nenhum catálogo oficial (historico_vendas.db nem data/catalog_500_products.json) encontrado.")
    except Exception as e:
        session.rollback()
        print(f"[SeedLoader] Erro ao sincronizar seed: {e}")
