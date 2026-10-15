"""Script de setup e migração do banco de dados.

Uso:
    python -m src.database.setup [comando]

Comandos:
    create    - Cria todas as tabelas no banco de dados
    drop      - Remove todas as tabelas (CUIDADO!)
    seed      - Popula com dados de exemplo
    sync      - Sincronizar histórico até a data de hoje (preencher dias faltantes)
    status    - Mostra status das tabelas
    reset     - Drop + Create + Seed

Para desenvolvimento local, utiliza SQLite.
Para produção, configure DATABASE_URL no .env apontando para PostgreSQL.
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
from src.database.models import (
    Base, Product, SalesHistory, SearchTrend, CollectionLog,
    MacroIndicator, MarketplaceFeedback, ProductOpportunity
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_manager() -> DatabaseManager:
    """Obtém o gerenciador de banco de dados.
    
    Em desenvolvimento, usa SQLite se DATABASE_URL não estiver configurado
    ou se estiver com o placeholder padrão.
    """
    db_url = os.getenv("DATABASE_URL", "")
    
    # Se não tem PostgreSQL configurado, usar SQLite para desenvolvimento
    if not db_url or "user:password" in db_url:
        db_path = Path(__file__).parent.parent.parent / "data" / "trendcommerce_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"
        logger.info(f"Usando SQLite para desenvolvimento: {db_path}")
    else:
        logger.info(f"Usando banco de dados: {db_url.split('@')[-1] if '@' in db_url else 'configurado'}")
    
    return DatabaseManager(database_url=db_url)


def create_tables(manager: DatabaseManager):
    """Cria todas as tabelas."""
    logger.info("Criando tabelas...")
    Base.metadata.create_all(manager.engine)
    
    inspector = inspect(manager.engine)
    tables = inspector.get_table_names()
    logger.info(f"Tabelas criadas: {', '.join(tables)}")
    return tables


def drop_tables(manager: DatabaseManager):
    """Remove todas as tabelas."""
    logger.warning("Removendo todas as tabelas...")
    Base.metadata.drop_all(manager.engine)
    logger.info("Tabelas removidas.")


def seed_data(manager: DatabaseManager):
    """Popula com dados de exemplo para desenvolvimento."""
    import numpy as np
    np.random.seed(42)
    
    logger.info("Populando banco com dados de exemplo...")
    
    with manager.session() as session:
        # Criar catálogo expandido de produtos reais de mercado
        products = [
            # Notebooks & Informática
            Product(external_id="MLB101", platform="mercadolivre", title="Notebook Dell Inspiron 15 Intel Core i7 16GB 512GB SSD", category="Informática", price=3499.99, currency="BRL", condition="new"),
            Product(external_id="MLB102", platform="mercadolivre", title="MacBook Air M2 13.6 Polegadas 8GB RAM 256GB SSD", category="Informática", price=6899.00, currency="BRL", condition="new"),
            Product(external_id="MLB103", platform="mercadolivre", title="Notebook Gamer Acer Nitro 5 Intel Core i5 RTX 3050 16GB", category="Informática", price=4299.00, currency="BRL", condition="new"),
            Product(external_id="MLB104", platform="mercadolivre", title="Notebook Lenovo IdeaPad 1 AMD Ryzen 5 8GB 256GB SSD", category="Informática", price=2399.00, currency="BRL", condition="new"),
            Product(external_id="MLB105", platform="mercadolivre", title="Monitor Gamer LG UltraGear 27 IPS 144Hz 1ms Full HD", category="Informática", price=999.00, currency="BRL", condition="new"),
            
            # Celulares & Smartphones
            Product(external_id="MLB201", platform="mercadolivre", title="iPhone 15 Pro 256GB Titânio Natural", category="Celulares", price=7999.00, currency="BRL", condition="new"),
            Product(external_id="MLB202", platform="mercadolivre", title="iPhone 13 Apple 128GB Estelar", category="Celulares", price=3599.00, currency="BRL", condition="new"),
            Product(external_id="MLB203", platform="mercadolivre", title="Samsung Galaxy S24 Ultra 5G 512GB 12GB RAM", category="Celulares", price=6499.00, currency="BRL", condition="new"),
            Product(external_id="MLB204", platform="mercadolivre", title="Xiaomi Redmi Note 13 Pro 5G 256GB 8GB RAM", category="Celulares", price=1699.00, currency="BRL", condition="new"),
            Product(external_id="MLB205", platform="mercadolivre", title="Motorola Moto G84 5G 256GB 8GB RAM", category="Celulares", price=1299.00, currency="BRL", condition="new"),
            
            # Consoles & Games
            Product(external_id="MLB301", platform="mercadolivre", title="Console PlayStation 5 Edição Digital 1TB", category="Games", price=3699.00, currency="BRL", condition="new"),
            Product(external_id="MLB302", platform="mercadolivre", title="Console Xbox Series S 512GB SSD Branco", category="Games", price=2499.00, currency="BRL", condition="new"),
            Product(external_id="MLB303", platform="mercadolivre", title="Console Nintendo Switch OLED 64GB com Joy-Con", category="Games", price=2099.00, currency="BRL", condition="new"),
            Product(external_id="MLB304", platform="mercadolivre", title="Controle Sem Fio DualSense PS5 Midnight Black", category="Games", price=399.00, currency="BRL", condition="new"),
            Product(external_id="MLB305", platform="mercadolivre", title="Headset Gamer HyperX Cloud II Som Surround 7.1", category="Games", price=459.00, currency="BRL", condition="new"),

            # Áudio & Som
            Product(external_id="MLB401", platform="mercadolivre", title="Fone de Ouvido Apple AirPods Pro 2ª Geração MagSafe", category="Áudio", price=1899.00, currency="BRL", condition="new"),
            Product(external_id="MLB402", platform="mercadolivre", title="Fone Bluetooth JBL Tune 520BT com Microfone", category="Áudio", price=219.00, currency="BRL", condition="new"),
            Product(external_id="MLB403", platform="mercadolivre", title="Caixa de Som Bluetooth JBL Boombox 3 180W RMS", category="Áudio", price=2399.00, currency="BRL", condition="new"),
            Product(external_id="MLB404", platform="mercadolivre", title="Fone de Ouvido Sony WH-1000XM5 Noise Cancelling", category="Áudio", price=2199.00, currency="BRL", condition="new"),

            # Smart TVs & Home Theater
            Product(external_id="MLB501", platform="mercadolivre", title="Smart TV Samsung 55 4K Crystal UHD HDR10+", category="Eletrônicos", price=2599.00, currency="BRL", condition="new"),
            Product(external_id="MLB502", platform="mercadolivre", title="Smart TV LG 50 4K UHD ThinQ AI HDR", category="Eletrônicos", price=2199.00, currency="BRL", condition="new"),
            Product(external_id="MLB503", platform="mercadolivre", title="Smart TV TCL 65 4K QLED Google TV", category="Eletrônicos", price=3299.00, currency="BRL", condition="new"),

            # Casa Inteligente & Eletroportáteis
            Product(external_id="ASIN001", platform="amazon", title="Echo Dot 5ª Geração Smart Speaker com Alexa", category="Casa Inteligente", price=349.99, currency="BRL", condition="new"),
            Product(external_id="ASIN002", platform="amazon", title="Kindle Paperwhite 16GB Tela de 6.8 Polegadas", category="Eletrônicos", price=599.00, currency="BRL", condition="new"),
            Product(external_id="ASIN003", platform="amazon", title="Fritadeira Elétrica Airfryer Philips Walita 4.1L", category="Eletroportáteis", price=429.00, currency="BRL", condition="new"),
            Product(external_id="ASIN004", platform="amazon", title="Aspirador de Pó Robô Xiaomi Robot Vacuum E10", category="Eletroportáteis", price=1099.00, currency="BRL", condition="new"),

            # Moda & Vestuário
            Product(external_id="MLB601", platform="mercadolivre", title="Tênis de Corrida Masculino Nike Revolution 7", category="Moda & Vestuário", price=299.90, currency="BRL", condition="new"),
            Product(external_id="MLB602", platform="mercadolivre", title="Vestido Midi Feminino Canelado Elegante", category="Moda & Vestuário", price=89.90, currency="BRL", condition="new"),
            Product(external_id="MLB603", platform="mercadolivre", title="Jaqueta Corta Vento Impermeável Unissex", category="Moda & Vestuário", price=129.90, currency="BRL", condition="new"),
            Product(external_id="MLB604", platform="mercadolivre", title="Camisa Social Masculina Slim Fit Algodão", category="Moda & Vestuário", price=119.00, currency="BRL", condition="new"),

            # Beleza & Cuidados Pessoais
            Product(external_id="MLB701", platform="mercadolivre", title="Protetor Solar Facial Anthelios Airlicium FPS 60", category="Beleza & Cosméticos", price=84.90, currency="BRL", condition="new"),
            Product(external_id="MLB702", platform="mercadolivre", title="Perfume Importado Masculino 1 Million Paco Rabanne 100ml", category="Beleza & Cosméticos", price=489.00, currency="BRL", condition="new"),
            Product(external_id="MLB703", platform="mercadolivre", title="Sérum Facial Vitamina C 10 Anti-Idade La Roche-Posay", category="Beleza & Cosméticos", price=179.90, currency="BRL", condition="new"),
            Product(external_id="MLB704", platform="mercadolivre", title="Secador de Cabelo Taiff Vulcan 2500W Profissional", category="Beleza & Cosméticos", price=459.00, currency="BRL", condition="new"),

            # Esportes & Suplementos
            Product(external_id="MLB801", platform="mercadolivre", title="Whey Protein 100% Pure Integralmédica 900g Baunilha", category="Esportes & Fitness", price=109.90, currency="BRL", condition="new"),
            Product(external_id="MLB802", platform="mercadolivre", title="Creatina Monohidratada 100% Pura Max Titanium 300g", category="Esportes & Fitness", price=89.90, currency="BRL", condition="new"),
            Product(external_id="MLB803", platform="mercadolivre", title="Kit 5 Elásticos Extensores Faixas Borracha Musculação", category="Esportes & Fitness", price=49.90, currency="BRL", condition="new"),
            Product(external_id="MLB804", platform="mercadolivre", title="Tapete Yoga Mat 10mm Antiderrapante com Alça", category="Esportes & Fitness", price=79.90, currency="BRL", condition="new"),

            # Móveis & Decoração
            Product(external_id="MLB901", platform="mercadolivre", title="Cadeira de Escritório Ergonômica Presidente com Apoio", category="Móveis & Casa", price=649.00, currency="BRL", condition="new"),
            Product(external_id="MLB902", platform="mercadolivre", title="Mesa Home Office Escrivaninha Computador 120cm", category="Móveis & Casa", price=289.00, currency="BRL", condition="new"),
            Product(external_id="MLB903", platform="mercadolivre", title="Luminária de Mesa Articulada com Garra LED", category="Móveis & Casa", price=59.90, currency="BRL", condition="new"),

            # Ferramentas & Construção
            Product(external_id="MLB1001", platform="mercadolivre", title="Parafusadeira e Furadeira de Impacto Bateria 12V Bosch", category="Ferramentas", price=329.00, currency="BRL", condition="new"),
            Product(external_id="MLB1002", platform="mercadolivre", title="Maleta de Ferramentas Completa 110 Peças Aço Cromo", category="Ferramentas", price=199.90, currency="BRL", condition="new"),

            # Alimentos & Bebidas
            Product(external_id="MLB1101", platform="mercadolivre", title="Kit 50 Cápsulas de Café Espresso Compatíveis Nespresso", category="Alimentos & Bebidas", price=98.00, currency="BRL", condition="new"),
            Product(external_id="MLB1102", platform="mercadolivre", title="Azeite de Oliva Chileno Deleyda Extra Virgem 500ml", category="Alimentos & Bebidas", price=54.90, currency="BRL", condition="new"),

            # Automotivo
            Product(external_id="MLB1201", platform="mercadolivre", title="Suporte de Celular Veicular Magnético MagSafe para Painel", category="Automotivo", price=45.90, currency="BRL", condition="new"),
            Product(external_id="MLB1202", platform="mercadolivre", title="Compressor de Ar Portátil Digital Recarregável Pneus 12V", category="Automotivo", price=139.90, currency="BRL", condition="new"),

            # Livros
            Product(external_id="ASIN101", platform="amazon", title="Livro A Psicologia Financeira - Morgan Housel", category="Livros", price=42.90, currency="BRL", condition="new"),
            Product(external_id="ASIN102", platform="amazon", title="Livro Hábitos Atômicos - James Clear", category="Livros", price=49.90, currency="BRL", condition="new"),
        ]
        
        for product in products:
            session.add(product)
        session.flush()  # Para obter os IDs
        
        logger.info(f"Criados {len(products)} produtos reais de mercado")
        
        # Criar histórico de vendas realista (90 dias até hoje)
        # Modelando: Volume base por faixa de preço, elasticidade de preço e sazonalidade semanal
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sales_count = 0
        
        for product in products:
            # Produtos mais baratos têm volume diário base maior; produtos caros têm volume menor
            if product.price < 500:
                base_sales = np.random.randint(35, 75)
            elif product.price < 2500:
                base_sales = np.random.randint(18, 40)
            elif product.price < 5000:
                base_sales = np.random.randint(8, 22)
            else:
                base_sales = np.random.randint(3, 12)
                
            base_price = product.price
            np.random.seed(product.id * 31 + 42)
            
            for day in range(90):
                date = today - timedelta(days=90 - 1 - day)
                day_of_week = date.weekday()
                
                # Efeito Sazonal: Fins de semana (Sex, Sáb, Dom) vendem mais
                weekend_multiplier = 1.30 if day_of_week in [4, 5, 6] else 0.92
                
                # Flutuação de preço (promoções pontuais ou aumentos)
                price_ratio = np.random.uniform(0.92, 1.08)
                current_price = round(base_price * price_ratio, 2)
                
                # Elasticidade de preço: Preço menor gera mais vendas; preço maior reduz vendas
                price_elasticity = (1.0 - (price_ratio - 1.0) * 1.5)
                
                noise = np.random.uniform(0.75, 1.25)
                quantity = max(1, int(round(base_sales * weekend_multiplier * price_elasticity * noise)))
                
                sale = SalesHistory(
                    product_id=product.id,
                    date=date,
                    quantity_sold=quantity,
                    price_at_date=current_price,
                    available_quantity=int(np.random.randint(25, 250)),
                    platform=product.platform,
                )
                session.add(sale)
                sales_count += 1
        
        logger.info(f"Criados {sales_count} registros de histórico de vendas (até {today.strftime('%d/%m/%Y')})")
        
        # Criar tendências de pesquisa (30 dias até hoje)
        keywords = ["notebook", "smartphone", "smart tv", "echo dot", "kindle"]
        trends_count = 0
        
        for keyword in keywords:
            for day in range(30):
                date = today - timedelta(days=30 - 1 - day)
                interest = np.random.randint(10, 100)
                
                trend = SearchTrend(
                    keyword=keyword,
                    date=date,
                    interest_score=interest,
                    source="mock",
                    is_mock=True,
                )
                session.add(trend)
                trends_count += 1
        
        logger.info(f"Criados {trends_count} registros de tendências")
        
        # Criar indicadores macroeconômicos (Dólar, Selic, Feriados)
        macro_count = 0
        try:
            from src.collectors.macro_collector import MacroCollector
            macro_col = MacroCollector()
            holidays = macro_col.fetch_holidays_brasilapi(today.year)

            for h in holidays:
                try:
                    h_dt = datetime.strptime(h["date"], "%Y-%m-%d")
                    m_ind = MacroIndicator(
                        date=h_dt,
                        indicator_type="holiday",
                        value=1.0,
                        label=f"Feriado: {h['name']}",
                        source=h.get("source", "brasilapi")
                    )
                    session.add(m_ind)
                    macro_count += 1
                except Exception:
                    continue

            # Inserir série diária de Dólar PTAX e Selic
            dolar_series = macro_col.fetch_bcb_series(10813, last_n=90)
            for d in dolar_series:
                try:
                    d_dt = datetime.strptime(d["date"], "%Y-%m-%d")
                    m_ind = MacroIndicator(
                        date=d_dt,
                        indicator_type="dolar_ptax",
                        value=d["value"],
                        label="Dólar Comercial PTAX Venda",
                        source=d.get("source", "bcb_sgs")
                    )
                    session.add(m_ind)
                    macro_count += 1
                except Exception:
                    continue

            # Inserir Selic
            m_selic = MacroIndicator(
                date=today,
                indicator_type="selic",
                value=10.50,
                label="Taxa Selic Meta (% a.a.)",
                source="bcb_sgs"
            )
            session.add(m_selic)
            macro_count += 1

            logger.info(f"Criados {macro_count} registros de indicadores macroeconômicos e feriados")
        except ImportError:
            logger.info("MacroCollector será integrado na Parte 2 (Coletores).")

        # Criar métricas de feedback de marketplace para cada produto
        feedback_count = 0
        try:
            from src.collectors.marketplace_public_collector import MarketplacePublicCollector
            mkt_col = MarketplacePublicCollector()

            for p in products:
                q_info = mkt_col.fetch_questions(p.external_id)
                r_info = mkt_col.fetch_reviews(p.external_id)
                fb = MarketplaceFeedback(
                    product_id=p.id,
                    date=today,
                    platform=p.platform,
                    questions_count=q_info["total_questions"],
                    unanswered_questions=q_info["unanswered"],
                    average_rating=r_info["rating_average"],
                    reviews_count=r_info["total_reviews"],
                    trend_term=p.category
                )
                session.add(fb)
                feedback_count += 1

            logger.info(f"Criados {feedback_count} registros de feedback público de marketplace")
        except ImportError:
            logger.info("MarketplacePublicCollector será integrado na Parte 2 (Coletores).")

        # Log da coleta
        log = CollectionLog(
            collector_name="seed_script",
            endpoint="seed_data",
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            records_collected=len(products) + sales_count + trends_count + macro_count + feedback_count,
            success=True,
        )
        session.add(log)
    
    logger.info("Dados de exemplo e novos indicadores inseridos com sucesso!")


def sync_up_to_today(manager: DatabaseManager) -> int:
    """Preenche os dias faltantes entre a última data no banco e a data de hoje.
    
    Garante que dias como 25/08, 26/08 e a data atual estejam sempre presentes
    no histórico de vendas de todos os produtos cadastrados.
    
    Returns:
        Quantidade de novos registros de vendas adicionados
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
            # Buscar a venda mais recente para o produto
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
            logger.info(f"Sincronizados {added_records} novos registros de vendas até a data de hoje ({today.strftime('%d/%m/%Y')}).")
            
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
    """Ponto de entrada do script de setup."""
    commands = {
        "create": "Criar tabelas",
        "drop": "Remover tabelas",
        "seed": "Popular com dados de exemplo",
        "sync": "Sincronizar histórico até a data de hoje (preencher dias faltantes)",
        "status": "Mostrar status",
        "reset": "Reset completo (drop + create + seed)",
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("\n📦 TrendCommerce AI - Setup do Banco de Dados")
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
