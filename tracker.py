"""
Ethereum Whale Tracker — Full Edition
======================================
Features:
  - Real-time whale alerts in terminal (colored)
  - Telegram notifications
  - Watch specific wallet addresses
  - Sound alert on new whale
  - Web dashboard at http://localhost:5050
  - CSV logging
  - Session statistics

Run:
    pip install requests colorama flask

    python tracker.py                          # terminal only
    python tracker.py --web                    # + web dashboard
    python tracker.py --tg-token TOKEN --tg-chat CHAT_ID
    python tracker.py --watch 0xABC...  0xDEF...
    python tracker.py --min-eth 500 --sound
"""

import csv
import time
import os
import sys
import threading
import argparse
import platform
import requests
from datetime import datetime
from pathlib import Path
from queue import Queue

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    C_CYAN    = Fore.CYAN
    C_GREEN   = Fore.GREEN
    C_YELLOW  = Fore.YELLOW
    C_RED     = Fore.RED
    C_BLUE    = Fore.BLUE
    C_MAGENTA = Fore.MAGENTA
    C_BOLD    = Style.BRIGHT
    C_RESET   = Style.RESET_ALL
except ImportError:
    C_CYAN = C_GREEN = C_YELLOW = C_RED = C_BLUE = C_MAGENTA = C_BOLD = C_RESET = ""

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ETHERSCAN_API_KEY = "YourApiKeyToken"   # etherscan.io/apis
ETHERSCAN_URL     = "https://api.etherscan.io/api"

DEFAULT_MIN_ETH   = 100
POLL_INTERVAL     = 15
DEFAULT_LOG_FILE  = "whales.csv"
WEB_PORT          = 5050

TIER_MEGA         = 1000
TIER_LARGE        = 500

# ---------------------------------------------------------------------------
# Etherscan API
# ---------------------------------------------------------------------------

def get_latest_block() -> int:
    r = requests.get(ETHERSCAN_URL, params={
        "module": "proxy", "action": "eth_blockNumber",
        "apikey": ETHERSCAN_API_KEY,
    }, timeout=10)
    r.raise_for_status()
    return int(r.json()["result"], 16)


def get_block_transactions(block_number: int) -> list:
    r = requests.get(ETHERSCAN_URL, params={
        "module": "proxy", "action": "eth_getBlockByNumber",
        "tag": hex(block_number), "boolean": "true",
        "apikey": ETHERSCAN_API_KEY,
    }, timeout=15)
    r.raise_for_status()
    result = r.json().get("result")
    return result["transactions"] if result and "transactions" in result else []


