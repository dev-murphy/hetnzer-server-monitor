# Hetzner Server Monitor

Polls the Hetzner Cloud API for server type availability and sends a Telegram
alert the moment a watched server type/location combination becomes available.

## How it works

- Reads the list of server types and locations to watch from `config.yaml`.
- Every `CHECK_INTERVAL` seconds, queries the Hetzner Cloud `server_types` API.
- Tracks last-known availability per `server:location` in `data/state.json`.
- Sends a Telegram message when a tracked server transitions from
  unavailable to available.

## Configuration

### `config.yaml`

```yaml
servers:
  - name: CX43
    locations: all

  - name: CPX32
    locations: all
```

`locations` can be `all` or a list of specific location names.

### Environment variables (`.env`)

Copy `.env.example` to `.env` and fill in the values:

| Variable             | Description                                  |
| -------------------- | --------------------------------------------- |
| `HCLOUD_TOKEN`       | Hetzner Cloud API token                       |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token                            |
| `TELEGRAM_CHAT_ID`   | Telegram chat ID to send alerts to            |
| `CHECK_HOURS`        | (see `.env.example`; check interval settings) |

## Running with Docker Compose

```bash
docker compose up -d --build
```

This builds the image, mounts `config.yaml` read-only, and persists state to
`./data`.

## Running locally

```bash
pip install -r requirements.txt
python app/monitor.py
```

Make sure `HCLOUD_TOKEN`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` are set
in your environment.
