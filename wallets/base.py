"""wallets/base.py — Abstract base class for all wallet connectors."""

from abc import ABC, abstractmethod


class BaseWallet(ABC):
    name: str      = "base"
    read_only: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the wallet/RPC is reachable."""

    @abstractmethod
    def get_balance(self, token: str = "native") -> float:
        """Return the balance for the given token."""

    @abstractmethod
    def get_pending_rewards(self) -> float:
        """Return unclaimed/pending reward amount."""

    @abstractmethod
    def claim_rewards(self) -> dict:
        """Claim pending rewards. Returns result dict."""

    @abstractmethod
    def send(self, to_address: str, amount: float, token: str = "native") -> dict:
        """Send tokens to an external address. Returns result dict."""
