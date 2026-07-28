"""
Ethereum Whale Tracker
======================
Monitors Ethereum blockchain for large transactions in real time.
Data source: Etherscan API (free key at etherscan.io/apis)

Run:
    pip install requests
    python tracker.py

    # Custom threshold (default: 100 ETH)
    python tracker.py --min-eth 500
"""

import time
import argparse
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ETHERSCAN_API_KEY = "YourApiKeyToken"  # get free at etherscan.io/apis
ETHERSCAN_URL     = "https://api.etherscan.io/api"

DEFAULT_MIN_ETH   = 100      # minimum ETH to be considered a "whale" tx
POLL_INTERVAL     = 15       # seconds between checks

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def get_latest_block() -> int:
    """Returns the latest Ethereum block number."""
    params = {
        "module": "proxy",
        "action": "eth_blockNumber",
        "apikey": ETHERSCAN_API_KEY,
    }
    r = requests.get(ETHERSCAN_URL, params=params, timeout=10)
    r.raise_for_status()
    return int(r.json()["result"], 16)


def get_block_transactions(block_number: int) -> list:
    """Returns all transactions in a given block."""
    params = {
        "module": "proxy",
        "action": "eth_getBlockByNumber",
        "tag": hex(block_number),
        "boolean": "true",
        "apikey": ETHERSCAN_API_KEY,
    }
    r = requests.get(ETHERSCAN_URL, params=params, timeout=15)
    r.raise_for_status()
    result = r.json().get("result")
    if result and "transactions" in result:
        return result["transactions"]
    return []


def get_recent_large_txs(min_eth: float):
    """Scans the latest block for whale transactions."""
    block = get_latest_block()
    txs = get_block_transactions(block)

    whales = []
    for tx in txs:
        value_wei = int(tx.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18
        if value_eth >= min_eth:
            whales.append({
                "block": block,
                "hash":  tx.get("hash", ""),
                "from":  tx.get("from", ""),
                "to":    tx.get("to") or "Contract Creation",
                "eth":   round(value_eth, 4),
            })
    return whales, block


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def fmt_addr(addr: str) -> str:
    if not addr or len(addr) < 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


def print_whale(tx: dict):
    ts = datetime.now().strftime("%H:%M:%S")
    print()
    print("🐋 " + "═" * 59)
    print(f"   Time:    {ts}")
    print(f"   Block:   {tx['block']}")
    print(f"   Amount:  {tx['eth']:,.2f} ETH")
    print(f"   From:    {fmt_addr(tx['from'])}")
    print(f"   To:      {fmt_addr(tx['to'])}")
    print(f"   Tx:      {tx['hash'][:20]}...")
    print(f"   Link:    https://etherscan.io/tx/{tx['hash']}")
    print("   " + "═" * 59)


def print_status(block: int, found: int, min_eth: float, total: int):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] Block #{block} — {found} whale(s) | Total: {total} | Min: {min_eth} ETH", end="\r")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ethereum Whale Tracker")
    parser.add_argument("--min-eth", type=float, default=DEFAULT_MIN_ETH)
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL)
    args = parser.parse_args()

    print()
    print("═" * 62)
    print("  🐋  ETHEREUM WHALE TRACKER")
    print("═" * 62)
    print(f"  Minimum size : {args.min_eth} ETH")
    print(f"  Poll every   : {args.interval}s")
    print(f"  Source       : Etherscan API")
    print("═" * 62)
    print("  Watching for whales... Press Ctrl+C to stop.")
    print()

    seen = set()
    total = 0
    last_block = 0

    try:
        while True:
            try:
                whales, block = get_recent_large_txs(args.min_eth)
                if block != last_block:
                    last_block = block
                    new = [tx for tx in whales if tx["hash"] not in seen]
                    for tx in new:
                        seen.add(tx["hash"])
                        total += 1
                        print_whale(tx)
                    print_status(block, len(new), args.min_eth, total)
            except requests.exceptions.RequestException as e:
                print(f"\n  ⚠️  API error: {e}. Retrying...")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n  Stopped. Total alerts: {total}\n")


if __name__ == "__main__":
    main()
