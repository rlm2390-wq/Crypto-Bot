"""
layers/vault.py     — Layer 1: Vault milestone tracking + Ledger sync
layers/swing.py     — Layer 2: Swing stack engine
layers/yield_layer.py — Layer 3: Reward claiming + routing
layers/side_bets.py — Layer 4: Side bet rotation
"""

# ============================================================
#  LAYER 1: VAULT
# ============================================================

def get_current_milestone(symbol: str, balance: float) -> float:
    from config import MILESTONES
    ladder   = MILESTONES.get(symbol, [])
    achieved = [m for m in ladder if balance >= m]
    return max(achieved) if achieved else (ladder[0] if ladder else 0.0)


def next_milestone_str(symbol: str, balance: float) -> str:
    from config import MILESTONES
    ladder   = MILESTONES.get(symbol, [])
    upcoming = [m for m in ladder if m > balance]
    return str(min(upcoming)) if upcoming else "MAX"


def update_vault_minimums():
    """
    Scan all vault assets (exchange side).
    Update vault_min based on current balance milestone.
    Vault minimum ratchets up only — never decreases.
    Also sync Ledger balances into PORTFOLIO for dashboard display.
    """
    from config     import VAULT_ASSETS
    from core.state import PORTFOLIO
    from core.logger import activity
    from wallets    import get_wallet

    # Sync Ledger balances
    ledger = get_wallet("ledger")
    if ledger:
        for symbol in VAULT_ASSETS:
            bal = ledger.get_balance(symbol)
            PORTFOLIO[f"LEDGER_{symbol}"] = {
                "balance": bal,
                "source":  "ledger",
            }

    # Update exchange vault minimums
    for symbol in VAULT_ASSETS:
        entry   = PORTFOLIO.get(symbol, {})
        balance = entry.get("balance", 0.0)
        new_min = get_current_milestone(symbol, balance)
        old_min = entry.get("vault_min", 0.0)

        if new_min > old_min:
            activity(f"[VAULT] {symbol} milestone ↑ {old_min} → {new_min}")
            PORTFOLIO[symbol]["vault_min"]    = new_min
            PORTFOLIO[symbol]["vault_locked"] = new_min

        PORTFOLIO[symbol]["swing_stack"] = max(0.0, balance - new_min)


def lock_gains_into_vault(symbol: str, amount: float):
    """Lock swing-stack gains into vault. Never requires approval."""
    from core.state  import PORTFOLIO
    from core.logger import activity
    entry      = PORTFOLIO.get(symbol, {})
    old_locked = entry.get("vault_locked", 0.0)
    PORTFOLIO[symbol]["vault_locked"] = old_locked + amount
    activity(f"[VAULT] Locked {amount:.6f} {symbol} → vault total: {old_locked+amount:.6f}")


# ============================================================
#  LAYER 2: SWING STACK
# ============================================================

def run_swing_stack():
    """
    For each vault asset: trade a portion of the swing stack,
    then reinvest a % of gains back into the vault.
    Requires approval if trade value > LARGE_MOVE_USD.
    """
    from config      import VAULT_ASSETS, LARGE_MOVE_USD, SWING_TRADE_SIZE_PCT, SWING_REINVEST_PCT, SIMULATION_MODE
    from core.state  import PORTFOLIO, ENGINE_STATE
    from core.logger import activity
    from core.safety import is_safe_to_trade
    from core.approvals import request_approval
    from exchanges   import get_exchange

    for symbol in VAULT_ASSETS:
        if ENGINE_STATE["paused"]:
            break

        if not is_safe_to_trade(symbol):
            continue

        entry     = PORTFOLIO.get(symbol, {})
        swing     = entry.get("swing_stack", 0.0)
        source    = entry.get("source", "coinbase")
        exchange  = get_exchange(source)
        if not exchange:
            continue

        price     = exchange.get_price(symbol)
        swing_usd = swing * price

        if swing_usd < 10.0:
            continue

        trade_amount = swing * SWING_TRADE_SIZE_PCT
        trade_usd    = trade_amount * price

        if trade_usd >= LARGE_MOVE_USD:
            desc = f"Swing trade {symbol}: sell {trade_amount:.6f} ({_usd(trade_usd)}) from swing stack"
            if not request_approval(desc, trade_usd):
                continue

        exchange.sell(symbol, trade_amount, "swing stack trade")
        reinvest = trade_amount * SWING_REINVEST_PCT
        exchange.buy(symbol, reinvest, "swing profit → vault reinvestment")
        lock_gains_into_vault(symbol, reinvest)
        PORTFOLIO[symbol]["swing_stack"] = max(0.0, swing - trade_amount + reinvest)


