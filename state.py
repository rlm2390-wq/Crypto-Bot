"""core/state.py — Shared portfolio state, engine flags, approval queue."""

import threading
from datetime import datetime, timedelta

# ── Thread lock for all shared state mutations ──
state_lock = threading.Lock()

# ── Engine control flags ──
ENGINE_STATE = {
    "running":      True,
    "paused":       False,
    "pause_reason": "",
    "simulation":   True,   # overwritten by config on startup
    "loop_count":   0,
    "last_loop":    None,
    "last_error":   None,
}

# ── Portfolio state ──
# Keyed by symbol. Each entry has relevant fields per asset type.
# Populated at runtime by balance fetches (or sim defaults).
PORTFOLIO: dict = {}

# ── Active side bets ──
ACTIVE_SIDE_BETS: list        = ["SHIB", "SUI", "DOGE"]
LAST_SIDE_BET_ROTATION: datetime = datetime.now() - timedelta(days=15)

# ── Simulated prices (used in SIMULATION_MODE) ──
SIM_PRICES = {
    "BTC":67500.0,"ETH":3500.0,"SOL":145.0,"XRP":0.52,
    "VET":0.038,"LINK":14.50,"XDC":0.055,"ADA":0.44,
    "ATOM":8.20,"MATIC":0.70,
    "HBAR":0.095,"DOT":7.10,"ALGO":0.18,"NEAR":5.50,"EGLD":42.0,
    "SGB":0.012,"FLR":0.018,
    "SHIB":0.000025,"SUI":1.20,"BONK":0.000032,"DOGE":0.16,
    "PEPE":0.0000115,"JUP":0.85,"FET":2.30,"AGIX":0.90,
    "RNDR":8.50,"APT":9.20,"OP":2.40,"ARB":1.10,
}

# ── Simulated portfolio defaults ──
SIM_PORTFOLIO = {
    "BTC":   {"balance":0.03,    "vault_locked":0.01,  "swing_stack":0.02,  "source":"coinbase"},
    "ETH":   {"balance":0.8,     "vault_locked":0.5,   "swing_stack":0.3,   "source":"coinbase"},
    "SOL":   {"balance":12.0,    "vault_locked":10.0,  "swing_stack":2.0,   "source":"coinbase"},
    "XRP":   {"balance":650.0,   "vault_locked":500.0, "swing_stack":150.0, "source":"uphold"},
    "VET":   {"balance":8500.0,  "vault_locked":5000.0,"swing_stack":3500.0,"source":"binance"},
    "LINK":  {"balance":30.0,    "vault_locked":25.0,  "swing_stack":5.0,   "source":"coinbase"},
    "XDC":   {"balance":6000.0,  "vault_locked":5000.0,"swing_stack":1000.0,"source":"bitrue"},
    "ADA":   {"balance":800.0,   "vault_locked":500.0, "swing_stack":300.0, "source":"kraken"},
    "ATOM":  {"balance":28.0,    "vault_locked":25.0,  "swing_stack":3.0,   "source":"kraken"},
    "MATIC": {"balance":700.0,   "vault_locked":500.0, "swing_stack":200.0, "source":"coinbase"},
    # Yield
    "HBAR":  {"balance":5000.0,  "rewards":120.0,  "source":"uphold"},
    "DOT":   {"balance":50.0,    "rewards":2.1,    "source":"kraken"},
    "ALGO":  {"balance":2000.0,  "rewards":80.0,   "source":"coinbase"},
    "NEAR":  {"balance":100.0,   "rewards":4.5,    "source":"coinbase"},
    "EGLD":  {"balance":5.0,     "rewards":0.3,    "source":"kraken"},
    "SGB":   {"balance":10000.0, "rewards":250.0,  "source":"bifrost_sgb"},
    "FLR":   {"balance":8000.0,  "rewards":180.0,  "source":"bifrost_flr"},
    # Side bets
    "SHIB":  {"balance":5_000_000, "active":True, "source":"coinbase"},
    "SUI":   {"balance":500.0,     "active":True, "source":"binance"},
    "DOGE":  {"balance":1500.0,    "active":True, "source":"coinbase"},
    # Ledger vault balances (read-only)
    "LEDGER_BTC":   {"balance":0.05, "source":"ledger"},
    "LEDGER_ETH":   {"balance":1.2,  "source":"ledger"},
    "LEDGER_SOL":   {"balance":25.0, "source":"ledger"},
    "LEDGER_XRP":   {"balance":2000.0,"source":"ledger"},
    "LEDGER_ADA":   {"balance":1500.0,"source":"ledger"},
    "LEDGER_ATOM":  {"balance":50.0,  "source":"ledger"},
    "LEDGER_MATIC": {"balance":2500.0,"source":"ledger"},
    "LEDGER_LINK":  {"balance":75.0,  "source":"ledger"},
    "LEDGER_VET":   {"balance":20000.0,"source":"ledger"},
    "LEDGER_XDC":   {"balance":15000.0,"source":"ledger"},
}

# ── Approval queue ──
APPROVAL_QUEUE:   list = []
approval_events:  dict = {}   # id -> threading.Event
approval_results: dict = {}   # id -> bool


def init_portfolio(simulation: bool):
    """Seed portfolio with sim defaults or empty state for live mode."""
    global PORTFOLIO
    if simulation:
        PORTFOLIO = {k: dict(v) for k, v in SIM_PORTFOLIO.items()}
    else:
        PORTFOLIO = {}
