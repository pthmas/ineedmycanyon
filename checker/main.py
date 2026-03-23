import logging
import os
import random
import sys
import time

from dotenv import load_dotenv

from .notifier import broadcast, format_message
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
    required = ["BIKE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    chat_ids = [cid.strip() for cid in os.environ["TELEGRAM_CHAT_IDS"].split(",") if cid.strip()]

    return {
        "bike_url": os.environ["BIKE_URL"],
        "telegram_token": os.environ["TELEGRAM_BOT_TOKEN"],
        "telegram_chat_ids": chat_ids,
        "check_interval_hours": float(os.getenv("CHECK_INTERVAL_HOURS", "1")),
        "state_file": os.getenv("STATE_FILE_PATH", "/data/state.json"),
        "canyon_site": os.getenv("CANYON_SITE", "RoW"),
    }


def run_check(config: dict, params: dict, consecutive_failures: int) -> int:
    """Run a single check cycle. Returns updated consecutive_failures count."""
    try:
        new_state = fetch_bike_state(params)
        old_state = load_state(config["state_file"])

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
            message = format_message(config["bike_url"], changes)
            broadcast(config["telegram_token"], config["telegram_chat_ids"], message)
        else:
            logger.info(
                "No changes (available=%s, delivery=%s)",
                new_state.available,
                new_state.expected_delivery,
            )

        save_state(config["state_file"], new_state)
        return 0

    except Exception as e:
        consecutive_failures += 1
        logger.error("Check failed (attempt %d): %s", consecutive_failures, e)

        if consecutive_failures == 5:
            try:
                broadcast(
                    config["telegram_token"],
                    config["telegram_chat_ids"],
                    f"Canyon bike checker has failed {consecutive_failures} times in a row.\n"
                    f"Last error: {e}\n\nMonitoring may have lapsed.",
                )
            except Exception as notify_err:
                logger.error("Could not send failure notification: %s", notify_err)

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

    consecutive_failures = 0
    while True:
        consecutive_failures = run_check(config, params, consecutive_failures)
        jitter = random.uniform(-300, 300)
        sleep_seconds = config["check_interval_hours"] * 3600 + jitter
        logger.info("Next check in %.0f minutes", sleep_seconds / 60)
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
