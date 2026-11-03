"""Módulo de banco de dados do TrendCommerce AI.

Gerencia a conexão e os modelos de Usuários, Produtos e Histórico de Vendas.
"""

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
