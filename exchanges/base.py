"""exchanges/base.py — Abstract base class for all exchange connectors."""

from abc import ABC, abstractmethod


class BaseExchange(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the exchange API is reachable."""

    @abstractmethod
    def get_balance(self, symbol: str) -> float:
        """Return the free balance for a given asset symbol."""

    @abstractmethod
    def get_price(self, symbol: str) -> float:
        """Return the current market price for a given asset symbol."""

    @abstractmethod
    def buy(self, symbol: str, amount: float, reason: str) -> dict:
        """Place a market buy order. Returns order dict."""

    @abstractmethod
    def sell(self, symbol: str, amount: float, reason: str) -> dict:
        """Place a market sell order. Returns order dict."""

    @abstractmethod
    def withdraw(self, symbol: str, amount: float, address: str, reason: str) -> dict:
        """Withdraw funds to an external address. Returns result dict."""
