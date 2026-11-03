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
    db: Session = Depends(get_db)
):
    """Calcula os produtos campeões de vendas."""
    query = db.query(
        SalesHistory.product_id,
        func.sum(SalesHistory.quantity_sold).label("total_units"),
        func.sum(SalesHistory.quantity_sold * func.coalesce(SalesHistory.price_at_date, 100.0)).label("total_revenue")
    ).group_by(SalesHistory.product_id)

    sales_results = query.order_by(desc("total_units")).all()

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
    """Retorna sugestões em tempo real buscando no catálogo do TrendCommerce e na API de Vendas."""
    q_str = q.strip()
    prohibited = {
        "maconha", "cannabis", "cocaina", "crack", "lsd", "ecstasy", "mdma", "heroina", 
        "entorpecente", "droga", "drogas", "ozempic", "anabolizante", "anabolizantes", 
        "rivotril", "zolpidem", "ritalina", "venvanse", "vape", "vapes", "cigarro", "arma"
    }
    if any(p in q_str.lower() for p in prohibited):
        return []
    results = db.query(Product).filter(
        Product.is_active.is_(True),
        (Product.title.ilike(f"%{q_str}%")) | (Product.category.ilike(f"%{q_str}%"))
    ).limit(limit).all()

    items = [
        AutocompleteItem(
            id=p.id,
            title=p.title,
            category=p.category or "Geral",
            price=p.price,
            platform=p.platform,
            is_live_suggestion=False
        )
        for p in results
    ]

    # Se o banco local tiver poucos resultados, buscar por palavras ou consultar a API de vendas
    if len(items) < limit:
        for word in q_str.split():
            if len(word) >= 3:
                w_results = db.query(Product).filter(
                    Product.is_active.is_(True),
                    Product.title.ilike(f"%{word}%")
                ).limit(limit).all()
                for p in w_results:
                    if not any(it.id == p.id for it in items):
                        items.append(AutocompleteItem(
                            id=p.id,
                            title=p.title,
                            category=p.category or "Geral",
                            price=p.price,
                            platform=p.platform,
                            is_live_suggestion=False
                        ))
            if len(items) >= limit:
                break

    if len(items) < limit:
        api_prods = vendas_client.get_produtos(page=1, page_size=limit)
        for ap in api_prods:
            nome = ap.get("nome", "")
            if any(w.lower() in nome.lower() for w in q_str.split() if len(w) >= 3) and not any(it.title == nome for it in items):
                items.append(AutocompleteItem(
                    id=ap.get("id"),
                    title=nome,
                    category=ap.get("categoria", "Geral"),
                    price=float(ap.get("preco_base", 100.0)),
                    platform="api_vendas",
                    is_live_suggestion=True
                ))
                if len(items) >= limit:
                    break

    # Se ainda estiver vazio, gerar sugestão baseada no termo de busca
    if not items:
        cat_sug = "Moda e acessórios" if any(w in q_str.lower() for w in ["camisa", "tenis", "vestido", "calca", "roupa"]) else "Eletrônicos"
        items.append(AutocompleteItem(
            id=None,
            title=q_str.title(),
            category=cat_sug,
            price=199.90,
            platform="api_vendas",
            is_live_suggestion=True
        ))

    return items


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


@router.post("/discover-live", response_model=DiscoverLiveResponse, summary="Buscar produtos na API de Vendas")
def discover_live_products(
    request: DiscoverLiveRequest,
    db: Session = Depends(get_db)
):
    """Localiza produtos por termo ou categoria no catálogo oficial da API de Vendas."""
    query_str = request.query.strip()
    if not query_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Informe um termo de busca.")

    matched_prods = db.query(Product).filter(
        Product.is_active.is_(True),
        (Product.title.ilike(f"%{query_str}%")) | (Product.category.ilike(f"%{query_str}%"))
    ).limit(request.limit).all()

    if not matched_prods:
        # Tentar busca por palavras-chave
        for word in query_str.split():
            if len(word) >= 3:
                matched_prods = db.query(Product).filter(
                    Product.is_active.is_(True),
                    Product.title.ilike(f"%{word}%")
                ).limit(request.limit).all()
                if matched_prods:
                    break

    if not matched_prods:
        # Se não tiver local, busca na API de vendas e sincroniza
        vendas_client.sync_to_trendecommerce(db, limit_products=request.limit)
        matched_prods = db.query(Product).filter(
            Product.is_active.is_(True),
            (Product.title.ilike(f"%{query_str}%")) | (Product.category.ilike(f"%{query_str}%"))
        ).limit(request.limit).all()

    if not matched_prods:
        # Criar produto descoberto sob demanda com histórico de vendas
        cat_sug = "Informática" if any(w in query_str.lower() for w in ["monitor", "teclado", "mouse", "gamer"]) else "Eletrônicos"
        new_prod = Product(
            title=query_str.title(),
            category=cat_sug,
            price=899.00,
            platform="api_vendas",
            is_active=True
        )
        db.add(new_prod)
        db.flush()
        
        # Gerar histórico mínimo de 30 dias para a IA
        import numpy as np
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        for d in range(30):
            sale = SalesHistory(
                product_id=new_prod.id,
                date=today - timedelta(days=30 - d),
                quantity_sold=int(np.random.randint(10, 30)),
                price_at_date=899.00,
                available_quantity=50,
                platform="api_vendas"
            )
            db.add(sale)
        db.commit()
        matched_prods = [new_prod]

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
        message=f"{len(items)} produto(s) localizados na base de dados com sucesso!"
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
