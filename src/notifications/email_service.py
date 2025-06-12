from email.message import EmailMessage
import aiosmtplib

from notifications import EmailSenderInterface

class SMTPEmailSender(EmailSenderInterface):
    def __init__(self, smtp_host, smtp_port, username, password):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    async def send_email(self, to: str, subject: str, body: str):
        message = EmailMessage()
        message["From"] = self.username
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            start_tls=True,
            username=self.username,
            password=self.password,
        )
