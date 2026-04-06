"""exchanges/__init__.py — Exchange registry. Returns active connectors."""

from config import EXCHANGES, SIMULATION_MODE
from exchanges.coinbase       import CoinbaseExchange
from exchanges.other_exchanges import KrakenExchange, BinanceExchange, UpholdExchange, BitrueExchange

_registry: dict = {}


def get_exchange(name: str):
    """Return a cached exchange connector by name."""
    return _registry.get(name)


def get_all_exchanges() -> dict:
    return _registry


def init_exchanges():
    """Initialize all enabled exchange connectors."""
    cfg = EXCHANGES

    if cfg["coinbase"]["enabled"] or SIMULATION_MODE:
        _registry["coinbase"] = CoinbaseExchange(
            cfg["coinbase"]["api_key"],
            cfg["coinbase"]["api_secret"],
            cfg["coinbase"]["password"],
            simulation=SIMULATION_MODE,
        )

    if cfg["kraken"]["enabled"] or SIMULATION_MODE:
        _registry["kraken"] = KrakenExchange(
            cfg["kraken"]["api_key"],
            cfg["kraken"]["api_secret"],
            simulation=SIMULATION_MODE,
        )

    if cfg["binance"]["enabled"] or SIMULATION_MODE:
        _registry["binance"] = BinanceExchange(
            cfg["binance"]["api_key"],
            cfg["binance"]["api_secret"],
            simulation=SIMULATION_MODE,
        )

    if cfg["uphold"]["enabled"] or SIMULATION_MODE:
        _registry["uphold"] = UpholdExchange(
            cfg["uphold"]["api_key"],
            cfg["uphold"]["api_secret"],
            simulation=SIMULATION_MODE,
        )

    if cfg["bitrue"]["enabled"] or SIMULATION_MODE:
        _registry["bitrue"] = BitrueExchange(
            cfg["bitrue"]["api_key"],
            cfg["bitrue"]["api_secret"],
            simulation=SIMULATION_MODE,
        )

    from core.logger import activity
    activity(f"[EXCHANGES] Initialized: {list(_registry.keys())}")
