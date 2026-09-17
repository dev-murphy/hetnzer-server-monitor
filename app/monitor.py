import os
import time
import json
import logging
from pathlib import Path

import requests
import yaml


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

API_URL = "https://api.hetzner.cloud/v1/server_types"

HCLOUD_TOKEN = os.environ["HCLOUD_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

CONFIG_FILE = os.getenv("CONFIG_FILE", "/config/config.yaml")
STATE_FILE = os.getenv("STATE_FILE", "/data/state.json")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("hetzner-monitor")


# ---------------------------------------------------------
# HTTP
# ---------------------------------------------------------

session = requests.Session()

session.headers.update({
    "Authorization": f"Bearer {HCLOUD_TOKEN}",
    "Content-Type": "application/json",
})


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

def load_state():
    path = Path(STATE_FILE)

    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    path = Path(STATE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------
# Telegram
# ---------------------------------------------------------

def telegram(message):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

    except Exception as e:
        log.error("Telegram error: %s", e)


# ---------------------------------------------------------
# Hetzner API
# ---------------------------------------------------------

def get_server_types():
    response = session.get(
        API_URL,
        params={"per_page": 100},
        timeout=20,
    )

    response.raise_for_status()

    return response.json()["server_types"]


# ---------------------------------------------------------
# Find server
# ---------------------------------------------------------

def find_server_type(server_types, wanted_name):
    wanted_name = wanted_name.lower()

    for server in server_types:
        if server["name"].lower() == wanted_name:
            return server

    return None


# ---------------------------------------------------------
# Availability
# ---------------------------------------------------------

def get_availability(server, wanted_locations):
    result = {}

    locations = server.get("locations", [])

    for location in locations:
        name = location["name"]

        if wanted_locations != "all":
            if name not in wanted_locations:
                continue

        result[name] = location.get("available", False)

    return result


# ---------------------------------------------------------
# Formatting
# ---------------------------------------------------------

def format_available_message(
    server,
    location,
    location_info,
):
    cores = server.get("cores", "?")
    memory = server.get("memory", "?")
    disk = server.get("disk", "?")
    architecture = server.get("architecture", "?")

    prices = server.get("prices", [])

    price = "Unknown"

    for pricing in prices:
        if pricing.get("location") == location:
            price = pricing.get("price_monthly", {}).get(
                "gross",
                "Unknown",
            )

            currency = pricing.get("price_monthly", {}).get(
                "currency",
                "",
            )

            if price != "Unknown":
                price = f"{price} {currency}"

            break

    return (
        "🚨 <b>HETZNER SERVER AVAILABLE</b>\n\n"
        f"<b>Server:</b> {server['name']}\n"
        f"<b>Location:</b> {location}\n\n"
        f"<b>CPU:</b> {cores} vCPU\n"
        f"<b>RAM:</b> {memory} GB\n"
        f"<b>Disk:</b> {disk} GB\n"
        f"<b>Architecture:</b> {architecture}\n"
        f"<b>Price:</b> {price}/month\n\n"
        "⚠️ Availability is an indicator and "
        "can change before ordering."
    )


# ---------------------------------------------------------
# Status
# ---------------------------------------------------------

def format_status(
    server,
    availability,
):
    lines = [
        f"🖥️ <b>{server['name']}</b>",
        "",
    ]

    for location, available in availability.items():
        icon = "✅" if available else "❌"

        lines.append(
            f"{icon} {location}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------
# Main check
# ---------------------------------------------------------

def check():
    config = load_config()
    state = load_state()

    try:
        server_types = get_server_types()

    except Exception as e:
        log.error(
            "Unable to query Hetzner API: %s",
            e,
        )
        return

    for target in config.get("servers", []):

        name = target["name"]

        wanted_locations = target.get(
            "locations",
            "all",
        )

        server = find_server_type(
            server_types,
            name,
        )

        if not server:
            log.warning(
                "Server type not found: %s",
                name,
            )
            continue

        availability = get_availability(
            server,
            wanted_locations,
        )

        log.info(
            "%s: %s",
            name,
            ", ".join(
                f"{location}={'YES' if available else 'NO'}"
                for location, available
                in availability.items()
            ),
        )

        for location, available in availability.items():

            state_key = f"{name}:{location}"

            previous = state.get(
                state_key,
                False,
            )

            # ---------------------------------------------
            # Newly available
            # ---------------------------------------------

            if available and not previous:

                message = format_available_message(
                    server,
                    location,
                    None,
                )

                telegram(message)

                log.info(
                    "🚨 %s became available in %s",
                    name,
                    location,
                )

            # ---------------------------------------------
            # No longer available
            # ---------------------------------------------

            elif not available and previous:

                log.info(
                    "%s is no longer available in %s",
                    name,
                    location,
                )

            state[state_key] = available

    save_state(state)


# ---------------------------------------------------------
# Loop
# ---------------------------------------------------------

def main():

    log.info("Starting Hetzner availability monitor")
    log.info(
        "Check interval: %s seconds",
        CHECK_INTERVAL,
    )

    # Run immediately
    check()

    while True:

        time.sleep(CHECK_INTERVAL)

        try:
            check()

        except Exception:
            log.exception(
                "Unexpected error during check"
            )


if __name__ == "__main__":
    main()