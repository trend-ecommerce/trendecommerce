"""Cliente de Integração com a API Local de Histórico de Vendas.

Consome o serviço fornecido pelo professor (api_vendas.exe) ou
importa diretamente do banco SQLite de histórico quando o servidor
não estiver ativo em segundo plano.
"""

import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.parse
import json

from sqlalchemy.orm import Session
from src.database.models import Product, SalesHistory

logger = logging.getLogger(__name__)

# Possíveis caminhos do arquivo de dados da API fornecida
POSSIBLE_DB_PATHS = [
    Path(os.getenv("VENDAS_DB_PATH")) if os.getenv("VENDAS_DB_PATH") else None,
    Path(r"c:\Users\Aluno\Downloads\API_Historico_Vendas\API_Historico_Vendas\data\historico_vendas.db"),
    Path(r"c:\Users\Aluno\Downloads\API_Historico_Vendas\data\historico_vendas.db"),
    Path(__file__).parent.parent.parent / "data" / "historico_vendas.db"
]


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

    def get_health(self) -> Dict[str, Any]:
        """Obtém status de saúde da API."""
        data = self._http_get("/health")
        if data:
            return {
                "online": True,
                "url": self.base_url,
                "status": data.get("status", "online"),
                "total_registros_vendas": data.get("total_registros_vendas", 0),
                "total_produtos": data.get("total_produtos", 0)
            }

        # Checar se temos o arquivo físico como fallback
        db_path = self.get_database_path()
        return {
            "online": False,
            "url": self.base_url,
            "database_file_available": bool(db_path and db_path.exists()),
            "database_path": str(db_path) if db_path else None
        }

    def get_categorias(self) -> List[str]:
        """Lista as categorias disponíveis."""
        cats = self._http_get("/categorias")
        if isinstance(cats, list) and cats:
            return cats

        # Fallback local direto
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                c = conn.cursor()
                res = [row[0] for row in c.execute("SELECT DISTINCT categoria FROM produtos").fetchall()]
                conn.close()
                return res
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

        # Fallback local direto
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                query = "SELECT * FROM produtos"
                params = []
                if categoria:
                    query += " WHERE categoria LIKE ?"
                    params.append(f"%{categoria}%")
                query += " LIMIT ? OFFSET ?"
                params.extend([page_size, (page - 1) * page_size])
                rows = [dict(r) for r in c.execute(query, params).fetchall()]
                conn.close()
                return rows
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

        # Fallback local direto
        db_path = self.get_database_path()
        if db_path and db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                query = "SELECT * FROM vendas_historicas WHERE produto_id = ?"
                params = [produto_id]
                if ano:
                    query += " AND ano = ?"
                    params.append(ano)
                if mes:
                    query += " AND mes = ?"
                    params.append(mes)
                query += " ORDER BY data_venda DESC LIMIT ?"
                params.append(page_size)
                rows = [dict(r) for r in c.execute(query, params).fetchall()]
                conn.close()
                return rows
            except Exception:
                pass
        return []

    def get_database_path(self) -> Optional[Path]:
        """Localiza o arquivo sqlite historico_vendas.db no disco."""
        for p in POSSIBLE_DB_PATHS:
            if p and p.exists():
                return p
        return None

    def sync_to_trendecommerce(self, session: Session, min_date: str = "2024-01-01", limit_products: Optional[int] = None) -> Dict[str, Any]:
        """Sincroniza os produtos e histórico da API de Vendas para o banco local.
        
        Utiliza importação em lote de alta performance para sincronizar milhares
        de registros em poucos segundos.
        """
        db_path = self.get_database_path()
        if not db_path or not db_path.exists():
            return {"success": False, "error": f"Arquivo historico_vendas.db não encontrado nos caminhos mapeados."}

        # Conectar ao banco local do SQLAlchemy
        engine = session.get_bind()
        local_db_url = str(engine.url)
        
        if not local_db_url.startswith("sqlite:///"):
            # Para bancos não-SQLite, fazer inserção via SQLAlchemy em lote
            return self._sync_via_sqlalchemy(session, db_path, min_date, limit_products)

        # Para SQLite local: ATTACH DATABASE para cópia instantânea
        local_sqlite_path = Path(__file__).parent.parent.parent / "data" / "trendcommerce_dev.db"
        local_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Garantir que as tabelas existem antes de sincronizar
        from src.database.models import Base
        Base.metadata.create_all(engine)

        conn = sqlite3.connect(str(local_sqlite_path))
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

            # 2. Copiar histórico de vendas a partir de min_date
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
                WHERE v.data_venda >= ?
            """, (min_date,))

            conn.commit()

            total_prods = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            total_sales = cursor.execute("SELECT COUNT(*) FROM sales_history").fetchone()[0]

            cursor.execute("DETACH DATABASE src_api")
            conn.close()

            logger.info(f"[VendasApiClient] Sincronização concluída com sucesso: {total_prods} produtos e {total_sales} vendas.")
            return {
                "success": True,
                "total_products": total_prods,
                "total_sales": total_sales,
                "synced_from_date": min_date,
                "source": "api_vendas"
            }

        except Exception as e:
            conn.close()
            logger.error(f"[VendasApiClient] Erro na sincronização: {e}")
            return {"success": False, "error": str(e)}

    def _sync_via_sqlalchemy(self, session: Session, db_path: Path, min_date: str, limit_products: Optional[int]) -> Dict[str, Any]:
        """Sincroniza registros lendo o SQLite de origem e inserindo via Session."""
        src_conn = sqlite3.connect(str(db_path))
        src_conn.row_factory = sqlite3.Row
        c = src_conn.cursor()

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
                    is_active=True
                )
                session.add(prod)
        session.flush()

        sales = c.execute("SELECT * FROM vendas_historicas WHERE data_venda >= ?", (min_date,)).fetchall()
        for s in sales:
            sale = SalesHistory(
                id=s["id"],
                product_id=s["produto_id"],
                date=datetime.strptime(s["data_venda"][:10], "%Y-%m-%d"),
                quantity_sold=int(s["vendas"] or 0),
                price_at_date=float(s["preco"] or 100.0),
                available_quantity=100,
                platform="api_vendas"
            )
            session.merge(sale)

        session.commit()
        src_conn.close()
        return {"success": True, "total_products": len(products), "total_sales": len(sales)}


vendas_client = VendasApiClient()
