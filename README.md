# ineedmycanyon

Monitors a Canyon bike for availability changes and notifies you via Telegram when it comes back in stock or when the estimated delivery date changes.

## How it works

The checker calls Canyon's product API every hour (configurable). When the availability or delivery date changes compared to the last check, it sends a Telegram message to your account. It runs in a Docker container so it works 24/7 in the background on your laptop.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A Telegram account

---

## Setup

### 1. Create a Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` — save it

### 2. Get your Telegram Chat ID

1. Search for your new bot in Telegram and send it any message (e.g. `/start`)
2. Open this URL in your browser, replacing `YOUR_TOKEN` with your bot token:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. You'll see a JSON response. Find `"chat": {"id": 123456789}` — that number is your Chat ID

### 3. Find your Canyon bike URL

1. Go to [canyon.com](https://www.canyon.com) and navigate to the bike you want
2. **Important:** Select your exact color and size using the dropdowns on the product page
3. Copy the full URL from your browser — it should look like:
   ```
   https://www.canyon.com/de-de/rennrad/.../4164.html?dwvar_4164_pv_rahmenfarbe=R138_P01&dwvar_4164_pv_rahmengroesse=M
   ```

### 4. Configure

```bash
cp .env.example .env
```

Open `.env` and fill in the three required values:

```
BIKE_URL=<your Canyon URL from step 3>
TELEGRAM_BOT_TOKEN=<your token from step 1>
TELEGRAM_CHAT_IDS=<your chat ID from step 2>
```

To notify multiple people when the bike is available, add their chat IDs separated by commas:
```
TELEGRAM_CHAT_IDS=123456789,987654321
```

Optionally, set `TELEGRAM_ADMIN_CHAT_ID` to receive heartbeats every 3 days and failure alerts:
```
TELEGRAM_ADMIN_CHAT_ID=<your chat ID>
```

### 5. Run

```bash
docker compose up -d
```

The checker will start immediately. You can verify it's working by checking the logs:

```bash
docker compose logs -f
```

You should see something like:
```
2026-03-23 12:00:00 [INFO] Starting Canyon bike checker
2026-03-23 12:00:00 [INFO] Monitoring: size=M, color=R138_P01
2026-03-23 12:00:01 [INFO] First run — saving initial state (available=False, delivery=None)
2026-03-23 12:00:01 [INFO] Next check in 62 minutes
```

### 6. Stop

```bash
docker compose down
```

The current state is saved in `./data/state.json` so the checker won't send duplicate notifications after a restart.

---

## Configuration reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `BIKE_URL` | Yes | — | Canyon product page URL with color and size selected |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_IDS` | Yes | — | Comma-separated list of Telegram user IDs to notify when bike is available |
| `CHECK_INTERVAL_HOURS` | No | `1` | How often to check, in hours |
| `TELEGRAM_ADMIN_CHAT_ID` | No | — | Telegram user ID that receives heartbeats and failure alerts |
| `HEARTBEAT_INTERVAL_DAYS` | No | `3` | How often the admin receives a status heartbeat, in days |
| `LOG_LEVEL` | No | `INFO` | Set to `DEBUG` for verbose logging |

