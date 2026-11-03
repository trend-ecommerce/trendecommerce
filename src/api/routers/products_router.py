import difflib
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.api.dependencies import get_db
from src.database.models import Product, SalesHistory
from src.services.vendas_api_client import vendas_client
from src.schemas.product_schema import (
    ProductResponse,
    ProductDetailResponse,
    ProductListResponse,
    SalesHistoryResponse,
    TopProductItem
)

router = APIRouter(prefix="/products", tags=["Produtos & Histórico"])


@router.get("", response_model=ProductListResponse, summary="Listar produtos com busca e paginação")
def list_products(
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
    search: Optional[str] = Query(None, description="Filtro de busca por nome ou categoria"),
    category: Optional[str] = Query(None, description="Filtro de categoria"),
    platform: Optional[str] = Query(None, description="Filtro de plataforma (api_vendas, proprio)"),
    db: Session = Depends(get_db)
):
    """Retorna lista de produtos cadastrados com paginação e totalizadores de vendas."""
    query = db.query(Product).filter(Product.is_active.is_(True))

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Product.title.ilike(search_fmt)) | (Product.category.ilike(search_fmt))
        )

    if category:
        query = query.filter(Product.category == category)

    if platform:
        query = query.filter(Product.platform == platform)

    total = query.count()
    offset = (page - 1) * limit
    products = query.order_by(Product.id).offset(offset).limit(limit).all()

    # Agregar totais de venda por produto nos últimos 30 dias (vendas do mês)
    product_ids = [p.id for p in products]
    sales_map = {}
    if product_ids:
        latest_date = db.query(func.max(SalesHistory.date)).scalar()
        sales_q = db.query(
            SalesHistory.product_id,
            func.sum(SalesHistory.quantity_sold).label("total_units"),
            func.sum(SalesHistory.quantity_sold * func.coalesce(SalesHistory.price_at_date, 100.0)).label("total_rev")
        ).filter(SalesHistory.product_id.in_(product_ids))

        if latest_date:
            sales_q = sales_q.filter(SalesHistory.date >= latest_date - timedelta(days=30))

        sales_aggs = sales_q.group_by(SalesHistory.product_id).all()
        for s_pid, s_units, s_rev in sales_aggs:
            sales_map[s_pid] = (int(s_units or 0), float(s_rev or 0.0))

    items = []
    for prod in products:
        total_units, total_rev = sales_map.get(prod.id, (0, 0.0))
        item = ProductResponse(
            id=prod.id,
            external_id=prod.external_id,
            platform=prod.platform,
            title=prod.title,
            category=prod.category,
            price=prod.price,
            currency=prod.currency,
            condition=prod.condition,
            url=prod.url,
            attributes=prod.attributes,
            is_active=prod.is_active,
            created_at=prod.created_at,
            total_sold_units=total_units,
            total_revenue=round(total_rev, 2)
        )
        items.append(item)

    pages = (total + limit - 1) // limit if total > 0 else 1

    return ProductListResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        items=items
    )


@router.get("/categories", response_model=List[str], summary="Listar todas as categorias com produtos cadastrados")
def get_categories(db: Session = Depends(get_db)):
    """Retorna a lista de categorias disponíveis no sistema e na API de Vendas."""
    db_cats = [
        c[0] for c in db.query(Product.category).filter(
            Product.is_active.is_(True),
            Product.category.isnot(None)
        ).distinct().order_by(Product.category).all()
        if c[0]
    ]
    if db_cats:
        return db_cats
    return vendas_client.get_categorias()


@router.get("/api-status", summary="Verificar status de conexão com a API de Histórico de Vendas")
def get_vendas_api_status():
    """Retorna a saúde e status de conexão com a API externa fornecida pelo professor."""
    return vendas_client.get_health()


