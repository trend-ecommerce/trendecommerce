import sys
import os
import random
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_db_connection
from db.migrator import DatabaseMigrator
from pipeline.execution_tracker import PipelineTracker

NICHES = [
    ("MLB1648", "Notebooks & Computadores", ["Dell", "Lenovo", "Apple", "Asus", "Acer", "HP", "Samsung", "MSI"]),
    ("MLB1051", "Smartphones & Celulares", ["Samsung", "Apple", "Xiaomi", "Motorola", "Realme", "POCO", "Infinix"]),
    ("MLB431326", "Consoles & Games", ["Sony", "Microsoft", "Nintendo", "Logitech", "Razer", "Redragon"]),
    ("MLB1002", "Smart TVs & Home Theater", ["LG", "Samsung", "TCL", "Philips", "JBL", "Sony", "Hisense"]),
    ("MLB14407", "Monitores & Perifericos", ["AOC", "LG", "Dell", "Samsung", "BenQ", "Gigabyte", "Asus"]),
    ("MLB35267", "Smartwatches & Fitbands", ["Apple", "Samsung", "Amazfit", "Garmin", "Huawei", "Haylou"]),
    ("MLB1039", "Eletrodomesticos & Cozinha", ["Brastemp", "Consul", "Electrolux", "Arno", "Mondial", "Oster"]),
    ("MLB1144", "Hardware & Placas de Video", ["NVIDIA", "AMD", "Corsair", "Kingston", "Asus", "MSI", "EVGA"]),
    ("MLB1037", "Cameras & Foto", ["Canon", "Nikon", "Sony", "GoPro", "DJI", "Insta360"]),
    ("MLB1276", "Calcados & Moda Esportiva", ["Nike", "Adidas", "Puma", "Under Armour", "Asics", "Mizuno", "Olympikus"])
]

MODELS_SUFFIX = [
    "Pro Max", "Ultra 5G", "Gamer RGB", "Air M3", "Hero 4K", "Edition 2026", "Prime Series",
    "Turbo Nitro", "V3 Pro", "Evo Slim", "Master", "Elite", "Legend", "Strix", "Odyssey"
]


def populate_10000():
    print("=================================================================")
    print(" [INICIO] POVOAMENTO MASSIVO DE 10.000 PRODUTOS (10 NICHOS) ")
    print("=================================================================\n")

    t0 = time.time()

    migrator = DatabaseMigrator()
    migrator.run_migrations()

    with PipelineTracker("Ingestion_Massive_10k", "MultiNiche_APIs", "/sites/MLB/search") as tracker:
        conn = get_db_connection()
        try:
            categories_batch = []
            products_batch = []
            prices_batch = []
            features_batch = []

            categories_seen = set()

            for idx in range(1, 10001):
                cat_id, cat_name, brands = NICHES[idx % len(NICHES)]

                if cat_id not in categories_seen:
                    categories_seen.add(cat_id)
                    categories_batch.append((cat_id, "MLB", cat_name))

                brand = random.choice(brands)
                suffix = random.choice(MODELS_SUFFIX)
                product_id = f"MLB2000{idx:05d}"
                title = f"{brand} {cat_name.split('&')[0].strip()} {suffix} #{idx}"
                price = round(random.uniform(89.90, 12500.00), 2)
                orig_price = round(price * random.uniform(1.08, 1.30), 2) if idx % 4 == 0 else None
                stock = random.randint(1, 150)
                seller_id = f"SELLER_{random.randint(100, 999)}"
                permalink = f"https://produto.mercadolivre.com.br/{product_id}"

                products_batch.append((
                    product_id, "MLB", title, cat_id, brand, seller_id, permalink, "BRL"
                ))

                collected_time = datetime.utcnow() - timedelta(minutes=random.randint(0, 43200))
                prices_batch.append((
                    product_id, price, orig_price, "BRL", stock, collected_time
                ))

                r7d = round(price * random.uniform(0.95, 1.05), 2)
                r30d = round(price * random.uniform(0.90, 1.10), 2)
                pct_7d = round(((price - r7d) / r7d) * 100.0, 2)
                today_str = datetime.utcnow().strftime("%Y-%m-%d")

                features_batch.append((
                    product_id, today_str, price, r7d, r30d, pct_7d
                ))

                tracker.increment_fetched(1)
                tracker.increment_inserted(1)

            with conn.cursor() as cur:
                for cat in categories_batch:
                    cur.execute("""
                        INSERT INTO dim_categories (category_id, site_id, name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (category_id) DO NOTHING;
                    """, cat)

                print("   [BANCO] Inserindo 10.000 produtos em dim_products...")
                for p in products_batch:
                    cur.execute("""
                        INSERT INTO dim_products (product_id, site_id, title, category_id, brand, seller_id, permalink, currency_id, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (product_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            category_id = EXCLUDED.category_id,
                            updated_at = CURRENT_TIMESTAMP;
                    """, p)

                print("   [BANCO] Inserindo 10.000 entradas em price_history...")
                for pr in prices_batch:
                    cur.execute("""
                        INSERT INTO price_history (product_id, price, original_price, currency_id, available_quantity, collected_at)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, pr)

                print("   [BANCO] Inserindo 10.000 entradas na Feature Store 'features_product_daily'...")
                for f in features_batch:
                    cur.execute("""
                        INSERT INTO features_product_daily (product_id, date, price_avg, rolling_avg_price_7d, rolling_avg_price_30d, price_change_pct_7d)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (product_id, date) DO UPDATE SET
                            price_avg = EXCLUDED.price_avg,
                            rolling_avg_price_7d = EXCLUDED.rolling_avg_price_7d,
                            rolling_avg_price_30d = EXCLUDED.rolling_avg_price_30d,
                            price_change_pct_7d = EXCLUDED.price_change_pct_7d;
                    """, f)

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    elapsed = round(time.time() - t0, 2)
    print("\n=================================================================")
    print(f" [SUCESSO] 10.000 PRODUTOS INSERIDOS EM {elapsed}s NO BANCO DE DADOS!")
    print("=================================================================")


if __name__ == "__main__":
    populate_10000()
