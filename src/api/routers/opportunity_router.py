from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
import pandas as pd

from src.database.connection import get_session
from src.database.models import Product, SalesHistory
from src.features.feature_engineering import FeatureEngineer
from src.ml.opportunity_recommender import OpportunityRecommender

router = APIRouter(prefix="/recommendations", tags=["Recomendações & Oportunidades"])


@router.get("/top-products")
def get_top_products_to_sell(
    days: int = Query(14, description="Horizonte de projeção em dias (7, 14 ou 30)"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    min_score: float = Query(0.0, description="Score mínimo de oportunidade (0 a 100)"),
    limit: int = Query(10, description="Limite de produtos retornados"),
    db: Session = Depends(get_session)
):
    """Retorna os melhores produtos para vender com base em demanda futura e margem."""
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

    date_bounds = db.query(
        func.min(func.date(SalesHistory.date)),
        func.max(func.date(SalesHistory.date)),
    ).first()

    sales_df = pd.DataFrame()
    if date_bounds and date_bounds[0] and date_bounds[1]:
        db_min_dt = pd.Timestamp(str(date_bounds[0])[:10])
        db_max_dt = pd.Timestamp(str(date_bounds[1])[:10])
        today_local = pd.Timestamp(datetime.now().date())
        cutoff_dt = min(today_local, db_max_dt) if today_local >= db_min_dt else db_max_dt
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
        start_dt = cutoff_dt - pd.Timedelta(days=60)
        start_str = start_dt.strftime("%Y-%m-%d")

        rows = (
            db.query(
                SalesHistory.product_id,
                SalesHistory.date,
                SalesHistory.quantity_sold,
                SalesHistory.price_at_date,
                SalesHistory.platform,
            )
            .filter(
                SalesHistory.date >= (start_dt.to_pydatetime() - timedelta(days=1)),
                SalesHistory.date <= (cutoff_dt.to_pydatetime() + timedelta(days=1)),
                func.date(SalesHistory.date) >= start_str,
                func.date(SalesHistory.date) <= cutoff_str,
            )
            .all()
        )
        if rows:
            sales_df = pd.DataFrame([
                {
                    "product_id": r[0],
                    "date": r[1],
                    "quantity_sold": r[2],
                    "price": r[3] or 100.0,
                    "platform": r[4],
                }
                for r in rows
            ])
            sales_df["date"] = pd.to_datetime(sales_df["date"])

    grouped_sales = (
        {int(pid): grp for pid, grp in sales_df.sort_values("date").groupby("product_id")}
        if not sales_df.empty
        else {}
    )

    forecasts = {}
    for p_id in products_df["product_id"]:
        p_sales = grouped_sales.get(int(p_id), pd.DataFrame())
        if len(p_sales) >= 14:
            clean_qty = FeatureEngineer.sanitize_sales_series(p_sales["quantity_sold"])
            recent_avg = clean_qty.iloc[-7:].mean()
            prior_avg = clean_qty.iloc[-14:-7].mean()
            growth = ((recent_avg - prior_avg) / max(1.0, prior_avg)) * 100.0
            pred_total = int(round(recent_avg * days * (1.0 + (growth / 200.0))))
            forecasts[p_id] = {
                "predicted_units": max(5, pred_total),
                "growth_pct": round(growth, 2)
            }
        else:
            forecasts[p_id] = {"predicted_units": 25, "growth_pct": 5.0}

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