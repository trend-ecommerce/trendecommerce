"""Módulo de banco de dados do TrendCommerce AI."""

from .connection import get_engine, get_session, DatabaseManager
from .models import Base, User, Product, SalesHistory

__all__ = [
    "get_engine",
    "get_session",
    "DatabaseManager",
    "Base",
    "User",
    "Product",
    "SalesHistory",
]
