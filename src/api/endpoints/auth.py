"""Endpoint de autenticação da aplicação."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class LoginSchema(BaseModel):
    username: str
    password: str


@router.post("/login", summary="Autenticação de Usuário")
def login(credentials: LoginSchema):
    if credentials.username == "admin" and credentials.password == "admin123":
        return {
            "access_token": "token_jwt_simulado_trendecommerce",
            "token_type": "bearer",
            "user": {"name": "Gestor Ecommerce", "role": "admin"}
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas"
    )