"""Script de setup e inicialização do banco de dados limpo e leve.

Uso:
    python -m src.database.setup [comando]

Comandos:
    create    - Cria todas as tabelas essenciais no banco de dados
    drop      - Remove todas as tabelas
    seed      - Popula com catálogo e histórico (integra API do professor)
    status    - Mostra status das tabelas
    reset     - Drop + Create + Seed (recria banco zerado e integrado)

Para desenvolvimento local, utiliza SQLite em data/trendcommerce_dev.db.
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import inspect, text
from src.database.connection import DatabaseManager
from src.database.models import Base, User, Product, SalesHistory
from src.services.vendas_api_client import vendas_client
import bcrypt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_manager() -> DatabaseManager:
    """Obtém o gerenciador de banco de dados."""
    db_url = os.getenv("DATABASE_URL", "")
    
    if not db_url or "user:password" in db_url:
        db_path = Path(__file__).parent.parent.parent / "data" / "trendcommerce_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"
        logger.info(f"Usando SQLite para desenvolvimento: {db_path}")
    else:
        logger.info(f"Usando banco de dados: {db_url.split('@')[-1] if '@' in db_url else 'configurado'}")
    
    return DatabaseManager(database_url=db_url)


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
    """Popula o banco integrando a API de Vendas do professor e criando usuário padrão."""
    import numpy as np
    np.random.seed(42)
    
    logger.info("Iniciando população do banco de dados...")
    
    with manager.session() as session:
        # 1. Usuário Administrador de Teste
        existing_user = session.query(User).filter_by(email="admin@trendecommerce.com").first()
        if not existing_user:
            admin_user = User(
                email="admin@trendecommerce.com",
                name="Administrador",
                hashed_password=bcrypt.hashpw(b"admin123", bcrypt.gensalt(10)).decode("utf-8"),
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            logger.info("Usuário de teste criado: admin@trendecommerce.com (senha: admin123)")
        else:
            existing_user.hashed_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt(10)).decode("utf-8")
            session.commit()

        # 2. Tentar sincronizar da nova API de Vendas oficial do professor
        logger.info("Tentando sincronizar produtos e histórico da API de Histórico de Vendas...")
        sync_res = vendas_client.sync_to_trendecommerce(session, min_date="2024-01-01")

        if sync_res.get("success"):
            logger.info(f"Sucesso! {sync_res['total_products']} produtos e {sync_res['total_sales']:,} registros de vendas importados da API oficial.")
            return

        # 3. Fallback de contingência caso os arquivos da API não estejam disponíveis
        logger.warning(f"Não foi possível sincronizar da API externa ({sync_res.get('error')}). Usando catálogo base de contingência.")
        products = [
            Product(external_id="PROD_101", platform="api_vendas", title="Notebook Dell Inspiron 15 Intel Core i7 16GB 512GB SSD", category="Eletrônicos", price=3499.99),
            Product(external_id="PROD_102", platform="api_vendas", title="MacBook Air M2 13.6 Polegadas 8GB RAM 256GB SSD", category="Eletrônicos", price=6899.00),
            Product(external_id="PROD_103", platform="api_vendas", title="Notebook Gamer Acer Nitro 5 Intel Core i5 RTX 3050 16GB", category="Eletrônicos", price=4299.00),
            Product(external_id="PROD_201", platform="api_vendas", title="iPhone 15 Pro 256GB Titânio Natural", category="Eletrônicos", price=7999.00),
            Product(external_id="PROD_202", platform="api_vendas", title="Samsung Galaxy S24 Ultra 5G 512GB 12GB RAM", category="Eletrônicos", price=6499.00),
            Product(external_id="PROD_301", platform="api_vendas", title="Tênis de Corrida Masculino Nike Revolution 7", category="Moda e acessórios", price=299.90),
            Product(external_id="PROD_401", platform="api_vendas", title="Fritadeira Elétrica Airfryer Philips Walita 4.1L", category="Casa e decoração", price=429.00),
            Product(external_id="PROD_501", platform="api_vendas", title="Aspirador de Pó Robô Xiaomi Robot Vacuum E10", category="Casa e decoração", price=1099.00),
        ]
        session.add_all(products)
        session.flush()

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for product in products:
            for day_idx in range(90):
                date = today - timedelta(days=90 - 1 - day_idx)
                qty = np.random.randint(15, 60)
                sale = SalesHistory(
                    product_id=product.id,
                    date=date,
                    quantity_sold=qty,
                    price_at_date=product.price,
                    available_quantity=100,
                    platform=product.platform
                )
                session.add(sale)
        session.commit()
        logger.info("Catálogo base de contingência criado com sucesso.")


def show_status(manager: DatabaseManager):
    """Mostra o status das tabelas."""
    inspector = inspect(manager.engine)
    tables = inspector.get_table_names()
    
    if not tables:
        logger.info("Nenhuma tabela encontrada.")
        return
    
    logger.info(f"\nTabelas encontradas ({len(tables)}):")
    with manager.session() as session:
        for table in tables:
            try:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                logger.info(f"  📊 {table}: {count:,} registros")
            except Exception as e:
                logger.warning(f"  ⚠️ {table}: erro ao contar ({e})")


def main():
    """Ponto de entrada do script."""
    command = sys.argv[1] if len(sys.argv) > 1 else "reset"
    manager = get_db_manager()
    
    if command == "create":
        create_tables(manager)
    elif command == "drop":
        drop_tables(manager)
    elif command == "seed":
        seed_data(manager)
        show_status(manager)
    elif command == "status":
        show_status(manager)
    elif command == "reset":
        drop_tables(manager)
        create_tables(manager)
        seed_data(manager)
        show_status(manager)
    else:
        print(f"Comando desconhecido: {command}")


if __name__ == "__main__":
    main()
