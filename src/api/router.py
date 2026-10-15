"""Roteador principal agregando todas as rotas v1."""

from fastapi import APIRouter
from src.api.endpoints import auth, products, forecast, recommendations

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(products.router, prefix="/products", tags=["Produtos"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Previsões de Demanda"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recomendações"])