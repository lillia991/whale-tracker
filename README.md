# 🐋 Ethereum Whale Tracker

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![Etherscan](https://img.shields.io/badge/Etherscan-API-lightblue)
![License](https://img.shields.io/badge/License-MIT-yellow)

Real-time Ethereum whale transaction monitor with Telegram alerts, web dashboard, address filter, and sound notifications.

## Features

- Colored terminal output — 🔴 Mega (≥1000 ETH) / 🟡 Large (≥500 ETH) / 🔵 Whale (≥100 ETH)
- CSV logging of every transaction
- Session statistics on exit (win rate, volume, top 3)
- Telegram bot alerts straight to your phone
- Watch specific wallet addresses (`--watch`)
- Sound alert on new whale detection
- Live web dashboard at `http://localhost:5050`

## Setup

```bash
# 1. Get a free Etherscan API key
#    → https://etherscan.io/apis

# 2. Open tracker.py and set your key:
#    ETHERSCAN_API_KEY = "your_key_here"

# 3. Install dependencies
pip install requests colorama flask

# 4. Run
python tracker.py
```

## Usage

```bash
# Basic — terminal only
python tracker.py

# With web dashboard (open http://localhost:5050)
python tracker.py --web

# Custom threshold
python tracker.py --min-eth 500

# With sound alert
python tracker.py --sound

# Watch a specific wallet
python tracker.py --watch 0xYOUR_ADDRESS

# Telegram alerts
python tracker.py --tg-token BOT_TOKEN --tg-chat CHAT_ID

# Everything at once
python tracker.py --web --sound --min-eth 100 --tg-token TOKEN --tg-chat ID --watch 0x...
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--min-eth` | 100 | Min transaction size in ETH |
| `--interval` | 15 | Poll interval (seconds) |
| `--log` | whales.csv | CSV log file |
| `--sound` | off | Play sound on alert |
| `--web` | off | Enable web dashboard |
| `--tg-token` | — | Telegram bot token |
| `--tg-chat` | — | Telegram chat ID |
| `--watch` | — | Watch specific addresses |

## Telegram Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → get your token
2. Message [@userinfobot](https://t.me/userinfobot) → get your chat ID
3. Run: `python tracker.py --tg-token TOKEN --tg-chat CHAT_ID`

## Example Output

```
══════════════════════════════════════════════════════════
  🐋  ETHEREUM WHALE TRACKER — FULL EDITION
══════════════════════════════════════════════════════════
  Min size  : 100 ETH
  Sound     : ✅
  Telegram  : ✅
  Web UI    : ✅ http://localhost:5050

🔴🐋 ═══════════════════════════════════════════════════════
   Time:    2024-01-15 14:23:11
   Block:   19023441
   Amount:  1,250.00 ETH
   From:    0x1234...abcd
   To:      0x5678...ef01
   Link:    https://etherscan.io/tx/0x...
```

## Stack

- **requests** — Etherscan API calls
- **colorama** — colored terminal output
- **flask** — web dashboard (SSE streaming)
- Etherscan API (free tier, no credit card)

## License

MIT
