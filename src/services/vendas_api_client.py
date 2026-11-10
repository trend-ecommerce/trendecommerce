"""Cliente de Integração com a API Local de Histórico de Vendas.

Consome o serviço fornecido pelo professor (api_vendas.exe),
importa diretamente do banco SQLite historico_vendas.db quando disponível,
ou opera em fallback total via banco local/catálogo JSON no Render.
"""

import json
import logging
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from src.database.models import Product, SalesHistory

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_JSON_PATH = PROJECT_ROOT / "data" / "catalog_500_products.json"


def _discover_possible_db_paths() -> List[Path]:
    """Localiza dinamicamente possíveis caminhos para historico_vendas.db em qualquer PC."""
    candidates: List[Path] = []
    env_db = os.getenv("VENDAS_DB_PATH")
    if env_db and env_db.strip().lower() not in {"none", "disabled"}:
        candidates.append(Path(env_db))

    home = Path.home()

    search_roots: List[Path] = [
        PROJECT_ROOT.parent,
        home / "Desktop",
        home / "Área de Trabalho",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Área de Trabalho",
        home / "Downloads",
        home / "OneDrive" / "Downloads",
        home / "Documents",
        home / "Documentos",
    ]

    # Suporte a pastas OneDrive corporativas/personalizadas no Windows (ex: "OneDrive - Empresa")
    try:
        for od_dir in home.glob("OneDrive*"):
            if od_dir.is_dir():
                for sub in ("Desktop", "Área de Trabalho", "Downloads"):
                    search_roots.append(od_dir / sub)
    except Exception:
        pass

    for root in search_roots:
        candidates.append(root / "API_Historico_Vendas" / "data" / "historico_vendas.db")
        candidates.append(root / "API_Historico_Vendas" / "API_Historico_Vendas" / "data" / "historico_vendas.db")

    candidates.append(PROJECT_ROOT / "data" / "historico_vendas.db")

    unique: List[Path] = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


# Possíveis caminhos do arquivo de dados da API fornecida
POSSIBLE_DB_PATHS = _discover_possible_db_paths()


