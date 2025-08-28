import imaplib
import email
from datetime import datetime

def fetch_unseen_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login("your_email@gmail.com", "your_app_password")
    mail.select("inbox")

    status, messages = mail.search(None, '(UNSEEN)')
    ids = messages[0].split()

    print(f"[{datetime.now()}] Найдено новых писем: {len(ids)}")

    for email_id in ids:
        _, msg_data = mail.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        print(f"Тема: {msg['Subject']}")

    mail.logout()

if __name__ == "__main__":
    EMAIL = "your_email@gmail.com"
    PASSWORD = "your_app_password"  # из GitHub Secrets

    # Замени на переменные окружения
    import os
    EMAIL = os.getenv("EMAIL")
    PASSWORD = os.getenv("APP_PASSWORD")

    fetch_unseen_emails()
