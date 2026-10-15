"""Módulo de coletores de dados do TrendCommerce AI.

Responsável por acessar as APIs autorizadas e coletar dados
de diferentes plataformas de e-commerce.
"""

from .base_collector import BaseCollector, CollectorResult
from .amazon_collector import AmazonCollector
from .mercadolivre_collector import MercadoLivreCollector
from .google_trends_collector import GoogleTrendsCollector

__all__ = [
    "BaseCollector",
    "CollectorResult",
    "AmazonCollector",
    "MercadoLivreCollector",
    "GoogleTrendsCollector",
]
