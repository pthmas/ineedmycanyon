import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept": "application/json, text/html, */*",
}

BASE_URL = "https://www.canyon.com"


@dataclass
class BikeState:
    available: bool
    availability_text: str
    expected_delivery: str | None


def extract_params_from_url(product_url: str, site: str = "RoW") -> dict:
    """Extract Canyon Demandware API parameters from a product page URL.

    Example URL:
    https://www.canyon.com/de-de/rennrad/.../4164.html?dwvar_4164_pv_rahmenfarbe=R138_P01&dwvar_4164_pv_rahmengroesse=M
    """
    parsed = urlparse(product_url)

    # Extract locale from first path segment (e.g. /de-de/ → de_DE)
    path_parts = [p for p in parsed.path.split("/") if p]
    locale_raw = path_parts[0]  # e.g. "de-de"
    parts = locale_raw.split("-")
    locale = f"{parts[0]}_{parts[1].upper()}" if len(parts) == 2 else locale_raw

    # Extract pid from last path segment (e.g. 4164.html → 4164)
    filename = path_parts[-1]
    pid = filename.replace(".html", "")

    # Extract variant params from query string
    query_params = parse_qs(parsed.query)
    color_param = next((k for k in query_params if "rahmenfarbe" in k), None)
    size_param = next((k for k in query_params if "rahmengroesse" in k), None)

    if not color_param or not size_param:
        raise ValueError(
            f"Could not find color/size variant parameters in URL: {product_url}\n"
            "Make sure you selected a specific color AND size on the Canyon product page before copying the URL."
        )

    return {
        "site": site,
        "locale": locale,
        "pid": pid,
        "color_param": color_param,
        "color_value": query_params[color_param][0],
        "size_param": size_param,
        "size_value": query_params[size_param][0],
    }


def fetch_bike_state(params: dict) -> BikeState:
    """Fetch current bike availability and delivery date from Canyon API."""
    api_url = (
        f"{BASE_URL}/on/demandware.store"
        f"/Sites-{params['site']}-Site/{params['locale']}/Product-Variation"
    )
    query = {
        params["color_param"]: params["color_value"],
        params["size_param"]: params["size_value"],
        "pid": params["pid"],
        "quantity": "1",
    }

    response = requests.get(api_url, params=query, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    availability_text = _extract_availability(data)
    available = _is_available(availability_text)
    logger.debug("Raw availability text: %r", availability_text)

    # Try to get delivery date from productSummary lazy-loaded endpoint
    expected_delivery = None
    summary_path = data.get("productSummary", {}).get("url")
    if summary_path:
        expected_delivery = _fetch_delivery_date(BASE_URL + summary_path)

    return BikeState(
        available=available,
        availability_text=availability_text,
        expected_delivery=expected_delivery,
    )


def _extract_availability(data: dict) -> str:
    """Extract availability text from the gtmModel in the API response."""
    events = data.get("gtmModel", [])

    # Prefer the structured view_item event
    for event in events:
        if event.get("event") == "view_item":
            items = event.get("ecommerce", {}).get("items", [])
            if items and "item_availability" in items[0]:
                return items[0]["item_availability"]

    # Fallback: any event with item_availability
    for event in events:
        items = (event.get("ecommerce", {}) or {}).get("items", [])
        if items and "item_availability" in items[0]:
            return items[0]["item_availability"]

    raise ValueError(
        "Could not find availability data in Canyon API response. "
        "Run with LOG_LEVEL=DEBUG to inspect the raw response."
    )


def _is_available(availability_text: str) -> bool:
    """Return True if the availability text does not indicate sold-out/unavailable."""
    unavailable_phrases = [
        "not available",
        "nicht verfügbar",
        "sold out",
        "ausverkauft",
        "out of stock",
    ]
    text_lower = availability_text.lower()
    return not any(phrase in text_lower for phrase in unavailable_phrases)


def _fetch_delivery_date(summary_url: str) -> str | None:
    """Fetch and parse estimated delivery date from the productSummary endpoint."""
    try:
        response = requests.get(summary_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(separator=" ")

        delivery_patterns = [
            r"Expected delivery[:\s]+([^\n<.]+)",
            r"Estimated delivery[:\s]+([^\n<.]+)",
            r"Lieferdatum[:\s]+([^\n<.]+)",
            r"Lieferung[:\s]+([^\n<.]+)",
            r"Ships by[:\s]+([^\n<.]+)",
        ]
        for pattern in delivery_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        logger.debug("No delivery date found in productSummary response")
        return None
    except Exception as e:
        logger.debug("Could not fetch delivery date: %s", e)
        return None
