import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_db_connection
from db.migrator import DatabaseMigrator
from pipeline.execution_tracker import PipelineTracker
from pipeline.repository import DataRepository

CATEGORIES = [
    ("MLB1648", "Notebooks & Informatica", ["Dell", "Lenovo", "Apple", "Asus", "Acer", "HP", "Samsung"]),
    ("MLB1051", "Cellphones & Smartphones", ["Samsung", "Apple", "Xiaomi", "Motorola", "Realme", "POCO"]),
    ("MLB431326", "Consoles & Games", ["Sony", "Microsoft", "Nintendo", "Logitech", "Razer"]),
    ("MLB1002", "Smart TVs & Audio", ["LG", "Samsung", "TCL", "Philips", "JBL", "Sony"]),
    ("MLB14407", "Monitores & Acessorios", ["AOC", "LG", "Dell", "Samsung", "BenQ", "Gigabyte"]),
    ("MLB35267", "Smartwatches & Wearables", ["Apple", "Samsung", "Amazfit", "Garmin", "Huawei"]),
    ("MLB1039", "Eletrodomesticos", ["Brastemp", "Consul", "Electrolux", "Arno", "Mondial"]),
    ("MLB1144", "Hardware & PC Gamer", ["NVIDIA", "AMD", "Corsair", "Kingston", "Asus", "MSI"])
]

NOUNS = [
    "Pro", "Ultra", "Gamer", "Max", "Air", "Hero", "Edition", "Prime", "Turbo", "V2", "Evo", "Slim"
]


def generate_1000_products():
    print("=================================================================")
    print(" [INICIO] POVOAMENTO MASSIVO DE 1000 PRODUTOS NO BANCO DE DADOS ")
    print("=================================================================\n")

    # 1. Run DB Migrations
    migrator = DatabaseMigrator()
    migrator.run_migrations()

    # 2. Pipeline Execution Tracker
    with PipelineTracker("MercadoLivre_1000_Ingestion", "MercadoLivre", "/sites/MLB/search") as tracker:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                count = 0
                for idx in range(1, 1001):
                    cat_id, cat_name, brands = CATEGORIES[idx % len(CATEGORIES)]
                    brand = random.choice(brands)
                    noun = random.choice(NOUNS)
                    product_id = f"MLB1000{idx:04d}"
                    title = f"{brand} {cat_name.split('&')[0].strip()} {noun} {idx}"
                    price = round(random.uniform(150.0, 9500.0), 2)
                    orig_price = round(price * random.uniform(1.05, 1.25), 2) if idx % 3 == 0 else None
                    stock = random.randint(1, 85)

                    # Upsert Product Dimension
                    product_dim = {
                        "product_id": product_id,
                        "site_id": "MLB",
                        "title": title,
                        "category_id": cat_id,
                        "brand": brand,
                        "seller_id": f"SELLER_{random.randint(100, 999)}",
                        "permalink": f"https://produto.mercadolivre.com.br/{product_id}",
                        "currency_id": "BRL"
                    }
                    DataRepository.upsert_product(product_dim)

                    # Insert Temporal Price History
                    collected_time = datetime.utcnow() - timedelta(minutes=random.randint(0, 1440))
                    price_entry = {
                        "product_id": product_id,
                        "price": price,
                        "original_price": orig_price,
                        "currency_id": "BRL",
                        "available_quantity": stock,
                        "collected_at": collected_time
                    }
                    DataRepository.insert_price_history(price_entry)

                    tracker.increment_fetched(1)
                    tracker.increment_inserted(1)
                    count += 1

                    if count % 200 == 0:
                        print(f"   [PROGRESSO] {count}/1000 produtos inseridos no banco...")

        finally:
            conn.close()

    print("\n=================================================================")
    print(" [SUCESSO] 1000 PRODUTOS INSERIDOS COM SUCESSO NO BANCO DE DADOS!")
    print("=================================================================")


if __name__ == "__main__":
    generate_1000_products()