@router.get("/top-sales", response_model=List[TopProductItem], summary="Produtos mais vendidos com ranking")
def get_top_sales(
    limit: int = Query(10, ge=1, le=50, description="Quantidade de produtos"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    days: int = Query(30, ge=1, le=3650, description="Janela de dias históricos para o cálculo (padrão: 30 dias do mês)"),
    db: Session = Depends(get_db)
):
    """Calcula os produtos campeões de vendas no período (últimos 30 dias / mês)."""
    latest_date = db.query(func.max(SalesHistory.date)).scalar()

    query = db.query(
        SalesHistory.product_id,
        func.sum(SalesHistory.quantity_sold).label("total_units"),
        func.sum(SalesHistory.quantity_sold * func.coalesce(SalesHistory.price_at_date, 100.0)).label("total_revenue")
    )

    if latest_date and days:
        min_date = latest_date - timedelta(days=days)
        query = query.filter(SalesHistory.date >= min_date)

    sales_results = query.group_by(SalesHistory.product_id).order_by(desc("total_units")).all()

    items = []
    rank = 1
    for p_id, units, rev in sales_results:
        prod = db.query(Product).filter(Product.id == p_id).first()
        if not prod or not prod.is_active:
            continue
        if category and prod.category != category:
            continue

        items.append(TopProductItem(
            rank=rank,
            id=prod.id,
            title=prod.title,
            category=prod.category or "Geral",
            price=prod.price or 0.0,
            quantity_sold=int(units or 0),
            revenue=round(float(rev or 0.0), 2)
        ))
        rank += 1
        if len(items) >= limit:
            break

    return items


def _strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()


def search_catalog_products(q: str, db: Session, limit: int = 8) -> List[Product]:
    """Busca produtos no catálogo oficial por correspondência exata, palavras-chave ou similaridade de caracteres."""
    q_str = q.strip()
    if not q_str:
        return []

    q_norm = _strip_accents(q_str)
    q_tokens = [w for w in q_norm.split() if len(w) >= 2]
    if not q_tokens:
        q_tokens = [q_norm]

    # 1. Correspondência direta via SQL (rápida)
    direct_query = db.query(Product).filter(
        Product.is_active.is_(True),
        (Product.title.ilike(f"%{q_str}%")) | (Product.category.ilike(f"%{q_str}%"))
    ).limit(limit).all()

    if len(direct_query) >= limit:
        return direct_query

    # 2. Ranqueamento por similaridade de caracteres contra produtos ativos
    all_active = db.query(Product).filter(Product.is_active.is_(True)).all()
    seen_ids = {p.id for p in direct_query}
    scored = [(2.0, p) for p in direct_query]

    for p in all_active:
        if p.id in seen_ids:
            continue

        p_title_norm = _strip_accents(p.title)
        p_tokens = [w for w in p_title_norm.split() if len(w) >= 2]

        # Frase completa no título
        if q_norm in p_title_norm:
            score = 2.0 + (len(q_norm) / max(len(p_title_norm), 1))
            scored.append((score, p))
            seen_ids.add(p.id)
            continue

        # Similaridade termo a termo / caracteres parecidos
        token_sims = []
        for qt in q_tokens:
            best_sim = 0.0
            for pt in p_tokens:
                if qt == pt:
                    sim = 1.0
                elif len(qt) >= 4 and len(pt) >= 4 and (qt in pt or pt in qt):
                    sim = len(qt) / len(pt) if len(qt) < len(pt) else len(pt) / len(qt)
                else:
                    sim = difflib.SequenceMatcher(None, qt, pt).ratio()
                if sim > best_sim:
                    best_sim = sim
            token_sims.append(best_sim)

        max_sim = max(token_sims) if token_sims else 0.0
        strong_matches = [s for s in token_sims if s >= 0.70]

        if strong_matches:
            score = (max_sim * 0.6) + ((sum(strong_matches) / len(q_tokens)) * 0.4)
            if score >= 0.50:
                scored.append((score, p))
                seen_ids.add(p.id)

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]


class AutocompleteItem(BaseModel):
    id: Optional[int] = None
    title: str
    category: str
    price: float
    platform: str = "api_vendas"
    is_live_suggestion: bool = False


@router.get("/autocomplete", response_model=List[AutocompleteItem], summary="Autocompletar produtos do catálogo")
def autocomplete_products(
    q: str = Query(..., min_length=1, description="Termo de pesquisa"),
    limit: int = Query(8, ge=1, le=20, description="Quantidade máxima de recomendações"),
    db: Session = Depends(get_db)
):
    """Retorna sugestões do catálogo cadastrado com correspondência exata ou caracteres parecidos."""
    q_str = q.strip()
    prohibited = {
        "maconha", "cannabis", "cocaina", "crack", "lsd", "ecstasy", "mdma", "heroina", 
        "entorpecente", "droga", "drogas", "ozempic", "anabolizante", "anabolizantes", 
        "rivotril", "zolpidem", "ritalina", "venvanse", "vape", "vapes", "cigarro", "arma"
    }
    if any(p in q_str.lower() for p in prohibited):
        return []

    matched = search_catalog_products(q_str, db, limit=limit)
    return [
        AutocompleteItem(
            id=p.id,
            title=p.title,
            category=p.category or "Geral",
            price=p.price or 0.0,
            platform=p.platform,
            is_live_suggestion=False
        )
        for p in matched
    ]


