import html
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
from urllib.parse import urlencode

from config import settings

logger = logging.getLogger(__name__)

class EmailConfigurationError(RuntimeError):
    """Raised when email delivery is requested without a complete SMTP setup."""


class EmailDeliveryError(RuntimeError):
    """Raised when the SMTP server cannot deliver a message."""


def _redact_email(email_address: str) -> str:
    """Return a log-safe representation of an email address."""
    local_part, separator, domain = email_address.partition("@")
    if not separator:
        return "<invalid-email>"
    visible = local_part[:1] if local_part else "*"
    safe_domain = domain.replace("\r", "").replace("\n", "")
    return f"{visible}***@{safe_domain}"


def _safe_header(value: str) -> str:
    """Collapse line breaks so dynamic values cannot create email headers."""
    return " ".join(value.splitlines()).strip()


def _token_link(path: str, token: str) -> str:
    """Build an encoded action link without interpolating a raw token into HTML."""
    query = urlencode({"token": token})
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/{path}?{query}"


async def send_email(to_email: str, subject: str, html_content: str):
    """
    Envia um e-mail usando SMTP de forma assíncrona.
    """
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.EMAILS_FROM_EMAIL]):
        logger.error("Configuração SMTP incompleta; mensagem não enviada")
        raise EmailConfigurationError("Configuração SMTP incompleta")

    message = MIMEMultipart("alternative")
    safe_subject = _safe_header(subject)
    safe_from_email = _safe_header(settings.EMAILS_FROM_EMAIL)
    safe_to_email = _safe_header(to_email)
    message["Subject"] = safe_subject
    message["From"] = safe_from_email
    message["To"] = safe_to_email

    # Anexa a parte HTML ao e-mail
    message.attach(MIMEText(html_content, "html"))

    def send_sync_email():
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        ) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(
                safe_from_email, safe_to_email, message.as_string()
            )

    try:
        await run_in_threadpool(send_sync_email)
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail para %s", _redact_email(to_email))
        raise EmailDeliveryError("Não foi possível enviar o e-mail") from exc

    logger.info("E-mail enviado para %s", _redact_email(to_email))

async def send_reset_password_email(to_email: str, token: str):
    """
    Envia o e-mail de redefinição de senha.
    """
    project_name = _safe_header(settings.PROJECT_NAME)
    subject = f"{project_name} - Redefinição de Senha"
    link = _token_link("reset-password", token)
    safe_link = html.escape(link, quote=True)
    html_content = f"""
    <p>Olá,</p>
    <p>Você solicitou a redefinição da sua senha. Clique no link abaixo para continuar:</p>
    <p><a href=\"{safe_link}\">{safe_link}</a></p>
    <p>Se você não solicitou isso, por favor, ignore este e-mail.</p>
    """
    await send_email(to_email, subject, html_content)

async def send_verification_email(to_email: str, token: str):
    """
    Envia o e-mail de verificação de conta.
    """
    project_name = _safe_header(settings.PROJECT_NAME)
    subject = f"{project_name} - Verifique sua conta"
    link = _token_link("verify", token)
    safe_link = html.escape(link, quote=True)
    html_content = f"""
    <p>Olá,</p>
    <p>Obrigado por se registrar! Por favor, clique no link abaixo para verificar seu endereço de e-mail:</p>
    <p><a href=\"{safe_link}\">{safe_link}</a></p>
    """
    await send_email(to_email, subject, html_content)

async def send_session_status_email(
    to_email: str, 
    user_name: str, 
    dataset_name: str, 
    status: str, 
    started_at: datetime, 
    finished_at: datetime = None,
    recordings_count: int = 0
):
    """
    Envia email quando uma sessão é finalizada ou cancelada.
    """
    subject_status = "Finalizada com Sucesso" if status == "finished" else "Cancelada"
    subject = f"Sua sessão no dataset {_safe_header(dataset_name)} foi {subject_status}"
    safe_user_name = html.escape(user_name, quote=True)
    safe_dataset_name = html.escape(dataset_name, quote=True)
    
    # Calcular duração se houver data de fim
    duration_str = "N/A"
    if finished_at and started_at:
        diff = finished_at - started_at
        minutes = int(diff.total_seconds() // 60)
        seconds = int(diff.total_seconds() % 60)
        duration_str = f"{minutes}m {seconds}s"

    # Conteúdo do email (HTML simples)
    if status == "finished":
        intro = f"Parabéns <strong>{safe_user_name}</strong>! Você concluiu uma sessão de gravação."
        color = "#4CAF50" # Green
    else:
        intro = f"Olá <strong>{safe_user_name}</strong>. Confirmamos o cancelamento da sua sessão."
        color = "#F44336" # Red

    html_content = f"""
    <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
        <div style="background-color: {color}; color: white; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">Sessão {subject_status}</h2>
        </div>
        <div style="padding: 20px;">
            <p>{intro}</p>
            <p>Aqui estão os detalhes da sua contribuição:</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold;">Dataset:</td>
                    <td style="padding: 10px;">{safe_dataset_name}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold;">Início:</td>
                    <td style="padding: 10px;">{started_at.strftime('%d/%m/%Y %H:%M')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 10px; font-weight: bold;">Duração:</td>
                    <td style="padding: 10px;">{duration_str}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold;">Gravações:</td>
                    <td style="padding: 10px;">{recordings_count}</td>
                </tr>
            </table>
            <p style="margin-top: 20px;">Obrigado por contribuir com nossa pesquisa de voz!</p>
        </div>
        <div style="background-color: #f9f9f9; padding: 10px; text-align: center; font-size: 12px; color: #888;">
            <p>Este é um email automático, por favor não responda.</p>
        </div>
    </div>
    """
    
    await send_email(to_email, subject, html_content)
