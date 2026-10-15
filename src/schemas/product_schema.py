"""Schemas Pydantic para Produtos e Histórico de Vendas."""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class SalesHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    date: datetime
    quantity_sold: int
    price_at_date: Optional[float] = None
    available_quantity: Optional[int] = None
    platform: str
    revenue: Optional[float] = Field(None, description="Faturamento diário (quantidade * preço)")


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    platform: str
    title: str
    category: Optional[str] = None
    price: Optional[float] = None
    currency: str = "BRL"
    condition: Optional[str] = None
    url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    total_sold_units: Optional[int] = 0
    total_revenue: Optional[float] = 0.0



class ProductDetailResponse(ProductResponse):
    sales_history: List[SalesHistoryResponse] = []


class ProductListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    items: List[ProductResponse]


class TopProductItem(BaseModel):
    rank: int
    id: int
    title: str
    category: Optional[str] = None
    price: float
    quantity_sold: int
    revenue: float
