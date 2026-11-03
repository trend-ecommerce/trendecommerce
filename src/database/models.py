"""Modelos do banco de dados (SQLAlchemy ORM).

Define as tabelas utilizadas pelo TrendCommerce AI
para armazenar dados de usuários, produtos e histórico de vendas.
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
    """Tabela de produtos coletados.
    
    Armazena informações básicas de produtos de
    diferentes plataformas (Amazon, Mercado Livre, etc).
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), nullable=False, comment="ID do produto na plataforma de origem")
    platform = Column(String(50), nullable=False, comment="Plataforma de origem (amazon, mercadolivre)")
    title = Column(String(500), nullable=False)
    category = Column(String(255), nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String(10), default="BRL")
    condition = Column(String(50), nullable=True)
    url = Column(Text, nullable=True)
    attributes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relacionamentos
    sales_history = relationship("SalesHistory", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_products_platform", "platform"),
        Index("idx_products_category", "category"),
        Index("idx_products_external_id", "external_id", "platform", unique=True),
    )

    def __repr__(self):
        return f"<Product(id={self.id}, title='{self.title[:50]}', platform='{self.platform}')>"


class SalesHistory(Base):
    """Tabela de histórico de vendas.
    
    Registra a evolução das vendas ao longo do tempo.
    Permite calcular crescimento, média móvel, tendência,
    sazonalidade e variação.
    """
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    quantity_sold = Column(Integer, default=0)
    price_at_date = Column(Float, nullable=True)
    available_quantity = Column(Integer, nullable=True)
    platform = Column(String(50), nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    product = relationship("Product", back_populates="sales_history")

    __table_args__ = (
        Index("idx_sales_product_date", "product_id", "date"),
        Index("idx_sales_platform", "platform"),
        Index("idx_sales_date", "date"),
    )

    def __repr__(self):
        return f"<SalesHistory(product_id={self.product_id}, date={self.date}, qty={self.quantity_sold})>"
