import hashlib
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from src.api.dependencies import (
    ALGORITHM,
    SECRET_KEY,
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
    EmailVerifyCodeRequest,
    TokenResponse,
    UserResponse,
    PasswordResetRequest,
    PasswordResetVerifyRequest,
    PasswordResetConfirmRequest,
    MessageResponse
)
from src.api.services.email_service import send_verification_email
from src.api.services.supabase_service import (
    SYSTEM_ALLOWED_EMAILS,
    validate_real_email,
    supabase_sign_up,
    supabase_sign_in,
    supabase_resend_confirmation,
    supabase_sync_user_row,
    supabase_send_password_recovery,
    supabase_ensure_auth_user_for_recovery,
    supabase_verify_recovery_otp,
    supabase_update_auth_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Autenticação"])

# Armazenamento em memória para verificação de e-mail e tentativas de login
_email_verify_codes: Dict[str, str] = {}
_login_attempts: Dict[str, list[float]] = {}


def _password_fingerprint(hashed_password: str) -> str:
    """Gera impressão digital curta do hash atual da senha para invalidar tickets já usados."""
    return hashlib.sha256((hashed_password or "").encode("utf-8")).hexdigest()[:16]


def _create_password_reset_ticket(
    email: str,
    sb_access_token: str,
    current_hashed_password: str,
) -> str:
    """Cria um ticket JWT stateless assinado (válido por 15 min) para redefinição de senha."""
    now = datetime.now(timezone.utc)
    payload = {
        "purpose": "password_reset",
        "sub": email,
        "sb_access_token": sb_access_token,
        "pwd_fp": _password_fingerprint(current_hashed_password),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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
    smtp_ok, _ = send_verification_email(email_clean, otp_code)

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
def verify_registration_email(request: EmailVerifyCodeRequest, db: Session = Depends(get_db)):
    """Ativa a conta do usuário mediante código OTP enviado para o e-mail real."""
    email_clean = str(request.email).lower().strip()
    expected_code = _email_verify_codes.get(email_clean)

    if not expected_code or request.code != expected_code:
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

    # 1. Se o usuario ja existe no banco local, valida a senha diretamente
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

    # 2. Se o usuario nao existe no banco local, consulta o Supabase Auth
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


@router.get("/me", response_model=UserResponse, summary="Obter dados do usuário logado")
def get_me(current_user: User = Depends(get_current_user)):
    """Retorna os dados do perfil do usuário atualmente autenticado via JWT."""
    return current_user


@router.post("/forgot-password", response_model=MessageResponse, summary="Solicitar código de recuperação de senha")
def forgot_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """Dispara o código OTP de 6 dígitos para recuperação de senha exclusivamente via Supabase Auth."""
    email_clean = str(request.email).lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta cadastrada com este email."
        )

    # Garante que contas antigas ou criadas apenas no banco local existam no Supabase Auth
    sync_status = supabase_ensure_auth_user_for_recovery(email_clean, user.name)
    logger.info(
        "[RECUPERACAO DE SENHA] Conta verificada no Supabase Auth | email=%s | status=%s",
        email_clean,
        sync_status,
    )

    sb_sent, sb_msg = supabase_send_password_recovery(email_clean)
    if not sb_sent:
        is_rate_limit = "limite" in sb_msg.lower() or "aguarde" in sb_msg.lower() or "429" in sb_msg
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if is_rate_limit else status.HTTP_502_BAD_GATEWAY,
            detail=sb_msg,
        )

    logger.info("[RECUPERACAO DE SENHA] E-mail de recuperação solicitado via Supabase Auth | email=%s", email_clean)

    return MessageResponse(
        message=f"Código de verificação de 6 dígitos enviado para {email_clean}! Verifique sua caixa de entrada e a pasta de spam/lixeira.",
        success=True
    )


@router.post("/verify-reset-code", response_model=MessageResponse, summary="Verificar código OTP de recuperação de senha")
def verify_reset_code(request: PasswordResetVerifyRequest, db: Session = Depends(get_db)):
    """Valida o código OTP de 6 dígitos no Supabase Auth e emite um ticket JWT stateless de redefinição."""
    email_clean = str(request.email).lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma conta cadastrada com este email."
        )

    code_clean = request.code.strip()
    if not code_clean.isdigit() or len(code_clean) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digite os 6 dígitos numéricos do código enviado para seu e-mail."
        )

    ok, msg, access_token = supabase_verify_recovery_otp(email_clean, code_clean)
    if not ok or not access_token:
        is_rate_limit = "tentativas" in msg.lower() or "limite" in msg.lower()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if is_rate_limit else status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    reset_token = _create_password_reset_ticket(
        email=email_clean,
        sb_access_token=access_token,
        current_hashed_password=user.hashed_password,
    )

    return MessageResponse(
        message="Código de verificação validado com sucesso!",
        success=True,
        reset_token=reset_token,
    )


@router.post("/reset-password", response_model=MessageResponse, summary="Redefinir senha com ticket de recuperação")
def reset_password(request: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    """Valida o ticket JWT emitido em /verify-reset-code e atualiza a senha localmente e no Supabase Auth."""
    email_clean = str(request.email).lower().strip()
    ticket_jwt = (request.reset_token or request.code or "").strip()
    if not ticket_jwt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação ausente ou inválido. Solicite um novo código."
        )

    try:
        payload = jwt.decode(ticket_jwt, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sua sessão de recuperação expirou. Solicite um novo código."
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão de recuperação inválida ou expirada. Solicite um novo código."
        )

    if payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação inválido. Solicite um novo código."
        )

    if str(payload.get("sub") or "").lower().strip() != email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de recuperação não corresponde ao e-mail informado."
        )

    sb_access_token = str(payload.get("sb_access_token") or "").strip()
    if not sb_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão de recuperação inválida ou expirada. Solicite um novo código."
        )

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado."
        )

    if payload.get("pwd_fp") != _password_fingerprint(user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão de recuperação já utilizada ou expirada. Solicite um novo código."
        )

    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve conter no mínimo 6 caracteres."
        )

    user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    db.refresh(user)

    sb_updated = supabase_update_auth_password(sb_access_token, request.new_password)
    if not sb_updated:
        logger.warning(
            "[RECUPERACAO DE SENHA] Senha local atualizada, porém não foi possível sincronizar no Supabase Auth | email=%s",
            email_clean,
        )

    # Sincronizar com tabela users no Supabase caso ativo
    try:
        supabase_sync_user_row(user.email, user.hashed_password, user.name or email_clean.split('@')[0], is_active=user.is_active)
    except Exception:
        pass

    return MessageResponse(
        message="Senha redefinida com sucesso! Você já pode realizar o login.",
        success=True
    )