@router.get("/{product_id}", response_model=ProductDetailResponse, summary="Obter detalhes de um produto específico")
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Retorna as informações completas de um produto e seu histórico recente."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    sales = db.query(SalesHistory)\
              .filter(SalesHistory.product_id == product_id)\
              .order_by(SalesHistory.date.desc())\
              .limit(30)\
              .all()

    sales_history_list = []
    total_units = 0
    total_rev = 0.0

    for s in reversed(sales):
        unit_price = s.price_at_date or prod.price or 0.0
        rev = round(s.quantity_sold * unit_price, 2)
        total_units += s.quantity_sold
        total_rev += rev

        sales_history_list.append(SalesHistoryResponse(
            id=s.id,
            product_id=s.product_id,
            date=s.date,
            quantity_sold=s.quantity_sold,
            price_at_date=unit_price,
            available_quantity=s.available_quantity,
            platform=s.platform,
            revenue=rev
        ))

    return ProductDetailResponse(
        id=prod.id,
        external_id=prod.external_id,
        platform=prod.platform,
        title=prod.title,
        category=prod.category,
        price=prod.price,
        currency=prod.currency,
        condition=prod.condition,
        url=prod.url,
        attributes=prod.attributes,
        is_active=prod.is_active,
        created_at=prod.created_at,
        total_sold_units=total_units,
        total_revenue=round(total_rev, 2),
        sales_history=sales_history_list
    )


@router.get("/{product_id}/history", response_model=List[SalesHistoryResponse], summary="Obter série temporal de vendas")
def get_product_sales_history(
    product_id: int,
    days: int = Query(30, ge=7, le=1000, description="Quantidade de dias históricos"),
    db: Session = Depends(get_db)
):
    """Retorna os dados cronológicos de vendas para alimentação de gráficos no frontend."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    sales = db.query(SalesHistory)\
              .filter(SalesHistory.product_id == product_id)\
              .order_by(SalesHistory.date.desc())\
              .limit(days)\
              .all()

    history = []
    for s in reversed(sales):
        price = s.price_at_date or prod.price or 0.0
        history.append(SalesHistoryResponse(
            id=s.id,
            product_id=s.product_id,
            date=s.date,
            quantity_sold=s.quantity_sold,
            price_at_date=price,
            available_quantity=s.available_quantity,
            platform=s.platform,
            revenue=round(s.quantity_sold * price, 2)
        ))
    return history


class DiscoverLiveRequest(BaseModel):
    query: str
    limit: int = 5


class DiscoverLiveResponse(BaseModel):
    query: str
    total_found: int
    products: List[ProductResponse]
    message: str


@router.post("/discover-live", response_model=DiscoverLiveResponse, summary="Buscar produtos no catálogo oficial")
def discover_live_products(
    request: DiscoverLiveRequest,
    db: Session = Depends(get_db)
):
    """Localiza produtos por termo ou caracteres similares no catálogo oficial."""
    query_str = request.query.strip()
    if not query_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um termo de busca.")

    matched_prods = search_catalog_products(query_str, db, limit=request.limit)

    if not matched_prods:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto '{query_str}' não encontrado no catálogo."
        )

    items = []
    for prod in matched_prods:
        sales_agg = db.query(
            func.sum(SalesHistory.quantity_sold).label("total_units"),
            func.sum(SalesHistory.quantity_sold * func.coalesce(SalesHistory.price_at_date, prod.price or 0.0)).label("total_rev")
        ).filter(SalesHistory.product_id == prod.id).first()

        total_units = int(sales_agg.total_units or 0)
        total_rev = float(sales_agg.total_rev or 0.0)

        items.append(ProductResponse(
            id=prod.id,
            external_id=prod.external_id,
            platform=prod.platform,
            title=prod.title,
            category=prod.category,
            price=prod.price,
            currency=prod.currency,
            condition=prod.condition,
            url=prod.url,
            attributes=prod.attributes,
            is_active=prod.is_active,
            created_at=prod.created_at,
            total_sold_units=total_units,
            total_revenue=round(total_rev, 2)
        ))

    return DiscoverLiveResponse(
        query=query_str,
        total_found=len(items),
        products=items,
        message=f"{len(items)} produto(s) encontrado(s) no catálogo."
    )


class SyncCategoriesResponse(BaseModel):
    status: str
    total_synced_products: int
    total_sales: int
    sample_products: List[str]
    message: str


@router.post("/sync-categories", response_model=SyncCategoriesResponse, summary="Sincronizar dados da API de Histórico de Vendas")
def sync_vendas_api_endpoint(
    min_date: str = Query("2024-01-01", description="Data inicial do histórico a importar (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Sincroniza o catálogo de produtos e séries de vendas da API do professor."""
    result = vendas_client.sync_to_trendecommerce(db, min_date=min_date)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao sincronizar com a API de Vendas: {result.get('error')}"
        )

    samples = [p.title for p in db.query(Product).limit(5).all()]

    return SyncCategoriesResponse(
        status="success",
        total_synced_products=result["total_products"],
        total_sales=result["total_sales"],
        sample_products=samples,
        message=f"{result['total_products']} produtos e {result['total_sales']:,} registros de vendas sincronizados com sucesso!"
    )
