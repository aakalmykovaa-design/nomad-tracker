import os
import logging
import httpx

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "ok": "✅",
    "info": "ℹ️",
    "warning": "⚠️",
    "urgent": "🚨",
}


def send_alert(chat_id: str, country_flag: str, country_name: str, title: str, summary: str, severity: str = "info") -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not chat_id:
        logger.warning("Telegram не настроен (нет токена или chat_id)")
        return False

    emoji = SEVERITY_EMOJI.get(severity, "ℹ️")
    text = (
        f"{emoji} *{country_flag} {country_name}*\n\n"
        f"*{title}*\n\n"
        f"{summary}\n\n"
        f"_Nomad Tracker_"
    )

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram ошибка: {e}")
        return False


def send_test_message(chat_id: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not chat_id:
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ Nomad Tracker подключён! Буду присылать алерты сюда."},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram test error: {e}")
        return False
