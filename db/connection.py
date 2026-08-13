import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from .config import DatabaseConfig

_is_sqlite_mode = False


def is_mock_mode() -> bool:
    global _is_sqlite_mode
    return _is_sqlite_mode


def set_mock_mode(enabled: bool):
    global _is_sqlite_mode
    _is_sqlite_mode = enabled


class SQLiteCursorWrapper:
    def __init__(self, sqlite_cursor):
        self.cur = sqlite_cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def execute(self, query, params=None):
        # Convert PostgreSQL DDL/DML syntax to SQLite compatible syntax
        q = query.replace("TIMESTAMPTZ", "DATETIME")
        q = q.replace("BIGSERIAL", "INTEGER")
        q = q.replace("JSONB", "TEXT")
        q = q.replace("SERIAL", "INTEGER")
        q = q.replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP")
        q = q.replace("VARCHAR(64) REFERENCES pipeline_runs(id) ON DELETE SET NULL", "TEXT")
        q = q.replace("VARCHAR(100) REFERENCES dim_products(product_id) ON DELETE CASCADE", "TEXT")
        q = q.replace("VARCHAR(100) REFERENCES dim_categories(category_id) ON DELETE SET NULL", "TEXT")
        q = q.replace("%s", "?")

        # Convert ON CONFLICT DO UPDATE to SQLite UPSERT
        if "ON CONFLICT (PRODUCT_ID) DO UPDATE" in q.upper():
            q = """
                INSERT INTO dim_products (product_id, site_id, title, category_id, brand, seller_id, permalink, currency_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(product_id) DO UPDATE SET
                    title=excluded.title,
                    category_id=COALESCE(excluded.category_id, dim_products.category_id),
                    brand=COALESCE(excluded.brand, dim_products.brand),
                    seller_id=COALESCE(excluded.seller_id, dim_products.seller_id),
                    permalink=excluded.permalink,
                    updated_at=CURRENT_TIMESTAMP;
            """
        elif "ON CONFLICT (CATEGORY_ID) DO NOTHING" in q.upper():
            q = """
                INSERT INTO dim_categories (category_id, site_id, name)
                VALUES (?, ?, ?)
                ON CONFLICT(category_id) DO NOTHING;
            """
        elif "ON CONFLICT (ID) DO UPDATE" in q.upper():
            q = """
                INSERT INTO pipeline_runs (
                    id, pipeline_name, api_source, endpoint, start_time, end_time, status,
                    records_fetched, records_inserted, records_updated, records_quarantined, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    end_time=excluded.end_time,
                    status=excluded.status,
                    records_fetched=excluded.records_fetched,
                    records_inserted=excluded.records_inserted,
                    records_updated=excluded.records_updated,
                    records_quarantined=excluded.records_quarantined,
                    error_message=excluded.error_message;
            """

        if params is None:
            self.cur.execute(q)
        else:
            # Convert dicts/lists to json strings for SQLite TEXT columns
            clean_params = []
            for p in params:
                if isinstance(p, (dict, list)):
                    import json
                    clean_params.append(json.dumps(p))
                else:
                    clean_params.append(p)
            self.cur.execute(q, clean_params)

    def fetchall(self):
        return self.cur.fetchall()

    def fetchone(self):
        return self.cur.fetchone()

    def close(self):
        self.cur.close()


class SQLiteConnectionWrapper:
    def __init__(self, sqlite_conn):
        self.conn = sqlite_conn

    def cursor(self, cursor_factory=None):
        return SQLiteCursorWrapper(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def get_db_connection(config_dict=None):
    """
    Returns a PostgreSQL connection if authenticated.
    Otherwise falls back seamlessly to a persistent SQLite database ('trendcommerce.db').
    """
    if _is_sqlite_mode:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trendcommerce.db')
        sqlite_conn = sqlite3.connect(db_path)
        sqlite_conn.row_factory = sqlite3.Row
        return SQLiteConnectionWrapper(sqlite_conn)

    if config_dict is None:
        config_dict = DatabaseConfig.get_connection_dict()

    try:
        conn = psycopg2.connect(
            host=config_dict.get("host"),
            port=config_dict.get("port"),
            dbname=config_dict.get("dbname"),
            user=config_dict.get("user"),
            password=config_dict.get("password"),
            connect_timeout=config_dict.get("connect_timeout", 2),
            client_encoding="UTF8"
        )
        return conn
    except Exception:
        set_mock_mode(True)
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trendcommerce.db')
        sqlite_conn = sqlite3.connect(db_path)
        sqlite_conn.row_factory = sqlite3.Row
        return SQLiteConnectionWrapper(sqlite_conn)


def execute_statement(sql: str, params=None) -> bool:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def fetch_all(sql: str, params=None) -> list:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()
