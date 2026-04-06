"""exchanges/coinbase.py — Coinbase Advanced Trade connector via ccxt."""

from exchanges.base import BaseExchange
from core.logger    import activity


class CoinbaseExchange(BaseExchange):
    name = "coinbase"

    def __init__(self, api_key: str, api_secret: str, password: str = "", simulation: bool = True):
        self.simulation = simulation
        self.api_key    = api_key
        self.api_secret = api_secret
        self.password   = password
        self._client    = None
        if not simulation and api_key:
            self._init_client()

    def _init_client(self):
        try:
            import ccxt
            self._client = ccxt.coinbase({
                "apiKey":    self.api_key,
                "secret":    self.api_secret,
                "password":  self.password,
            })
            activity("[COINBASE] Client initialized.")
        except Exception as e:
            activity(f"[COINBASE] Init failed: {e}", "ERROR")

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
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get(symbol, {})
            if entry.get("source") == "coinbase":
                return entry.get("balance", 0.0)
            return 0.0
        try:
            balances = self._client.fetch_balance()
            return float(balances.get("free", {}).get(symbol, 0.0))
        except Exception as e:
            activity(f"[COINBASE] get_balance {symbol} error: {e}", "ERROR")
            return 0.0

    def get_price(self, symbol: str) -> float:
        if self.simulation:
            import random
            from core.state import SIM_PRICES
            base = SIM_PRICES.get(symbol, 1.0)
            return round(base * (1 + random.uniform(-0.005, 0.005)), 8)
        try:
            ticker = self._client.fetch_ticker(f"{symbol}/USDT")
            return float(ticker["last"])
        except Exception as e:
            activity(f"[COINBASE] get_price {symbol} error: {e}", "ERROR")
            return 0.0

    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[SIM][COINBASE] BUY {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get(symbol, {"balance": 0.0})
            entry["balance"] = entry.get("balance", 0.0) + amount
            PORTFOLIO[symbol] = entry
            return {"id": "sim", "symbol": symbol, "amount": amount, "price": price, "status": "simulated"}
        try:
            order = self._client.create_market_buy_order(f"{symbol}/USDT", amount)
            activity(f"[COINBASE] BUY executed: {order}")
            return order
        except Exception as e:
            activity(f"[COINBASE] BUY {symbol} failed: {e}", "ERROR")
            return {}

    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        price = self.get_price(symbol)
        activity(f"[SIM][COINBASE] SELL {amount:.6f} {symbol} @ ${price:,.4f} | {reason}")
        if self.simulation:
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get(symbol, {"balance": 0.0})
            entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
            PORTFOLIO[symbol] = entry
            return {"id": "sim", "symbol": symbol, "amount": amount, "price": price, "status": "simulated"}
        try:
            order = self._client.create_market_sell_order(f"{symbol}/USDT", amount)
            activity(f"[COINBASE] SELL executed: {order}")
            return order
        except Exception as e:
            activity(f"[COINBASE] SELL {symbol} failed: {e}", "ERROR")
            return {}

    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        activity(f"[SIM][COINBASE] WITHDRAW {amount:.6f} {symbol} → {address[:12]}... | {reason}")
        if self.simulation:
            return {"id": "sim", "status": "simulated"}
        try:
            result = self._client.withdraw(symbol, amount, address)
            activity(f"[COINBASE] WITHDRAW submitted: {result}")
            return result
        except Exception as e:
            activity(f"[COINBASE] WITHDRAW {symbol} failed: {e}", "ERROR")
            return {}
