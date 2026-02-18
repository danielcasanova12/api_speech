import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.concurrency import run_in_threadpool
from datetime import datetime

from config import settings

async def send_email(to_email: str, subject: str, html_content: str):
    """
    Envia um e-mail usando SMTP de forma assíncrona.
    """
    # Verifica se as configurações de SMTP estão presentes
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.EMAILS_FROM_EMAIL]):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! AVISO: Configurações de SMTP não estão completas. !!!")
        print("!!! O e-mail não será enviado.                       !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = settings.EMAILS_FROM_EMAIL
    message["To"] = to_email

    # Anexa a parte HTML ao e-mail
    message.attach(MIMEText(html_content, "html"))

    def send_sync_email():
        try:
            # Conecta ao servidor SMTP e envia o e-mail
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()  # Habilita segurança
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(
                    settings.EMAILS_FROM_EMAIL, to_email, message.as_string()
                )
            print(f"E-mail enviado para {to_email} com sucesso.")
        except Exception as e:
            print(f"Erro ao enviar e-mail para {to_email}: {e}")

    # Executa a função de envio síncrona em um thread pool
    await run_in_threadpool(send_sync_email)

async def send_reset_password_email(to_email: str, token: str):
    """
    Envia o e-mail de redefinição de senha.
    """
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Redefinição de Senha"
    link = f"http://localhost:3000/reset-password?token={token}" # Exemplo: ajuste para sua URL real
    html_content = f"""
    <p>Olá,</p>
    <p>Você solicitou a redefinição da sua senha. Clique no link abaixo para continuar:</p>
    <p><a href=\"{link}\">{link}</a></p>
    <p>Se você não solicitou isso, por favor, ignore este e-mail.</p>
    """
    await send_email(to_email, subject, html_content)

async def send_verification_email(to_email: str, token: str):
    """
    Envia o e-mail de verificação de conta.
    """
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Verifique sua conta"
    link = f"http://localhost:3000/verify?token={token}" # Exemplo: ajuste para sua URL real
    html_content = f"""
    <p>Olá,</p>
    <p>Obrigado por se registrar! Por favor, clique no link abaixo para verificar seu endereço de e-mail:</p>
    <p><a href=\"{link}\">{link}</a></p>
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
    subject = f"Sua sessão no dataset {dataset_name} foi {subject_status}"
    
    # Calcular duração se houver data de fim
    duration_str = "N/A"
    if finished_at and started_at:
        diff = finished_at - started_at
        minutes = int(diff.total_seconds() // 60)
        seconds = int(diff.total_seconds() % 60)
        duration_str = f"{minutes}m {seconds}s"

    # Conteúdo do email (HTML simples)
    if status == "finished":
        intro = f"Parabéns <strong>{user_name}</strong>! Você concluiu uma sessão de gravação."
        color = "#4CAF50" # Green
    else:
        intro = f"Olá <strong>{user_name}</strong>. Confirmamos o cancelamento da sua sessão."
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
                    <td style="padding: 10px;">{dataset_name}</td>
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
