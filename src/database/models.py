"""Modelos do banco de dados (SQLAlchemy ORM).

Define as tabelas essenciais utilizadas pelo TrendCommerce AI
para armazenar usuários, catálogo de produtos e histórico de vendas.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, 
    Boolean, ForeignKey, Index, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Tabela de usuários para autenticação e controle de acesso."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"


class Product(Base):
    """Tabela de produtos do catálogo."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), nullable=True, default="", comment="ID ou SKU do produto")
    platform = Column(String(50), default="proprio", comment="Origem do produto ou canal")
    title = Column(String(500), nullable=False)
    category = Column(String(255), nullable=True)
    price = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="BRL")
    condition = Column(String(50), default="new")
    url = Column(Text, nullable=True)
    attributes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relacionamento 1 para N com Histórico de Vendas
    sales_history = relationship("SalesHistory", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_products_category", "category"),
        Index("idx_products_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, title='{self.title[:50]}', price={self.price})>"


class SalesHistory(Base):
    """Tabela de histórico de vendas diárias.
    
    Registra a evolução das vendas e preços praticados ao longo do tempo.
    Permite calcular crescimento, sazonalidade, faturamento e alimentar
    os modelos preditivos de Machine Learning (XGBoost).
    """
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    quantity_sold = Column(Integer, default=0)
    price_at_date = Column(Float, nullable=False, default=0.0)
    available_quantity = Column(Integer, nullable=True, default=0)
    platform = Column(String(50), default="proprio")
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento de volta para o Produto
    product = relationship("Product", back_populates="sales_history")

    __table_args__ = (
        Index("idx_sales_product_date", "product_id", "date"),
        Index("idx_sales_date", "date"),
    )

    def __repr__(self):
        return f"<SalesHistory(product_id={self.product_id}, date={self.date}, qty={self.quantity_sold}, price={self.price_at_date})>"
