"""Ponto de entrada da aplicação FastAPI - TrendEcommerce AI."""

from src.api.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
