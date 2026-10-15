from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import pandas as pd

from src.database.connection import get_session
from src.database.models import Product, SalesHistory, SearchTrend, MarketplaceFeedback, MacroIndicator
from src.ml.opportunity_recommender import OpportunityRecommender

router = APIRouter(prefix="/api/v1/recommendations", tags=["Recomendações & Oportunidades"])


@router.get("/top-products")
def get_top_products_to_sell(
    days: int = Query(14, description="Horizonte de projeção em dias (7, 14 ou 30)"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    min_score: float = Query(0.0, description="Score mínimo de oportunidade (0 a 100)"),
    limit: int = Query(10, description="Limite de produtos retornados"),
    db: Session = Depends(get_session)
):
    """Retorna os melhores produtos para vender com base em demanda futura, tendências e margem."""
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

    # Buscar históricos de vendas recentes para estimar projeções
    sales = db.query(SalesHistory).all()
    sales_df = pd.DataFrame([{
        "product_id": s.product_id,
        "date": s.date,
        "quantity_sold": s.quantity_sold,
        "price": s.price_at_date or 100.0,
        "platform": s.platform
    } for s in sales])

    # Simular/Computar previsões agregadas por produto
    forecasts = {}
    for p_id in products_df["product_id"]:
        p_sales = sales_df[sales_df["product_id"] == p_id].sort_values("date")
        if len(p_sales) >= 14:
            recent_avg = p_sales["quantity_sold"].iloc[-7:].mean()
            prior_avg = p_sales["quantity_sold"].iloc[-14:-7].mean()
            growth = ((recent_avg - prior_avg) / max(1.0, prior_avg)) * 100.0
            pred_total = int(round(recent_avg * days * (1.0 + (growth / 200.0))))
            forecasts[p_id] = {
                "predicted_units": max(5, pred_total),
                "growth_pct": round(growth, 2)
            }
        else:
            forecasts[p_id] = {"predicted_units": 25, "growth_pct": 5.0}

    trends = db.query(SearchTrend).all()
    trends_df = pd.DataFrame([{
        "keyword": t.keyword,
        "interest_score": t.interest_score,
        "date": t.date
    } for t in trends]) if trends else None

    feedbacks = db.query(MarketplaceFeedback).all()
    feedbacks_df = pd.DataFrame([{
        "product_id": fb.product_id,
        "questions_count": fb.questions_count,
        "average_rating": fb.average_rating
    } for fb in feedbacks]) if feedbacks else None

    recommender = OpportunityRecommender()
    recommendations = recommender.evaluate_opportunities(
        products_df=products_df,
        forecasts=forecasts,
        trends_df=trends_df,
        feedbacks_df=feedbacks_df,
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
                "rationale": item.rationale,
                "metrics": item.metrics
            }
            for item in filtered
        ]
    }

@router.get("/macro-indicators")
def get_macro_indicators(db: Session = Depends(get_session)):
    """Retorna os indicadores macroeconômicos e feriados ativos no sistema."""
    indicators = db.query(MacroIndicator).order_by(MacroIndicator.date.desc()).limit(50).all()
    return {
        "count": len(indicators),
        "indicators": [
            {
                "date": ind.date.strftime("%Y-%m-%d"),
                "type": ind.indicator_type,
                "value": ind.value,
                "label": ind.label,
                "source": ind.source
            }
            for ind in indicators
        ]
    }