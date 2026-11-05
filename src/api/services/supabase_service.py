"""Serviço de integração com o Supabase (Auth + PostgREST) e validação de e-mails reais."""

import logging
import os
import re
import socket
from typing import Any, Dict, Optional, Tuple
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_SUPABASE_URL = "https://mfpuqpdkfiwkyadpwdbh.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1mcHVxcGRrZml3a3lhZHB3ZGJoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM4NzU3NzAsImV4cCI6MjEwOTQ1MTc3MH0."
    "Y1I9MLrzHkfK92h_wNFBlAbELYS_HDZ0DzN8doyMebk"
)

# Domínios descartáveis, temporários ou de teste bloqueados
BLOCKED_EMAIL_DOMAINS = {
    "teste.com", "teste.com.br", "test.com", "example.com", "example.org", "example.net",
    "falso.com", "fake.com", "fakemail.com", "email.com", "dominio.com", "meudominio.com",
    "tempmail.com", "temp-mail.org", "10minutemail.com", "mailinator.com", "yopmail.com",
    "guerrillamail.com", "sharklasers.com", "trashmail.com", "getnada.com", "maildrop.cc",
    "dispostable.com", "throwawaymail.com", "mohmal.com", "mailnesia.com", "tempail.com",
    "burnermail.io", "mytemp.email", "nada.email", "linshiyouxiang.net",
    # Erros comuns de digitação em provedores reais
    "gamil.com", "gmial.com", "gnail.com", "gmai.com", "gmail.co", "gmail.con",
    "outlok.com", "outllok.com", "outlook.co", "hotmal.com", "hotmial.com", "htmail.com",
    "yaho.com", "yahooo.com",
}

# Provedores reais amplamente reconhecidos (fast-path sem latência de rede)
TRUSTED_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "outlook.com.br", "hotmail.com", "hotmail.com.br", "live.com", "msn.com",
    "yahoo.com", "yahoo.com.br", "ymail.com",
    "icloud.com", "me.com", "mac.com",
    "uol.com.br", "bol.com.br", "terra.com.br", "globo.com", "ig.com.br", "r7.com",
    "protonmail.com", "proton.me", "pm.me",
    "zoho.com", "aol.com", "gmx.com", "fastmail.com",
}

# Contas de sistema internas permitidas sem confirmação de e-mail externo
SYSTEM_ALLOWED_EMAILS = {
    "admin@trendecommerce.com",
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def get_supabase_config() -> Tuple[str, str]:
    url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip().rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_ANON_KEY)).strip()
    return url, key


