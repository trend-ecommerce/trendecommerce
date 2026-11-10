"""Carregador de dados iniciais (Seed Data).

Sincroniza automaticamente o catálogo de produtos e o histórico de vendas
da API de Histórico de Vendas caso o banco de dados esteja vazio ou contenha
registros fora do padrão da API oficial.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import Product, SalesHistory
from src.services.vendas_api_client import vendas_client


def _parse_dt(val):
    if not val:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return datetime.utcnow()


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
    """Sincroniza produtos e histórico da API de Vendas se o banco estiver vazio ou desatualizado."""
    try:
        products_count = session.query(Product).count()
        non_api_count = session.query(Product).filter(
            Product.platform != "api_vendas"
        ).count()

        # Se o banco contiver produtos legados/fora do padrão oficial, resetar
        if non_api_count > 0:
            session.query(SalesHistory).delete()
            session.query(Product).delete()
            session.commit()
            products_count = 0

        # Se já temos produtos, garantir que as datas de vendas estão calibradas para hoje
        if products_count > 0:
            max_sale_date = session.query(func.max(SalesHistory.date)).scalar()
            if max_sale_date:
                today_midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                diff_days = (today_midnight - max_sale_date.replace(hour=0, minute=0, second=0, microsecond=0)).days
                if diff_days >= 2:
                    shift = timedelta(days=diff_days)
                    session.query(SalesHistory).update({SalesHistory.date: SalesHistory.date + shift})
                    session.commit()
                    print(f"[SeedLoader] Histórico de vendas calibrado para hoje (+{diff_days} dias).")
            return

        # 1. Tentar sincronizar da API oficial de vendas (ambiente de desenvolvimento local)
        try:
            sync_res = vendas_client.sync_to_trendecommerce(session, min_date="2020-01-01")
            if sync_res.get("success") and sync_res.get("total_products", 0) > 0:
                print(
                    f"[SeedLoader] Catálogo oficial sincronizado: "
                    f"{sync_res['total_products']} produtos e {sync_res['total_sales']:,} vendas."
                )
                return
        except Exception as sync_err:
            print(f"[SeedLoader] Sincronização via API local ignorada: {sync_err}")

        # 2. Fallback essencial para produção (Render / Vercel): carregar data/initial_seed.json
        seed_file = Path(__file__).parent.parent.parent / "data" / "initial_seed.json"
        if not seed_file.exists():
            print(f"[SeedLoader] Arquivo initial_seed.json não encontrado. Usando catálogo de contingência.")
            _seed_contingency_catalog(session)
            return

        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        products_data = data.get("products", [])
        sales_data = data.get("sales_history", [])

        if not products_data:
            _seed_contingency_catalog(session)
            return

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

        # Ajuste de sequences caso o banco seja PostgreSQL (ex: Supabase / Render Postgres)
        try:
            bind = session.get_bind()
            if bind and bind.dialect.name == "postgresql":
                from sqlalchemy import text
                session.execute(text("SELECT setval(pg_get_serial_sequence('products', 'id'), coalesce(max(id), 1)) FROM products;"))
                session.execute(text("SELECT setval(pg_get_serial_sequence('sales_history', 'id'), coalesce(max(id), 1)) FROM sales_history;"))
                session.commit()
        except Exception:
            pass

        print(f"[SeedLoader] Catálogo inicial carregado: {len(products_data)} produtos e {len(sales_data):,} vendas.")
    except Exception as e:
        session.rollback()
        print(f"[SeedLoader] Erro ao sincronizar seed: {e}")
