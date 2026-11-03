from .auth_router import router as auth_router
from .products_router import router as products_router
from .forecast_router import router as forecast_router
from .opportunity_router import router as opportunity_router

__all__ = ["auth_router", "products_router", "forecast_router", "opportunity_router"]