def has_valid_mx_or_dns(domain: str) -> bool:
    """Verifica se o domínio existe de verdade e possui registros MX (servidor de e-mail) ativos."""
    domain = domain.lower().strip()
    if not domain or "." not in domain:
        return False

    try:
        resp = requests.get(
            "https://dns.google/resolve",
            params={"name": domain, "type": "MX"},
            timeout=3.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Status") == 0 and data.get("Answer"):
                return True
            if data.get("Status") == 3:
                return False
    except Exception as exc:
        logger.debug(f"Fallback DNS socket para {domain}: {exc}")

    try:
        socket.getaddrinfo(domain, None)
        return True
    except socket.gaierror:
        return False


def validate_real_email(email: str) -> Tuple[bool, str]:
    """Valida se o e-mail possui formato válido, não é descartável/falso e pertence a um domínio real."""
    if not email or not isinstance(email, str):
        return False, "Informe um endereço de e-mail válido."

    clean_email = email.strip().lower()

    if clean_email in SYSTEM_ALLOWED_EMAILS:
        return True, ""

    if not EMAIL_REGEX.match(clean_email):
        return False, "Formato de e-mail inválido. Digite um e-mail real (ex: nome@gmail.com)."

    local_part, domain = clean_email.rsplit("@", 1)

    if len(local_part) < 2 or local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
        return False, "Endereço de e-mail inválido. Verifique o nome antes do @."

    if domain in BLOCKED_EMAIL_DOMAINS:
        return (
            False,
            f"O domínio '@{domain}' não é permitido ou possui erro de digitação. "
            "Utilize um e-mail verdadeiro (ex: Gmail, Outlook, Hotmail ou corporativo)."
        )

    if local_part in {"teste", "test", "fake", "falso", "asdf", "qwerty", "123", "1234", "12345", "123456"}:
        return False, "E-mails de teste ou fictícios não são permitidos. Utilize o seu e-mail verdadeiro."

    if domain in TRUSTED_EMAIL_DOMAINS:
        return True, ""

    if not has_valid_mx_or_dns(domain):
        return (
            False,
            f"O domínio '@{domain}' não existe ou não possui servidor de e-mail válido. "
            "Digite um e-mail verdadeiro."
        )

    return True, ""


def supabase_sign_up(
    email: str,
    password: str,
    name: Optional[str] = None,
    redirect_to: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Registra o usuário no Supabase Auth (disparando e-mail de confirmação real)."""
    url, key = get_supabase_config()
    if not url or not key:
        return False, {"error": "Supabase não configurado"}

    redirect_url = redirect_to or os.getenv("AUTH_REDIRECT_URL", "http://localhost:8000/login.html?verified=1")
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    payload = {
        "email": email.lower().strip(),
        "password": password,
        "data": {"name": name or email.split("@")[0]},
    }

    try:
        resp = requests.post(
            f"{url}/auth/v1/signup",
            params={"redirect_to": redirect_url},
            headers=headers,
            json=payload,
            timeout=6.0,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code in (200, 201):
            return True, data
        return False, data
    except Exception as exc:
        logger.warning(f"Aviso ao sincronizar signup com Supabase Auth: {exc}")
        return False, {"error": str(exc)}


def supabase_sign_in(email: str, password: str) -> Tuple[str, Dict[str, Any]]:
    """Autentica o usuário no Supabase Auth e verifica se o e-mail já foi confirmado.

    Retorna:
        Tuple[status_str, payload_dict] onde status_str é:
        - "confirmed": credenciais válidas e e-mail confirmado no Supabase Auth
        - "unconfirmed": conta existe no Supabase Auth mas o e-mail ainda NÃO foi confirmado
        - "invalid": credenciais incorretas ou usuário não encontrado no Supabase
        - "error": falha de conexão
    """
    url, key = get_supabase_config()
    if not url or not key:
        return "error", {"error": "Supabase não configurado"}

    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    payload = {
        "email": email.lower().strip(),
        "password": password,
    }

    try:
        resp = requests.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers=headers,
            json=payload,
            timeout=6.0,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and "access_token" in data:
            user_obj = data.get("user") or {}
            if user_obj.get("email_confirmed_at") or user_obj.get("confirmed_at"):
                return "confirmed", data
            return "unconfirmed", data

        err_code = str(data.get("error_code") or "").lower()
        err_msg = str(data.get("msg") or data.get("error_description") or data.get("message") or "").lower()
        if "email_not_confirmed" in err_code or "not confirmed" in err_msg:
            return "unconfirmed", data

        return "invalid", data
    except Exception as exc:
        logger.warning(f"Aviso ao autenticar no Supabase Auth: {exc}")
        return "error", {"error": str(exc)}


def supabase_resend_confirmation(email: str, redirect_to: Optional[str] = None) -> Tuple[bool, str]:
    """Reenvia o e-mail de confirmação de cadastro via Supabase Auth."""
    url, key = get_supabase_config()
    if not url or not key:
        return False, "Supabase não configurado."

    redirect_url = redirect_to or os.getenv("AUTH_REDIRECT_URL", "http://localhost:8000/login.html?verified=1")
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    payload = {
        "type": "signup",
        "email": email.lower().strip(),
        "options": {"email_redirect_to": redirect_url},
    }

    try:
        resp = requests.post(
            f"{url}/auth/v1/resend",
            headers=headers,
            json=payload,
            timeout=6.0,
        )
        if resp.status_code in (200, 201, 204):
            return True, "E-mail de confirmação reenviado pelo Supabase! Verifique sua caixa de entrada e a pasta de spam/lixeira."
        data = resp.json() if resp.content else {}
        err_code = str(data.get("error_code") or "").lower()
        if resp.status_code == 429 or "rate_limit" in err_code:
            return False, "Limite temporário de envio de e-mails do Supabase atingido (máx 3-4 por hora no plano gratuito). Verifique sua pasta de spam ou aguarde alguns minutos."
        msg = data.get("msg") or data.get("error_description") or data.get("message") or "Aguarde alguns segundos antes de solicitar novo envio."
        return False, msg
    except Exception as exc:
        return False, f"Erro ao reenviar confirmação: {exc}"


def supabase_sync_user_row(email: str, hashed_password: str, name: str, is_active: bool = False) -> bool:
    """Sincroniza o registro do usuário na tabela public.users do Supabase via PostgREST."""
    url, key = get_supabase_config()
    if not url or not key:
        return False

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    payload = {
        "email": email.lower().strip(),
        "hashed_password": hashed_password,
        "name": name,
        "is_active": is_active,
    }

    try:
        resp = requests.post(
            f"{url}/rest/v1/users?on_conflict=email",
            headers=headers,
            json=payload,
            timeout=5.0,
        )
        return resp.status_code in (200, 201, 204)
    except Exception as exc:
        logger.debug(f"Falha ao sincronizar usuário no PostgREST: {exc}")
        return False


def supabase_send_password_recovery(email: str, redirect_to: Optional[str] = None) -> Tuple[bool, str]:
    """Envia o e-mail oficial de redefinição de senha via Supabase Auth."""
    url, key = get_supabase_config()
    if not url or not key:
        return False, "Supabase não configurado."

    redirect_url = redirect_to or os.getenv("AUTH_RESET_REDIRECT_URL", "http://localhost:8000/novasenha.html")
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    payload = {
        "email": email.lower().strip(),
    }

    try:
        resp = requests.post(
            f"{url}/auth/v1/recover",
            params={"redirect_to": redirect_url},
            headers=headers,
            json=payload,
            timeout=6.0,
        )
        if resp.status_code in (200, 201, 204):
            return True, "E-mail de recuperação enviado pelo Supabase! Verifique sua caixa de entrada e a pasta de spam/lixeira."
        data = resp.json() if resp.content else {}
        err_code = str(data.get("error_code") or "").lower()
        if resp.status_code == 429 or "rate_limit" in err_code:
            return False, "Limite temporário de envio do Supabase atingido (máx 3-4 por hora). Verifique a pasta de spam ou utilize o código de contingência."
        msg = data.get("msg") or data.get("error_description") or data.get("message") or "Erro ao solicitar recuperação no Supabase."
        return False, msg
    except Exception as exc:
        return False, f"Erro ao contatar Supabase: {exc}"
