"""Script de setup e inicialização do banco de dados limpo e leve.

Uso:
    python -m src.database.setup [comando]

Comandos:
    create    - Cria todas as tabelas essenciais no banco de dados
    drop      - Remove todas as tabelas
    seed      - Popula com catálogo de produtos e histórico de vendas
    sync      - Sincroniza histórico até a data de hoje (preencher dias faltantes)
    status    - Mostra status das tabelas
    reset     - Drop + Create + Seed (recria banco zerado e leve)

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
    """Popula o banco com catálogo de produtos, histórico diário de vendas e usuário padrão."""
    import numpy as np
    np.random.seed(42)
    
    logger.info("Populando banco com catálogo e histórico de vendas...")
    
    with manager.session() as session:
        # 1. Usuário Administrador de Teste
        existing_user = session.query(User).filter_by(email="admin@trendecommerce.com").first()
        if not existing_user:
            admin_user = User(
                email="admin@trendecommerce.com",
                name="Administrador",
                hashed_password=bcrypt.hashpw(b"123456", bcrypt.gensalt(10)).decode("utf-8"),
                is_active=True
            )
            session.add(admin_user)
            logger.info("Usuário de teste criado: admin@trendecommerce.com (senha: 123456)")

        # 2. Catálogo Realista de Produtos Próprios
        products = [
            # Notebooks & Informática
            Product(external_id="PROD_101", platform="proprio", title="Notebook Dell Inspiron 15 Intel Core i7 16GB 512GB SSD", category="Informática", price=3499.99),
            Product(external_id="PROD_102", platform="proprio", title="MacBook Air M2 13.6 Polegadas 8GB RAM 256GB SSD", category="Informática", price=6899.00),
            Product(external_id="PROD_103", platform="proprio", title="Notebook Gamer Acer Nitro 5 Intel Core i5 RTX 3050 16GB", category="Informática", price=4299.00),
            Product(external_id="PROD_104", platform="proprio", title="Notebook Lenovo IdeaPad 1 AMD Ryzen 5 8GB 256GB SSD", category="Informática", price=2399.00),
            Product(external_id="PROD_105", platform="proprio", title="Monitor Gamer LG UltraGear 27 IPS 144Hz 1ms Full HD", category="Informática", price=999.00),
            
            # Celulares & Smartphones
            Product(external_id="PROD_201", platform="proprio", title="iPhone 15 Pro 256GB Titânio Natural", category="Celulares", price=7999.00),
            Product(external_id="PROD_202", platform="proprio", title="iPhone 13 Apple 128GB Estelar", category="Celulares", price=3599.00),
            Product(external_id="PROD_203", platform="proprio", title="Samsung Galaxy S24 Ultra 5G 512GB 12GB RAM", category="Celulares", price=6499.00),
            Product(external_id="PROD_204", platform="proprio", title="Xiaomi Redmi Note 13 Pro 5G 256GB 8GB RAM", category="Celulares", price=1699.00),
            Product(external_id="PROD_205", platform="proprio", title="Motorola Moto G84 5G 256GB 8GB RAM", category="Celulares", price=1299.00),
            
            # Consoles & Games
            Product(external_id="PROD_301", platform="proprio", title="Console PlayStation 5 Edição Digital 1TB", category="Games", price=3699.00),
            Product(external_id="PROD_302", platform="proprio", title="Console Xbox Series S 512GB SSD Branco", category="Games", price=2499.00),
            Product(external_id="PROD_303", platform="proprio", title="Console Nintendo Switch OLED 64GB com Joy-Con", category="Games", price=2099.00),
            Product(external_id="PROD_304", platform="proprio", title="Controle Sem Fio DualSense PS5 Midnight Black", category="Games", price=399.00),
            Product(external_id="PROD_305", platform="proprio", title="Headset Gamer HyperX Cloud II Som Surround 7.1", category="Games", price=459.00),

            # Áudio & Som
            Product(external_id="PROD_401", platform="proprio", title="Fone de Ouvido Apple AirPods Pro 2ª Geração MagSafe", category="Áudio", price=1899.00),
            Product(external_id="PROD_402", platform="proprio", title="Fone Bluetooth JBL Tune 520BT com Microfone", category="Áudio", price=219.00),
            Product(external_id="PROD_403", platform="proprio", title="Caixa de Som Bluetooth JBL Boombox 3 180W RMS", category="Áudio", price=2399.00),
            Product(external_id="PROD_404", platform="proprio", title="Fone de Ouvido Sony WH-1000XM5 Noise Cancelling", category="Áudio", price=2199.00),

            # Smart TVs & Eletrônicos
            Product(external_id="PROD_501", platform="proprio", title="Smart TV Samsung 55 4K Crystal UHD HDR10+", category="Eletrônicos", price=2599.00),
            Product(external_id="PROD_502", platform="proprio", title="Smart TV LG 50 4K UHD ThinQ AI HDR", category="Eletrônicos", price=2199.00),
            Product(external_id="PROD_503", platform="proprio", title="Smart TV TCL 65 4K QLED Google TV", category="Eletrônicos", price=3299.00),

            # Eletroportáteis & Casa
            Product(external_id="PROD_601", platform="proprio", title="Fritadeira Elétrica Airfryer Philips Walita 4.1L", category="Eletroportáteis", price=429.00),
            Product(external_id="PROD_602", platform="proprio", title="Aspirador de Pó Robô Xiaomi Robot Vacuum E10", category="Eletroportáteis", price=1099.00),
            Product(external_id="PROD_603", platform="proprio", title="Cafeteira Nespresso Essenza Mini 110V", category="Eletroportáteis", price=389.00),

            # Moda & Vestuário
            Product(external_id="PROD_701", platform="proprio", title="Tênis de Corrida Masculino Nike Revolution 7", category="Moda & Vestuário", price=299.90),
            Product(external_id="PROD_702", platform="proprio", title="Vestido Midi Feminino Canelado Elegante", category="Moda & Vestuário", price=89.90),
            Product(external_id="PROD_703", platform="proprio", title="Jaqueta Corta Vento Impermeável Unissex", category="Moda & Vestuário", price=129.90),
            Product(external_id="PROD_704", platform="proprio", title="Camisa Social Masculina Slim Fit Algodão", category="Moda & Vestuário", price=119.00),
        ]
        
        session.add_all(products)
        session.flush()
        logger.info(f"Cadastrados {len(products)} produtos no catálogo.")

        # 3. Gerar 90 dias de histórico diário de vendas e preços para cada produto
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        days_history = 90
        sales_count = 0

        for product in products:
            base_sales = np.random.randint(10, 45)
            trend_slope = np.random.uniform(-0.05, 0.15)
            
            for day_idx in range(days_history):
                date = today - timedelta(days=days_history - 1 - day_idx)
                day_of_week = date.weekday()
                
                # Fator fim de semana (sexta, sábado e domingo vendem mais)
                weekend_factor = 1.35 if day_of_week in [4, 5, 6] else 0.90
                
                # Tendência temporal
                trend_factor = 1.0 + (trend_slope * (day_idx / days_history))
                
                # Variação aleatória
                noise = np.random.normal(1.0, 0.15)
                
                daily_sales = max(1, int(round(base_sales * weekend_factor * trend_factor * noise)))
                
                # Pequena flutuação de preço (promoções periódicas)
                promo_factor = 0.90 if day_idx % 14 == 0 else 1.0
                current_price = round(product.price * promo_factor, 2)

                sale = SalesHistory(
                    product_id=product.id,
                    date=date,
                    quantity_sold=daily_sales,
                    price_at_date=current_price,
                    available_quantity=int(np.random.randint(30, 200)),
                    platform=product.platform,
                )
                session.add(sale)
                sales_count += 1
        
        logger.info(f"Criados {sales_count} registros de histórico de vendas ({days_history} dias até hoje).")

    logger.info("Banco inicializado e populado com sucesso!")


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
                logger.info(f"  📊 {table}: {count} registros")
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