def scan_block(min_eth: float, watch_addrs: set):
    block = get_latest_block()
    txs   = get_block_transactions(block)
    whales = []
    for tx in txs:
        value_eth = int(tx.get("value", "0x0"), 16) / 1e18
        from_addr = (tx.get("from") or "").lower()
        to_addr   = (tx.get("to")   or "").lower()
        is_watched = bool(watch_addrs) and (from_addr in watch_addrs or to_addr in watch_addrs)
        if value_eth >= min_eth or is_watched:
            whales.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "block":     block,
                "hash":      tx.get("hash", ""),
                "from":      tx.get("from", ""),
                "to":        tx.get("to") or "Contract Creation",
                "eth":       round(value_eth, 4),
                "watched":   is_watched,
            })
    return whales, block


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(token: str, chat_id: str, tx: dict):
    emoji = "🔴" if tx["eth"] >= TIER_MEGA else ("🟡" if tx["eth"] >= TIER_LARGE else "🔵")
    watched = " 👁 WATCHED WALLET" if tx.get("watched") else ""
    text = (
        f"{emoji} *Whale Alert*{watched}\n"
        f"💰 *{tx['eth']:,.2f} ETH*\n"
        f"📤 From: `{tx['from'][:10]}...{tx['from'][-6:]}`\n"
        f"📥 To: `{tx['to'][:10]}...{tx['to'][-6:]}`\n"
        f"🔗 [View on Etherscan](https://etherscan.io/tx/{tx['hash']})\n"
        f"🕐 {tx['timestamp']}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"\n  {C_RED}⚠️  Telegram error: {e}{C_RESET}")


# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------

def play_sound():
    try:
        system = platform.system()
        if system == "Darwin":
            os.system("afplay /System/Library/Sounds/Ping.aiff &")
        elif system == "Linux":
            os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga &")
        elif system == "Windows":
            import winsound
            winsound.Beep(1000, 300)
    except Exception:
        print("\a", end="", flush=True)  # fallback beep


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

CSV_HEADERS = ["timestamp", "block", "hash", "from", "to", "eth", "watched"]

def init_csv(log_file: str):
    path = Path(log_file)
    if not path.exists():
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()
        print(f"  {C_GREEN}📄 Log created: {log_file}{C_RESET}")
    else:
        print(f"  {C_YELLOW}📄 Appending to: {log_file}{C_RESET}")


def save_csv(tx: dict, log_file: str):
    with open(log_file, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(
            {k: tx.get(k, "") for k in CSV_HEADERS}
        )


# ---------------------------------------------------------------------------
# Web dashboard (Flask SSE)
# ---------------------------------------------------------------------------

_web_queue: Queue = Queue()
_web_history: list = []

WEB_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>🐋 Ethereum Whale Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d1117; color: #e6edf3; font-family: 'Courier New', monospace; }
  header { background: #161b22; padding: 20px 30px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.4rem; color: #58a6ff; }
  #stats { display: flex; gap: 20px; padding: 16px 30px; background: #161b22; border-bottom: 1px solid #30363d; flex-wrap: wrap; }
  .stat { background: #21262d; border-radius: 8px; padding: 10px 18px; min-width: 140px; }
  .stat-label { font-size: 0.7rem; color: #8b949e; text-transform: uppercase; }
  .stat-value { font-size: 1.3rem; font-weight: bold; color: #58a6ff; margin-top: 2px; }
  #feed { padding: 20px 30px; max-width: 900px; margin: 0 auto; }
  .tx { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px 20px; margin-bottom: 14px; animation: fadeIn 0.4s ease; }
  .tx.mega  { border-left: 4px solid #f85149; }
  .tx.large { border-left: 4px solid #e3b341; }
  .tx.med   { border-left: 4px solid #58a6ff; }
  .tx.watched { border-left: 4px solid #3fb950; }
  .tx-amount { font-size: 1.5rem; font-weight: bold; }
  .tx.mega  .tx-amount { color: #f85149; }
  .tx.large .tx-amount { color: #e3b341; }
  .tx.med   .tx-amount { color: #58a6ff; }
  .tx-meta  { font-size: 0.78rem; color: #8b949e; margin-top: 6px; line-height: 1.7; }
  .tx-meta a { color: #58a6ff; text-decoration: none; }
  .tx-meta a:hover { text-decoration: underline; }
  .badge { display: inline-block; font-size: 0.65rem; padding: 2px 8px; border-radius: 4px; margin-left: 8px; font-weight: bold; }
  .badge-mega    { background: #f85149; color: #fff; }
  .badge-large   { background: #e3b341; color: #000; }
  .badge-watched { background: #3fb950; color: #000; }
  #empty { text-align: center; color: #8b949e; padding: 60px 20px; font-size: 1rem; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
  .dot { width: 8px; height: 8px; background: #3fb950; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
</style>
</head>
<body>
<header>
  <span>🐋</span>
  <h1>Ethereum Whale Tracker</h1>
  <span class="dot" style="margin-left:auto"></span>
  <span style="font-size:0.8rem;color:#8b949e;margin-left:6px">LIVE</span>
</header>
<div id="stats">
  <div class="stat"><div class="stat-label">Total Alerts</div><div class="stat-value" id="s-total">0</div></div>
  <div class="stat"><div class="stat-label">Total Volume</div><div class="stat-value" id="s-volume">0 ETH</div></div>
  <div class="stat"><div class="stat-label">Largest Tx</div><div class="stat-value" id="s-max">—</div></div>
  <div class="stat"><div class="stat-label">🔴 Mega</div><div class="stat-value" id="s-mega">0</div></div>
  <div class="stat"><div class="stat-label">🟡 Large</div><div class="stat-value" id="s-large">0</div></div>
</div>
<div id="feed"><div id="empty">⏳ Watching for whales...</div></div>
<script>
let total=0, volume=0, maxEth=0, mega=0, large=0;
const feed = document.getElementById('feed');
const empty = document.getElementById('empty');

function fmt(n){ return n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}); }
function short(a){ return a.length>12 ? a.slice(0,6)+'...'+a.slice(-4) : a; }

function addTx(tx){
  if(empty) empty.remove();
  total++; volume+=tx.eth;
  if(tx.eth>=1000) mega++;
  else if(tx.eth>=500) large++;
  if(tx.eth>maxEth){ maxEth=tx.eth; document.getElementById('s-max').textContent=fmt(tx.eth)+' ETH'; }
  document.getElementById('s-total').textContent=total;
  document.getElementById('s-volume').textContent=fmt(volume)+' ETH';
  document.getElementById('s-mega').textContent=mega;
  document.getElementById('s-large').textContent=large;

  let cls = tx.eth>=1000?'mega':tx.eth>=500?'large':'med';
  if(tx.watched) cls='watched';
  let badge = tx.eth>=1000?'<span class="badge badge-mega">MEGA WHALE</span>':tx.eth>=500?'<span class="badge badge-large">LARGE</span>':'';
  if(tx.watched) badge+='<span class="badge badge-watched">WATCHED</span>';

  const div = document.createElement('div');
  div.className = 'tx '+cls;
  div.innerHTML = `
    <div class="tx-amount">${fmt(tx.eth)} ETH ${badge}</div>
    <div class="tx-meta">
      <b>From:</b> ${short(tx.from)} &nbsp;→&nbsp; <b>To:</b> ${short(tx.to)}<br>
      <b>Block:</b> ${tx.block} &nbsp;|&nbsp; <b>Time:</b> ${tx.timestamp}<br>
      <a href="https://etherscan.io/tx/${tx.hash}" target="_blank">🔗 View on Etherscan</a>
    </div>`;
  feed.insertBefore(div, feed.firstChild);
}

const es = new EventSource('/stream');
es.onmessage = e => { const tx = JSON.parse(e.data); addTx(tx); };
</script>
</body>
</html>"""


def start_web(history: list, queue: Queue, port: int):
    """Starts the Flask web dashboard in a background thread."""
    try:
        from flask import Flask, Response, stream_with_context
        import json
    except ImportError:
        print(f"  {C_RED}⚠️  Flask not installed. Run: pip install flask{C_RESET}")
        return

    app = Flask(__name__)

    @app.route("/")
    def index():
        return WEB_HTML

    @app.route("/stream")
    def stream():
        def generate():
            # Send history first
            for tx in history[-50:]:
                yield f"data: {json.dumps(tx)}\n\n"
            # Then stream new events
            local_q = Queue()
            listeners.append(local_q)
            try:
                while True:
                    tx = local_q.get()
                    yield f"data: {json.dumps(tx)}\n\n"
            finally:
                listeners.remove(local_q)
        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    t = threading.Thread(target=lambda: app.run(port=port, threaded=True), daemon=True)
    t.start()
    print(f"  {C_GREEN}🌐 Web dashboard: http://localhost:{port}{C_RESET}")


listeners = []

def broadcast_web(tx: dict):
    for q in listeners:
        q.put(tx)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def fmt_addr(a: str) -> str:
    return f"{a[:6]}...{a[-4:]}" if a and len(a) > 10 else a

def whale_color(eth: float) -> str:
    if eth >= TIER_MEGA:  return C_RED
    if eth >= TIER_LARGE: return C_YELLOW
    return C_CYAN

def whale_emoji(eth: float) -> str:
    if eth >= TIER_MEGA:  return "🔴🐋"
    if eth >= TIER_LARGE: return "🟡🐋"
    return "🔵🐋"

def print_whale(tx: dict):
    color  = whale_color(tx["eth"])
    emoji  = whale_emoji(tx["eth"])
    watch  = f"  {C_GREEN}👁 WATCHED{C_RESET}" if tx.get("watched") else ""
    print()
    print(f"{color}{C_BOLD}{emoji} {'═'*55}{C_RESET}{watch}")
    print(f"{color}   Time:    {tx['timestamp']}{C_RESET}")
    print(f"{color}   Block:   {tx['block']}{C_RESET}")
    print(f"{C_BOLD}{color}   Amount:  {tx['eth']:,.2f} ETH{C_RESET}")
    print(f"{color}   From:    {fmt_addr(tx['from'])}{C_RESET}")
    print(f"{color}   To:      {fmt_addr(tx['to'])}{C_RESET}")
    print(f"{color}   Tx:      {tx['hash'][:22]}...{C_RESET}")
    print(f"{C_BLUE}   Link:    https://etherscan.io/tx/{tx['hash']}{C_RESET}")
    print(f"{color}   {'═'*55}{C_RESET}")

def print_status(block, found, min_eth, total, log_file):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C_GREEN}[{ts}]{C_RESET} Block #{C_BOLD}{block}{C_RESET}"
          f" — {C_YELLOW}{found} whale(s){C_RESET}"
          f" | Total: {C_BOLD}{total}{C_RESET}"
          f" | Min: {min_eth} ETH | Log: {log_file}", end="\r")

def print_header(args):
    print()
    print(f"{C_CYAN}{C_BOLD}{'═'*62}{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}  🐋  ETHEREUM WHALE TRACKER — FULL EDITION{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'═'*62}{C_RESET}")
    print(f"  Min size  : {C_BOLD}{args.min_eth} ETH{C_RESET}")
    print(f"  Interval  : {args.interval}s")
    print(f"  Log       : {C_GREEN}{args.log}{C_RESET}")
    print(f"  Sound     : {'✅' if args.sound else '❌'}")
    print(f"  Telegram  : {'✅' if args.tg_token else '❌'}")
    print(f"  Web UI    : {'✅ http://localhost:'+str(WEB_PORT) if args.web else '❌'}")
    if args.watch:
        print(f"  Watching  : {C_GREEN}{', '.join(fmt_addr(a) for a in args.watch)}{C_RESET}")
    print(f"  {C_RED}🔴 ≥{TIER_MEGA} ETH   {C_YELLOW}🟡 ≥{TIER_LARGE} ETH   {C_CYAN}🔵 ≥{args.min_eth} ETH{C_RESET}")
    print(f"{C_CYAN}{C_BOLD}{'═'*62}{C_RESET}")
    print(f"  Press {C_BOLD}Ctrl+C{C_RESET} to stop and see statistics.")
    print()

def print_stats(all_txs, start_time, log_file):
    dur = datetime.now() - start_time
    m, s = divmod(int(dur.total_seconds()), 60)
    print(f"\n{C_MAGENTA}{C_BOLD}{'═'*62}{C_RESET}")
    print(f"{C_MAGENTA}{C_BOLD}  📊  SESSION STATISTICS{C_RESET}")
    print(f"{C_MAGENTA}{C_BOLD}{'═'*62}{C_RESET}")
    if not all_txs:
        print("  No whale transactions found this session.")
        print(f"{C_MAGENTA}{'═'*62}{C_RESET}\n")
        return
    amounts   = [tx["eth"] for tx in all_txs]
    total_eth = sum(amounts)
    avg_eth   = total_eth / len(amounts)
    max_tx    = max(all_txs, key=lambda x: x["eth"])
    top3      = sorted(all_txs, key=lambda x: x["eth"], reverse=True)[:3]
    mega  = sum(1 for e in amounts if e >= TIER_MEGA)
    large = sum(1 for e in amounts if TIER_LARGE <= e < TIER_MEGA)
    med   = len(amounts) - mega - large
    print(f"  Duration  : {m}m {s}s")
    print(f"  Alerts    : {C_BOLD}{len(all_txs)}{C_RESET}")
    print(f"  Volume    : {C_BOLD}{total_eth:,.2f} ETH{C_RESET}")
    print(f"  Average   : {avg_eth:,.2f} ETH")
    print()
    print(f"  {C_RED}🔴 Mega  (≥{TIER_MEGA} ETH) : {mega}{C_RESET}")
    print(f"  {C_YELLOW}🟡 Large (≥{TIER_LARGE} ETH) : {large}{C_RESET}")
    print(f"  {C_CYAN}🔵 Whale             : {med}{C_RESET}")
    print()
    print(f"  {C_BOLD}🏆 Biggest:{C_RESET} {max_tx['eth']:,.2f} ETH")
    print(f"     {C_BLUE}https://etherscan.io/tx/{max_tx['hash']}{C_RESET}")
    print()
    print(f"  {C_BOLD}🥇 Top 3:{C_RESET}")
    for i, tx in enumerate(top3, 1):
        c = whale_color(tx["eth"])
        print(f"  {i}. {c}{tx['eth']:,.2f} ETH{C_RESET} | {tx['timestamp']} | {fmt_addr(tx['from'])} → {fmt_addr(tx['to'])}")
    print()
    print(f"  💾 Saved to: {C_GREEN}{log_file}{C_RESET}")
    print(f"{C_MAGENTA}{C_BOLD}{'═'*62}{C_RESET}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ethereum Whale Tracker")
    parser.add_argument("--min-eth",  type=float, default=DEFAULT_MIN_ETH, help="Min ETH threshold")
    parser.add_argument("--interval", type=int,   default=POLL_INTERVAL,   help="Poll interval (seconds)")
    parser.add_argument("--log",      type=str,   default=DEFAULT_LOG_FILE, help="CSV log file")
    parser.add_argument("--sound",    action="store_true",                  help="Play sound on alert")
    parser.add_argument("--web",      action="store_true",                  help="Enable web dashboard")
    parser.add_argument("--tg-token", type=str,   default="",               help="Telegram bot token")
    parser.add_argument("--tg-chat",  type=str,   default="",               help="Telegram chat ID")
    parser.add_argument("--watch",    nargs="*",  default=[],               help="Watch specific addresses")
    args = parser.parse_args()

    watch_addrs = {a.lower() for a in (args.watch or [])}

    print_header(args)
    init_csv(args.log)

    if args.web:
        start_web(_web_history, _web_queue, WEB_PORT)

    seen       = set()
    all_txs    = []
    total      = 0
    last_block = 0
    start_time = datetime.now()

    try:
        while True:
            try:
                whales, block = scan_block(args.min_eth, watch_addrs)
                if block != last_block:
                    last_block = block
                    new = [tx for tx in whales if tx["hash"] not in seen]
                    for tx in new:
                        seen.add(tx["hash"])
                        total += 1
                        all_txs.append(tx)
                        _web_history.append(tx)
                        print_whale(tx)
                        save_csv(tx, args.log)
                        if args.sound:
                            play_sound()
                        if args.tg_token and args.tg_chat:
                            send_telegram(args.tg_token, args.tg_chat, tx)
                        if args.web:
                            broadcast_web(tx)
                    print_status(block, len(new), args.min_eth, total, args.log)

            except requests.exceptions.RequestException as e:
                print(f"\n  {C_RED}⚠️  API error: {e}. Retrying...{C_RESET}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print_stats(all_txs, start_time, args.log)


if __name__ == "__main__":
    main()
