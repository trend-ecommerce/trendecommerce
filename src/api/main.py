import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.api.routers import auth_router, products_router, forecast_router, opportunity_router
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
            print(f"[TrendCommerce] Erro ao carregar seed inicial: {err}")

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
                print("[TrendCommerce] Usuário administrador padrão criado com sucesso.")
        except Exception as err:
            print(f"[TrendCommerce] Erro ao criar admin padrão: {err}")

        # 3. Pré-aquecer motor ML em background no startup para respostas instantâneas
        try:
            from src.api.dependencies import get_ml_forecaster
            get_ml_forecaster(session)
            print("[TrendCommerce] Motor preditivo XGBoost aquecido e pronto na memória.")
        except Exception as err:
            print(f"[TrendCommerce] Erro no warmup ML: {err}")
    yield


app = FastAPI(
    title="TrendCommerce API",
    description="API REST de Gestão de Catálogo, Histórico de Vendas e Previsão de Demanda com Inteligência Artificial (XGBoost).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ==========================================
# Configuração Segura de CORS
# ==========================================
custom_cors = os.getenv("CORS_ORIGINS", "")
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
]
if custom_cors:
    for o in custom_cors.split(","):
        cleaned = o.strip()
        if cleaned and cleaned not in origins:
            origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*(\.vercel\.app|\.onrender\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# Inclusão dos Routers REST
# ==========================================
API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix="/api")
app.include_router(products_router, prefix=API_PREFIX)
app.include_router(forecast_router, prefix=API_PREFIX)
app.include_router(opportunity_router, prefix=API_PREFIX)


# ==========================================
# Servir Frontend Estático
# ==========================================
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.get("/", tags=["Health & Status"], summary="Status e Redirecionamento da API")
def root():
    """Redireciona para o frontend ou retorna status da API."""
    if frontend_dir.exists():
        return RedirectResponse(url="/app/ia-preditiva.html")
    return {
        "system": "TrendCommerce API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health", tags=["Health & Status"], summary="Health check da API")
def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "model": "xgboost-demand-regressor"
    }


@app.api_route("/api/v1/admin/reseed", methods=["GET", "POST"], tags=["Admin"], summary="Recarregar catálogo e histórico inicial")
def reseed_database():
    """Injeta ou sincroniza o catálogo e históricos diários."""
    from src.database.seed_loader import seed_database_if_empty
    db_manager = get_db_instance()
    with db_manager.session() as session:
        seed_database_if_empty(session)
        from src.database.models import Product, SalesHistory
        prod_count = session.query(Product).count()
        sales_count = session.query(SalesHistory).count()
    return {
        "status": "success",
        "message": "Catálogo e histórico sincronizados com sucesso!",
        "total_products": prod_count,
        "total_sales_history": sales_count
    }


@app.get("/api/v1/debug/status", tags=["Admin"], summary="Status detalhado do banco de dados")
def debug_status():
    from src.database.models import Product, SalesHistory, User
    db_manager = get_db_instance()
    with db_manager.session() as session:
        return {
            "db_type": "postgresql" if "postgres" in db_manager._database_url else "sqlite",
            "products_count": session.query(Product).count(),
            "sales_history_count": session.query(SalesHistory).count(),
            "users_count": session.query(User).count()
        }
