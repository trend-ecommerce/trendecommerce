"""Schemas Pydantic para Previsões de Demanda e Motor ML (XGBoost)."""

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    product_id: int = Field(..., description="ID do produto no banco de dados")
    horizon_days: Literal[7, 14, 30] = Field(7, description="Horizonte de previsão em dias (7, 14 ou 30)")


class DailyForecastItem(BaseModel):
    date: str
    day_name: str
    predicted_demand: int
    confidence_min: int
    confidence_max: int
    projected_revenue: float


class ExplanationFactor(BaseModel):
    name: str
    weight_pct: int
    impact: str
    description: str


class ForecastExplanation(BaseModel):
    summary: str
    primary_driver: str
    factors: List[ExplanationFactor]


class ProductForecastResponse(BaseModel):
    product_id: int
    product_title: str
    category: str
    unit_price: float
    horizon_days: int
    start_date: str
    end_date: str
    total_predicted_units: int
    min_predicted_units: int
    max_predicted_units: int
    total_projected_revenue: float
    daily_average: float
    recommended_stock_buffer: int
    days: List[DailyForecastItem]
    explanation: Optional[ForecastExplanation] = None


class ForecastSummaryResponse(BaseModel):
    horizon_days: int
    total_products: int
    total_projected_revenue: float
    total_predicted_units: int
    items: List[ProductForecastResponse]


class RankingForecastItem(BaseModel):
    rank: int
    product_id: int
    title: str
    category: str
    price: float
    projected_units: int
    projected_revenue: float
    rank_reason: Optional[str] = None
    key_driver: Optional[str] = None


class ForecastRankingResponse(BaseModel):
    horizon_days: int
    top_overall: List[RankingForecastItem]
    top_by_category: Dict[str, List[RankingForecastItem]]


class CompareForecastRequest(BaseModel):
    product_id_a: int
    product_id_b: int
    horizon_days: Literal[7, 14, 30] = 30


class CompareForecastResponse(BaseModel):
    horizon_days: int
    product_a: ProductForecastResponse
    product_b: ProductForecastResponse
    revenue_difference: float
    revenue_leader: str
    demand_difference: int
    demand_leader: str
    verdict: str
