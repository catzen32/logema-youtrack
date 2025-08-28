import imaplib
import email
from datetime import datetime
import os
import requests
import re

# === Переменные из секретов ===
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("MAIL_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_SENDER = os.getenv("SENDER_EMAIL")  # Только от этого отправителя

IMAP_SERVER = "imap.mail.ru"
IMAP_PORT = 993


def extract_youtrack_link(body):
    """
    Ищет вторую ссылку, начинающуюся с https://youtrack.logema.org/
    Возвращает (текст_ссылки, ссылка)
    """
    # Найдём все ссылки вида: <a href="URL">Текст</a>
    pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, body, re.IGNORECASE)

    # Фильтруем только те, что начинаются с нужного URL
    youtrack_links = [m for m in matches if m[0].startswith("https://youtrack.logema.org/")]

    if len(youtrack_links) >= 2:
        link_info = youtrack_links[1]  # Вторая ссылка
        return link_info[1].strip(), link_info[0]  # (текст, URL)
    elif len(youtrack_links) == 1:
        return youtrack_links[0][1].strip(), youtrack_links[0][0]
    else:
        return None, None


def send_to_telegram(text):
    print(f"🔧 Отправляем в Telegram: {text[:50]}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False  # Пусть ссылка отображается красиво
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"📨 Статус: {response.status_code}, ответ: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")


def mark_as_read(mail, email_id):
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        print(f"✅ Письмо {email_id.decode()} отмечено как прочитанное")
    except Exception as e:
        print(f"❌ Ошибка при отметке: {e}")


def decode_header(header):
    decoded_parts = email.header.decode_header(header)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="ignore")
        else:
            result += part
    return result


def check_new_emails():
    print(f"[{datetime.now()}] 🔎 Проверка почты: {EMAIL}")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL, PASSWORD)
        print("✅ Вход выполнен")

        mail.select("INBOX")
        _, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split() if messages[0] else []

        if not email_ids:
            print("📭 Нет новых писем")
            return

        print(f"✅ Найдено {len(email_ids)} непрочитанных писем")

        for email_id in email_ids:
            try:
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                # Проверяем отправителя
                sender = msg.get("From", "")
                if ALLOWED_SENDER not in sender:
                    print(f"📧 Пропуск письма от: {sender} (не из списка разрешённых)")
                    continue

                # Декодируем тему
                subject = decode_header(msg["Subject"]) if msg["Subject"] else "Без темы"

                # Получаем тело письма
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    if msg.get_content_type() == "text/html":
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                if not body:
                    print("⚠️ Тело письма пустое")
                    mark_as_read(mail, email_id)
                    continue

                # Ищем вторую ссылку на youtrack.logema.org
                link_text, link_url = extract_youtrack_link(body)

                if not link_url:
                    print("❌ Ссылка на YouTrack не найдена")
                    mark_as_read(mail, email_id)
                    continue

                # Формируем сообщение
                telegram_text = f"""
📬 <b>Новое уведомление из YouTrack</b>
📌 <b>Событие:</b> {link_text}
🔗 <a href="{link_url}">Перейти к задаче</a>
                """.strip()

                print(f"📤 Отправляем: {link_text}")
                send_to_telegram(telegram_text)
                mark_as_read(mail, email_id)

            except Exception as e:
                print(f"❌ Ошибка обработки письма: {e}")

        mail.logout()
        print("🔚 Проверка завершена")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise


if __name__ == "__main__":
    if not all([EMAIL, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALLOWED_SENDER]):
        print("❗ Не все секреты заданы!")
#        exit(1)

    check_new_emails()
