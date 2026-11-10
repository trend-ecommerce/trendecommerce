import os
from datetime import datetime, timedelta
from typing import Generator, Optional
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database.connection import DatabaseManager
from src.database.setup import get_db_manager
from src.database.models import User, Product, SalesHistory
from src.ml.future_forecaster import FutureForecaster

# ==========================================
# Configurações de Segurança e JWT
# ==========================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "trendecommerce-secret-key-development-2026-super-secure")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 horas

security_bearer = HTTPBearer(auto_error=False)

# Singleton do DatabaseManager e do FutureForecaster
_db_manager: Optional[DatabaseManager] = None
_forecaster_instance: Optional[FutureForecaster] = None
_forecaster_trained: bool = False

# ==========================================
# Dependência de Banco de Dados
# ==========================================
def get_db_instance() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = get_db_manager()
    return _db_manager


def get_db() -> Generator[Session, None, None]:
    """Gera uma sessão do banco de dados por requisição com fechamento garantido."""
    manager = get_db_instance()
    with manager.session() as session:
        yield session


import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica senha com bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return plain_password == hashed_password


def get_password_hash(password: str) -> str:
    """Gera o hash seguro bcrypt."""
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Gera um token JWT com expiração."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """Valida o token JWT e retorna o usuário autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais de autenticação inválidas ou expiradas.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not auth or not auth.credentials:
        raise credentials_exception

    token = auth.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# ==========================================
# Dependência do Motor ML (XGBoost)
# ==========================================
def get_ml_forecaster(db: Session = Depends(get_db)) -> FutureForecaster:
    """Retorna instância rápida do FutureForecaster com carregamento otimizado (<80MB RAM)."""
    global _forecaster_instance, _forecaster_trained

    model_path = Path("models/xgboost_demand_v1.json")

    if _forecaster_instance is None:
        _forecaster_instance = FutureForecaster(
            db_manager=get_db_instance(),
            model_path=str(model_path)
        )

    if not _forecaster_trained:
        if not model_path.exists():
            try:
                from src.ml.train_pipeline import run_training_pipeline
                run_training_pipeline(str(model_path))
                _forecaster_instance = FutureForecaster(
                    db_manager=get_db_instance(),
                    model_path=str(model_path)
                )
            except Exception as e:
                print(f"[Aviso ML] Erro ao treinar pipeline inicial: {e}")
        _forecaster_trained = True

    return _forecaster_instance
