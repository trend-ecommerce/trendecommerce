"""Script de setup e manutenção do banco de dados (TrendEcommerce AI).

Uso:
    python -m src.database.setup [comando]

Comandos:
    create    - Cria todas as tabelas essenciais no banco de dados
    drop      - Remove todas as tabelas (CUIDADO!)
    seed      - Popula com catálogo e histórico (integra API de Vendas)
    sync      - Sincroniza histórico de vendas até a data de hoje
    status    - Mostra status das tabelas e contagem de registros
    reset     - Drop + Create + Seed (recria banco zerado e integrado)

Para desenvolvimento local, utiliza SQLite em data/trendcommerce_dev.db.
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import inspect, text
from src.database.connection import DatabaseManager
from src.database.models import Base, User, Product, SalesHistory
from src.services.vendas_api_client import vendas_client
import bcrypt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_manager() -> DatabaseManager:
    """Retorna uma instância do DatabaseManager."""
    return DatabaseManager()


def create_tables(manager: DatabaseManager):
    """Cria todas as tabelas essenciais."""
    logger.info("Criando tabelas essenciais...")
    Base.metadata.create_all(manager.engine)
    
    inspector = inspect(manager.engine)
    tables = inspector.get_table_names()
    logger.info(f"Tabelas ativas no banco: {', '.join(tables)}")
    return tables


def drop_tables(manager: DatabaseManager):
    """Remove todas as tabelas."""
    logger.warning("Removendo tabelas antigas...")
    Base.metadata.drop_all(manager.engine)
    logger.info("Tabelas removidas com sucesso.")


def seed_data(manager: DatabaseManager):
    """Popula o banco integrando a API de Histórico de Vendas e garantindo o catálogo oficial calibrado."""
    logger.info("Iniciando população do banco de dados...")

    needs_calibration = False
    with manager.session() as session:
        # 1. Usuário Administrador de Teste
        existing_user = session.query(User).filter_by(email="admin@trendecommerce.com").first()
        if not existing_user:
            admin_user = User(
                email="admin@trendecommerce.com",
                name="Administrador Master",
                hashed_password=bcrypt.hashpw(b"admin123", bcrypt.gensalt(10)).decode("utf-8"),
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            logger.info("Usuário de teste criado: admin@trendecommerce.com (senha: admin123)")
        else:
            existing_user.hashed_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt(10)).decode("utf-8")
            session.commit()

        # 2. Tentar sincronizar da API oficial de Histórico de Vendas
        logger.info("Tentando sincronizar produtos e histórico da API de Histórico de Vendas...")
        sync_res = vendas_client.sync_to_trendecommerce(session, min_date="2020-01-01")

        if sync_res.get("success"):
            logger.info(
                f"Sucesso! {sync_res['total_products']} produtos e "
                f"{sync_res['total_sales']:,} registros de vendas importados da API oficial."
            )
            return

        logger.warning(
            f"Não foi possível sincronizar diretamente via API ({sync_res.get('error')}). "
            "Delegando para ensure_calibrated_databases..."
        )
        needs_calibration = True

    if needs_calibration:
        from src.database.seed_loader import ensure_calibrated_databases

        if ensure_calibrated_databases(manager):
            logger.info("Banco de dados calibrado com sucesso via ensure_calibrated_databases.")
        else:
            logger.error("Falha ao calibrar o banco de dados via ensure_calibrated_databases.")


def sync_up_to_today(manager: DatabaseManager) -> int:
    """Preenche os dias faltantes entre a última data no banco e a data de hoje."""
    import numpy as np
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    added_records = 0
    
    with manager.session() as session:
        products = session.query(Product).all()
        if not products:
            logger.warning("Nenhum produto cadastrado para sincronizar.")
            return 0
            
        for product in products:
            last_sale = session.query(SalesHistory).filter_by(
                product_id=product.id
            ).order_by(SalesHistory.date.desc()).first()
            
            if not last_sale:
                continue
                
            last_date = last_sale.date.replace(hour=0, minute=0, second=0, microsecond=0)
            days_diff = (today - last_date).days
            
            if days_diff > 0:
                base_price = product.price or 100.0
                np.random.seed(product.id * 100 + days_diff)
                
                for step in range(1, days_diff + 1):
                    target_date = last_date + timedelta(days=step)
                    day_of_week = target_date.weekday()
                    weekend_factor = 1.25 if day_of_week in [4, 5, 6] else 0.95
                    base_sales = np.random.randint(15, 45)
                    noise = np.random.randint(-5, 6)
                    quantity = max(1, int(round((base_sales + noise) * weekend_factor)))
                    price = round(base_price * np.random.uniform(0.96, 1.04), 2)
                    
                    sale = SalesHistory(
                        product_id=product.id,
                        date=target_date,
                        quantity_sold=quantity,
                        price_at_date=price,
                        available_quantity=np.random.randint(20, 200),
                        platform=product.platform,
                    )
                    session.add(sale)
                    added_records += 1
                    
        if added_records > 0:
            logger.info(f"Sincronizados {added_records} novos registros de vendas até {today.strftime('%d/%m/%Y')}.")
            
    return added_records


def show_status(manager: DatabaseManager):
    """Mostra o status atual das tabelas."""
    inspector = inspect(manager.engine)
    tables = inspector.get_table_names()
    
    if not tables:
        logger.info("Nenhuma tabela encontrada.")
        return
    
    logger.info(f"\nTabelas encontradas ({len(tables)}):")
    with manager.session() as session:
        for table in tables:
            try:
                count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                logger.info(f"  - {table}: {count:,} registros")
            except Exception as e:
                logger.info(f"  - {table}: erro ao contar ({e})")


def main():
    commands = {
        "create": "Criar tabelas",
        "drop": "Remover tabelas (CUIDADO)",
        "seed": "Popula catálogo e histórico via API de Vendas",
        "sync": "Sincronizar histórico até a data de hoje",
        "status": "Mostrar status das tabelas",
        "reset": "Recriar banco do zero e popular",
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("\n TrendEcommerce AI - Setup do Banco de Dados")
        print("=" * 50)
        print("\nUso: python -m src.database.setup [comando]\n")
        print("Comandos disponíveis:")
        for cmd, desc in commands.items():
            print(f"  {cmd:10s} - {desc}")
        print()
        return
    
    command = sys.argv[1]
    manager = get_db_manager()
    
    if command == "create":
        create_tables(manager)
    elif command == "drop":
        drop_tables(manager)
    elif command == "seed":
        seed_data(manager)
        show_status(manager)
    elif command == "sync":
        sync_up_to_today(manager)
        show_status(manager)
    elif command == "status":
        show_status(manager)
    elif command == "reset":
        drop_tables(manager)
        create_tables(manager)
        seed_data(manager)
        show_status(manager)


if __name__ == "__main__":
    main()
