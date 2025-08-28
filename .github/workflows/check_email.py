import imaplib
import email
from datetime import datetime
import os

# Получаем данные из переменных окружения (будут из GitHub Secrets)
EMAIL = os.getenv("EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")

def check_new_emails():
    print(f"[{datetime.now()}] Проверка новых писем...")

    try:
        # Подключаемся к Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL, APP_PASSWORD)
        mail.select("inbox")

        # Ищем непрочитанные письма
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()

        if email_ids:
            print(f"✅ Найдено {len(email_ids)} новых писем!")
            # Можно добавить обработку: отправка в Telegram, запись в файл и т.д.
            for i, email_id in enumerate(email_ids[:5]):  # покажем первые 5
                _, msg_data = mail.fetch(email_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                subject = msg["Subject"] or "(без темы)"
                print(f"  {i+1}. Тема: {subject}")
        else:
            print("📭 Нет новых писем.")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"❌ Ошибка при проверке почты: {e}")
        raise

if __name__ == "__main__":
    if not EMAIL or not APP_PASSWORD:
        print("❗ Не заданы EMAIL или APP_PASSWORD")
    else:
        check_new_emails()
