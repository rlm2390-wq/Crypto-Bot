"""
exchanges/kraken.py    — Kraken connector
exchanges/binance.py   — Binance connector
exchanges/uphold.py    — Uphold connector
exchanges/bitrue.py    — Bitrue connector

All follow the same pattern as coinbase.py.
In SIMULATION_MODE they read/write from core.state.PORTFOLIO filtered by source.
In LIVE mode they use ccxt (or exchange-specific SDK for Uphold/Bitrue).
"""

import random
from exchanges.base  import BaseExchange
from core.logger     import activity
from core.state      import PORTFOLIO, SIM_PRICES


# ============================================================
#  SHARED HELPERS
# ============================================================

def _sim_price(symbol: str) -> float:
    base = SIM_PRICES.get(symbol, 1.0)
    return round(base * (1 + random.uniform(-0.005, 0.005)), 8)

def _sim_balance(symbol: str, source: str) -> float:
    entry = PORTFOLIO.get(symbol, {})
    if entry.get("source") == source:
        return entry.get("balance", 0.0)
    return 0.0

def _sim_buy(symbol: str, amount: float, price: float):
    entry = PORTFOLIO.get(symbol, {"balance": 0.0})
    entry["balance"] = entry.get("balance", 0.0) + amount
    PORTFOLIO[symbol] = entry

def _sim_sell(symbol: str, amount: float):
    entry = PORTFOLIO.get(symbol, {"balance": 0.0})
    entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
    PORTFOLIO[symbol] = entry


# ============================================================
#  KRAKEN
# ============================================================

