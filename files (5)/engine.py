"""
================================================================================
  RIZZ CRYPTO PORTFOLIO AUTOMATION ENGINE
  engine.py — v2.0  (SIMULATION MODE)
  
  Layers:
    1. CORE VAULT ASSETS     — BTC ETH SOL XRP VET LINK XDC ADA ATOM MATIC
    2. SWING STACK           — portion above vault minimum, trades exponentially
    3. YIELD-ONLY ASSETS     — HBAR DOT ALGO NEAR EGLD  (auto-sell → vault)
    4. SIDE BETS             — 3 rotating speculative coins

  Control surfaces:
    - Flask web dashboard    → http://localhost:5000  (or Railway URL)
    - Telegram bot           → approvals + status via chat

  Set SIMULATION_MODE = False + wire exchange SDK to go live.
================================================================================
"""

import os
import time
import logging
import random
import json
import threading
import uuid
from datetime import datetime, timedelta
from typing import Optional
from collections import deque

from flask import Flask, jsonify, request, render_template, abort
import requests as http_requests

# ============================================================
#  CONFIGURATION  — set via Railway environment variables
# ============================================================

API_KEY             = os.environ.get("API_KEY", "YOUR_API_KEY")
API_SECRET          = os.environ.get("API_SECRET", "YOUR_API_SECRET")
EXCHANGE            = os.environ.get("EXCHANGE", "coinbase")

TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "")

DASHBOARD_SECRET    = os.environ.get("DASHBOARD_SECRET", "changeme")  # simple auth token
PORT                = int(os.environ.get("PORT", 5000))

SIMULATION_MODE         = os.environ.get("SIMULATION_MODE", "true").lower() == "true"
LOOP_INTERVAL_SECONDS   = int(os.environ.get("LOOP_INTERVAL", 60))
APPROVAL_TIMEOUT        = int(os.environ.get("APPROVAL_TIMEOUT", 300))   # 5 min

MAX_GAS_GWEI            = float(os.environ.get("MAX_GAS_GWEI", 80))
MAX_VOLATILITY_PCT      = float(os.environ.get("MAX_VOLATILITY_PCT", 15.0))
MIN_LIQUIDITY_USD       = float(os.environ.get("MIN_LIQUIDITY_USD", 50000))
LARGE_MOVE_USD          = float(os.environ.get("LARGE_MOVE_USD", 100.0))
SIDE_BET_ROTATE_USD     = float(os.environ.get("SIDE_BET_ROTATE_USD", 50.0))

SWING_REINVEST_PCT      = 0.50
SWING_TRADE_SIZE_PCT    = 0.10
SIDE_BET_ROTATE_DAYS    = 30
MAX_ACTIVE_SIDE_BETS    = 3

# ============================================================
#  ASSET DEFINITIONS
# ============================================================

VAULT_ASSETS    = ["BTC","ETH","SOL","XRP","VET","LINK","XDC","ADA","ATOM","MATIC"]
YIELD_ASSETS    = ["HBAR","DOT","ALGO","NEAR","EGLD"]
YIELD_PHASE_OUT = ["ALGO"]

SIDE_BET_POOL = [
    "SHIB","SUI","BONK","DOGE","PEPE",
    "JUP","FET","AGIX","RNDR","APT","OP","ARB"
]

