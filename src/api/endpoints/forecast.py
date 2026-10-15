"""Endpoints de previsão de demanda."""

from fastapi import APIRouter, HTTPException, Query
from src.database.setup import get_db_manager
from src.services.forecast_service import ForecastService

router = APIRouter()


@router.get("/{product_id}", summary="Previsão de Demanda por Produto")
def get_product_forecast(
    product_id: int,
    days: int = Query(default=7, ge=1, le=30, description="Horizonte de previsão em dias")
):
    manager = get_db_manager()
    service = ForecastService(db_manager=manager)
    forecast = service.get_forecast_for_product(product_id, horizon_days=days)
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Produto não encontrado ou sem dados suficientes")
    
    return forecast