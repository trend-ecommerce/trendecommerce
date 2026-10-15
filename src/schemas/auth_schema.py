"""Schemas Pydantic para Autenticação e Usuários."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Email de cadastro do usuário")
    password: str = Field(..., min_length=6, description="Senha de no mínimo 6 caracteres")
    name: Optional[str] = Field(None, description="Nome completo ou de exibição")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email cadastrado")
    password: str = Field(..., description="Senha do usuário")


class GoogleAuthRequest(BaseModel):
    token: Optional[str] = Field(None, description="Google ID Token JWT")
    credential: Optional[str] = Field(None, description="Google ID Token JWT (alias GIS credential)")
    email: Optional[EmailStr] = Field(None, description="Email fornecido pelo Google")
    name: Optional[str] = Field(None, description="Nome do usuário do Google")
    picture: Optional[str] = Field(None, description="URL do avatar do Google")
    sub: Optional[str] = Field(None, description="Google User ID")



class GoogleRequestCodeRequest(BaseModel):
    email: EmailStr = Field(..., description="Email da conta Google selecionada")
    name: Optional[str] = Field(None, description="Nome de exibição da conta Google")


class GoogleVerifyCodeRequest(BaseModel):
    email: EmailStr = Field(..., description="Email da conta Google")
    code: str = Field(..., min_length=4, max_length=4, description="Código de 4 dígitos enviado ao e-mail")
    name: Optional[str] = Field(None, description="Nome da conta Google")




class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None



class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordResetRequest(BaseModel):
    email: EmailStr = Field(..., description="Email para envio do código de recuperação")


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=4, description="Código de 4 dígitos")
    new_password: str = Field(..., min_length=6, description="Nova senha")


class MessageResponse(BaseModel):
    message: str
    success: bool = True