MILESTONES = {
    "BTC":   [0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
    "ETH":   [0.1,  0.5,  1.0, 2.5,  5.0, 10.0],
    "SOL":   [1.0,  5.0,  10,  25,   50,  100],
    "XRP":   [100,  500,  1000,2500, 5000,10000],
    "VET":   [1000, 5000, 10000,25000,50000,100000],
    "LINK":  [5,    25,   50,  100,  250,  500],
    "XDC":   [1000, 5000, 10000,25000,50000,100000],
    "ADA":   [100,  500,  1000,2500, 5000, 10000],
    "ATOM":  [5,    25,   50,  100,  250,  500],
    "MATIC": [100,  500,  1000,2500, 5000, 10000],
}

# ============================================================
#  SHARED ENGINE STATE  (thread-safe via locks)
# ============================================================

state_lock = threading.Lock()

ENGINE_STATE = {
    "running":        True,
    "paused":         False,
    "pause_reason":   "",
    "simulation":     SIMULATION_MODE,
    "loop_count":     0,
    "last_loop":      None,
    "last_error":     None,
}

PORTFOLIO = {
    # Core Vault
    "BTC":   {"balance":0.03,    "vault_min":0.01,   "vault_locked":0.01,   "swing_stack":0.02},
    "ETH":   {"balance":0.8,     "vault_min":0.5,    "vault_locked":0.5,    "swing_stack":0.3},
    "SOL":   {"balance":12.0,    "vault_min":10.0,   "vault_locked":10.0,   "swing_stack":2.0},
    "XRP":   {"balance":650.0,   "vault_min":500.0,  "vault_locked":500.0,  "swing_stack":150.0},
    "VET":   {"balance":8500.0,  "vault_min":5000.0, "vault_locked":5000.0, "swing_stack":3500.0},
    "LINK":  {"balance":30.0,    "vault_min":25.0,   "vault_locked":25.0,   "swing_stack":5.0},
    "XDC":   {"balance":6000.0,  "vault_min":5000.0, "vault_locked":5000.0, "swing_stack":1000.0},
    "ADA":   {"balance":800.0,   "vault_min":500.0,  "vault_locked":500.0,  "swing_stack":300.0},
    "ATOM":  {"balance":28.0,    "vault_min":25.0,   "vault_locked":25.0,   "swing_stack":3.0},
    "MATIC": {"balance":700.0,   "vault_min":500.0,  "vault_locked":500.0,  "swing_stack":200.0},
    # Yield
    "HBAR":  {"balance":5000.0,  "rewards":120.0},
    "DOT":   {"balance":50.0,    "rewards":2.1},
    "ALGO":  {"balance":2000.0,  "rewards":80.0},
    "NEAR":  {"balance":100.0,   "rewards":4.5},
    "EGLD":  {"balance":5.0,     "rewards":0.3},
    # Side Bets
    "SHIB":  {"balance":5_000_000, "active":True},
    "SUI":   {"balance":500.0,     "active":True},
    "DOGE":  {"balance":1500.0,    "active":True},
}

ACTIVE_SIDE_BETS         = ["SHIB", "SUI", "DOGE"]
LAST_SIDE_BET_ROTATION   = datetime.now() - timedelta(days=15)

PRICES = {
    "BTC":67500.0,"ETH":3500.0,"SOL":145.0,"XRP":0.52,
    "VET":0.038,"LINK":14.50,"XDC":0.055,"ADA":0.44,
    "ATOM":8.20,"MATIC":0.70,
    "HBAR":0.095,"DOT":7.10,"ALGO":0.18,"NEAR":5.50,"EGLD":42.0,
    "SHIB":0.000025,"SUI":1.20,"BONK":0.000032,"DOGE":0.16,
    "PEPE":0.0000115,"JUP":0.85,"FET":2.30,"AGIX":0.90,
    "RNDR":8.50,"APT":9.20,"OP":2.40,"ARB":1.10,
}

# Approval queue: pending items waiting for yes/no
# Each item: {id, description, usd_value, created_at, status, resolved_at}
APPROVAL_QUEUE   = []
approval_events  = {}   # id -> threading.Event
approval_results = {}   # id -> bool

# Activity log (last 200 entries)
ACTIVITY_LOG = deque(maxlen=200)

# ============================================================
#  LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    handlers=[
        logging.FileHandler("engine.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ENGINE")

def activity(msg: str, level: str = "INFO"):
    """Add to activity log + standard logger."""
    entry = {"ts": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level}
    ACTIVITY_LOG.appendleft(entry)
    getattr(log, level.lower(), log.info)(msg)

# ============================================================
#  TELEGRAM
# ============================================================

def telegram_send(text: str):
    """Send a message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        http_requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")

def telegram_send_approval(approval_id: str, description: str, usd_value: float):
    """Send approval request via Telegram with approve/deny instructions."""
    dashboard_url = os.environ.get("RAILWAY_STATIC_URL", f"http://localhost:{PORT}")
    msg = (
        f"⚠️ <b>APPROVAL REQUIRED</b>\n\n"
        f"{description}\n"
        f"Value: <b>${usd_value:,.2f}</b>\n\n"
        f"→ Approve/Deny at:\n{dashboard_url}\n\n"
        f"Or reply with:\n"
        f"<code>/approve {approval_id[:8]}</code>\n"
        f"<code>/deny {approval_id[:8]}</code>"
    )
    telegram_send(msg)

def poll_telegram_commands():
    """
    Background thread that polls Telegram for /approve and /deny commands.
    Updates approval_results accordingly.
    """
    if not TELEGRAM_BOT_TOKEN:
        return
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            resp = http_requests.get(url, params={"offset": last_update_id + 1, "timeout": 30}, timeout=35)
            data = resp.json()
            for update in data.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                if text.startswith("/approve ") or text.startswith("/deny "):
                    parts = text.split()
                    cmd     = parts[0]
                    id_hint = parts[1] if len(parts) > 1 else ""
                    # Match partial approval ID
                    for appr in APPROVAL_QUEUE:
                        if appr["id"].startswith(id_hint) and appr["status"] == "pending":
                            result = cmd == "/approve"
                            _resolve_approval(appr["id"], result)
                            reply = "✅ Approved" if result else "❌ Denied"
                            telegram_send(f"{reply}: {appr['description'][:80]}")
                            break
        except Exception as e:
            log.debug(f"Telegram poll error: {e}")
        time.sleep(2)

def _resolve_approval(approval_id: str, result: bool):
    """Mark an approval as resolved and signal the waiting engine thread."""
    for appr in APPROVAL_QUEUE:
        if appr["id"] == approval_id and appr["status"] == "pending":
            appr["status"]      = "approved" if result else "denied"
            appr["resolved_at"] = datetime.now().isoformat()
            approval_results[approval_id] = result
            ev = approval_events.get(approval_id)
            if ev:
                ev.set()
            activity(
                f"Approval {'APPROVED' if result else 'DENIED'}: {appr['description'][:60]}",
                "INFO" if result else "WARNING"
            )
            break

# ============================================================
#  APPROVAL SYSTEM
# ============================================================

def request_approval(description: str, usd_value: float = 0.0) -> bool:
    """
    Queue an approval request, notify via Telegram + dashboard.
    Blocks the engine thread until resolved or timed out.
    Returns True if approved, False otherwise.
    """
    approval_id = str(uuid.uuid4())
    event = threading.Event()
    approval_events[approval_id] = event

    entry = {
        "id":          approval_id,
        "description": description,
        "usd_value":   usd_value,
        "created_at":  datetime.now().isoformat(),
        "status":      "pending",
        "resolved_at": None,
    }
    APPROVAL_QUEUE.append(entry)
    activity(f"[APPROVAL PENDING] {description} | ${usd_value:,.2f}", "WARNING")

    # Notify Telegram
    telegram_send_approval(approval_id, description, usd_value)

    # Wait for resolution
    resolved = event.wait(timeout=APPROVAL_TIMEOUT)
    if not resolved:
        entry["status"]      = "timeout"
        entry["resolved_at"] = datetime.now().isoformat()
        activity(f"[APPROVAL TIMEOUT] {description}", "WARNING")
        return False

    return approval_results.get(approval_id, False)

# ============================================================
#  UTILITY
# ============================================================

def usd(val: float) -> str:
    return f"${val:,.2f}"

def sim_tag() -> str:
    return "[SIM] " if SIMULATION_MODE else ""

def get_price(symbol: str) -> float:
    if SIMULATION_MODE:
        base  = PRICES.get(symbol, 1.0)
        noise = random.uniform(-0.005, 0.005)
        return round(base * (1 + noise), 8)
    # TODO: live exchange price fetch
    raise NotImplementedError("Live price feed not wired in.")

def get_balance(symbol: str) -> float:
    if SIMULATION_MODE:
        return PORTFOLIO.get(symbol, {}).get("balance", 0.0)
    # TODO: live exchange balance fetch
    raise NotImplementedError("Live balance fetch not wired in.")

def execute_trade(action: str, symbol: str, amount: float, reason: str):
    price   = get_price(symbol)
    usd_val = amount * price
    msg     = (
        f"{sim_tag()}{action.upper()} {amount:.6f} {symbol} "
        f"@ {usd(price)} = {usd(usd_val)} | {reason}"
    )
    activity(msg)
    if SIMULATION_MODE:
        entry = PORTFOLIO.get(symbol, {"balance": 0.0})
        if action.lower() == "buy":
            entry["balance"] = entry.get("balance", 0.0) + amount
        elif action.lower() == "sell":
            entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
        PORTFOLIO[symbol] = entry
    else:
        # TODO: live exchange order
        raise NotImplementedError("Live trade execution not wired in.")

# ============================================================
#  SAFETY LAYER
# ============================================================

def check_gas_fees() -> bool:
    if SIMULATION_MODE:
        gwei = random.uniform(20, 120)
        if gwei > MAX_GAS_GWEI:
            activity(f"[SAFETY] High gas: {gwei:.0f} gwei", "WARNING")
            return False
        return True
    return True  # TODO: gas oracle

def check_volatility(symbol: str) -> bool:
    if SIMULATION_MODE:
        swing = random.uniform(0.5, 20.0)
        if swing > MAX_VOLATILITY_PCT:
            activity(f"[SAFETY] High volatility {symbol}: {swing:.1f}%", "WARNING")
            return False
        return True
    return True  # TODO: OHLCV check

def check_exchange_status() -> bool:
    if SIMULATION_MODE:
        return True
    return True  # TODO: ping exchange

def is_safe_to_trade(symbol: str = "ETH") -> bool:
    return all([
        check_exchange_status(),
        check_gas_fees(),
        check_volatility(symbol),
    ])

# ============================================================
#  LAYER 1: VAULT
# ============================================================

def get_current_milestone(symbol: str, balance: float) -> float:
    ladder   = MILESTONES.get(symbol, [])
    achieved = [m for m in ladder if balance >= m]
    return max(achieved) if achieved else (ladder[0] if ladder else 0.0)

def next_milestone(symbol: str, balance: float) -> str:
    ladder   = MILESTONES.get(symbol, [])
    upcoming = [m for m in ladder if m > balance]
    return str(min(upcoming)) if upcoming else "MAX"

def update_vault_minimums():
    for symbol in VAULT_ASSETS:
        entry   = PORTFOLIO.get(symbol, {})
        balance = get_balance(symbol)
        new_min = get_current_milestone(symbol, balance)
        old_min = entry.get("vault_min", 0.0)
        if new_min > old_min:
            activity(f"[VAULT] {symbol} milestone ↑ {old_min} → {new_min}")
            PORTFOLIO[symbol]["vault_min"]    = new_min
            PORTFOLIO[symbol]["vault_locked"] = new_min
        PORTFOLIO[symbol]["swing_stack"] = max(0.0, balance - new_min)

def lock_gains_into_vault(symbol: str, amount: float):
    entry      = PORTFOLIO.get(symbol, {})
    old_locked = entry.get("vault_locked", 0.0)
    PORTFOLIO[symbol]["vault_locked"] = old_locked + amount
    activity(f"{sim_tag()}[VAULT] Locked {amount:.6f} {symbol} → vault total: {old_locked+amount:.6f}")

# ============================================================
#  LAYER 2: SWING STACK
# ============================================================

def run_swing_stack():
    for symbol in VAULT_ASSETS:
        if ENGINE_STATE["paused"]:
            break
        if not is_safe_to_trade(symbol):
            continue
        entry     = PORTFOLIO.get(symbol, {})
        swing     = entry.get("swing_stack", 0.0)
        price     = get_price(symbol)
        swing_usd = swing * price
        if swing_usd < 10.0:
            continue
        trade_amount = swing * SWING_TRADE_SIZE_PCT
        trade_usd    = trade_amount * price
        if trade_usd >= LARGE_MOVE_USD:
            desc = f"Swing trade {symbol}: sell {trade_amount:.6f} ({usd(trade_usd)}) from swing stack"
            if not request_approval(desc, trade_usd):
                continue
        execute_trade("sell", symbol, trade_amount, "swing stack trade")
        reinvest = trade_amount * SWING_REINVEST_PCT
        execute_trade("buy", symbol, reinvest, "swing profit → vault")
        lock_gains_into_vault(symbol, reinvest)
        PORTFOLIO[symbol]["swing_stack"] = max(0.0, swing - trade_amount + reinvest)

# ============================================================
#  LAYER 3: YIELD
# ============================================================

def pick_weakest_vault_asset() -> str:
    weakest, weakest_val = None, float("inf")
    for symbol in VAULT_ASSETS:
        val = PORTFOLIO.get(symbol, {}).get("swing_stack", 0.0) * get_price(symbol)
        if val < weakest_val:
            weakest_val, weakest = val, symbol
    return weakest or "BTC"

def sell_yield_rewards(symbol: str):
    entry      = PORTFOLIO.get(symbol, {})
    rewards    = entry.get("rewards", 0.0)
    price      = get_price(symbol)
    reward_usd = rewards * price
    if rewards <= 0.0 or reward_usd < 1.0:
        return
    if reward_usd >= LARGE_MOVE_USD:
        if not request_approval(f"Auto-sell {symbol} rewards: {rewards:.4f}", reward_usd):
            return
    execute_trade("sell", symbol, rewards, f"{symbol} yield rewards → vault")
    PORTFOLIO[symbol]["rewards"] = 0.0
    target     = pick_weakest_vault_asset()
    buy_amount = (reward_usd * 0.98) / get_price(target)
    execute_trade("buy", target, buy_amount, f"yield route from {symbol}")
    lock_gains_into_vault(target, buy_amount * SWING_REINVEST_PCT)

def run_yield_layer():
    for symbol in YIELD_ASSETS:
        if ENGINE_STATE["paused"]:
            break
        sell_yield_rewards(symbol)
    if "ALGO" in YIELD_PHASE_OUT:
        _maybe_phase_out_algo()

def _maybe_phase_out_algo():
    if not is_safe_to_trade("ALGO"):
        return
    entry     = PORTFOLIO.get("ALGO", {})
    bal       = entry.get("balance", 0.0)
    total_usd = bal * get_price("ALGO")
    if total_usd < 5.0:
        return
    desc = f"Phase out ALGO: sell {bal:.2f} ALGO ({usd(total_usd)}) → vault"
    if request_approval(desc, total_usd):
        execute_trade("sell", "ALGO", bal, "ALGO phase-out")
        target     = pick_weakest_vault_asset()
        buy_amount = (total_usd * 0.98) / get_price(target)
        execute_trade("buy", target, buy_amount, f"ALGO phase-out → {target}")
        lock_gains_into_vault(target, buy_amount * SWING_REINVEST_PCT)
        PORTFOLIO["ALGO"]["balance"] = 0.0

# ============================================================
#  LAYER 4: SIDE BETS
# ============================================================

def run_side_bets():
    global ACTIVE_SIDE_BETS, LAST_SIDE_BET_ROTATION
    if ENGINE_STATE["paused"]:
        return
    days_since = (datetime.now() - LAST_SIDE_BET_ROTATION).days
    if days_since >= SIDE_BET_ROTATE_DAYS:
        _rotate_side_bets()

def _rotate_side_bets():
    global ACTIVE_SIDE_BETS, LAST_SIDE_BET_ROTATION
    available = [s for s in SIDE_BET_POOL if s not in ACTIVE_SIDE_BETS]
    incoming  = random.sample(available, MAX_ACTIVE_SIDE_BETS)
    outgoing  = list(ACTIVE_SIDE_BETS)
    total_sell = sum(
        PORTFOLIO.get(s, {"balance":0}).get("balance", 0) * get_price(s)
        for s in outgoing
    )
    desc = f"Side-bet rotation: OUT {outgoing} → IN {incoming}"
    if total_sell >= SIDE_BET_ROTATE_USD:
        if not request_approval(desc, total_sell):
            return
    else:
        activity(f"[SIDE BETS] Auto-rotating (below threshold): {desc}")

    for symbol in outgoing:
        bal = PORTFOLIO.get(symbol, {"balance":0}).get("balance", 0)
        if bal > 0:
            execute_trade("sell", symbol, bal, "side-bet rotation out")
            PORTFOLIO[symbol]["balance"] = 0.0
            PORTFOLIO[symbol]["active"]  = False

    per_coin = (total_sell * 0.98) / MAX_ACTIVE_SIDE_BETS
    for symbol in incoming:
        amount = per_coin / get_price(symbol)
        execute_trade("buy", symbol, amount, "side-bet rotation in")
        PORTFOLIO[symbol] = {"balance": amount, "active": True}

    ACTIVE_SIDE_BETS       = incoming
    LAST_SIDE_BET_ROTATION = datetime.now()
    activity(f"[SIDE BETS] Rotation complete → {incoming}")
    telegram_send(f"🔄 Side-bet rotation complete\nNow holding: {', '.join(incoming)}")

# ============================================================
#  ENGINE LOOP  (runs in background thread)
# ============================================================

def engine_loop():
    activity("Engine started.")
    telegram_send(
        f"🚀 <b>Rizz Engine Started</b>\n"
        f"Mode: {'SIMULATION' if SIMULATION_MODE else 'LIVE'}\n"
        f"Exchange: {EXCHANGE}"
    )

    while ENGINE_STATE["running"]:
        with state_lock:
            paused = ENGINE_STATE["paused"]

        if paused:
            time.sleep(5)
            continue

        try:
            with state_lock:
                ENGINE_STATE["loop_count"] += 1
                ENGINE_STATE["last_loop"]   = datetime.now().isoformat()
                loop_n = ENGINE_STATE["loop_count"]

            activity(f"── Loop #{loop_n} ──")

            if not check_exchange_status():
                _pause_engine("Exchange unreachable")
                continue
            if not check_gas_fees():
                _pause_engine("Gas fees too high")
                continue

            update_vault_minimums()
            run_swing_stack()
            run_yield_layer()
            run_side_bets()

            with state_lock:
                ENGINE_STATE["last_error"] = None

        except Exception as e:
            msg = f"Loop error: {e}"
            activity(msg, "ERROR")
            with state_lock:
                ENGINE_STATE["last_error"] = msg
            telegram_send(f"❌ Engine error: {msg}")
            time.sleep(LOOP_INTERVAL_SECONDS * 2)
            continue

        time.sleep(LOOP_INTERVAL_SECONDS)

def _pause_engine(reason: str):
    with state_lock:
        ENGINE_STATE["paused"]       = True
        ENGINE_STATE["pause_reason"] = reason
    activity(f"[ENGINE PAUSED] {reason}", "WARNING")
    telegram_send(f"⏸ Engine paused: {reason}")

def _resume_engine():
    with state_lock:
        ENGINE_STATE["paused"]       = False
        ENGINE_STATE["pause_reason"] = ""
    activity("[ENGINE RESUMED]")
    telegram_send("▶️ Engine resumed.")

# ============================================================
#  FLASK DASHBOARD
# ============================================================

app = Flask(__name__)

def require_auth():
    """Simple token auth via ?secret= or Authorization header."""
    secret = request.args.get("secret") or request.headers.get("X-Dashboard-Secret", "")
    if DASHBOARD_SECRET and DASHBOARD_SECRET != "changeme" and secret != DASHBOARD_SECRET:
        abort(401)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

# --- API: engine status ---
@app.route("/api/status")
def api_status():
    require_auth()
    with state_lock:
        s = dict(ENGINE_STATE)

    vault_data = []
    for symbol in VAULT_ASSETS:
        e     = PORTFOLIO.get(symbol, {})
        price = get_price(symbol)
        bal   = e.get("balance", 0.0)
        vault_data.append({
            "symbol":       symbol,
            "balance":      bal,
            "vault_locked": e.get("vault_locked", 0.0),
            "swing_stack":  e.get("swing_stack", 0.0),
            "vault_usd":    round(e.get("vault_locked", 0.0) * price, 2),
            "swing_usd":    round(e.get("swing_stack", 0.0) * price, 2),
            "total_usd":    round(bal * price, 2),
            "next_ms":      next_milestone(symbol, bal),
            "price":        round(price, 6),
        })

    yield_data = []
    for symbol in YIELD_ASSETS:
        e     = PORTFOLIO.get(symbol, {})
        price = get_price(symbol)
        bal   = e.get("balance", 0.0)
        yield_data.append({
            "symbol":    symbol,
            "balance":   bal,
            "rewards":   e.get("rewards", 0.0),
            "total_usd": round(bal * price, 2),
            "phase_out": symbol in YIELD_PHASE_OUT,
        })

    side_bet_data = []
    for symbol in ACTIVE_SIDE_BETS:
        e     = PORTFOLIO.get(symbol, {"balance": 0.0})
        price = get_price(symbol)
        bal   = e.get("balance", 0.0)
        side_bet_data.append({
            "symbol":    symbol,
            "balance":   bal,
            "total_usd": round(bal * price, 2),
        })

    days_to_rotate = max(0, SIDE_BET_ROTATE_DAYS - (datetime.now() - LAST_SIDE_BET_ROTATION).days)

    total_vault_usd = sum(d["vault_usd"] for d in vault_data)
    total_swing_usd = sum(d["swing_usd"] for d in vault_data)
    total_yield_usd = sum(d["total_usd"] for d in yield_data)
    total_side_usd  = sum(d["total_usd"] for d in side_bet_data)

    return jsonify({
        "engine":          s,
        "vault":           vault_data,
        "yield":           yield_data,
        "side_bets":       side_bet_data,
        "days_to_rotate":  days_to_rotate,
        "totals": {
            "vault_locked": round(total_vault_usd, 2),
            "swing_stacks": round(total_swing_usd, 2),
            "yield_assets": round(total_yield_usd, 2),
            "side_bets":    round(total_side_usd, 2),
            "grand_total":  round(total_vault_usd + total_swing_usd + total_yield_usd + total_side_usd, 2),
        },
        "activity": list(ACTIVITY_LOG)[:50],
    })

# --- API: pending approvals ---
@app.route("/api/approvals")
def api_approvals():
    require_auth()
    pending = [a for a in APPROVAL_QUEUE if a["status"] == "pending"]
    return jsonify(pending)

# --- API: resolve approval ---
@app.route("/api/approve/<approval_id>", methods=["POST"])
def api_approve(approval_id):
    require_auth()
    data   = request.get_json(silent=True) or {}
    result = data.get("approved", False)
    _resolve_approval(approval_id, result)
    return jsonify({"ok": True, "approved": result})

# --- API: pause / resume ---
@app.route("/api/pause", methods=["POST"])
def api_pause():
    require_auth()
    data   = request.get_json(silent=True) or {}
    reason = data.get("reason", "Manual pause from dashboard")
    _pause_engine(reason)
    return jsonify({"ok": True})

@app.route("/api/resume", methods=["POST"])
def api_resume():
    require_auth()
    _resume_engine()
    return jsonify({"ok": True})

# --- API: force side-bet rotation ---
@app.route("/api/rotate_side_bets", methods=["POST"])
def api_rotate():
    require_auth()
    activity("[MANUAL] Force side-bet rotation triggered from dashboard", "WARNING")
    threading.Thread(target=_rotate_side_bets, daemon=True).start()
    return jsonify({"ok": True})

# --- API: manual override trade ---
@app.route("/api/manual_trade", methods=["POST"])
def api_manual_trade():
    require_auth()
    data   = request.get_json(silent=True) or {}
    action = data.get("action", "").lower()
    symbol = data.get("symbol", "").upper()
    amount = float(data.get("amount", 0.0))

    if action not in ("buy", "sell"):
        return jsonify({"ok": False, "error": "action must be buy or sell"}), 400
    if symbol not in {**{s: 1 for s in VAULT_ASSETS}, **{s: 1 for s in YIELD_ASSETS}, **{s: 1 for s in SIDE_BET_POOL}}:
        return jsonify({"ok": False, "error": "unknown symbol"}), 400
    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400

    # Vault protection — selling vault assets requires approval
    if symbol in VAULT_ASSETS and action == "sell":
        price = get_price(symbol)
        desc  = f"MANUAL OVERRIDE: sell {amount} {symbol} ({usd(amount*price)})"
        if not request_approval(desc, amount * price):
            return jsonify({"ok": False, "error": "Approval denied or timed out"})

    execute_trade(action, symbol, amount, "manual override from dashboard")
    return jsonify({"ok": True})

# --- API: activity log ---
@app.route("/api/activity")
def api_activity():
    require_auth()
    return jsonify(list(ACTIVITY_LOG))

# ============================================================
#  MAIN
# ============================================================

if __name__ == "__main__":
    # Start Telegram polling thread
    tg_thread = threading.Thread(target=poll_telegram_commands, daemon=True)
    tg_thread.start()

    # Start engine loop thread
    eng_thread = threading.Thread(target=engine_loop, daemon=True)
    eng_thread.start()

    # Start Flask (blocks main thread)
    log.info(f"Dashboard starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
