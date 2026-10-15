"""Modelos do banco de dados (SQLAlchemy ORM).

Define as tabelas utilizadas pelo TrendCommerce AI
para armazenar dados coletados e histórico.
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
    prediction_logs = relationship("PredictionLog", back_populates="product", cascade="all, delete-orphan")
    marketplace_feedbacks = relationship("MarketplaceFeedback", back_populates="product", cascade="all, delete-orphan")
    opportunities = relationship("ProductOpportunity", back_populates="product", cascade="all, delete-orphan")

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


class SearchTrend(Base):
    """Tabela de tendências de pesquisa.
    
    Armazena dados de interesse/pesquisa ao longo do tempo.
    Pode conter dados reais ou simulados.
    """
    __tablename__ = "search_trends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False)
    date = Column(DateTime, nullable=False)
    interest_score = Column(Integer, default=0, comment="Score de interesse (0-100)")
    source = Column(String(50), nullable=False, comment="Fonte dos dados (google_trends, mock, etc)")
    is_mock = Column(Boolean, default=False, comment="Se os dados são simulados")
    collected_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_trends_keyword_date", "keyword", "date"),
        Index("idx_trends_source", "source"),
    )

    def __repr__(self):
        return f"<SearchTrend(keyword='{self.keyword}', date={self.date}, interest={self.interest_score})>"


class CollectionLog(Base):
    """Log de coletas realizadas.
    
    Registra cada execução dos coletores para
    auditoria e monitoramento.
    """
    __tablename__ = "collection_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_name = Column(String(100), nullable=False)
    endpoint = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    records_collected = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<CollectionLog(collector='{self.collector_name}', records={self.records_collected})>"


class PredictionLog(Base):
    """Tabela de logs e auditoria de previsões vs realidade.
    
    Registra cada previsão feita pelo XGBoost e o valor real observado,
    permitindo auditar a assertividade, erro absoluto e percentual de acerto.
    """
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    prediction_date = Column(DateTime, default=datetime.utcnow, comment="Data em que a previsão foi gerada")
    target_date = Column(DateTime, nullable=False, comment="Data alvo para a qual a demanda foi prevista")
    predicted_demand = Column(Float, nullable=False, comment="Demanda prevista pelo XGBoost")
    actual_demand = Column(Float, nullable=True, comment="Demanda real observada no dia")
    error = Column(Float, nullable=True, comment="Erro absoluto (Real - Previsto)")
    error_pct = Column(Float, nullable=True, comment="Percentual de erro relativo")
    accuracy_pct = Column(Float, nullable=True, comment="Taxa de acurácia (0 a 100%)")
    confidence_min = Column(Float, nullable=True, comment="Limite inferior da faixa de confiança")
    confidence_max = Column(Float, nullable=True, comment="Limite superior da faixa de confiança")
    hit_confidence_interval = Column(Boolean, nullable=True, comment="Se o valor real caiu dentro da faixa prevista")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    product = relationship("Product", back_populates="prediction_logs")

    __table_args__ = (
        Index("idx_prediction_product_target", "product_id", "target_date"),
        Index("idx_prediction_date", "prediction_date"),
    )

    def __repr__(self):
        return f"<PredictionLog(product_id={self.product_id}, target={self.target_date}, pred={self.predicted_demand}, actual={self.actual_demand})>"


class MacroIndicator(Base):
    """Tabela de Indicadores Macroeconômicos e Calendário.
    
    Armazena dados de fontes como BrasilAPI (feriados), BCB SGS (Dólar, Selic, IPCA),
    Nager.Date, CoinGecko e clima histórico.
    """
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, nullable=False, index=True)
    indicator_type = Column(String(50), nullable=False, comment="Tipo: dolar_ptax, selic, ipca, holiday, weather_temp")
    value = Column(Float, nullable=True, comment="Valor numérico do indicador")
    label = Column(String(255), nullable=True, comment="Descrição legível ou nome do feriado")
    source = Column(String(50), nullable=False, comment="Fonte: brasilapi, bcb_sgs, ibge, nager_date, coingecko, weather")
    details = Column(JSON, nullable=True)
    collected_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_macro_date_type", "date", "indicator_type"),
        Index("idx_macro_type", "indicator_type"),
    )

    def __repr__(self):
        return f"<MacroIndicator(date={self.date}, type='{self.indicator_type}', value={self.value})>"


class MarketplaceFeedback(Base):
    """Tabela de métricas de engajamento público de marketplace.
    
    Armazena volume de perguntas, reviews, notas médias e tendências de termos
    obtidos via endpoints públicos do Mercado Livre.
    """
    __tablename__ = "marketplace_feedbacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    platform = Column(String(50), default="mercadolivre")
    questions_count = Column(Integer, default=0, comment="Volume diário/acumulado de perguntas")
    unanswered_questions = Column(Integer, default=0)
    average_rating = Column(Float, nullable=True, comment="Nota média das avaliações (1 a 5)")
    reviews_count = Column(Integer, default=0, comment="Total de avaliações recebidas")
    trend_term = Column(String(255), nullable=True, comment="Termo de tendência associado")
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    product = relationship("Product", back_populates="marketplace_feedbacks")

    __table_args__ = (
        Index("idx_mkt_feedback_product_date", "product_id", "date"),
    )

    def __repr__(self):
        return f"<MarketplaceFeedback(product_id={self.product_id}, date={self.date}, rating={self.average_rating})>"


class ProductOpportunity(Base):
    """Tabela de Recomendações e Ranking de Melhores Produtos para Vender.
    
    Registra os scores de oportunidade gerados pelo OpportunityRecommender.
    """
    __tablename__ = "product_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    horizon_days = Column(Integer, default=14, comment="Horizonte temporal avaliado: 7, 14 ou 30 dias")
    opportunity_score = Column(Float, nullable=False, comment="Score de 0 a 100 de recomendação")
    quadrant = Column(String(50), nullable=False, comment="EXPLOSIVE_GROWTH, HIGH_STABILITY, MODERATE, LOW_PRIORITY")
    projected_growth_pct = Column(Float, nullable=False, comment="Crescimento projetado de vendas em %")
    predicted_units = Column(Integer, nullable=False, comment="Total de unidades previstas no período")
    estimated_revenue = Column(Float, nullable=False, comment="Faturamento estimado no período")
    rationale = Column(Text, nullable=True, comment="Justificativa explicável do score")
    details = Column(JSON, nullable=True)

    # Relacionamentos
    product = relationship("Product", back_populates="opportunities")

    __table_args__ = (
        Index("idx_opp_product_horizon", "product_id", "horizon_days"),
        Index("idx_opp_score", "opportunity_score"),
    )

    def __repr__(self):
        return f"<ProductOpportunity(product_id={self.product_id}, score={self.opportunity_score}, quad='{self.quadrant}')>"