class VendasApiClient:
    """Cliente HTTP e conector direto da API de Histórico de Vendas."""

    def __init__(self, base_url: Optional[str] = None):
        configured_url = os.getenv("VENDAS_API_URL")
        self.base_url = (base_url or configured_url or "http://127.0.0.1:8001").rstrip("/")
        self.fallback_urls = ["http://127.0.0.1:8001", "http://127.0.0.1:8000", "http://127.0.0.1:5000"]

    def _get_active_url(self) -> Optional[str]:
        """Testa se a API está respondendo na URL base ou nas alternativas."""
        test_urls = [self.base_url] + [u for u in self.fallback_urls if u != self.base_url]
        for url in test_urls:
            try:
                req = urllib.request.Request(f"{url}/health", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        self.base_url = url
                        return url
            except Exception:
                continue
        return None

    def _http_get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Executa uma requisição GET HTTP para a API."""
        active_url = self._get_active_url()
        if not active_url:
            return None

        url = f"{active_url}{endpoint}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url += f"?{query}"

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Erro ao requisitar {url}: {e}")
            return None

    def _get_local_db_path(self) -> Optional[Path]:
        """Localiza o arquivo SQLite local (data/trendcommerce_dev.db ou DATABASE_URL)."""
        try:
            from sqlalchemy.engine.url import make_url
            from src.database.connection import get_database_url

            db_url = get_database_url()
            if db_url.startswith("sqlite:///"):
                parsed = make_url(db_url)
                if parsed.database and parsed.database != ":memory:":
                    return Path(parsed.database)
        except Exception:
            pass
        return PROJECT_ROOT / "data" / "trendcommerce_dev.db"

    def _ensure_local_db_calibrated_if_needed(self) -> Optional[Path]:
        """Garante que o banco local exista e esteja populado caso seja usado como fallback no Render."""
        local_db = self._get_local_db_path()
        needs_calibration = False

        if local_db is None or not local_db.exists():
            needs_calibration = True
        else:
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=10.0)
                has_tables = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('products', 'sales_history')"
                ).fetchone()[0]
                if int(has_tables or 0) < 2:
                    needs_calibration = True
                else:
                    prod_cnt = int(conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] or 0)
                    sales_cnt = int(conn.execute("SELECT COUNT(*) FROM sales_history").fetchone()[0] or 0)
                    if prod_cnt < 500 or sales_cnt == 0:
                        needs_calibration = True
            except Exception:
                needs_calibration = True
            finally:
                if conn is not None:
                    conn.close()

        if needs_calibration and CATALOG_JSON_PATH.exists():
            try:
                from scripts.update_historical_data_to_nov30 import main as run_update_nov30
                run_update_nov30()
                local_db = self._get_local_db_path()
            except Exception as err:
                logger.warning(f"[VendasApiClient] Falha ao auto-calibrar banco local: {err}")

        return local_db

    def get_health(self) -> Dict[str, Any]:
        """Obtém status de saúde da API ou do banco de fallback."""
        data = self._http_get("/health")
        if data:
            total_prods = data.get("total_produtos")
            if not total_prods:
                stats = self._http_get("/estatisticas")
                if isinstance(stats, dict) and "total_produtos" in stats:
                    total_prods = stats.get("total_produtos")
                else:
                    total_prods = 500
            return {
                "online": True,
                "url": self.base_url,
                "status": data.get("status", "online"),
                "total_registros_vendas": data.get("total_registros_vendas", 0),
                "total_produtos": total_prods,
            }

        # 1. Tentar arquivo físico oficial da API externa
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            prod_cnt = None
            sales_cnt = None
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(db_path), timeout=5.0)
                prod_cnt = int(conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] or 0)
                sales_cnt = int(conn.execute("SELECT COUNT(*) FROM vendas_historicas").fetchone()[0] or 0)
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()
            res: Dict[str, Any] = {
                "online": False,
                "url": self.base_url,
                "database_file_available": True,
                "database_path": str(db_path),
                "source": "api_db",
            }
            if prod_cnt is not None:
                res["total_produtos"] = prod_cnt
                res["total_registros_vendas"] = sales_cnt
            return res

        # 2. Fallback para banco local/Render
        local_db = self._ensure_local_db_calibrated_if_needed()
        if local_db and local_db.exists():
            conn = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=5.0)
                prod_cnt = int(conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0] or 0)
                sales_cnt = int(conn.execute("SELECT COUNT(*) FROM sales_history").fetchone()[0] or 0)
                if prod_cnt > 0:
                    return {
                        "online": False,
                        "url": self.base_url,
                        "database_file_available": True,
                        "database_path": str(local_db),
                        "source": "local_db",
                        "total_produtos": prod_cnt,
                        "total_registros_vendas": sales_cnt,
                    }
            except Exception as err:
                logger.warning(f"[VendasApiClient] Erro no fallback local get_health: {err}")
            finally:
                if conn is not None:
                    conn.close()

        return {
            "online": False,
            "url": self.base_url,
            "database_file_available": False,
            "database_path": None,
        }

    def get_categorias(self) -> List[str]:
        """Lista as categorias disponíveis."""
        cats = self._http_get("/categorias")
        if isinstance(cats, list) and cats:
            return cats

        # Fallback banco externo historico_vendas.db
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(db_path), timeout=5.0)
                res = [row[0] for row in conn.execute("SELECT DISTINCT categoria FROM produtos ORDER BY categoria").fetchall() if row[0]]
                if res:
                    return res
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        # Fallback banco local/Render
        local_db = self._ensure_local_db_calibrated_if_needed()
        if local_db and local_db.exists():
            conn = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=5.0)
                res = [
                    row[0]
                    for row in conn.execute(
                        "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = 1 ORDER BY category"
                    ).fetchall()
                    if row[0]
                ]
                if res:
                    return res
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        if CATALOG_JSON_PATH.exists():
            try:
                with open(CATALOG_JSON_PATH, "r", encoding="utf-8") as f:
                    items = json.load(f)
                cats_json = sorted({str(p["categoria"]) for p in items if p.get("categoria")})
                if cats_json:
                    return cats_json
            except Exception:
                pass

        return ["Eletrônicos", "Moda e acessórios", "Casa e decoração", "Esportes e fitness", "Beleza e cuidados pessoais"]

    def get_produtos(self, categoria: Optional[str] = None, page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Busca catálogo de produtos."""
        data = self._http_get("/produtos", {"categoria": categoria, "page": page, "page_size": page_size})
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"]

        # Fallback banco externo historico_vendas.db
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(db_path), timeout=10.0)
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM produtos"
                params: List[Any] = []
                if categoria:
                    query += " WHERE categoria LIKE ?"
                    params.append(f"%{categoria}%")
                query += " ORDER BY id ASC LIMIT ? OFFSET ?"
                params.extend([page_size, max(0, (page - 1) * page_size)])
                return [dict(r) for r in conn.execute(query, params).fetchall()]
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        # Fallback banco local/Render
        local_db = self._ensure_local_db_calibrated_if_needed()
        if local_db and local_db.exists():
            conn = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=10.0)
                conn.row_factory = sqlite3.Row
                query = (
                    "SELECT id, title AS nome, title, category AS categoria, category, "
                    "price AS preco_base, price, platform, currency, is_active, created_at "
                    "FROM products WHERE is_active = 1"
                )
                params = []
                if categoria:
                    query += " AND category LIKE ?"
                    params.append(f"%{categoria}%")
                query += " ORDER BY id ASC LIMIT ? OFFSET ?"
                params.extend([page_size, max(0, (page - 1) * page_size)])
                rows = [dict(r) for r in conn.execute(query, params).fetchall()]
                if rows or not CATALOG_JSON_PATH.exists():
                    return rows
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        # Fallback direto JSON
        if CATALOG_JSON_PATH.exists():
            try:
                with open(CATALOG_JSON_PATH, "r", encoding="utf-8") as f:
                    items = json.load(f)
                if categoria:
                    cat_lower = categoria.lower()
                    items = [p for p in items if cat_lower in str(p.get("categoria", "")).lower()]
                offset = max(0, (page - 1) * page_size)
                return items[offset : offset + page_size]
            except Exception:
                pass

        return []

    def get_vendas_produto(self, produto_id: int, ano: Optional[int] = None, mes: Optional[int] = None, page_size: int = 500) -> List[Dict[str, Any]]:
        """Busca série de vendas de um produto específico."""
        data = self._http_get(f"/vendas/{produto_id}", {"ano": ano, "mes": mes, "page": 1, "page_size": page_size})
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        if isinstance(data, list):
            return data

        # Fallback banco externo historico_vendas.db
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(db_path), timeout=10.0)
                conn.row_factory = sqlite3.Row
                query = "SELECT * FROM vendas_historicas WHERE produto_id = ?"
                params: List[Any] = [produto_id]
                if ano is not None:
                    query += " AND ano = ?"
                    params.append(int(ano))
                if mes is not None:
                    query += " AND mes = ?"
                    params.append(int(mes))
                query += " ORDER BY data_venda DESC LIMIT ?"
                params.append(int(page_size))
                return [dict(r) for r in conn.execute(query, params).fetchall()]
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        # Fallback banco local/Render
        local_db = self._ensure_local_db_calibrated_if_needed()
        if local_db and local_db.exists():
            conn = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=10.0)
                conn.row_factory = sqlite3.Row
                query = (
                    "SELECT s.id, s.product_id AS produto_id, p.title AS nome_produto, "
                    "s.price_at_date AS preco, s.quantity_sold AS vendas, p.category AS categoria, "
                    "substr(s.date, 1, 10) AS data_venda, "
                    "CAST(strftime('%Y', s.date) AS INTEGER) AS ano, "
                    "CAST(strftime('%m', s.date) AS INTEGER) AS mes, "
                    "CAST(strftime('%d', s.date) AS INTEGER) AS dia "
                    "FROM sales_history s "
                    "LEFT JOIN products p ON p.id = s.product_id "
                    "WHERE s.product_id = ?"
                )
                params = [int(produto_id)]
                if ano is not None:
                    query += " AND CAST(strftime('%Y', s.date) AS INTEGER) = ?"
                    params.append(int(ano))
                if mes is not None:
                    query += " AND CAST(strftime('%m', s.date) AS INTEGER) = ?"
                    params.append(int(mes))
                query += " ORDER BY s.date DESC LIMIT ?"
                params.append(int(page_size))
                return [dict(r) for r in conn.execute(query, params).fetchall()]
            except Exception:
                pass
            finally:
                if conn is not None:
                    conn.close()

        return []

    def get_estatisticas(self) -> Dict[str, Any]:
        """Obtém estatísticas consolidadas da API ou do banco local no Render."""
        data = self._http_get("/estatisticas")
        if isinstance(data, dict) and data:
            return {**data, "online": True, "source": "http_api"}

        # Fallback banco externo historico_vendas.db
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(db_path), timeout=10.0)
                total_prods = int(conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] or 0)
                row_v = conn.execute(
                    "SELECT COUNT(*), MIN(data_venda), MAX(data_venda), COALESCE(SUM(vendas), 0) FROM vendas_historicas"
                ).fetchone()
                cats = [r[0] for r in conn.execute("SELECT DISTINCT categoria FROM produtos ORDER BY categoria").fetchall() if r[0]]
                return {
                    "online": False,
                    "source": "api_db",
                    "total_produtos": total_prods,
                    "total_registros_vendas": int(row_v[0] or 0),
                    "data_minima": row_v[1],
                    "data_maxima": row_v[2],
                    "total_vendas_unidades": int(row_v[3] or 0),
                    "categorias": cats,
                }
            except Exception as err:
                logger.warning(f"[VendasApiClient] Erro ao consultar estatísticas em {db_path}: {err}")
            finally:
                if conn is not None:
                    conn.close()

        # Fallback banco local/Render
        local_db = self._ensure_local_db_calibrated_if_needed()
        if local_db and local_db.exists():
            conn = None
            try:
                conn = sqlite3.connect(str(local_db), timeout=10.0)
                total_prods = int(conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0] or 0)
                row_s = conn.execute(
                    "SELECT COUNT(*), MIN(substr(date, 1, 10)), MAX(substr(date, 1, 10)), COALESCE(SUM(quantity_sold), 0) FROM sales_history"
                ).fetchone()
                cats = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND is_active = 1 ORDER BY category"
                    ).fetchall()
                    if r[0]
                ]
                return {
                    "online": False,
                    "source": "local_db",
                    "total_produtos": total_prods,
                    "total_registros_vendas": int(row_s[0] or 0),
                    "data_minima": row_s[1],
                    "data_maxima": row_s[2],
                    "total_vendas_unidades": int(row_s[3] or 0),
                    "categorias": cats,
                }
            except Exception as err:
                logger.warning(f"[VendasApiClient] Erro ao consultar estatísticas locais em {local_db}: {err}")
            finally:
                if conn is not None:
                    conn.close()

        return {
            "online": False,
            "source": "unavailable",
            "total_produtos": 0,
            "total_registros_vendas": 0,
            "categorias": [],
        }

    def get_database_path(self) -> Optional[Path]:
        """Localiza dinamicamente o arquivo sqlite historico_vendas.db no disco."""
        env_db = os.getenv("VENDAS_DB_PATH")
        if env_db:
            if env_db.strip().lower() in {"none", "disabled"}:
                return None
            env_path = Path(env_db)
            if env_path.exists():
                return env_path

        for p in POSSIBLE_DB_PATHS:
            if p and p.exists():
                return p

        for p in _discover_possible_db_paths():
            if p and p.exists():
                return p
        return None

    def sync_to_trendecommerce(self, session: Session, min_date: Optional[str] = "2020-01-01", limit_products: Optional[int] = None) -> Dict[str, Any]:
        """Sincroniza os produtos e histórico da API de Vendas para o banco local,
        com fallback completo no Render via catálogo JSON + banco local determinístico.
        """
        db_path = self.get_database_path()
        if not db_path or not db_path.exists():
            return self._sync_from_local_fallback(session, min_date=min_date)

        # Conectar ao banco local do SQLAlchemy
        engine = session.get_bind()
        local_db_url = str(engine.url)

        if not local_db_url.startswith("sqlite:///"):
            # Para bancos não-SQLite, fazer inserção via SQLAlchemy em lote
            return self._sync_via_sqlalchemy(session, db_path, min_date, limit_products)

        # Para SQLite local: ATTACH DATABASE para cópia instantânea
        url_db = getattr(engine.url, "database", None)
        if url_db and url_db != ":memory:":
            local_sqlite_path = Path(url_db)
        else:
            local_sqlite_path = PROJECT_ROOT / "data" / "trendcommerce_dev.db"
        local_sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        # Garantir que as tabelas existem antes de sincronizar
        from src.database.models import Base
        Base.metadata.create_all(engine)

        conn = sqlite3.connect(str(local_sqlite_path), timeout=60.0)
        cursor = conn.cursor()

        try:
            cursor.execute("ATTACH DATABASE ? AS src_api", (str(db_path),))

            # 1. Copiar produtos
            prod_limit_clause = f"LIMIT {limit_products}" if limit_products else ""
            cursor.execute(f"""
                INSERT OR REPLACE INTO products (
                    id, external_id, platform, title, category, price, currency, condition, is_active, created_at, updated_at
                )
                SELECT
                    id,
                    'API_' || id,
                    'api_vendas',
                    nome,
                    categoria,
                    COALESCE(preco_base, 100.0),
                    'BRL',
                    'new',
                    1,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM src_api.produtos
                {prod_limit_clause}
            """)

            # 2. Copiar histórico de vendas a partir de min_date (suporta min_date=None para copiar tudo)
            where_clause = "WHERE v.data_venda >= ?" if min_date else ""
            query_params = (min_date,) if min_date else ()

            if limit_products is None:
                if min_date:
                    cursor.execute("DELETE FROM sales_history WHERE date(date) < ?", (min_date,))
                cursor.execute(
                    "DELETE FROM sales_history WHERE date(date) > (SELECT MAX(data_venda) FROM src_api.vendas_historicas)"
                )
                cursor.execute("DELETE FROM products WHERE id NOT IN (SELECT id FROM src_api.produtos)")

            cursor.execute(f"""
                INSERT OR REPLACE INTO sales_history (
                    id, product_id, date, quantity_sold, price_at_date, available_quantity, platform, collected_at
                )
                SELECT
                    v.id,
                    v.produto_id,
                    v.data_venda,
                    COALESCE(v.vendas, 0),
                    COALESCE(v.preco, p.preco_base, 100.0),
                    100,
                    'api_vendas',
                    CURRENT_TIMESTAMP
                FROM src_api.vendas_historicas v
                JOIN src_api.produtos p ON v.produto_id = p.id
                {where_clause}
            """, query_params)

            conn.commit()

            total_prods = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            total_sales = cursor.execute("SELECT COUNT(*) FROM sales_history").fetchone()[0]

            cursor.execute("DETACH DATABASE src_api")

            logger.info(f"[VendasApiClient] Sincronização concluída com sucesso: {total_prods} produtos e {total_sales} vendas.")
            return {
                "success": True,
                "total_products": total_prods,
                "total_sales": total_sales,
                "synced_from_date": min_date,
                "source": "api_vendas",
            }

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(f"[VendasApiClient] Erro na sincronização: {e}")
            return {"success": False, "error": str(e)}
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _sync_from_local_fallback(self, session: Session, min_date: Optional[str] = "2020-01-01") -> Dict[str, Any]:
        """Fallback de sincronização para ambientes sem historico_vendas.db (ex: Render)."""
        try:
            from sqlalchemy.engine.url import make_url
            from src.database.models import Base
            from src.database.seed_loader import _is_local_db_calibrated

            engine = session.get_bind()
            session.rollback()
            Base.metadata.create_all(engine)

            is_calibrated = _is_local_db_calibrated(session, exact_api_signatures=True)
            session.rollback()

            if not is_calibrated:
                local_db_url = str(engine.url)
                if local_db_url.startswith("sqlite:///"):
                    parsed = make_url(local_db_url)
                    if parsed.database and parsed.database != ":memory:":
                        target_sqlite = Path(parsed.database)
                    else:
                        target_sqlite = self._get_local_db_path()
                    if target_sqlite is not None and (target_sqlite.exists() or CATALOG_JSON_PATH.exists()):
                        from scripts.update_historical_data_to_nov30 import update_api_sqlite_db
                        update_api_sqlite_db(target_sqlite, is_local_format=True)
                elif CATALOG_JSON_PATH.exists():
                    from scripts.update_historical_data_to_nov30 import _populate_non_sqlite_from_catalog
                    _populate_non_sqlite_from_catalog(engine)

            session.expire_all()
            total_prods = int(session.query(Product).count())
            total_sales = int(session.query(SalesHistory).count())

            if total_prods > 0 and total_sales > 0:
                logger.info(
                    f"[VendasApiClient] Sincronização via fallback local concluída: {total_prods} produtos e {total_sales:,} vendas."
                )
                return {
                    "success": True,
                    "total_products": total_prods,
                    "total_sales": total_sales,
                    "synced_from_date": min_date,
                    "source": "local_catalog",
                }
            return {
                "success": False,
                "error": "Arquivo historico_vendas.db não encontrado e catálogo local indisponível.",
            }
        except Exception as err:
            try:
                session.rollback()
            except Exception:
                pass
            logger.error(f"[VendasApiClient] Erro no fallback de sincronização: {err}")
            return {"success": False, "error": str(err)}

    def _sync_via_sqlalchemy(self, session: Session, db_path: Path, min_date: str, limit_products: Optional[int]) -> Dict[str, Any]:
        """Sincroniza registros lendo o SQLite de origem e inserindo via Session."""
        src_conn = sqlite3.connect(str(db_path))
        src_conn.row_factory = sqlite3.Row
        c = src_conn.cursor()

        try:
            query_p = "SELECT * FROM produtos"
            if limit_products:
                query_p += f" LIMIT {limit_products}"
            products = c.execute(query_p).fetchall()

            for p in products:
                existing = session.query(Product).filter_by(id=p["id"]).first()
                if not existing:
                    prod = Product(
                        id=p["id"],
                        external_id=f"API_{p['id']}",
                        platform="api_vendas",
                        title=p["nome"],
                        category=p["categoria"],
                        price=float(p["preco_base"] or 100.0),
                        currency="BRL",
                        condition="new",
                        is_active=True,
                    )
                    session.add(prod)
            session.flush()

            if min_date:
                sales = c.execute("SELECT * FROM vendas_historicas WHERE data_venda >= ?", (min_date,)).fetchall()
            else:
                sales = c.execute("SELECT * FROM vendas_historicas").fetchall()
            for s in sales:
                sale = SalesHistory(
                    id=s["id"],
                    product_id=s["produto_id"],
                    date=datetime.strptime(s["data_venda"][:10], "%Y-%m-%d"),
                    quantity_sold=int(s["vendas"] or 0),
                    price_at_date=float(s["preco"] or 100.0),
                    available_quantity=100,
                    platform="api_vendas",
                )
                session.merge(sale)

            session.commit()
            return {"success": True, "total_products": len(products), "total_sales": len(sales)}
        finally:
            src_conn.close()


vendas_client = VendasApiClient()
