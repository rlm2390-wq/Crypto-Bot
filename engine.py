"""
================================================================================
  RIZZ CRYPTO PORTFOLIO AUTOMATION ENGINE
  engine.py — v3.0

  Entry point. Starts:
    1. Telegram polling thread
    2. Engine loop thread (4 layers)
    3. Flask dashboard (main thread)

  All logic lives in:
    config.py       — settings, credentials, asset rules
    exchanges/      — Coinbase, Kraken, Binance, Uphold, Bitrue
    wallets/        — Ledger, Phantom, MetaMask, Keplr, Bifrost, XDC
    layers/         — Vault, Swing, Yield, Side Bets
    core/           — state, approvals, safety, logger

  LOCAL DEV:
    cp .env.example .env
    pip install -r requirements.txt
    python engine.py
    open http://localhost:5000?secret=YOUR_SECRET

  RAILWAY:
    Push to GitHub → connect repo → add env vars in Railway Variables tab
================================================================================
"""

import os
import time
import threading
import random
from datetime import datetime

from flask import Flask, jsonify, request, render_template, abort

# ── Core modules ──
from config import (
    SIMULATION_MODE, LOOP_INTERVAL, PORT, DASHBOARD_SECRET,
    VAULT_ASSETS, YIELD_ASSETS, SIDE_BET_POOL,
    LARGE_MOVE_USD, SIDE_BET_ROTATE_DAYS,
)
from core.logger   import activity, ACTIVITY_LOG
from core.state    import (
    ENGINE_STATE, PORTFOLIO, APPROVAL_QUEUE,
    ACTIVE_SIDE_BETS, LAST_SIDE_BET_ROTATION,
    init_portfolio, state_lock,
)
from core.approvals import (
    request_approval, resolve_approval,
    telegram_send, poll_telegram_commands,
)
from core.safety   import is_safe_to_trade, check_exchange_status, check_gas_fees
from layers        import (
    update_vault_minimums, run_swing_stack,
    run_yield_layer, run_side_bets, rotate_side_bets,
    next_milestone_str,
)
from exchanges     import init_exchanges, get_exchange, get_all_exchanges
from wallets       import init_wallets, get_wallet, get_all_wallets
import core.state as state


# ============================================================
#  ENGINE CONTROL
# ============================================================

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
#  ENGINE LOOP  (background thread)
# ============================================================

def engine_loop():
    activity("Engine loop starting.")
    telegram_send(
        f"🚀 <b>Rizz Engine v3.0 Started</b>\n"
        f"Mode: {'⚠️ SIMULATION' if SIMULATION_MODE else '🔴 LIVE TRADING'}\n"
        f"Exchanges: {list(get_all_exchanges().keys())}\n"
        f"Wallets: {list(get_all_wallets().keys())}"
    )

    while ENGINE_STATE["running"]:
        # ── Paused — wait and retry ──
        if ENGINE_STATE["paused"]:
            time.sleep(5)
            continue

        try:
            with state_lock:
                ENGINE_STATE["loop_count"] += 1
                ENGINE_STATE["last_loop"]   = datetime.now().isoformat()
                loop_n = ENGINE_STATE["loop_count"]

            activity(f"── Loop #{loop_n} ──")

            # Safety gates
            if not check_exchange_status():
                _pause_engine("Exchange unreachable")
                continue
            if not check_gas_fees():
                _pause_engine("Gas fees too high — waiting for lower fees")
                time.sleep(LOOP_INTERVAL * 2)
                _resume_engine()
                continue

            # ── Run all 4 layers ──
            update_vault_minimums()   # Layer 1 — vault milestones + Ledger sync
            run_swing_stack()          # Layer 2 — swing stack trades
            run_yield_layer()          # Layer 3 — claim rewards + route
            run_side_bets()            # Layer 4 — rotation check

            with state_lock:
                ENGINE_STATE["last_error"] = None

            activity(f"Loop #{loop_n} complete. Sleeping {LOOP_INTERVAL}s.")

        except Exception as e:
            msg = f"Loop #{ENGINE_STATE['loop_count']} error: {e}"
            activity(msg, "ERROR")
            with state_lock:
                ENGINE_STATE["last_error"] = msg
            telegram_send(f"❌ Engine error: {msg}")
            time.sleep(LOOP_INTERVAL * 2)
            continue

        time.sleep(LOOP_INTERVAL)


# ============================================================
#  FLASK DASHBOARD
# ============================================================

app = Flask(__name__)


