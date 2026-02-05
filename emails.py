import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.concurrency import run_in_threadpool

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