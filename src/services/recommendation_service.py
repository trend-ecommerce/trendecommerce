"""Serviço de inteligência de recomendações para a API."""

import logging
import pandas as pd
from src.database.connection import DatabaseManager
from src.database.models import Product, SalesHistory
from src.ml.opportunity_recommender import OpportunityRecommender, ProductOpportunityItem

logger = logging.getLogger(__name__)


class RecommendationService:
    """Gerencia as análises estratégicas do catálogo."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.recommender = OpportunityRecommender()

    def get_opportunities(self, horizon_days: int = 14) -> list[ProductOpportunityItem]:
        """Obtém o ranking de oportunidades do catálogo."""
        with self.db_manager.session() as session:
            products = session.query(Product).filter(Product.is_active == True).all()
            if not products:
                return []

            products_df = pd.DataFrame([{
                "product_id": p.id,
                "title": p.title,
                "category": p.category,
                "platform": p.platform,
                "price": p.price
            } for p in products])

            sales = session.query(SalesHistory).all()
            sales_df = pd.DataFrame([{
                "product_id": s.product_id,
                "date": s.date,
                "quantity_sold": s.quantity_sold
            } for s in sales])

            forecasts = {}
            for p_id in products_df["product_id"]:
                p_sales = sales_df[sales_df["product_id"] == p_id].sort_values("date")
                if len(p_sales) >= 7:
                    recent = p_sales["quantity_sold"].tail(7).mean()
                    forecasts[p_id] = {
                        "predicted_units": max(5, int(recent * horizon_days)),
                        "growth_pct": 8.5
                    }
                else:
                    forecasts[p_id] = {"predicted_units": 15, "growth_pct": 3.0}

            return self.recommender.evaluate_opportunities(products_df, forecasts, horizon_days=horizon_days)