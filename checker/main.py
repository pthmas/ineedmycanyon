import json
import logging
import os
import random
import sys
import time

from dotenv import load_dotenv

from .notifier import broadcast, format_failure, format_heartbeat, format_message, send_message
from .scraper import extract_params_from_url, fetch_bike_state
from .state import diff_states, load_state, save_state

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    required = ["BIKE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS", "TELEGRAM_ADMIN_CHAT_ID"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    chat_ids = [cid.strip() for cid in os.environ["TELEGRAM_CHAT_IDS"].split(",") if cid.strip()]

    return {
        "bike_url": os.environ["BIKE_URL"],
        "telegram_token": os.environ["TELEGRAM_BOT_TOKEN"],
        "telegram_chat_ids": chat_ids,
        "admin_chat_id": os.environ["TELEGRAM_ADMIN_CHAT_ID"],
        "check_interval_hours": float(os.getenv("CHECK_INTERVAL_HOURS", "1")),
        "heartbeat_interval_days": int(os.getenv("HEARTBEAT_INTERVAL_DAYS", "3")),
        "state_file": os.getenv("STATE_FILE_PATH", "/data/state.json"),
        "canyon_site": os.getenv("CANYON_SITE", "RoW"),
    }


def _heartbeat_file(state_file: str) -> str:
    return state_file.replace("state.json", "heartbeat.json")


def load_last_heartbeat(state_file: str) -> float:
    try:
        with open(_heartbeat_file(state_file)) as f:
            return json.load(f)["last_sent"]
    except Exception:
        return 0.0


def save_last_heartbeat(state_file: str) -> None:
    path = _heartbeat_file(state_file)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump({"last_sent": time.time()}, f)


def maybe_send_heartbeat(config: dict, params: dict, current_state) -> None:
    last = load_last_heartbeat(config["state_file"])
    interval = config["heartbeat_interval_days"] * 86400
    if time.time() - last >= interval:
        available = current_state.available if current_state else False
        product_name = current_state.product_name if current_state else None
        message = format_heartbeat(
            product_name=product_name,
            size=params["size_value"],
            available=available,
            check_interval_hours=config["check_interval_hours"],
            heartbeat_interval_days=config["heartbeat_interval_days"],
        )
        try:
            send_message(config["telegram_token"], config["admin_chat_id"], message)
            save_last_heartbeat(config["state_file"])
            logger.info("Heartbeat sent to admin")
        except Exception as e:
            logger.error("Failed to send heartbeat: %s", e)


def run_check(config: dict, params: dict, consecutive_failures: int) -> int:
    """Run a single check cycle. Returns updated consecutive_failures count."""
    try:
        new_state = fetch_bike_state(params)
        old_state = load_state(config["state_file"])

        maybe_send_heartbeat(config, params, new_state)

        if old_state is None:
            logger.info(
                "First run — saving initial state (available=%s, delivery=%s)",
                new_state.available,
                new_state.expected_delivery,
            )
            save_state(config["state_file"], new_state)
            return 0

        changes = diff_states(old_state, new_state)
        if changes:
            logger.info("State changed: %s", changes)
            message = format_message(
                config["bike_url"],
                changes,
                new_available=new_state.available,
                product_name=new_state.product_name,
            )
            broadcast(config["telegram_token"], config["telegram_chat_ids"], message)
        else:
            logger.info(
                "No changes (available=%s, delivery=%s)",
                new_state.available,
                new_state.expected_delivery,
            )

        save_state(config["state_file"], new_state)

        if consecutive_failures > 0:
            logger.info("Recovered after %d failure(s)", consecutive_failures)

        return 0

    except Exception as e:
        consecutive_failures += 1
        logger.error("Check failed (attempt %d): %s", consecutive_failures, e)

        # Alert admin on first failure and every 5 after that
        if consecutive_failures == 1 or consecutive_failures % 5 == 0:
            try:
                send_message(
                    config["telegram_token"],
                    config["admin_chat_id"],
                    format_failure(str(e), consecutive_failures),
                )
            except Exception as notify_err:
                logger.error("Could not send failure alert to admin: %s", notify_err)

        return consecutive_failures


def main() -> None:
    config = load_config()
    params = extract_params_from_url(config["bike_url"], site=config["canyon_site"])

    logger.info("Starting Canyon bike checker")
    logger.info("Bike: %s", config["bike_url"])
    logger.info(
        "Monitoring: size=%s, color=%s", params["size_value"], params["color_value"]
    )
    logger.info("Check interval: %s hour(s)", config["check_interval_hours"])
    logger.info("Heartbeat: every %s day(s) to admin", config["heartbeat_interval_days"])

    consecutive_failures = 0
    while True:
        consecutive_failures = run_check(config, params, consecutive_failures)
        jitter = random.uniform(-300, 300)
        sleep_seconds = config["check_interval_hours"] * 3600 + jitter
        logger.info("Next check in %.0f minutes", sleep_seconds / 60)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
