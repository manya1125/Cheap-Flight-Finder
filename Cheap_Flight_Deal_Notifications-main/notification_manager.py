import os
import smtplib

try:
    from twilio.rest import Client
except ImportError:
    Client = None

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


class NotificationManager:
    def __init__(self):
        if Client and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        else:
            self.client = None

    def email_configured(self):
        return bool(SMTP_EMAIL and SMTP_PASSWORD)

    def send_email(self, email, message):
        return self.send_emails([email], message)

    def send_emails(self, emails, message):
        if not SMTP_EMAIL or not SMTP_PASSWORD:
            return False

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as connection:
                connection.starttls()
                connection.login(user=SMTP_EMAIL, password=SMTP_PASSWORD)

                subject = "Flight Deal Alert"
                for email in emails:
                    email_body = f"Subject:{subject}\n\n{message}"
                    connection.sendmail(
                        from_addr=SMTP_EMAIL,
                        to_addrs=email,
                        msg=email_body.encode("utf-8"),
                    )
            return True
        except smtplib.SMTPException:
            return False

    def send_msg(self, message, to_number):
        if not self.client or not TWILIO_PHONE_NUMBER:
            return False

        try:
            self.client.messages.create(
                from_=TWILIO_PHONE_NUMBER,
                body=message,
                to=to_number,
            )
            return True
        except Exception:
            return False
