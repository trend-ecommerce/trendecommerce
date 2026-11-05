import pytest
import pandas as pd
from src.ml.opportunity_recommender import OpportunityRecommender


def test_opportunity_recommender_evaluation():
    products_df = pd.DataFrame([
        {"product_id": 1, "title": "Notebook Dell i7", "category": "Informática", "platform": "api_vendas", "price": 3500.0},
        {"product_id": 2, "title": "Fone Bluetooth", "category": "Áudio", "platform": "api_vendas", "price": 150.0},
    ])

    forecasts = {
        1: {"predicted_units": 45, "growth_pct": 25.0},
        2: {"predicted_units": 10, "growth_pct": -5.0},
    }

    recommender = OpportunityRecommender()
    results = recommender.evaluate_opportunities(products_df, forecasts, horizon_days=14)

    assert len(results) == 2
    # O produto com alto crescimento deve liderar o score de oportunidade
    assert results[0].product_id == 1
    assert results[0].opportunity_score > results[1].opportunity_score
    assert results[0].recommended_stock >= results[0].predicted_units
    assert results[0].estimated_revenue > 0
