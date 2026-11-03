"""Módulo de carregamento automático de sementes (Seed) de dados no startup."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.database.models import Product, SalesHistory


def _parse_dt(val):
    if not val:
        return datetime.utcnow()
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return datetime.utcnow()


def seed_database_if_empty(session: Session):
    """Sincroniza produtos e histórico do initial_seed.json se o banco estiver vazio."""
    seed_file = Path(__file__).parent.parent.parent / "data" / "initial_seed.json"
    if not seed_file.exists():
        return

    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        products_data = data.get("products", [])
        sales_data = data.get("sales_history", [])

        # 1. Inserir ou atualizar produtos caso tabela esteja vazia
        products_count = session.query(Product).count()
        if products_count == 0:
            for p_data in products_data:
                product = Product(
                    id=p_data.get("id"),
                    external_id=p_data.get("external_id") or f"PROD_{p_data.get('id')}",
                    platform=p_data.get("platform") or "ecommerce",
                    title=p_data.get("title") or "Produto",
                    category=p_data.get("category") or "Geral",
                    price=float(p_data.get("price") or 100.0),
                    currency=p_data.get("currency") or "BRL",
                    condition=p_data.get("condition") or "new",
                    url=p_data.get("url"),
                    attributes=p_data.get("attributes"),
                    created_at=_parse_dt(p_data.get("created_at")),
                    updated_at=_parse_dt(p_data.get("updated_at")),
                    is_active=bool(p_data.get("is_active", True))
                )
                session.add(product)
            session.flush()

        # 2. Sincronizar vendas se tabela de histórico estiver vazia
        sales_count = session.query(SalesHistory).count()
        if sales_count == 0 and sales_data:
            today_midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            dates = [_parse_dt(s.get("date")) for s in sales_data if s.get("date")]
            max_date = max(dates) if dates else today_midnight
            seed_shift = today_midnight - max_date

            for s_data in sales_data:
                shifted_date = _parse_dt(s_data.get("date")) + seed_shift
                sales_entry = SalesHistory(
                    id=s_data.get("id"),
                    product_id=s_data.get("product_id"),
                    date=shifted_date,
                    quantity_sold=int(s_data.get("quantity_sold", 10)),
                    price_at_date=float(s_data.get("price_at_date", 100.0)),
                    available_quantity=int(s_data.get("available_quantity", 50)),
                    platform=s_data.get("platform", "ecommerce"),
                    collected_at=_parse_dt(s_data.get("collected_at"))
                )
                session.add(sales_entry)

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[SeedLoader] Erro ao sincronizar seed: {e}")