# ============================================================
#  LAYER 3: YIELD
# ============================================================

def pick_weakest_vault_asset() -> str:
    """Return vault asset with smallest swing stack in USD."""
    from config     import VAULT_ASSETS
    from core.state import PORTFOLIO
    from exchanges  import get_exchange
    weakest, weakest_val = None, float("inf")
    for symbol in VAULT_ASSETS:
        entry    = PORTFOLIO.get(symbol, {})
        swing    = entry.get("swing_stack", 0.0)
        source   = entry.get("source", "coinbase")
        exchange = get_exchange(source)
        price    = exchange.get_price(symbol) if exchange else 1.0
        val      = swing * price
        if val < weakest_val:
            weakest_val, weakest = val, symbol
    return weakest or "BTC"


def run_yield_layer():
    """
    1. Claim rewards from all onchain wallets.
    2. Route claimed rewards to exchange or Ledger per REWARD_ROUTING config.
    3. Auto-sell yield asset rewards on exchanges → route to vault.
    4. Phase out ALGO if conditions are safe.
    """
    from config      import YIELD_ASSETS, YIELD_PHASE_OUT, REWARD_ROUTING, SIMULATION_MODE
    from core.state  import PORTFOLIO, ENGINE_STATE
    from core.logger import activity
    from wallets     import get_all_wallets
    from exchanges   import get_exchange

    if ENGINE_STATE["paused"]:
        return

    # Step 1 — Claim onchain wallet rewards
    wallet_reward_map = {
        "phantom":    "SOL",
        "keplr":      "ATOM",
        "bifrost_sgb":"SGB",
        "bifrost_flr":"FLR",
        "metamask_eth":"ETH",
    }
    for wallet_name, symbol in wallet_reward_map.items():
        wallet = get_all_wallets().get(wallet_name)
        if not wallet:
            continue
        try:
            pending = wallet.get_pending_rewards()
            if pending <= 0.0:
                continue
            activity(f"[YIELD] {wallet_name} pending rewards: {pending:.6f} {symbol}")
            result  = wallet.claim_rewards()
            if not result:
                continue
            # Route claimed rewards
            routing = REWARD_ROUTING.get(symbol, "exchange")
            _route_claimed_rewards(symbol, pending, routing, wallet)
        except Exception as e:
            activity(f"[YIELD] {wallet_name} claim error: {e}", "ERROR")

    # Step 2 — Sell exchange-held yield asset rewards
    for symbol in YIELD_ASSETS:
        _sell_exchange_rewards(symbol)

    # Step 3 — Phase out ALGO
    if "ALGO" in YIELD_PHASE_OUT:
        _maybe_phase_out_algo()


