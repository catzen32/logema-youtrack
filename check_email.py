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
    # Ищем все <tr> в письме
    tr_pattern = r'<tr[^>]*>(.*?)</tr>'
    matches = re.findall(tr_pattern, body, re.DOTALL | re.IGNORECASE)

    if len(matches) < 2:
        return None  # Нет второго tr

    second_tr_content = matches[1]  # Берём второй <tr>

    # Удаляем изображения
    clean_text = re.sub(r'<img[^>]*>', '', second_tr_content)
    # Заменяем ссылки на их текст
    clean_text = re.sub(r'<a[^>]*>([^<]*)</a>', r'\1', clean_text)
    # Удаляем остальные HTML-теги
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    # Убираем лишние пробелы и переносы
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    return clean_text if clean_text else None


def send_to_telegram(text):
    print(f"🔧 Отправляем в Telegram: {text[:50]}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
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
                if ALLOWED_SENDER and ALLOWED_SENDER not in sender:
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



                # === НОВЫЙ БЛОК: обработка писем от Bitrix24 с "Борисевич" ===
                if "bitrix24@rusgeocom.ru" in sender and "Борисевич" in body:
                    # Ищем фразу "Просмотр: " и извлекаем ссылку после неё
                    match = re.search(r'Просмотр:\s*<a[^>]+href="([^"]+)"', body, re.IGNORECASE)
                    if match:
                        view_link = match.group(1)
                        telegram_msg = f"Битрикс {view_link}"
                        print(f"📤 Отправляем Bitrix-сообщение: {telegram_msg}")
                        send_to_telegram(telegram_msg)
                        mark_as_read(mail, email_id)
                        continue  # Пропускаем остальную обработку
                # === КОНЕЦ НОВОГО БЛОКА ===

                # Извлекаем данные (старая логика)
                link_text, link_url = extract_youtrack_link(body)
                # ... остальной код без изменений ...


                
                # Извлекаем данные
                link_text, link_url = extract_youtrack_link(body)
                if not link_url:
                    print("❌ Ссылка на YouTrack не найдена")
                    mark_as_read(mail, email_id)
                    continue

                tr_text = extract_text_from_second_tr(body)
                if not tr_text:
                    tr_text = ""  # Не добавляем, если пусто

                # Формируем сообщение для Telegram
                telegram_text = f"{link_text}".strip()

                if tr_text:
                    telegram_text += f"\n\n{tr_text}"

                telegram_text += f"\n\n<a href='{link_url}'>Перейти к задаче</a>"

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
        exit(1)
    check_new_emails()
