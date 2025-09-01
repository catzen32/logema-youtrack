import imaplib
import email
from datetime import datetime
import os
import requests
import re
from bs4 import BeautifulSoup  # Нужно установить


def extract_youtrack_link(body):
    """
    Ищет вторую ссылку, начинающуюся с https://youtrack.logema.org/
    Возвращает (текст_ссылки, ссылка)
    """
    soup = BeautifulSoup(body, 'html.parser')
    links = soup.find_all('a', href=True)
    youtrack_links = [link for link in links if link['href'].startswith("https://youtrack.logema.org/")]

    if len(youtrack_links) >= 2:
        link = youtrack_links[1]
        return link.get_text(strip=True), link['href']
    elif len(youtrack_links) == 1:
        link = youtrack_links[0]
        return link.get_text(strip=True), link['href']
    else:
        return None, None


def extract_second_td_text(body):
    """
    Ищет второй <td> с нужным стилем и извлекает из него чистый текст
    """
    soup = BeautifulSoup(body, 'html.parser')
    tds = soup.find_all('td', style=re.compile(r'padding: 12px 16px;background: rgb\(240, 240, 240\)'))
    
    if len(tds) >= 2:
        td = tds[1]
        # Удаляем теги, картинки, ссылки — оставляем только текст
        for img in td.find_all('img'):
            img.decompose()
        for a in td.find_all('a'):
            a.replace_with(a.get_text())  # Заменяем ссылку на её текст
        return td.get_text(strip=False).strip()
    elif len(tds) == 1:
        td = tds[0]
        for img in td.find_all('img'):
            img.decompose()
        for a in td.find_all('a'):
            a.replace_with(a.get_text())
        return td.get_text(strip=False).strip()
    return None


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
                if ALLOWED_SENDER not in sender:
                    print(f"📧 Пропуск письма от: {sender}")
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

                # Ищем вторую ссылку на YouTrack
                link_text, link_url = extract_youtrack_link(body)
                if not link_url:
                    print("❌ Ссылка на YouTrack не найдена")
                    mark_as_read(mail, email_id)
                    continue

                # Извлекаем текст из второго <td>
                td_text = extract_second_td_text(body)
                if not td_text:
                    td_text = "Текст из уведомления не извлечён."

                # Формируем сообщение для Telegram
                telegram_text = f"""
{td_text}

<a href="{link_url}">Перейти к задаче</a>
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
