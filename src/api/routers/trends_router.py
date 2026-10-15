from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from src.api.dependencies import get_db
from src.database.models import SearchTrend

router = APIRouter(prefix="/trends", tags=["Tendências de Mercado"])


class TrendItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keyword: str
    date: datetime
    interest_score: int
    source: str
    is_mock: bool



@router.get("/search", response_model=List[TrendItemResponse], summary="Buscar histórico de tendências de pesquisa")
def search_trends(
    keyword: Optional[str] = Query(None, description="Palavra-chave a buscar"),
    limit: int = Query(30, ge=1, le=100, description="Quantidade de registros"),
    db: Session = Depends(get_db)
):
    """Retorna dados de volume e interesse de busca ao longo do tempo."""
    query = db.query(SearchTrend)
    if keyword:
        query = query.filter(SearchTrend.keyword.ilike(f"%{keyword}%"))

    trends = query.order_by(SearchTrend.date.desc()).limit(limit).all()
    return trends
