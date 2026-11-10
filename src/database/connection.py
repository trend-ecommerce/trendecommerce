"""Gerenciamento de conexão com o PostgreSQL e SQLite."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def get_database_url() -> str:
    """Obtém a URL de conexão do banco de dados.
    
    Em desenvolvimento local, se DATABASE_URL não estiver configurado
    ou contiver os valores padrão de exemplo, utiliza SQLite local.
    Trata URLs com prefixo legado postgres:// convertendo para postgresql://.
    """
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url or "user:password" in db_url:
        db_path = Path(__file__).parent.parent.parent / "data" / "trendcommerce_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return db_url


def get_engine(database_url: str | None = None):
    """Cria e retorna o engine do SQLAlchemy com SSL e pool seguro."""
    url = database_url or get_database_url()
    connect_args = {}
    if "sqlite" not in url:
        connect_args["sslmode"] = "require"

    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args
    )


def get_session(engine=None) -> Session:
    """Cria uma nova sessão do banco de dados."""
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class DatabaseManager:
    """Gerenciador de conexões com o banco de dados.
    
    Centraliza a criação de engines e sessões,
    e gerencia o ciclo de vida das conexões.
    """

    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or get_database_url()
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        if self._engine is None:
            connect_args = {}
            if "sqlite" not in self._database_url:
                connect_args["sslmode"] = "require"

            self._engine = create_engine(
                self._database_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args=connect_args
            )
        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Context manager para sessões do banco de dados com fechamento automático."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(bind=self.engine)
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self):
        """Cria todas as tabelas definidas nos models."""
        from .models import Base
        Base.metadata.create_all(self.engine)

    def drop_tables(self):
        """Remove todas as tabelas (usar com cuidado)."""
        from .models import Base
        Base.metadata.drop_all(self.engine)
