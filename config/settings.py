from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/trendcommerce"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "trendcommerce"
    db_user: str = "user"
    db_password: str = "password"
    
    # Amazon SP-API
    amazon_client_id: Optional[str] = None
    amazon_client_secret: Optional[str] = None
    amazon_refresh_token: Optional[str] = None
    amazon_marketplace_id: Optional[str] = None
    
    # Mercado Livre
    meli_app_id: Optional[str] = None
    meli_client_secret: Optional[str] = None
    meli_access_token: Optional[str] = None
    meli_refresh_token: Optional[str] = None
    
    # API Guardian
    guardian_strict_mode: bool = True
    guardian_log_blocked: bool = True
    
    # Google OAuth / GIS
    google_client_id: str = "33242244365-ubjiqb1h7thh0t6n5hdg3e3ugsuebm6e.apps.googleusercontent.com"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
