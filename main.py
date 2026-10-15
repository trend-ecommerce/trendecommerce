"""Ponto de entrada da aplicação FastAPI - TrendEcommerce AI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.router import api_router

app = FastAPI(
    title="TrendEcommerce AI API",
    description="API REST de Inteligência Preditiva e Gestão de Estoques para E-commerce",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["Status"])
def health_check():
    return {
        "status": "online",
        "service": "TrendEcommerce AI Engine",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)