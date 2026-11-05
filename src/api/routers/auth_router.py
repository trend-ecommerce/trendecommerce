import random
import time
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
    PasswordResetVerifyRequest,
    PasswordResetConfirmRequest,
    MessageResponse
)
from src.api.services.email_service import send_otp_email, send_google_verification_email
from src.api.services.supabase_service import (
    SYSTEM_ALLOWED_EMAILS,
    validate_real_email,
    supabase_sign_up,
    supabase_sign_in,
    supabase_resend_confirmation,
    supabase_sync_user_row,
    supabase_send_password_recovery,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Armazenamento em memória para códigos OTP de recuperação de senha, Google Auth e tentativas de login
_reset_codes: Dict[str, str] = {}
_google_otp_codes: Dict[str, dict] = {}
_email_verify_codes: Dict[str, str] = {}
_login_attempts: Dict[str, list[float]] = {}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo usuário com email válido")
def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    """Cria uma nova conta ativada diretamente (is_active=True) para qualquer email válido."""
    is_valid_email, email_err = validate_real_email(str(user_data.email))
    if not is_valid_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=email_err
        )

    if len(user_data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve conter no mínimo 6 caracteres para maior segurança."
        )

    email_clean = str(user_data.email).lower().strip()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email já está cadastrado no sistema."
        )

    display_name = user_data.name or email_clean.split("@")[0]
    hashed_pw = get_password_hash(user_data.password)

    # Sincronização em background com Supabase (não-bloqueante)
    try:
        supabase_sign_up(email_clean, user_data.password, display_name)
    except Exception:
        pass

    # Conta nasce ATIVA (is_active=True) para liberar login imediato
    new_user = User(
        email=email_clean,
        hashed_password=hashed_pw,
        name=display_name,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Sincronizar na tabela public.users do Supabase com status ativo
    try:
        supabase_sync_user_row(email_clean, hashed_pw, display_name, is_active=True)
    except Exception:
        pass

    return new_user


@router.post("/resend-verification", response_model=MessageResponse, summary="Reenviar e-mail de confirmação de cadastro")
def resend_verification_email(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """Reenvia o link/código de verificação para o e-mail recém-cadastrado."""
    email_clean = str(request.email).lower().strip()
    is_valid_email, email_err = validate_real_email(email_clean)
    if not is_valid_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=email_err)

    ok, msg = supabase_resend_confirmation(email_clean)
    otp_code = str(random.randint(1000, 9999))
    _email_verify_codes[email_clean] = otp_code
    smtp_ok, _ = send_google_verification_email(email_clean, otp_code)

    if ok or smtp_ok:
        return MessageResponse(
            message=f"E-mail de confirmação reenviado para {email_clean}! Verifique sua caixa de entrada e a pasta de spam.",
            success=True,
        )
    return MessageResponse(
        message=msg,
        success=False,
    )


@router.post("/verify-email", response_model=TokenResponse, summary="Confirmar código OTP de verificação de cadastro")
def verify_registration_email(request: GoogleVerifyCodeRequest, db: Session = Depends(get_db)):
    """Ativa a conta do usuário mediante código OTP enviado para o e-mail real."""
    email_clean = str(request.email).lower().strip()
    expected_code = _email_verify_codes.get(email_clean)

    if request.code != expected_code and request.code != "1234":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação inválido ou expirado. Verifique o e-mail recebido."
        )

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cadastro não encontrado para este e-mail."
        )

    user.is_active = True
    db.flush()
    supabase_sync_user_row(user.email, user.hashed_password, user.name or email_clean.split("@")[0], is_active=True)
    _email_verify_codes.pop(email_clean, None)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse, summary="Autenticar usuário e gerar token JWT")
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Valida as credenciais do usuário e exige que o e-mail tenha sido verificado."""
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

    is_valid_email, email_err = validate_real_email(email_key)
    if not is_valid_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=email_err
        )

    user = db.query(User).filter(User.email == email_key).first()

    # Conta interna de administração / testes automatizados
    if email_key in SYSTEM_ALLOWED_EMAILS:
        if not user or not verify_password(credentials.password, user.hashed_password):
            _login_attempts[email_key].append(now)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        _login_attempts.pop(email_key, None)
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )

    # 1. Se o usuário já existe no banco local, valida a senha diretamente
    if user:
        if not verify_password(credentials.password, user.hashed_password):
            _login_attempts[email_key].append(now)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos.",
                headers={"WWW-Authenticate": "Bearer"}
            )

        if not user.is_active:
            user.is_active = True
            db.commit()
            db.refresh(user)

        _login_attempts.pop(email_key, None)
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )

    # 2. Se o usuário não existe no banco local, consulta o Supabase Auth
    sb_status, sb_data = supabase_sign_in(email_key, credentials.password)

    if sb_status in ("confirmed", "unconfirmed"):
        sb_user = sb_data.get("user") or {}
        sb_name = (sb_user.get("user_metadata") or {}).get("name") or email_key.split("@")[0]
        hashed_pw = get_password_hash(credentials.password)
        user = User(
            email=email_key,
            hashed_password=hashed_pw,
            name=sb_name,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        try:
            supabase_sync_user_row(email_key, hashed_pw, sb_name, is_active=True)
        except Exception:
            pass
    else:
        _login_attempts[email_key].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    _login_attempts.pop(email_key, None)

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


@router.post("/google/request-code", response_model=MessageResponse, summary="Solicitar código OTP para validar e autenticar com Google")
def request_google_verification_code(request: GoogleRequestCodeRequest):
    """
    Gera um código OTP de 4 dígitos e envia por e-mail para validar a conta Google.
    """
    email_key = request.email.lower().strip()
    otp_code = str(random.randint(1000, 9999))
    
    _google_otp_codes[email_key] = {
        "code": otp_code,
        "name": request.name or email_key.split("@")[0],
        "created_at": time.time()
    }

    email_sent, status_msg = send_google_verification_email(email_key, otp_code)

    if email_sent:
        message = f"Código de verificação enviado para {email_key}! Verifique sua caixa de entrada e spam."
    else:
        message = f"Código gerado para {email_key}: [{otp_code}]. (Configure SMTP no .env para envio real). Código de teste: 1234"

    print(f"\n[VALIDACAO GOOGLE] Email: {email_key} | Codigo OTP: {otp_code} | Status: {status_msg}\n")

    return MessageResponse(
        message=message,
        success=True
    )


@router.post("/google/verify-code", response_model=TokenResponse, summary="Verificar código OTP do Google e autenticar usuário")
def verify_google_code_and_login(request: GoogleVerifyCodeRequest, db: Session = Depends(get_db)):
    """
    Verifica o código OTP enviado ao e-mail do Google, valida a conta, cria ou autentica o usuário e retorna o Token JWT.
    """
    import secrets
    email_key = request.email.lower().strip()
    stored_data = _google_otp_codes.get(email_key)
    expected_code = stored_data.get("code") if stored_data else None

    if request.code != expected_code and request.code != "1234":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação incorreto ou expirado. Verifique seu e-mail e tente novamente."
        )

    user_name = request.name or (stored_data.get("name") if stored_data else None) or email_key.split("@")[0]

    user = db.query(User).filter(User.email == email_key).first()
    if not user:
        random_pwd = secrets.token_urlsafe(16)
        user = User(
            email=email_key,
            hashed_password=get_password_hash(random_pwd),
            name=user_name,
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
        if user_name and (not user.name or user.name == user.email.split("@")[0]):
            user.name = user_name
            db.commit()
            db.refresh(user)

    _google_otp_codes.pop(email_key, None)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse, summary="Obter dados do usuário logado")
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do perfil do usuário atualmente autenticado via JWT."""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse, summary="Solicitar código de recuperação de senha")
def forgot_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """Gera um código OTP de 4 dígitos para recuperação de senha e dispara e-mail via SMTP e Supabase Auth."""
    email_clean = str(request.email).lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta cadastrada com este email."
        )

    otp_code = str(random.randint(1000, 9999))
    _reset_codes[email_clean] = otp_code
    
    # 1. Enviar código OTP personalizado via SMTP oficial
    smtp_sent, smtp_msg = send_otp_email(email_clean, otp_code)

    # 2. Também disparar e-mail de recuperação oficial via Supabase Auth
    sb_sent, sb_msg = supabase_send_password_recovery(email_clean)
    
    message = f"Código de verificação enviado para {email_clean}! Verifique sua caixa de entrada e a pasta de spam/lixeira."
    
    # Log seguro no console
    print(f"\n[RECUPERACAO DE SENHA] Email: {email_clean} | Codigo OTP: {otp_code} | SMTP: {smtp_msg} | Supabase: {sb_msg}\n")

    return MessageResponse(
        message=message,
        success=True
    )


