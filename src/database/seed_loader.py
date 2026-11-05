"""Carregador de dados iniciais (Seed Data).

Sincroniza automaticamente o catálogo de produtos e o histórico de vendas
da API de Histórico de Vendas caso o banco de dados esteja vazio ou contenha
registros fora do padrão da API oficial.
"""

import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from src.database.models import Product, SalesHistory
from src.services.vendas_api_client import vendas_client


def _parse_dt(val):
    if not val:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return datetime.utcnow()


def seed_database_if_empty(session: Session):
    """Sincroniza produtos e histórico da API de Vendas se o banco estiver vazio ou desatualizado."""
    try:
        products_count = session.query(Product).count()
        non_api_count = session.query(Product).filter(
            Product.platform != "api_vendas"
        ).count()

        # Se o banco estiver vazio ou contiver produtos que não são da API oficial, sincronizar
        if products_count == 0 or non_api_count > 0:
            if non_api_count > 0:
                session.query(SalesHistory).delete()
                session.query(Product).delete()
                session.commit()

            sync_res = vendas_client.sync_to_trendecommerce(session, min_date="2020-01-01")
            if sync_res.get("success") and sync_res.get("total_products", 0) > 0:
                print(
                    f"[SeedLoader] Catálogo oficial sincronizado: "
                    f"{sync_res['total_products']} produtos e {sync_res['total_sales']:,} vendas."
                )
                return

        # Fallback para initial_seed.json caso a API externa não esteja acessível e o banco esteja vazio
        if session.query(Product).count() > 0:
            return

        seed_file = Path(__file__).parent.parent.parent / "data" / "initial_seed.json"
        if not seed_file.exists():
            return

        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        products_data = data.get("products", [])
        sales_data = data.get("sales_history", [])

        for p_data in products_data:
            product = Product(
                id=p_data.get("id"),
                external_id=p_data.get("external_id") or f"PROD_{p_data.get('id')}",
                platform="api_vendas",
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

        if sales_data:
            today_midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            seed_dates = [_parse_dt(s.get("date")) for s in sales_data if s.get("date")]
            max_seed_date = max(seed_dates) if seed_dates else today_midnight
            seed_shift = today_midnight - max_seed_date

            for s_data in sales_data:
                shifted_date = _parse_dt(s_data.get("date")) + seed_shift
                sales_entry = SalesHistory(
                    id=s_data.get("id"),
                    product_id=s_data.get("product_id"),
                    date=shifted_date,
                    quantity_sold=int(s_data.get("quantity_sold", 10)),
                    price_at_date=float(s_data.get("price_at_date", 100.0)),
                    available_quantity=int(s_data.get("available_quantity", 50)),
                    platform="api_vendas",
                    collected_at=_parse_dt(s_data.get("collected_at"))
                )
                session.add(sales_entry)

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[SeedLoader] Erro ao sincronizar seed: {e}")