def _route_claimed_rewards(symbol: str, amount: float, routing: str, wallet):
    """Send claimed rewards to exchange or Ledger based on routing config."""
    from config      import WALLETS, PRIMARY_EXCHANGE, LARGE_MOVE_USD
    from core.logger import activity
    from core.approvals import request_approval
    from exchanges   import get_exchange
    from core.state  import SIM_PRICES
    import random

    price     = SIM_PRICES.get(symbol, 1.0) * (1 + random.uniform(-0.005, 0.005))
    value_usd = amount * price

    if routing == "ledger":
        # Get Ledger address for this asset
        ledger_addr = WALLETS["ledger"]["addresses"].get(symbol, "")
        if not ledger_addr:
            activity(f"[YIELD] No Ledger address for {symbol} — skipping route", "WARNING")
            return
        activity(f"[YIELD] Routing {amount:.6f} {symbol} → Ledger ({ledger_addr[:12]}...)")
        wallet.send(ledger_addr, amount, symbol)

    elif routing == "exchange":
        # Send to primary exchange deposit address (manual step for now)
        # TODO: fetch deposit address from exchange API
        target   = pick_weakest_vault_asset()
        exchange = get_exchange(PRIMARY_EXCHANGE)
        if not exchange:
            return
        activity(f"[YIELD] Routing {amount:.6f} {symbol} reward value → {target} on {PRIMARY_EXCHANGE}")
        buy_amount = (value_usd * 0.98) / exchange.get_price(target)
        exchange.buy(target, buy_amount, f"yield route: {symbol} rewards → {target}")
        from config import SWING_REINVEST_PCT
        lock_gains_into_vault(target, buy_amount * SWING_REINVEST_PCT)


def _sell_exchange_rewards(symbol: str):
    """Sell accumulated staking/yield rewards held on exchange."""
    from config      import LARGE_MOVE_USD, PRIMARY_EXCHANGE
    from core.state  import PORTFOLIO
    from core.logger import activity
    from core.approvals import request_approval
    from exchanges   import get_exchange

    entry      = PORTFOLIO.get(symbol, {})
    rewards    = entry.get("rewards", 0.0)
    source     = entry.get("source", PRIMARY_EXCHANGE)
    exchange   = get_exchange(source)
    if not exchange or rewards <= 0.0:
        return

    price      = exchange.get_price(symbol)
    reward_usd = rewards * price
    if reward_usd < 1.0:
        return

    if reward_usd >= LARGE_MOVE_USD:
        if not request_approval(f"Auto-sell {symbol} rewards: {rewards:.4f} ({_usd(reward_usd)})", reward_usd):
            return

    exchange.sell(symbol, rewards, f"{symbol} yield rewards → vault")
    PORTFOLIO[symbol]["rewards"] = 0.0

    target     = pick_weakest_vault_asset()
    tgt_exch   = get_exchange(PORTFOLIO.get(target, {}).get("source", PRIMARY_EXCHANGE))
    buy_amount = (reward_usd * 0.98) / tgt_exch.get_price(target)
    tgt_exch.buy(target, buy_amount, f"yield route from {symbol}")

    from config import SWING_REINVEST_PCT
    lock_gains_into_vault(target, buy_amount * SWING_REINVEST_PCT)


def _maybe_phase_out_algo():
    """Phase out ALGO position when conditions are safe."""
    from config      import PRIMARY_EXCHANGE, SWING_REINVEST_PCT
    from core.state  import PORTFOLIO
    from core.logger import activity
    from core.safety import is_safe_to_trade
    from core.approvals import request_approval
    from exchanges   import get_exchange

    if not is_safe_to_trade("ALGO"):
        return

    entry     = PORTFOLIO.get("ALGO", {})
    bal       = entry.get("balance", 0.0)
    exchange  = get_exchange(entry.get("source", PRIMARY_EXCHANGE))
    if not exchange:
        return
    total_usd = bal * exchange.get_price("ALGO")
    if total_usd < 5.0:
        return

    desc = f"Phase out ALGO: sell {bal:.2f} ALGO ({_usd(total_usd)}) → route to vault"
    activity(f"[YIELD] ALGO phase-out eligible: {_usd(total_usd)}")
    if request_approval(desc, total_usd):
        exchange.sell("ALGO", bal, "ALGO phase-out")
        target     = pick_weakest_vault_asset()
        tgt_exch   = get_exchange(PORTFOLIO.get(target, {}).get("source", PRIMARY_EXCHANGE))
        buy_amount = (total_usd * 0.98) / tgt_exch.get_price(target)
        tgt_exch.buy(target, buy_amount, f"ALGO phase-out → {target}")
        lock_gains_into_vault(target, buy_amount * SWING_REINVEST_PCT)
        PORTFOLIO["ALGO"]["balance"] = 0.0


