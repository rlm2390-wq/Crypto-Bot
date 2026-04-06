"""core/safety.py — All safety gate checks. Engine pauses if any fail."""

import random
from core.logger import activity


def check_gas_fees() -> bool:
    """Check ETH gas fees. Pause if above threshold."""
    from config import SIMULATION_MODE, MAX_GAS_GWEI
    if SIMULATION_MODE:
        gwei = random.uniform(20, 120)
        if gwei > MAX_GAS_GWEI:
            activity(f"[SAFETY] High gas: {gwei:.0f} gwei (max {MAX_GAS_GWEI})", "WARNING")
            return False
        return True
    # TODO: fetch from gas oracle e.g. https://api.etherscan.io/api?module=gastracker
    return True


def check_volatility(symbol: str) -> bool:
    """Check 1h price swing. Pause if above threshold."""
    from config import SIMULATION_MODE, MAX_VOLATILITY_PCT
    if SIMULATION_MODE:
        swing = random.uniform(0.5, 20.0)
        if swing > MAX_VOLATILITY_PCT:
            activity(f"[SAFETY] High volatility {symbol}: {swing:.1f}% (max {MAX_VOLATILITY_PCT}%)", "WARNING")
            return False
        return True
    # TODO: pull 1h OHLCV from exchange and compute high-low spread
    return True


def check_liquidity(symbol: str) -> bool:
    """Check 24h volume for adequate liquidity."""
    from config import SIMULATION_MODE
    if SIMULATION_MODE:
        return True
    # TODO: check 24h volume >= MIN_LIQUIDITY_USD
    return True


def check_exchange_status() -> bool:
    """Ping exchange to confirm API is reachable."""
    from config import SIMULATION_MODE
    if SIMULATION_MODE:
        return True
    # TODO: ping primary exchange status endpoint
    return True


def is_safe_to_trade(symbol: str = "ETH") -> bool:
    """
    Master safety gate. All checks must pass.
    Engine auto-pauses if this returns False.
    """
    return all([
        check_exchange_status(),
        check_gas_fees(),
        check_volatility(symbol),
        check_liquidity(symbol),
    ])
