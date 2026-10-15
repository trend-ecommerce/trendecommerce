"""Motor de recomendação e matriz de oportunidades comerciais."""

import logging
from dataclasses import dataclass
from typing import Any, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ProductOpportunityItem:
    product_id: int
    title: str
    category: str
    platform: str
    price: float
    horizon_days: int
    predicted_units: int
    projected_growth_pct: float
    opportunity_score: float
    quadrant: str
    estimated_revenue: float
    recommended_stock: int
    rationale: str


class OpportunityRecommender:
    """Classifica produtos nos quadrantes de oportunidade estratégica."""

    QUADRANT_EXPLOSIVE = "OPORTUNIDADE_EXPLOSIVA"
    QUADRANT_STABILITY = "ALTA_RENTABILIDADE"
    QUADRANT_MODERATE = "DEMANDA_MODERADA"
    QUADRANT_LOW = "BAIXA_PRIORIDADE"

    def evaluate_opportunities(
        self,
        products_df: pd.DataFrame,
        forecasts: dict[int, dict[str, Any]],
        horizon_days: int = 14
    ) -> list[ProductOpportunityItem]:
        """Calcula o índice de oportunidade (POI) de cada produto."""
        recommendations = []

        for _, prod in products_df.iterrows():
            p_id = int(prod["product_id"])
            title = str(prod["title"])
            price = float(prod.get("price", 100.0))
            
            f_info = forecasts.get(p_id, {"predicted_units": 15, "growth_pct": 5.0})
            pred_units = int(f_info["predicted_units"])
            growth_pct = float(f_info["growth_pct"])

            score = min(99.0, max(10.0, 50.0 + (growth_pct * 2.0) + (pred_units * 0.5)))
            
            if score >= 75.0 and growth_pct > 8.0:
                quadrant = self.QUADRANT_EXPLOSIVE
                rationale = "Forte aceleração de vendas com alta tração de mercado."
            elif score >= 60.0:
                quadrant = self.QUADRANT_STABILITY
                rationale = "Demanda estável, previsível e altamente rentável."
            elif score >= 40.0:
                quadrant = self.QUADRANT_MODERATE
                rationale = "Desempenho moderado, manter estoque padrão de giro."
            else:
                quadrant = self.QUADRANT_LOW
                rationale = "Baixa procura relativa, evitar estocagem em excesso."

            recommendations.append(ProductOpportunityItem(
                product_id=p_id,
                title=title,
                category=str(prod.get("category", "Geral")),
                platform=str(prod.get("platform", "mercadolivre")),
                price=price,
                horizon_days=horizon_days,
                predicted_units=pred_units,
                projected_growth_pct=round(growth_pct, 2),
                opportunity_score=round(score, 1),
                quadrant=quadrant,
                estimated_revenue=round(pred_units * price, 2),
                recommended_stock=int(np.ceil(pred_units * 1.2)),
                rationale=rationale
            ))

        recommendations.sort(key=lambda x: x.opportunity_score, reverse=True)
        return recommendations