# ============================================================
#  LAYER 4: SIDE BETS
# ============================================================

def run_side_bets():
    """Check if side-bet rotation is due. Rotate if triggered."""
    from config      import SIDE_BET_ROTATE_DAYS
    from core.state  import ACTIVE_SIDE_BETS, LAST_SIDE_BET_ROTATION, ENGINE_STATE
    from core.logger import activity
    from datetime    import datetime

    if ENGINE_STATE["paused"]:
        return

    days_since = (datetime.now() - LAST_SIDE_BET_ROTATION).days
    if days_since >= SIDE_BET_ROTATE_DAYS:
        activity(f"[SIDE BETS] Rotation due ({days_since} days since last).")
        rotate_side_bets()
    else:
        activity(f"[SIDE BETS] Next rotation in {SIDE_BET_ROTATE_DAYS - days_since} days.")


def rotate_side_bets():
    """Pick 3 new side bets, ask for approval, sell outgoing, buy incoming."""
    import random
    from config      import SIDE_BET_POOL, MAX_ACTIVE_SIDE_BETS, SIDE_BET_ROTATE_USD, PRIMARY_EXCHANGE
    from core.state  import PORTFOLIO, ACTIVE_SIDE_BETS, LAST_SIDE_BET_ROTATION
    from core.logger import activity
    from core.approvals import request_approval, telegram_send
    from exchanges   import get_exchange
    from datetime    import datetime

    # Need to modify module-level lists — use state module directly
    import core.state as state

    available = [s for s in SIDE_BET_POOL if s not in state.ACTIVE_SIDE_BETS]
    incoming  = random.sample(available, MAX_ACTIVE_SIDE_BETS)
    outgoing  = list(state.ACTIVE_SIDE_BETS)

    exchange   = get_exchange(PRIMARY_EXCHANGE)
    total_sell = sum(
        PORTFOLIO.get(s, {"balance": 0}).get("balance", 0) * exchange.get_price(s)
        for s in outgoing
    ) if exchange else 0.0

    desc = f"Side-bet rotation: OUT {outgoing} → IN {incoming}"
    if total_sell >= SIDE_BET_ROTATE_USD:
        if not request_approval(desc, total_sell):
            return
    else:
        activity(f"[SIDE BETS] Auto-rotating (below threshold): {desc}")

    for symbol in outgoing:
        bal = PORTFOLIO.get(symbol, {"balance": 0}).get("balance", 0)
        if bal > 0 and exchange:
            exchange.sell(symbol, bal, "side-bet rotation out")
            PORTFOLIO[symbol]["balance"] = 0.0
            PORTFOLIO[symbol]["active"]  = False

    per_coin = (total_sell * 0.98) / MAX_ACTIVE_SIDE_BETS if total_sell > 0 else 0
    for symbol in incoming:
        if exchange and per_coin > 0:
            amount = per_coin / exchange.get_price(symbol)
            exchange.buy(symbol, amount, "side-bet rotation in")
            PORTFOLIO[symbol] = {"balance": amount, "active": True, "source": PRIMARY_EXCHANGE}

    state.ACTIVE_SIDE_BETS       = incoming
    state.LAST_SIDE_BET_ROTATION = datetime.now()
    activity(f"[SIDE BETS] Rotation complete → {incoming}")
    telegram_send(f"🔄 Side-bet rotation complete\nNow holding: {', '.join(incoming)}")


# ── Shared helper ──
def _usd(val: float) -> str:
    return f"${val:,.2f}"
