"""
Ethereum Whale Tracker
======================
Monitors Ethereum blockchain for large transactions in real time.
Data source: Etherscan API (free key at etherscan.io/apis)

Run:
    pip install requests colorama
    python tracker.py

    # Custom threshold (default: 100 ETH)
    python tracker.py --min-eth 500

    # Custom log file
    python tracker.py --log whales.csv
"""

import csv
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Colors (colorama for Windows compatibility)
# ---------------------------------------------------------------------------

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    C_CYAN   = Fore.CYAN
    C_GREEN  = Fore.GREEN
    C_YELLOW = Fore.YELLOW
    C_RED    = Fore.RED
    C_BLUE   = Fore.BLUE
    C_BOLD   = Style.BRIGHT
    C_RESET  = Style.RESET_ALL
except ImportError:
    C_CYAN = C_GREEN = C_YELLOW = C_RED = C_BLUE = C_BOLD = C_RESET = ""

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ETHERSCAN_API_KEY = "YourApiKeyToken"  # get free at etherscan.io/apis
ETHERSCAN_URL     = "https://api.etherscan.io/api"

DEFAULT_MIN_ETH   = 100      # minimum ETH to be considered a "whale" tx
POLL_INTERVAL     = 15       # seconds between checks
DEFAULT_LOG_FILE  = "whales.csv"

# Color thresholds
TIER_MEGA  = 1000   # red    🔴 mega whale
TIER_LARGE = 500    # yellow 🟡 large whale
TIER_MED   = 100    # cyan   🔵 whale

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def get_latest_block() -> int:
    params = {
        "module": "proxy",
        "action": "eth_blockNumber",
        "apikey": ETHERSCAN_API_KEY,
    }
    r = requests.get(ETHERSCAN_URL, params=params, timeout=10)
    r.raise_for_status()
    return int(r.json()["result"], 16)


def get_block_transactions(block_number: int) -> list:
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
    block = get_latest_block()
    txs   = get_block_transactions(block)

    whales = []
    for tx in txs:
        value_wei = int(tx.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18
        if value_eth >= min_eth:
            whales.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "block":     block,
                "hash":      tx.get("hash", ""),
                "from":      tx.get("from", ""),
                "to":        tx.get("to") or "Contract Creation",
                "eth":       round(value_eth, 4),
            })
    return whales, block


# ---------------------------------------------------------------------------
# CSV logging
# ---------------------------------------------------------------------------

CSV_HEADERS = ["timestamp", "block", "hash", "from", "to", "eth"]

def init_csv(log_file: str):
    """Creates CSV file with headers if it doesn't exist."""
    path = Path(log_file)
    if not path.exists():
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
        print(f"  {C_GREEN}📄 Log file created: {log_file}{C_RESET}")
    else:
        print(f"  {C_YELLOW}📄 Appending to existing log: {log_file}{C_RESET}")


def save_to_csv(tx: dict, log_file: str):
    """Appends a single whale transaction to the CSV log."""
    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow({k: tx[k] for k in CSV_HEADERS})


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def fmt_addr(addr: str) -> str:
    if not addr or len(addr) < 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


def whale_color(eth: float) -> str:
    """Returns color based on transaction size."""
    if eth >= TIER_MEGA:
        return C_RED
    if eth >= TIER_LARGE:
        return C_YELLOW
    return C_CYAN


def whale_emoji(eth: float) -> str:
    if eth >= TIER_MEGA:
        return "🔴🐋"
    if eth >= TIER_LARGE:
        return "🟡🐋"
    return "🔵🐋"


def print_whale(tx: dict):
    color = whale_color(tx["eth"])
    emoji = whale_emoji(tx["eth"])

    print()
    print(f"{color}{C_BOLD}{emoji} {'═' * 57}{C_RESET}")
    print(f"{color}   Time:    {tx['timestamp']}{C_RESET}")
    print(f"{color}   Block:   {tx['block']}{C_RESET}")
    print(f"{C_BOLD}{color}   Amount:  {tx['eth']:,.2f} ETH{C_RESET}")
    print(f"{color}   From:    {fmt_addr(tx['from'])}{C_RESET}")
    print(f"{color}   To:      {fmt_addr(tx['to'])}{C_RESET}")
    print(f"{color}   Tx:      {tx['hash'][:22]}...{C_RESET}")
    print(f"{C_BLUE}   Link:    https://etherscan.io/tx/{tx['hash']}{C_RESET}")
    print(f"{color}   {'═' * 57}{C_RESET}")


def print_status(block: int, found: int, min_eth: float, total: int, log_file: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(
        f"  {C_GREEN}[{ts}]{C_RESET} Block #{C_BOLD}{block}{C_RESET}"
        f" — {C_YELLOW}{found} whale(s){C_RESET}"
        f" | Total: {C_BOLD}{total}{C_RESET}"
        f" | Min: {min_eth} ETH"
        f" | Log: {log_file}",
        end="\r"
    )


def print_header(min_eth: float, interval: int, log_file: str):
    print()
    print(f"{C_CYAN}{C_BOLD}{'═' * 62}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}  🐋  ETHEREUM WHALE TRACKER{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'═' * 62}{C_RESET}")
    print(f"  Minimum size : {C_BOLD}{min_eth} ETH{C_RESET}")
    print(f"  Poll every   : {interval}s")
    print(f"  Log file     : {C_GREEN}{log_file}{C_RESET}")
    print(f"  {C_RED}🔴 ≥ {TIER_MEGA} ETH   {C_YELLOW}🟡 ≥ {TIER_LARGE} ETH   {C_CYAN}🔵 ≥ {TIER_MED} ETH{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'═' * 62}{C_RESET}")
    print(f"  Watching for whales... Press {C_BOLD}Ctrl+C{C_RESET} to stop.")
    print()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ethereum Whale Tracker")
    parser.add_argument("--min-eth",  type=float, default=DEFAULT_MIN_ETH)
    parser.add_argument("--interval", type=int,   default=POLL_INTERVAL)
    parser.add_argument("--log",      type=str,   default=DEFAULT_LOG_FILE)
    args = parser.parse_args()

    print_header(args.min_eth, args.interval, args.log)
    init_csv(args.log)

    seen       = set()
    total      = 0
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
                        save_to_csv(tx, args.log)
                    print_status(block, len(new), args.min_eth, total, args.log)

            except requests.exceptions.RequestException as e:
                print(f"\n  {C_RED}⚠️  API error: {e}. Retrying...{C_RESET}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n  {C_GREEN}Stopped.{C_RESET} Total alerts: {C_BOLD}{total}{C_RESET} | Saved to: {args.log}\n")


if __name__ == "__main__":
    main()
