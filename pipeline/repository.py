from db.connection import get_db_connection


class DataRepository:
    @staticmethod
    def save_raw_response(execution_id: str, api_source: str, endpoint: str, url: str, http_status: int, payload: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raw_api_responses (execution_id, api_source, endpoint, url, http_status, payload)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (execution_id, api_source, endpoint, url, http_status, payload))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def ensure_category_exists(category_id: str, site_id: str = "MLB", name: str = "General Category"):
        if not category_id:
            return
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dim_categories (category_id, site_id, name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (category_id) DO NOTHING;
                """, (category_id, site_id, name))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    @staticmethod
    def upsert_product(product: dict) -> bool:
        """Idempotent UPSERT into dim_products."""
        DataRepository.ensure_category_exists(product.get("category_id"), product.get("site_id", "MLB"))

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO dim_products (product_id, site_id, title, category_id, brand, seller_id, permalink, currency_id, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (product_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        category_id = COALESCE(EXCLUDED.category_id, dim_products.category_id),
                        brand = COALESCE(EXCLUDED.brand, dim_products.brand),
                        seller_id = COALESCE(EXCLUDED.seller_id, dim_products.seller_id),
                        permalink = EXCLUDED.permalink,
                        updated_at = CURRENT_TIMESTAMP;
                """, (
                    product["product_id"],
                    product["site_id"],
                    product["title"],
                    product.get("category_id"),
                    product.get("brand"),
                    product.get("seller_id"),
                    product.get("permalink"),
                    product.get("currency_id", "BRL")
                ))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def insert_price_history(price_entry: dict) -> bool:
        """Appends new temporal entry into price_history ledger."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO price_history (product_id, price, original_price, currency_id, available_quantity, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    price_entry["product_id"],
                    price_entry["price"],
                    price_entry.get("original_price"),
                    price_entry.get("currency_id", "BRL"),
                    price_entry.get("available_quantity", 0),
                    price_entry.get("collected_at")
                ))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