class KrakenExchange(BaseExchange):
    name = "kraken"

    def __init__(self, api_key: str, api_secret: str, simulation: bool = True):
        self.simulation = simulation
        self.api_key    = api_key
        self.api_secret = api_secret
        self._client    = None
        if not simulation and api_key:
            self._init_client()

    def _init_client(self):
        try:
            import ccxt
            self._client = ccxt.kraken({"apiKey": self.api_key, "secret": self.api_secret})
            activity("[KRAKEN] Client initialized.")
        except Exception as e:
            activity(f"[KRAKEN] Init failed: {e}", "ERROR")

    def is_available(self) -> bool:
        if self.simulation:
            return True
        try:
            self._client.fetch_status()
            return True
        except Exception:
            return False

    def get_balance(self, symbol: str) -> float:
        if self.simulation:
            return _sim_balance(symbol, "kraken")
        try:
            b = self._client.fetch_balance()
            return float(b.get("free", {}).get(symbol, 0.0))
        except Exception as e:
            activity(f"[KRAKEN] get_balance {symbol}: {e}", "ERROR")
            return 0.0

    def get_price(self, symbol: str) -> float:
        if self.simulation:
            return _sim_price(symbol)
        try:
            t = self._client.fetch_ticker(f"{symbol}/USDT")
            return float(t["last"])
        except Exception as e:
            activity(f"[KRAKEN] get_price {symbol}: {e}", "ERROR")
            return 0.0

    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}KRAKEN] BUY {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_buy(symbol, amount, price)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_buy_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[KRAKEN] BUY {symbol} failed: {e}", "ERROR")
            return {}

    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}KRAKEN] SELL {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_sell(symbol, amount)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_sell_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[KRAKEN] SELL {symbol} failed: {e}", "ERROR")
            return {}

    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        activity(f"[{'SIM ' if self.simulation else ''}KRAKEN] WITHDRAW {amount:.6f} {symbol} → {address[:12]}... | {reason}")
        if self.simulation:
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.withdraw(symbol, amount, address)
        except Exception as e:
            activity(f"[KRAKEN] WITHDRAW {symbol} failed: {e}", "ERROR")
            return {}


# ============================================================
#  BINANCE
# ============================================================

class BinanceExchange(BaseExchange):
    name = "binance"

    def __init__(self, api_key: str, api_secret: str, simulation: bool = True):
        self.simulation = simulation
        self.api_key    = api_key
        self.api_secret = api_secret
        self._client    = None
        if not simulation and api_key:
            self._init_client()

    def _init_client(self):
        try:
            import ccxt
            self._client = ccxt.binance({"apiKey": self.api_key, "secret": self.api_secret})
            activity("[BINANCE] Client initialized.")
        except Exception as e:
            activity(f"[BINANCE] Init failed: {e}", "ERROR")

    def is_available(self) -> bool:
        if self.simulation:
            return True
        try:
            self._client.fetch_status()
            return True
        except Exception:
            return False

    def get_balance(self, symbol: str) -> float:
        if self.simulation:
            return _sim_balance(symbol, "binance")
        try:
            b = self._client.fetch_balance()
            return float(b.get("free", {}).get(symbol, 0.0))
        except Exception as e:
            activity(f"[BINANCE] get_balance {symbol}: {e}", "ERROR")
            return 0.0

    def get_price(self, symbol: str) -> float:
        if self.simulation:
            return _sim_price(symbol)
        try:
            t = self._client.fetch_ticker(f"{symbol}/USDT")
            return float(t["last"])
        except Exception as e:
            activity(f"[BINANCE] get_price {symbol}: {e}", "ERROR")
            return 0.0

    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}BINANCE] BUY {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_buy(symbol, amount, price)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_buy_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[BINANCE] BUY {symbol} failed: {e}", "ERROR")
            return {}

    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}BINANCE] SELL {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_sell(symbol, amount)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_sell_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[BINANCE] SELL {symbol} failed: {e}", "ERROR")
            return {}

    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        activity(f"[{'SIM ' if self.simulation else ''}BINANCE] WITHDRAW {amount:.6f} {symbol} → {address[:12]}... | {reason}")
        if self.simulation:
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.withdraw(symbol, amount, address)
        except Exception as e:
            activity(f"[BINANCE] WITHDRAW {symbol} failed: {e}", "ERROR")
            return {}


# ============================================================
#  UPHOLD
# ============================================================

class UpholdExchange(BaseExchange):
    """
    Uphold connector.
    ccxt has partial Uphold support. For full support, use the Uphold SDK:
    pip install uphold
    Wired as ccxt for now; swap to uphold SDK if needed.
    """
    name = "uphold"

    def __init__(self, api_key: str, api_secret: str, simulation: bool = True):
        self.simulation = simulation
        self.api_key    = api_key
        self.api_secret = api_secret
        self._client    = None
        if not simulation and api_key:
            self._init_client()

    def _init_client(self):
        try:
            import ccxt
            # Uphold uses OAuth — api_key = client_id, api_secret = client_secret
            self._client = ccxt.uphold({"apiKey": self.api_key, "secret": self.api_secret})
            activity("[UPHOLD] Client initialized.")
        except Exception as e:
            activity(f"[UPHOLD] Init failed: {e}", "ERROR")

    def is_available(self) -> bool:
        return True if self.simulation else bool(self._client)

    def get_balance(self, symbol: str) -> float:
        if self.simulation:
            return _sim_balance(symbol, "uphold")
        try:
            b = self._client.fetch_balance()
            return float(b.get("free", {}).get(symbol, 0.0))
        except Exception as e:
            activity(f"[UPHOLD] get_balance {symbol}: {e}", "ERROR")
            return 0.0

    def get_price(self, symbol: str) -> float:
        if self.simulation:
            return _sim_price(symbol)
        try:
            t = self._client.fetch_ticker(f"{symbol}/USD")
            return float(t["last"])
        except Exception as e:
            activity(f"[UPHOLD] get_price {symbol}: {e}", "ERROR")
            return 0.0

    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}UPHOLD] BUY {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_buy(symbol, amount, price)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_buy_order(f"{symbol}/USD", amount)
        except Exception as e:
            activity(f"[UPHOLD] BUY {symbol} failed: {e}", "ERROR")
            return {}

    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}UPHOLD] SELL {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_sell(symbol, amount)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_sell_order(f"{symbol}/USD", amount)
        except Exception as e:
            activity(f"[UPHOLD] SELL {symbol} failed: {e}", "ERROR")
            return {}

    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        activity(f"[{'SIM ' if self.simulation else ''}UPHOLD] WITHDRAW {amount:.6f} {symbol} → {address[:12]}... | {reason}")
        if self.simulation:
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.withdraw(symbol, amount, address)
        except Exception as e:
            activity(f"[UPHOLD] WITHDRAW {symbol} failed: {e}", "ERROR")
            return {}


# ============================================================
#  BITRUE
# ============================================================

class BitrueExchange(BaseExchange):
    """
    Bitrue connector via ccxt.
    Bitrue is well-known for XDC and VET pairs.
    """
    name = "bitrue"

    def __init__(self, api_key: str, api_secret: str, simulation: bool = True):
        self.simulation = simulation
        self.api_key    = api_key
        self.api_secret = api_secret
        self._client    = None
        if not simulation and api_key:
            self._init_client()

    def _init_client(self):
        try:
            import ccxt
            self._client = ccxt.bitrue({"apiKey": self.api_key, "secret": self.api_secret})
            activity("[BITRUE] Client initialized.")
        except Exception as e:
            activity(f"[BITRUE] Init failed: {e}", "ERROR")

    def is_available(self) -> bool:
        return True if self.simulation else bool(self._client)

    def get_balance(self, symbol: str) -> float:
        if self.simulation:
            return _sim_balance(symbol, "bitrue")
        try:
            b = self._client.fetch_balance()
            return float(b.get("free", {}).get(symbol, 0.0))
        except Exception as e:
            activity(f"[BITRUE] get_balance {symbol}: {e}", "ERROR")
            return 0.0

    def get_price(self, symbol: str) -> float:
        if self.simulation:
            return _sim_price(symbol)
        try:
            t = self._client.fetch_ticker(f"{symbol}/USDT")
            return float(t["last"])
        except Exception as e:
            activity(f"[BITRUE] get_price {symbol}: {e}", "ERROR")
            return 0.0

    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}BITRUE] BUY {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_buy(symbol, amount, price)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_buy_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[BITRUE] BUY {symbol} failed: {e}", "ERROR")
            return {}

    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[{'SIM ' if self.simulation else ''}BITRUE] SELL {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            _sim_sell(symbol, amount)
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.create_market_sell_order(f"{symbol}/USDT", amount)
        except Exception as e:
            activity(f"[BITRUE] SELL {symbol} failed: {e}", "ERROR")
            return {}

    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        activity(f"[{'SIM ' if self.simulation else ''}BITRUE] WITHDRAW {amount:.6f} {symbol} → {address[:12]}... | {reason}")
        if self.simulation:
            return {"id": "sim", "status": "simulated"}
        try:
            return self._client.withdraw(symbol, amount, address)
        except Exception as e:
            activity(f"[BITRUE] WITHDRAW {symbol} failed: {e}", "ERROR")
            return {}
