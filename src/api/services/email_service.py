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

        
        # Versão HTML Profissional (Cyber Navy + Logo + Alerta Vermelho de Segurança)
        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recuperação de Senha - TrendCommerce AI</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #040d1a;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #ffffff;
        }}
        .wrapper {{
            width: 100%;
            background-color: #040d1a;
            padding: 30px 10px;
        }}
        .container {{
            max-width: 540px;
            margin: 0 auto;
            background: #07192e;
            border: 1px solid #00b4d8;
            border-radius: 16px;
            padding: 36px 28px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7), 0 0 25px rgba(0, 180, 216, 0.2);
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .logo-img {{
            max-height: 75px;
            width: auto;
            max-width: 220px;
            object-fit: contain;
            border-radius: 8px;
            margin-bottom: 12px;
            display: inline-block;
        }}
        .logo-title {{
            font-size: 24px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 0.5px;
            margin: 0;
        }}
        .logo-accent {{
            color: #00d4ff;
        }}
        .subtitle {{
            font-size: 11px;
            color: #64748b;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-top: 6px;
        }}
        .card-body {{
            background: #0a223f;
            border: 1px solid rgba(0, 212, 255, 0.35);
            border-radius: 12px;
            padding: 24px 20px;
            text-align: center;
            margin: 20px 0;
        }}
        .instructions {{
            color: #cbd5e1;
            font-size: 14px;
            line-height: 1.6;
            margin: 0 0 16px 0;
        }}
        .otp-box {{
            display: inline-block;
            background: #041021;
            border: 2px solid #00f0ff;
            border-radius: 10px;
            padding: 14px 28px;
            font-size: 38px;
            font-weight: 800;
            letter-spacing: 10px;
            color: #00f0ff;
            margin: 8px 0 14px 0;
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
            font-family: 'Courier New', Courier, monospace;
        }}
        .expiry {{
            color: #38bdf8;
            font-size: 13px;
            font-weight: 600;
        }}
        .security-alert {{
            background: rgba(239, 68, 68, 0.12);
            border: 1px solid #ef4444;
            border-left: 4px solid #ef4444;
            border-radius: 8px;
            padding: 16px;
            margin: 22px 0 10px 0;
            text-align: left;
        }}
        .security-title {{
            color: #f87171;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .security-text {{
            color: #fecaca;
            font-size: 12px;
            line-height: 1.5;
            margin: 0;
        }}
        .footer {{
            text-align: center;
            color: #64748b;
            font-size: 11px;
            line-height: 1.5;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            padding-top: 18px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="container">
            <div class="header">
                <div>
                    <img class="logo-img" src="cid:trendecommerce_logo" alt="TrendCommerce AI Logo" />
                </div>
                <h1 class="logo-title"><span class="logo-accent">Trend</span>Commerce AI</h1>
                <div class="subtitle">SISTEMA PREDITIVO DE VENDAS E DADOS</div>
            </div>

            <div class="card-body">
                <p class="instructions">
                    Olá! Recebemos uma solicitação para redefinir a senha da sua conta.<br>
                    Utilize o código de verificação abaixo para concluir o processo:
                </p>

                <div class="otp-box">{code}</div>

                <div class="expiry">⏱️ Este código expira em <strong>15 minutos</strong></div>
            </div>

            <div class="security-alert">
                <div class="security-title">⚠️ NUNCA COMPARTILHE ESTE CÓDIGO COM NINGUÉM</div>
                <p class="security-text">
                    Este código é <strong>estritamente pessoal, confidencial e intransferível</strong>. 
                    A equipe do <strong>TrendCommerce AI</strong> nunca entrará em contato solicitando seu código de recuperação ou sua senha. Se alguém solicitar este código, não informe.
                </p>
            </div>

            <div class="footer">
                <p>Se você não solicitou a redefinição de senha, desconsidere esta mensagem. Sua conta permanece totalmente protegida.</p>
                <p>© 2026 TrendCommerce AI — Inteligência Preditiva de Mercado</p>
            </div>
        </div>
    </div>
</body>
</html>