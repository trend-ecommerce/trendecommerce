"""Ponto de entrada da aplicação FastAPI - TrendCommerce."""

import uvicorn
from src.api.main import app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
