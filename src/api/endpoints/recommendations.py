"""Endpoints de recomendações de oportunidade."""

from fastapi import APIRouter, Query
from src.database.setup import get_db_manager
from src.services.recommendation_service import RecommendationService

router = APIRouter()


@router.get("/opportunities", summary="Ranking de Oportunidades Comerciais")
def get_opportunity_recommendations(
    horizon: int = Query(default=14, ge=7, le=30, description="Horizonte de análise em dias")
):
    manager = get_db_manager()
    service = RecommendationService(db_manager=manager)
    return service.get_opportunities(horizon_days=horizon)