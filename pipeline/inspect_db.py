import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_db_connection


def print_table_records():
    conn = get_db_connection()
    print("=================================================================")
    print(" CONSULTA DE DADOS NO BANCO DE DADOS (TRENDCOMMERCE) ")
    print("=================================================================\n")

    with conn.cursor() as cur:
        # 1. dim_products
        cur.execute("SELECT product_id, title, category_id, currency_id FROM dim_products ORDER BY product_id;")
        products = cur.fetchall()
        print(f"[TABELA dim_products] ({len(products)} produtos cadastrados):")
        print("-" * 75)
        for idx, p in enumerate(products, 1):
            print(f"  {idx:2d}. [{p[0]}] {p[1]} (Categoria: {p[2]})")

        # 2. price_history
        cur.execute("""
            SELECT ph.product_id, dp.title, ph.price, ph.original_price, ph.collected_at
            FROM price_history ph
            JOIN dim_products dp ON ph.product_id = dp.product_id
            ORDER BY ph.collected_at DESC LIMIT 10;
        """)
        prices = cur.fetchall()
        print(f"\n[TABELA price_history] (Ultimas Entradas de Historico):")
        print("-" * 75)
        for idx, pr in enumerate(prices, 1):
            print(f"  {idx:2d}. [{pr[0]}] R$ {pr[2]:.2f} (Coletado em: {pr[4]})")

        # 3. pipeline_runs
        cur.execute("""
            SELECT id, pipeline_name, api_source, status, records_fetched, records_inserted, start_time
            FROM pipeline_runs ORDER BY start_time DESC LIMIT 5;
        """)
        runs = cur.fetchall()
        print(f"\n[TABELA pipeline_runs] (Ultimas Execucoes de Ingestao):")
        print("-" * 75)
        for r in runs:
            print(f"  - Run ID: {r[0]} | Pipeline: {r[1]} | Status: {r[3]} | Inseridos: {r[5]}")

    conn.close()
    print("\n=================================================================")


if __name__ == "__main__":
    print_table_records()
