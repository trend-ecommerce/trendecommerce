from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///data/trendcommerce_dev.db"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "trendcommerce"
    db_user: str = "user"
    db_password: str = "password"
    
    # JWT & Auth
    jwt_secret_key: str = "sua-chave-secreta-super-segura-aqui"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    
    # Microserviço API de Histórico de Vendas
    vendas_api_url: str = "http://127.0.0.1:8001"
    
    # Google OAuth / GIS
    google_client_id: str = "33242244365-ubjiqb1h7thh0t6n5hdg3e3ugsuebm6e.apps.googleusercontent.com"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
