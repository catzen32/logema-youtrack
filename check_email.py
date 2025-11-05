import imaplib
import email
from datetime import datetime
import os
import requests
import re
import html  # для декодирования &amp; -> &

# === Переменные из секретов ===
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("MAIL_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALLOWED_SENDER = os.getenv("SENDER_EMAIL")  # Только письма от этого отправителя

print(f"🔍 ALLOWED_SENDER: '{ALLOWED_SENDER}'")

IMAP_SERVER = "imap.mail.ru"
IMAP_PORT = 993


def extract_youtrack_link(body):
    """
    Ищет вторую ссылку, начинающуюся с https://youtrack.logema.org/
    Возвращает (текст_ссылки, ссылка)
    """
    pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, body, re.IGNORECASE)
    youtrack_links = [m for m in matches if m[0].startswith("https://youtrack.logema.org/")]
    if len(youtrack_links) >= 2:
        link_info = youtrack_links[1]  # Вторая ссылка
        return link_info[1].strip(), link_info[0]
    elif len(youtrack_links) == 1:
        return youtrack_links[0][1].strip(), youtrack_links[0][0]
    else:
        return None, None


def extract_text_from_second_tr(body):
    """
    Извлекает текст из второго <tr> в письме.
    Удаляет <img>, <a> и другие теги, оставляя только чистый текст.
    """
    tr_pattern = r'<tr[^>]*>(.*?)</tr>'
    matches = re.findall(tr_pattern, body, re.DOTALL | re.IGNORECASE)

    if len(matches) < 2:
        return None  # Нет второго tr

    second_tr_content = matches[1]

    clean_text = re.sub(r'<img[^>]*>', '', second_tr_content)
    clean_text = re.sub(r'<a[^>]*>([^<]*)</a>', r'\1', clean_text)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    return clean_text if clean_text else None


def send_to_telegram(text):
    print(f"🔧 Отправляем в Telegram: {text[:50]}...")
    # Исправлен URL: убраны пробелы после "bot"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            print("✅ Сообщение в Telegram отправлено")
        else:
            print(f"❌ Telegram API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")


def mark_as_read(mail, email_id):
    try:
        mail.store(email_id, '+FLAGS', '\\Seen')
        print(f"✅ Письмо {email_id.decode()} отмечено как прочитанное")
    except Exception as e:
        print(f"❌ Ошибка при отметке: {e}")


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

                sender = msg.get("From", "")

                # Разрешаем основной отправитель ИЛИ Bitrix24
                is_allowed_sender = ALLOWED_SENDER and ALLOWED_SENDER in sender
                is_bitrix_sender = "bitrix24@rusgeocom.ru" in sender

                if not (is_allowed_sender or is_bitrix_sender):
                    print(f"📧 Пропуск письма от: {sender}")
                    continue

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

                # === Обработка писем от Bitrix24 с "Борисевич" ===
                if "bitrix24@rusgeocom.ru" in sender and "Борисевич" in body:
                    print("✅ Найдено письмо от Bitrix24 с Борисевичем")

                    # Попытка 1: извлечь из href
                    match = re.search(r'Просмотр:\s*<a[^>]+href="([^"]+)"', body, re.IGNORECASE)
                    if match:
                        raw_link = match.group(1)
                        view_link = html.unescape(raw_link)
                    else:
                        # Попытка 2: извлечь plain URL
                        match = re.search(r'Просмотр:\s*(https?://[^\s<>"\)]+)', body, re.IGNORECASE)
                        if match:
                            view_link = match.group(1)
                        else:
                            print("❌ Не удалось найти ссылку после 'Просмотр:'")
                            mark_as_read(mail, email_id)
                            continue

                    telegram_msg = f"Битрикс {view_link}"
                    print(f"📤 Отправляем в Telegram: {telegram_msg}")
                    send_to_telegram(telegram_msg)
                    mark_as_read(mail, email_id)
                    continue
                # === Конец обработки Bitrix24 ===

                # === Обработка YouTrack ===
                link_text, link_url = extract_youtrack_link(body)
                if not link_url:
                    print("❌ Ссылка на YouTrack не найдена")
                    mark_as_read(mail, email_id)
                    continue

                tr_text = extract_text_from_second_tr(body)
                if not tr_text:
                    tr_text = ""

                telegram_text = f"{link_text}".strip()
                if tr_text:
                    telegram_text += f"\n\n{tr_text}"
                telegram_text += f"\n\n<a href='{link_url}'>Перейти к задаче</a>"

                print(f"📤 Отправляем YouTrack-сообщение: {link_text}")
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
    required_vars = [EMAIL, PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALLOWED_SENDER]
    if not all(required_vars):
        print("❗ Не все секреты заданы!")
        exit(1)
    check_new_emails()
