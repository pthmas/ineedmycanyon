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


def broadcast(token: str, chat_ids: list[str], text: str) -> None:
    """Send a Telegram message to all subscribers."""
    for chat_id in chat_ids:
        try:
            send_message(token, chat_id, text)
        except Exception as e:
            logger.error("Failed to send message to chat_id %s: %s", chat_id, e)


def format_heartbeat(product_name: str | None, size: str, available: bool, check_interval_hours: float, heartbeat_interval_days: int) -> str:
    """Format a heartbeat status message for the admin."""
    name = f"Canyon {product_name}" if product_name else "Canyon bike"
    status = "Not in stock" if not available else "IN STOCK"
    return (
        f"✅ Canyon checker is alive\n\n"
        f"Monitoring: {name} (size {size})\n"
        f"Current status: {status}\n"
        f"Check frequency: every {check_interval_hours:.0f}h\n\n"
        f"Next heartbeat in {heartbeat_interval_days} days."
    )


def format_failure(error: str, attempt: int) -> str:
    """Format a failure alert message for the admin."""
    return (
        f"⚠️ Canyon checker failure (attempt #{attempt})\n\n"
        f"Error: {error}"
    )


def format_message(bike_url: str, changes: list[str], new_available: bool = False, product_name: str | None = None) -> str:
    """Format a Telegram notification message."""
    if new_available and any("IN STOCK" in c for c in changes):
        name = f"Canyon {product_name}" if product_name else "Your Canyon bike"
        lines = [
            "🚨🚨 YOUR BIKE IS BACK IN STOCK 🚨🚨",
            "",
            f"🎉 The {name} is AVAILABLE NOW! 🔥🔥🔥",
            "",
            "👇 BUY IT NOW BEFORE IT'S GONE 👇",
            bike_url,
        ]
    else:
        lines = ["<b>Canyon Bike Alert</b>", ""]
        lines.extend(f"• {change}" for change in changes)
        lines.extend(["", bike_url])
    return "\n".join(lines)