def _auth():
    """Simple token auth — checked on all /api routes."""
    secret = request.args.get("secret") or request.headers.get("X-Dashboard-Secret", "")
    if DASHBOARD_SECRET and DASHBOARD_SECRET != "changeme" and secret != DASHBOARD_SECRET:
        abort(401)


# ── Dashboard UI ──

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ── Status ──

@app.route("/api/status")
def api_status():
    _auth()

    with state_lock:
        eng = dict(ENGINE_STATE)

    # Vault data (exchange layer)
    vault_data = []
    for symbol in VAULT_ASSETS:
        e        = PORTFOLIO.get(symbol, {})
        source   = e.get("source", "coinbase")
        exchange = get_exchange(source)
        price    = exchange.get_price(symbol) if exchange else 1.0
        bal      = e.get("balance", 0.0)
        locked   = e.get("vault_locked", 0.0)
        swing    = e.get("swing_stack", 0.0)
        # Ledger vault balance
        ledger_bal = PORTFOLIO.get(f"LEDGER_{symbol}", {}).get("balance", 0.0)
        vault_data.append({
            "symbol":       symbol,
            "balance":      round(bal, 8),
            "vault_locked": round(locked, 8),
            "swing_stack":  round(swing, 8),
            "ledger_bal":   round(ledger_bal, 8),
            "vault_usd":    round(locked * price, 2),
            "swing_usd":    round(swing * price, 2),
            "ledger_usd":   round(ledger_bal * price, 2),
            "total_usd":    round(bal * price, 2),
            "price":        round(price, 6),
            "source":       source,
            "next_ms":      next_milestone_str(symbol, bal),
        })

    # Yield data
    yield_data = []
    for symbol in YIELD_ASSETS:
        e        = PORTFOLIO.get(symbol, {})
        source   = e.get("source", "coinbase")
        exchange = get_exchange(source)
        price    = exchange.get_price(symbol) if exchange else 1.0
        bal      = e.get("balance", 0.0)
        yield_data.append({
            "symbol":    symbol,
            "balance":   round(bal, 6),
            "rewards":   round(e.get("rewards", 0.0), 6),
            "total_usd": round(bal * price, 2),
            "source":    source,
            "phase_out": symbol in ["ALGO"],
        })

    # Side bets
    side_data = []
    for symbol in state.ACTIVE_SIDE_BETS:
        e        = PORTFOLIO.get(symbol, {"balance": 0.0})
        source   = e.get("source", "coinbase")
        exchange = get_exchange(source)
        price    = exchange.get_price(symbol) if exchange else 1.0
        bal      = e.get("balance", 0.0)
        side_data.append({
            "symbol":    symbol,
            "balance":   round(bal, 4),
            "total_usd": round(bal * price, 2),
        })

    # Wallet status
    wallet_status = {}
    for name, wallet in get_all_wallets().items():
        wallet_status[name] = {
            "available": wallet.is_available(),
            "read_only": wallet.read_only,
        }

    # Exchange status
    exchange_status = {}
    for name, exchange in get_all_exchanges().items():
        exchange_status[name] = {"available": exchange.is_available()}

    # Totals
    total_vault_usd   = sum(d["vault_usd"]   for d in vault_data)
    total_swing_usd   = sum(d["swing_usd"]   for d in vault_data)
    total_ledger_usd  = sum(d["ledger_usd"]  for d in vault_data)
    total_yield_usd   = sum(d["total_usd"]   for d in yield_data)
    total_side_usd    = sum(d["total_usd"]   for d in side_data)

    days_to_rotate = max(0, SIDE_BET_ROTATE_DAYS -
                         (datetime.now() - state.LAST_SIDE_BET_ROTATION).days)

    return jsonify({
        "engine":          eng,
        "vault":           vault_data,
        "yield":           yield_data,
        "side_bets":       side_data,
        "wallet_status":   wallet_status,
        "exchange_status": exchange_status,
        "days_to_rotate":  days_to_rotate,
        "totals": {
            "ledger_vault":  round(total_ledger_usd, 2),
            "exchange_vault":round(total_vault_usd, 2),
            "swing_stacks":  round(total_swing_usd, 2),
            "yield_assets":  round(total_yield_usd, 2),
            "side_bets":     round(total_side_usd, 2),
            "grand_total":   round(
                total_ledger_usd + total_vault_usd +
                total_swing_usd  + total_yield_usd + total_side_usd, 2
            ),
        },
        "activity": list(ACTIVITY_LOG)[:60],
    })


# ── Approvals ──

