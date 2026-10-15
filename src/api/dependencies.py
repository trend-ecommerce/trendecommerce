import os
from datetime import datetime, timedelta
from typing import Generator, Optional
import pandas as pd

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_bearer = HTTPBearer(auto_error=False)

# Singleton do DatabaseManager e do FutureForecaster
_db_manager: Optional[DatabaseManager] = None
_forecaster_instance: Optional[FutureForecaster] = None
_forecaster_trained: bool = False