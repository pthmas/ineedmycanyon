import json
import logging
import os
from dataclasses import asdict
from typing import Optional

from .scraper import BikeState

logger = logging.getLogger(__name__)


def load_state(path: str) -> Optional[BikeState]:
    """Load saved state from JSON file. Returns None on first run."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return BikeState(**data)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("Could not load state file (treating as first run): %s", e)
        return None


def save_state(path: str, state: BikeState) -> None:
    """Atomically save state to JSON file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(asdict(state), f, indent=2)
    os.replace(tmp_path, path)


def diff_states(old: BikeState, new: BikeState) -> list[str]:
    """Return list of human-readable change descriptions between two states."""
    changes = []

    if old.available != new.available:
        if new.available:
            changes.append("Bike is now IN STOCK!")
        else:
            changes.append("Bike is now out of stock.")
    elif old.availability_text != new.availability_text:
        changes.append(
            f"Availability status changed: {old.availability_text!r} → {new.availability_text!r}"
        )

    if old.expected_delivery != new.expected_delivery:
        if old.expected_delivery and new.expected_delivery:
            changes.append(
                f"Delivery date changed: {old.expected_delivery} → {new.expected_delivery}"
            )
        elif new.expected_delivery:
            changes.append(f"Delivery date added: {new.expected_delivery}")
        elif old.expected_delivery:
            changes.append(f"Delivery date removed (was: {old.expected_delivery})")

    return changes
