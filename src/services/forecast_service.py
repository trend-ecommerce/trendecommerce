"""Serviço de orquestração de previsões para a API."""

import logging
from typing import Optional
import pandas as pd

from src.database.connection import DatabaseManager
from src.database.models import Product, SalesHistory
from src.ml.future_forecaster import FutureForecaster, ProductFutureForecast

logger = logging.getLogger(__name__)


class ForecastService:
    """Conecta a camada de banco de dados e ML para gerar previsões de demanda."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.forecaster = FutureForecaster(db_manager=db_manager)

    def get_forecast_for_product(self, product_id: int, horizon_days: int = 7) -> Optional[ProductFutureForecast]:
        """Obtém a previsão futura para um único produto."""
        with self.db_manager.session() as session:
            product = session.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
            if not product:
                return None

            sales = session.query(SalesHistory).filter(SalesHistory.product_id == product_id).all()
            
            product_series = pd.Series({
                "product_id": product.id,
                "title": product.title,
                "category": product.category,
                "price": product.price
            })

            sales_df = pd.DataFrame([{
                "product_id": s.product_id,
                "date": s.date,
                "quantity_sold": s.quantity_sold,
                "price": s.price_at_date
            } for s in sales])

            products_df = pd.DataFrame([product_series.to_dict()])
            if not sales_df.empty:
                self.forecaster.train_model(products_df, sales_df)
                return self.forecaster.forecast_product(product_series, sales_df, horizon_days=horizon_days)
            return None