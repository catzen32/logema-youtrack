import imaplib
import email
from datetime import datetime
import os
import requests

# === Переменные из секретов ===
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("MAIL_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

IMAP_SERVER = "imap.mail.ru"
IMAP_PORT = 993


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition and "text/plain" in content_type:
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                return body[:2000]
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        return body[:2000]
    return "(нет текста)"


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Сообщение в Telegram отправлено")
        else:
            print(f"❌ Ошибка Telegram: {r.status_code}, {r.text}")
    except Exception as e:
        print(f"❌ Исключение при отправке в Telegram: {e}")


def mark_as_read(mail, email_id):
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        print(f"✅ Письмо {email_id.decode()} отмечено как прочитанное")
    except Exception as e:
        print(f"❌ Не удалось отметить как прочитанное: {e}")


def decode_header(header):
    decoded_fragments = email.header.decode_header(header)
    result = ""
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result += fragment.decode(charset or "utf-8", errors="ignore")
        else:
            result += fragment
    return result


def check_new_emails():
    print(f"[{datetime.now()}] 🔎 Подключение к почте: {EMAIL}")
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL, PASSWORD)
        print("✅ Успешный вход в почту")
        
        status, _ = mail.select("INBOX")
        if status != "OK":
            print("❌ Не удалось открыть INBOX")
            return

        # Покажем общее количество писем
        status, total = mail.search(None, "ALL")
        print(f"📬 Всего писем в INBOX: {len(total[0].split()) if total[0] else 0}")

        # Ищем непрочитанные
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split() if messages[0] else []

        if not email_ids:
            print("📭 Нет непрочитанных писем")
        else:
            print(f"✅ Найдено {len(email_ids)} непрочитанных писем. Обрабатываю...")

            for email_id in email_ids:
                try:
                    _, msg_data = mail.fetch(email_id, '(RFC822)')
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)

                    subject = decode_header(msg["Subject"]) if msg["Subject"] else "Без темы"
                    sender = msg["From"]

                    body = get_body(msg)

                    text = f"""
📬 <b>Новое письмо</b>
📧 От: {sender}
📌 Тема: {subject}
📄 Текст:
{body}
                    """.strip()

                    send_to_telegram(text)
                    mark_as_read(mail, email_id)

                except Exception as e:
                    print(f"❌ Ошибка обработки письма {email_id}: {e}")

        mail.close()
        mail.logout()
        print("🔚 Проверка завершена")

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        raise


if __name__ == "__main__":
    if not EMAIL:
        print("❗ EMAIL не задан — проверь секреты")
    if not PASSWORD:
        print("❗ MAIL_PASSWORD не задан — проверь секреты")
    if not TELEGRAM_BOT_TOKEN:
        print("❗ TELEGRAM_BOT_TOKEN не задан — проверь секреты")
    if not TELEGRAM_CHAT_ID:
        print("❗ TELEGRAM_CHAT_ID не задан — проверь секреты")

    if not all([EMAIL, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("❌ Не все секреты переданы. Выход.")
        exit(1)

    check_new_emails()
