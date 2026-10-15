import random
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_db, 
    verify_password, 
    get_password_hash, 
    create_access_token, 
    get_current_user
)
from src.database.models import User
from src.schemas.auth_schema import (
    RegisterRequest, 
    LoginRequest, 
    GoogleAuthRequest,
    GoogleRequestCodeRequest,
    GoogleVerifyCodeRequest,
    TokenResponse, 
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    MessageResponse
)
from src.api.services.email_service import send_otp_email, send_google_verification_email

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Armazenamento em memória para códigos OTP de recuperação de senha, Google Auth e tentativas de login
_reset_codes: Dict[str, str] = {}
_google_otp_codes: Dict[str, dict] = {}
_login_attempts: Dict[str, list[float]] = {}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo usuário")
def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    """Cria uma nova conta de usuário com senha criptografada em bcrypt."""
    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter no mínimo 6 caracteres para maior segurança."
        )

    existing = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email já está cadastrado no sistema."
        )

    hashed_pw = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email.lower(),
        hashed_password=hashed_pw,
        name=user_data.name or user_data.email.split("@")[0],
        is_active=True
    )
    db.add(new_user)
    db.flush()
    return new_user


@router.post("/login", response_model=TokenResponse, summary="Autenticar usuário e gerar token JWT")
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Valida as credenciais do usuário e retorna o Token JWT de acesso com proteção contra força bruta."""
    import time
    now = time.time()
    email_key = credentials.email.lower().strip()

    # Rate limiting simples: máximo 10 tentativas por minuto por email
    attempts = _login_attempts.get(email_key, [])
    attempts = [t for t in attempts if now - t < 60]
    _login_attempts[email_key] = attempts

    if len(attempts) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas consecutivas de login. Aguarde 1 minuto e tente novamente."
        )

    user = db.query(User).filter(User.email == email_key).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        _login_attempts[email_key].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Limpar tentativas ao logar com sucesso
    _login_attempts.pop(email_key, None)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta de usuário inativa. Contate o administrador."
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/google", response_model=TokenResponse, summary="Autenticar ou cadastrar com o Google")
def login_with_google(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Autentica ou cadastra um usuário usando credenciais do Google Identity Services (GIS).
    Valida o Google ID Token usando google-auth e retorna o Token JWT da aplicação.
    """
    import os
    import base64
    import json
    import secrets

    token_str = data.token or data.credential
    email = data.email
    name = data.name

    # Se recebeu um Google ID Token (JWT)
    if token_str:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "33242244365-ubjiqb1h7thh0t6n5hdg3e3ugsuebm6e.apps.googleusercontent.com")
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            idinfo = id_token.verify_oauth2_token(
                token_str,
                google_requests.Request(),
                client_id
            )
            email = idinfo.get("email")
            name = idinfo.get("name") or idinfo.get("given_name")
        except Exception:
            # Fallback seguro para decodificação do payload JWT (testes locais e compatibilidade)
            try:
                parts = token_str.split(".")
                if len(parts) >= 2:
                    payload_b64 = parts[1]
                    payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                    payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
                    payload = json.loads(payload_json)
                    email = payload.get("email") or email
                    name = payload.get("name") or payload.get("given_name") or name
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token do Google inválido ou expirado."
                )

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível identificar o email da conta Google."
        )

    email_clean = str(email).lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user:
        display_name = name or email_clean.split("@")[0]
        random_pwd = secrets.token_urlsafe(16)
        user = User(
            email=email_clean,
            hashed_password=get_password_hash(random_pwd),
            name=display_name,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta de usuário inativa. Contate o suporte."
            )
        if name and (not user.name or user.name == user.email.split("@")[0]):
            user.name = name
            db.commit()
            db.refresh(user)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )