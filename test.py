import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["Subject"] = "Teste SMTP"
msg["From"] = "smtpakcit@gmail.com"
msg["To"] = "snaxofc11@gmail.com"
msg.set_content("Funcionou!")

with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
    smtp.starttls()
    smtp.login("smtpakcit@gmail.com", "gqrh vayy todp frht")
    smtp.send_message(msg)

print("EMAIL ENVIADO")
