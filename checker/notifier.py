import logging

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send a Telegram message to a specific user."""
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    logger.info("Telegram message sent to chat_id %s", chat_id)


def format_message(bike_url: str, changes: list[str]) -> str:
    """Format a Telegram notification message."""
    lines = ["<b>Canyon Bike Alert</b>", ""]
    lines.extend(f"• {change}" for change in changes)
    lines.extend(["", bike_url])
    return "\n".join(lines)
