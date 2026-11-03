from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.database.models import Product, SalesHistory
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
    platform: Optional[str] = Query(None, description="Filtro de plataforma"),
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


@router.get("/categories", response_model=List[str], summary="Listar categorias de produtos")
def get_categories(db: Session = Depends(get_db)):
    """Retorna lista de categorias cadastradas na base."""
    categories = db.query(Product.category).filter(Product.category.isnot(None), Product.is_active.is_(True)).distinct().all()
    unique_cats = sorted(list({c[0] for c in categories if c[0]}))
    return unique_cats if unique_cats else ["Geral", "Tecnologia", "Moda", "Casa e Móveis"]


@router.get("/top-sales", response_model=List[TopProductItem], summary="Ranking dos produtos mais vendidos no mês")
def get_top_selling_products(
    limit: int = Query(10, ge=1, le=50, description="Quantidade de produtos no ranking"),
    category: Optional[str] = Query(None, description="Filtro opcional de categoria"),
    days: int = Query(30, ge=1, le=365, description="Janela de dias para apuração de vendas (padrão: 30 dias)"),
    db: Session = Depends(get_db)
):
    """Retorna os produtos com maior volume de vendas apuradas no período."""
    latest_date = db.query(func.max(SalesHistory.date)).scalar()

    query = db.query(
        Product.id,
        Product.title,
        Product.category,
        Product.price,
        func.sum(SalesHistory.quantity_sold).label("total_sold"),
        func.sum(SalesHistory.quantity_sold * func.coalesce(SalesHistory.price_at_date, Product.price)).label("total_revenue")
    ).join(SalesHistory, Product.id == SalesHistory.product_id)

    if latest_date and days > 0:
        start_date = latest_date - timedelta(days=days)
        query = query.filter(SalesHistory.date >= start_date)

    if category and category.strip().upper() not in ["GERAIS", "GERAL", "TODAS", "TODOS"]:
        query = query.filter(Product.category == category.strip())
        results = query.group_by(Product.id, Product.title, Product.category, Product.price)\
                       .order_by(desc("total_sold"))\
                       .limit(limit)\
                       .all()

        items = []
        for rank, (p_id, title, cat, price, total_sold, total_rev) in enumerate(results, start=1):
            items.append(TopProductItem(
                rank=rank,
                id=p_id,
                title=title,
                category=cat or "Geral",
                price=float(price or 0.0),
                quantity_sold=int(total_sold or 0),
                revenue=round(float(total_rev or 0.0), 2)
            ))
        return items

    # Modo GERAIS: Seleciona o Top 1 mais vendido de cada nicho/categoria
    all_results = query.group_by(Product.id, Product.title, Product.category, Product.price)\
                       .order_by(desc("total_sold"))\
                       .all()

    seen_cats = set()
    items = []
    rank = 1
    for p_id, title, cat, price, total_sold, total_rev in all_results:
        clean_cat = cat or "Geral"
        if clean_cat not in seen_cats:
            seen_cats.add(clean_cat)
            items.append(TopProductItem(
                rank=rank,
                id=p_id,
                title=title,
                category=clean_cat,
                price=float(price or 0.0),
                quantity_sold=int(total_sold or 0),
                revenue=round(float(total_rev or 0.0), 2)
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
    platform: str = "ecommerce"
    is_live_suggestion: bool = False


@router.get("/autocomplete", response_model=List[AutocompleteItem], summary="Autocompletar de produtos")
def autocomplete_products(
    q: str = Query(..., min_length=1, description="Termo de pesquisa"),
    limit: int = Query(8, ge=1, le=20, description="Quantidade máxima de recomendações"),
    db: Session = Depends(get_db)
):
    """Retorna sugestões de produtos a partir da base de dados interna."""
    query = f"%{q.strip()}%"
    prods = db.query(Product).filter(
        (Product.title.ilike(query)) | (Product.category.ilike(query)),
        Product.is_active.is_(True)
    ).limit(limit).all()

    return [
        AutocompleteItem(
            id=p.id,
            title=p.title,
            category=p.category or "Geral",
            price=p.price or 0.0,
            platform=p.platform or "ecommerce",
            is_live_suggestion=False
        )
        for p in prods
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
    days: int = Query(30, ge=7, le=365, description="Quantidade de dias históricos"),
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


class CreateProductRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    category: str = Field(..., min_length=2, max_length=255)
    price: float = Field(..., gt=0)
    platform: Optional[str] = "ecommerce"
    currency: Optional[str] = "BRL"
    condition: Optional[str] = "new"
    url: Optional[str] = None


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo produto")
def create_product(payload: CreateProductRequest, db: Session = Depends(get_db)):
    """Cadastra um novo produto no catálogo interno."""
    new_prod = Product(
        external_id=f"INT_{int(datetime.utcnow().timestamp())}",
        platform=payload.platform or "ecommerce",
        title=payload.title,
        category=payload.category,
        price=payload.price,
        currency=payload.currency or "BRL",
        condition=payload.condition or "new",
        url=payload.url,
        is_active=True
    )
    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)

    return ProductResponse(
        id=new_prod.id,
        external_id=new_prod.external_id,
        platform=new_prod.platform,
        title=new_prod.title,
        category=new_prod.category,
        price=new_prod.price,
        currency=new_prod.currency,
        condition=new_prod.condition,
        url=new_prod.url,
        attributes=new_prod.attributes,
        is_active=new_prod.is_active,
        created_at=new_prod.created_at,
        total_sold_units=0,
        total_revenue=0.0
    )


class CreateSaleRequest(BaseModel):
    date: Optional[datetime] = None
    quantity_sold: int = Field(..., gt=0)
    price_at_date: Optional[float] = None
    available_quantity: Optional[int] = None


@router.post("/{product_id}/sales", response_model=SalesHistoryResponse, status_code=status.HTTP_201_CREATED, summary="Registrar venda para um produto")
def record_sale(product_id: int, payload: CreateSaleRequest, db: Session = Depends(get_db)):
    """Registra uma venda no histórico de um produto."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    sale_date = payload.date or datetime.utcnow()
    unit_price = payload.price_at_date if payload.price_at_date is not None else (prod.price or 0.0)

    sale = SalesHistory(
        product_id=prod.id,
        date=sale_date,
        quantity_sold=payload.quantity_sold,
        price_at_date=unit_price,
        available_quantity=payload.available_quantity,
        platform=prod.platform,
        collected_at=datetime.utcnow()
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)

    return SalesHistoryResponse(
        id=sale.id,
        product_id=sale.product_id,
        date=sale.date,
        quantity_sold=sale.quantity_sold,
        price_at_date=unit_price,
        available_quantity=sale.available_quantity,
        platform=sale.platform,
        revenue=round(sale.quantity_sold * unit_price, 2)
    )
