from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import numpy as np
import pandas as pd

from src.api.dependencies import get_db, get_ml_forecaster
from src.database.models import Product, SalesHistory
from src.ml.opportunity_recommender import OpportunityRecommender
from src.ml.future_forecaster import FutureForecaster

router = APIRouter(prefix="/recommendations", tags=["Recomendações & Oportunidades"])


@router.get("/top-products")
def get_top_products_to_sell(
    days: int = Query(14, description="Horizonte de projeção em dias (7, 14 ou 30)"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    min_score: float = Query(0.0, description="Score mínimo de oportunidade (0 a 100)"),
    limit: int = Query(10, description="Limite de produtos retornados"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Retorna os melhores produtos para vender conectados à matriz de saída preditiva real do XGBoost."""
    products_query = db.query(Product).filter(Product.is_active == True)
    if category:
        products_query = products_query.filter(Product.category.ilike(f"%{category}%"))
    products = products_query.all()

    if not products:
        return {"total": 0, "horizon_days": days, "items": []}

    products_df = pd.DataFrame([{
        "product_id": p.id,
        "title": p.title,
        "category": p.category,
        "platform": p.platform,
        "price": p.price
    } for p in products])

    sales = db.query(SalesHistory).all()
    sales_df = pd.DataFrame([{
        "product_id": s.product_id,
        "date": s.date,
        "quantity_sold": s.quantity_sold,
        "price": s.price_at_date or 100.0,
        "platform": s.platform
    } for s in sales])

    # 1. Projeção com o motor XGBoost real
    forecast_results = forecaster.forecast_all_products(
        products_df=products_df,
        sales_df=sales_df,
        horizon_days=days
    )

    # 2. Extração de aceleração/crescimento real recente %
    growth_map = {}
    for pid, grp in sales_df.groupby("product_id"):
        grp_sorted = grp.sort_values("date")
        qty = grp_sorted["quantity_sold"].values
        if len(qty) >= 14:
            recent = float(np.mean(qty[-7:]))
            prior = float(np.mean(qty[-14:-7]))
            growth = ((recent - prior) / max(1.0, prior)) * 100.0
        else:
            growth = 5.0
        growth_map[int(pid)] = growth

    forecasts = {
        f.product_id: {
            "predicted_units": f.total_predicted_units,
            "growth_pct": round(growth_map.get(f.product_id, 5.0), 2)
        }
        for f in forecast_results
    }

    recommender = OpportunityRecommender()
    recommendations = recommender.evaluate_opportunities(
        products_df=products_df,
        forecasts=forecasts,
        horizon_days=days
    )

    filtered = [r for r in recommendations if r.opportunity_score >= min_score][:limit]

    return {
        "total_analyzed": len(recommendations),
        "total_returned": len(filtered),
        "horizon_days": days,
        "top_recommendation": filtered[0].title if filtered else None,
        "items": [
            {
                "product_id": item.product_id,
                "title": item.title,
                "category": item.category,
                "platform": item.platform,
                "price": item.price,
                "opportunity_score": item.opportunity_score,
                "quadrant": item.quadrant,
                "predicted_units": item.predicted_units,
                "projected_growth_pct": item.projected_growth_pct,
                "estimated_revenue": item.estimated_revenue,
                "recommended_stock": item.recommended_stock,
                "rationale": item.rationale
            }
            for item in filtered
        ]
    }
