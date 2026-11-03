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
    """Carrega dados iniciais essenciais para produtos e histórico de vendas."""
    seed_file = Path(__file__).parent.parent.parent / "data" / "initial_seed.json"
    if not seed_file.exists():
        print(f"[SeedLoader] Arquivo de seed nao encontrado: {seed_file}")
        return

    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        products_data = data.get("products", [])
        sales_data = data.get("sales_history", [])

        # Inserir ou atualizar produtos
        for p_data in products_data:
            p_id = p_data.get("id")
            existing = session.query(Product).filter(Product.id == p_id).first()
            if existing:
                existing.price = float(p_data.get("price", existing.price))
                existing.title = p_data.get("title", existing.title)
                existing.category = p_data.get("category", existing.category)
            else:
                product = Product(
                    id=p_id,
                    external_id=p_data.get("external_id") or f"PROD_{p_id}",
                    platform=p_data.get("platform") or "proprio",
                    title=p_data.get("title") or "Produto",
                    category=p_data.get("category") or "Geral",
                    price=float(p_data.get("price") or 100.0),
                    currency=p_data.get("currency") or "BRL",
                    condition=p_data.get("condition") or "new",
                    url=p_data.get("url") or "",
                    attributes=p_data.get("attributes"),
                    is_active=bool(p_data.get("is_active", True)),
                    created_at=_parse_dt(p_data.get("created_at")),
                    updated_at=_parse_dt(p_data.get("updated_at"))
                )
                session.add(product)

        session.flush()

        # Inserir histórico de vendas caso vazio
        sales_count = session.query(SalesHistory).count()
        today_midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        seed_dates = [_parse_dt(s.get("date")) for s in sales_data if s.get("date")]
        max_seed_date = max(seed_dates) if seed_dates else today_midnight
        seed_shift = today_midnight - max_seed_date

        if sales_count == 0 and sales_data:
            for s_data in sales_data:
                shifted_date = _parse_dt(s_data.get("date")) + seed_shift
                sales_entry = SalesHistory(
                    id=s_data.get("id"),
                    product_id=s_data.get("product_id"),
                    date=shifted_date,
                    quantity_sold=int(s_data.get("quantity_sold", 10)),
                    price_at_date=float(s_data.get("price_at_date", 100.0)),
                    available_quantity=int(s_data.get("available_quantity", 50)),
                    platform=s_data.get("platform", "proprio"),
                    collected_at=_parse_dt(s_data.get("collected_at"))
                )
                session.add(sales_entry)

        session.commit()
        print(f"[SeedLoader] Banco inicializado com {len(products_data)} produtos.")
    except Exception as e:
        session.rollback()
        print(f"[SeedLoader] Erro ao sincronizar seed: {e}")
