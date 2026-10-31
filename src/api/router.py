"""Roteador principal agregando todas as rotas v1 do TrendEcommerce AI."""

from fastapi import APIRouter
from src.api.routers import (
    auth_router,
    products_router,
    forecast_router,
    trends_router,
    opportunity_router
)

api_router = APIRouter(prefix="/v1")

# Roteadores completos com suporte total à modelagem XGBoost, produtos e autenticação
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(forecast_router)
api_router.include_router(trends_router)
api_router.include_router(opportunity_router)
