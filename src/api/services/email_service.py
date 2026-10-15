import os
import smtplib
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


load_dotenv()


def send_otp_email(to_email: str, code: str) -> tuple[bool, str]:
    """Envia um e-mail HTML real com o código de recuperação de senha.
    
    Retorna:
        tuple[bool, str]: (sucesso: bool, mensagem_status: str)
    """
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", "trendeccomerceai@gmail.com").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
    from_name = os.getenv("EMAIL_FROM_NAME", "TrendCommerce AI").strip()

    if not smtp_password:
        logger.warning(
            f"Senha de aplicativo SMTP (SMTP_PASSWORD) não configurada para {smtp_user}. "
            "Defina SMTP_PASSWORD no .env ou nas variáveis de ambiente do Render."
        )
        return False, "Servidor de envio de e-mail não configurado (SMTP_PASSWORD ausente)."

    try:
        # Container principal com suporte a imagem incorporada (CID)
        msg_root = MIMEMultipart("related")
        msg_root["Subject"] = f"🔐 {code} é o seu código de recuperação — TrendCommerce AI"
        msg_root["From"] = f"{from_name} <{smtp_user}>"
        msg_root["To"] = to_email
        msg_root["Date"] = formatdate(localtime=True)
        msg_root["Message-ID"] = make_msgid(domain="gmail.com")

        # Container alternativo (Texto puro + HTML)
        msg_alternative = MIMEMultipart("alternative")
        msg_root.attach(msg_alternative)

        # Versão Texto Puro
        text_content = f"""TrendCommerce AI - Recuperação de Senha

Seu código de verificação é: {code}

⚠️ ATENÇÃO DE SEGURANÇA:
NUNCA COMPARTILHE ESTE CÓDIGO COM NINGUÉM.
Este código é estritamente pessoal, confidencial e intransferível.
A equipe do TrendCommerce AI NUNCA entrará em contato para solicitar seu código ou sua senha.

⏱️ Este código expira em 15 minutos.
Se você não solicitou a recuperação de senha, nenhuma ação é necessária.

© 2026 TrendCommerce AI — Inteligência Preditiva de Mercado
"""