@app.route("/api/approvals")
def api_approvals():
    _auth()
    return jsonify([a for a in APPROVAL_QUEUE if a["status"] == "pending"])


@app.route("/api/approve/<approval_id>", methods=["POST"])
def api_approve(approval_id):
    _auth()
    data   = request.get_json(silent=True) or {}
    result = data.get("approved", False)
    resolve_approval(approval_id, result)
    return jsonify({"ok": True, "approved": result})


# ── Engine controls ──

@app.route("/api/pause", methods=["POST"])
def api_pause():
    _auth()
    data   = request.get_json(silent=True) or {}
    reason = data.get("reason", "Manual pause from dashboard")
    _pause_engine(reason)
    return jsonify({"ok": True})


@app.route("/api/resume", methods=["POST"])
def api_resume():
    _auth()
    _resume_engine()
    return jsonify({"ok": True})


# ── Side bet controls ──

@app.route("/api/rotate_side_bets", methods=["POST"])
def api_rotate():
    _auth()
    activity("[MANUAL] Force side-bet rotation triggered from dashboard", "WARNING")
    threading.Thread(target=rotate_side_bets, daemon=True).start()
    return jsonify({"ok": True})


# ── Manual trade override ──

@app.route("/api/manual_trade", methods=["POST"])
def api_manual_trade():
    _auth()
    data   = request.get_json(silent=True) or {}
    action = data.get("action", "").lower()
    symbol = data.get("symbol", "").upper()
    amount = float(data.get("amount", 0.0))
    source = data.get("source", "coinbase")

    all_symbols = set(VAULT_ASSETS + YIELD_ASSETS + SIDE_BET_POOL)
    if action not in ("buy", "sell"):
        return jsonify({"ok": False, "error": "action must be buy or sell"}), 400
    if symbol not in all_symbols:
        return jsonify({"ok": False, "error": f"unknown symbol: {symbol}"}), 400
    if amount <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400

    exchange = get_exchange(source)
    if not exchange:
        return jsonify({"ok": False, "error": f"exchange not available: {source}"}), 400

    # Vault protection — selling vault assets always requires approval
    if symbol in VAULT_ASSETS and action == "sell":
        price = exchange.get_price(symbol)
        desc  = f"MANUAL OVERRIDE: sell {amount} {symbol} ({_usd(amount * price)}) on {source}"
        if not request_approval(desc, amount * price):
            return jsonify({"ok": False, "error": "Approval denied or timed out"})

    if action == "buy":
        exchange.buy(symbol, amount, f"manual override from dashboard")
    else:
        exchange.sell(symbol, amount, f"manual override from dashboard")

    return jsonify({"ok": True})


# ── Wallet status ──

@app.route("/api/wallet_balances")
def api_wallet_balances():
    _auth()
    result = {}
    ledger = get_wallet("ledger")
    if ledger:
        result["ledger"] = ledger.get_all_balances()
    return jsonify(result)


# ── Activity log ──

@app.route("/api/activity")
def api_activity():
    _auth()
    return jsonify(list(ACTIVITY_LOG))


# ── Health check (Railway uses this) ──

@app.route("/health")
def health():
    return jsonify({"status": "ok", "loop": ENGINE_STATE["loop_count"]})


# ============================================================
#  HELPERS
# ============================================================

def _usd(val: float) -> str:
    return f"${val:,.2f}"


# ============================================================
#  MAIN
# ============================================================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════╗
║          RIZZ CRYPTO PORTFOLIO ENGINE  v3.0              ║
║  Mode    : {'SIMULATION ⚠️ ' if SIMULATION_MODE else 'LIVE TRADING 🔴'}                              ║
║  Port    : {PORT}                                             ║
║  Dashboard: http://localhost:{PORT}?secret=<your_secret>   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 1. Seed portfolio state
    init_portfolio(SIMULATION_MODE)

    # 2. Init exchange connectors
    init_exchanges()

    # 3. Init wallet connectors
    init_wallets()

    # 4. Sync engine simulation flag into state
    ENGINE_STATE["simulation"] = SIMULATION_MODE

    # 5. Start Telegram polling thread
    tg_thread = threading.Thread(target=poll_telegram_commands, daemon=True)
    tg_thread.start()
    activity("Telegram polling thread started.")

    # 6. Start engine loop thread
    eng_thread = threading.Thread(target=engine_loop, daemon=True)
    eng_thread.start()
    activity("Engine loop thread started.")

    # 7. Start Flask (blocks main thread)
    activity(f"Dashboard starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
