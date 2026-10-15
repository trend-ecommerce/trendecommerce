"""Módulo de banco de dados do TrendCommerce AI.

Utiliza PostgreSQL para armazenar dados coletados
e manter histórico para treinamento do modelo.
"""

from .connection import get_engine, get_session, DatabaseManager
from .models import Base, Product, SalesHistory, SearchTrend, CollectionLog, PredictionLog

__all__ = [
    "get_engine",
    "get_session",
    "DatabaseManager",
    "Base",
    "Product",
    "SalesHistory",
    "SearchTrend",
    "CollectionLog",
    "PredictionLog",
]
