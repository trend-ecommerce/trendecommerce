"""Script de setup e manutenção do banco de dados (TrendCommerce).

Uso:
    python -m src.database.setup [comando]

Comandos:
    create    - Cria todas as tabelas no banco de dados (users, products, sales_history)
    drop      - Remove todas as tabelas (CUIDADO!)
    status    - Mostra status das tabelas e contagem de registros
    sync      - Sincroniza histórico de vendas até a data de hoje
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_manager() -> DatabaseManager:
    """Obtém o gerenciador de banco de dados.
    
    Em desenvolvimento, usa SQLite se DATABASE_URL não estiver configurado
    ou se estiver com o placeholder padrão.
    """
    db_url = os.getenv("DATABASE_URL", "")
    
    if not db_url or "user:password" in db_url:
        db_path = Path(__file__).parent.parent.parent / "data" / "trendcommerce_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"
        logger.info(f"Usando SQLite para desenvolvimento: {db_path}")
    else:
        logger.info(f"Usando banco de dados configurado.")
    
    return DatabaseManager(database_url=db_url)


def create_tables(manager: DatabaseManager):
    """Cria todas as tabelas definidas nos models."""
    logger.info("Criando tabelas...")
    Base.metadata.create_all(manager.engine)
    logger.info("Tabelas criadas com sucesso!")


def drop_tables(manager: DatabaseManager):
    """Remove todas as tabelas."""
    logger.warning("Removendo todas as tabelas...")
    Base.metadata.drop_all(manager.engine)
    logger.info("Tabelas removidas.")


def sync_up_to_today(manager: DatabaseManager) -> int:
    """Preenche os dias faltantes entre a última data no banco e a data de hoje.
    
    Garante que o histórico de vendas esteja atualizado até a data de hoje.
    """
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
    """Mostra o status das tabelas."""
    inspector = inspect(manager.engine)
    tables = inspector.get_table_names()
    
    if not tables:
        logger.info("Nenhuma tabela encontrada. Execute 'create' primeiro.")
        return
    
    logger.info(f"\nTabelas encontradas: {len(tables)}")
    with manager.session() as session:
        for table in tables:
            try:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                logger.info(f"  📊 {table}: {count} registros")
            except Exception as e:
                logger.warning(f"  ⚠️ {table}: erro ao contar ({e})")


def main():
    commands = {
        "create": "Criar tabelas",
        "drop": "Remover tabelas",
        "sync": "Sincronizar histórico até a data de hoje",
        "status": "Mostrar status",
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("\n📦 TrendCommerce - Setup do Banco de Dados")
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
    elif command == "sync":
        sync_up_to_today(manager)
        show_status(manager)
    elif command == "status":
        show_status(manager)


if __name__ == "__main__":
    main()