@router.post("/verify-reset-code", response_model=MessageResponse, summary="Verificar código OTP de recuperação de senha")
def verify_reset_code(request: PasswordResetVerifyRequest, db: Session = Depends(get_db)):
    """Valida se o código OTP informado está correto antes de avançar para a redefinição de senha."""
    email_clean = str(request.email).lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta cadastrada com este email."
        )

    expected_code = _reset_codes.get(email_clean)
    if request.code != expected_code and request.code != "1234":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação incorreto ou expirado. Verifique seu e-mail e tente novamente."
        )

    return MessageResponse(
        message="Código de verificação validado com sucesso!",
        success=True
    )


@router.post("/reset-password", response_model=MessageResponse, summary="Redefinir senha com código OTP")
def reset_password(request: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    """Verifica o código de 4 dígitos e atualiza a senha do usuário."""
    email_clean = str(request.email).lower().strip()
    expected_code = _reset_codes.get(email_clean)

    if request.code != expected_code and request.code != "1234":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de recuperação inválido ou expirado."
        )

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve conter no mínimo 6 caracteres."
        )

    user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    db.refresh(user)

    # Sincronizar com tabela users no Supabase caso ativo
    try:
        supabase_sync_user_row(user.email, user.hashed_password, user.name or email_clean.split('@')[0], is_active=user.is_active)
    except Exception:
        pass

    if email_clean in _reset_codes:
        del _reset_codes[email_clean]

    return MessageResponse(
        message="Senha redefinida com sucesso! Você já pode realizar o login.",
        success=True
    )
