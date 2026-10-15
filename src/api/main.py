import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.api.routers import auth_router, products_router, forecast_router, trends_router, opportunity_router
from src.api.dependencies import get_db_instance, get_password_hash
from src.database.models import Base, User



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia inicialização e encerramento da aplicação."""
    db_manager = get_db_instance()
    Base.metadata.create_all(db_manager.engine)

    # Garantir dados iniciais e usuário administrador
    with db_manager.session() as session:
        # 1. Injetar catálogo de produtos e histórico caso o banco esteja vazio
        try:
            from src.database.seed_loader import seed_database_if_empty
            seed_database_if_empty(session)
        except Exception as err:
            print(f"[TrendCommerce AI] Erro ao carregar seed inicial: {err}")

        # 2. Garantir usuário administrador padrão
        try:
            admin_user = session.query(User).filter(User.email == "admin@trendecommerce.com").first()
            if not admin_user:
                admin_user = User(
                    email="admin@trendecommerce.com",
                    hashed_password=get_password_hash("admin123"),
                    name="Administrador Master",
                    is_active=True
                )
                session.add(admin_user)
                session.commit()
                print("[TrendCommerce AI] Usuário administrador padrão criado com sucesso.")
        except Exception as err:
            print(f"[TrendCommerce AI] Erro ao criar admin padrão: {err}")

        # 3. Pré-aquecer motor ML em background no startup para respostas instantâneas (<10ms)
        try:
            from src.api.dependencies import get_ml_forecaster
            get_ml_forecaster(session)
            print("[TrendCommerce AI] Motor preditivo XGBoost aquecido e pronto na memória.")
        except Exception as err:
            print(f"[TrendCommerce AI] Erro no warmup ML: {err}")
    yield