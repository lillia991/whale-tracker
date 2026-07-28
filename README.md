# 🐋 Ethereum Whale Tracker

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Etherscan](https://img.shields.io/badge/API-Etherscan-brightgreen)

Real-time Ethereum whale transaction monitor. Get alerted whenever a large ETH transfer happens on-chain.

## ✨ Features

- Real-time block scanning
- Configurable minimum ETH threshold
- Direct Etherscan link for each whale tx
- Clean terminal output with 🐋 alerts
- Free — no paid API required

## 🚀 Setup

```bash
# 1. Get a free API key at https://etherscan.io/apis
# 2. Open tracker.py and set your key:
#    ETHERSCAN_API_KEY = "your_key_here"

# 3. Install dependencies
pip install requests

# 4. Run
python tracker.py
```

## ⚙️ Options

```bash
# Custom threshold (default: 100 ETH)
python tracker.py --min-eth 500

# Custom polling interval (default: 15s)
python tracker.py --min-eth 100 --interval 10
```

## 📊 Example output

```
══════════════════════════════════════════════════════════════
  🐋  ETHEREUM WHALE TRACKER
══════════════════════════════════════════════════════════════
  Minimum size : 100 ETH
  Poll every   : 15s
  Source       : Etherscan API
══════════════════════════════════════════════════════════════
  Watching for whales... Press Ctrl+C to stop.

🐋 ═══════════════════════════════════════════════════════════
   Time:    14:23:07
   Block:   19842301
   Amount:  1,250.00 ETH
   From:    0x1234...a1b2
   To:      0x5678...c3d4
   Tx:      0xabc123def456...
   Link:    https://etherscan.io/tx/0xabc123...
   ═══════════════════════════════════════════════════════════
```

## 🛠 Stack

- **Python 3.8+**
- **requests** — HTTP calls to Etherscan API
- Etherscan API (free tier)

## 📄 License

MIT
