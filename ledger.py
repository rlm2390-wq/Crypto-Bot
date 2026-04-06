"""
wallets/ledger.py — Ledger hardware wallet connector.

ALWAYS read-only. Engine NEVER signs Ledger transactions.
Reads balances via public RPC using wallet addresses from .env.
All 10 vault assets tracked here = THE VAULT.
"""

from wallets.base import BaseWallet
from core.logger  import activity


class LedgerWallet(BaseWallet):
    name      = "ledger"
    read_only = True   # ENFORCED — never changes

    def __init__(self, addresses: dict, simulation: bool = True):
        """
        addresses: dict of {symbol: address} from config.WALLETS["ledger"]["addresses"]
        """
        self.addresses  = addresses
        self.simulation = simulation

    def is_available(self) -> bool:
        return True  # Ledger is always "available" — we just read public RPC

    def get_balance(self, token: str = "ETH") -> float:
        """
        Read on-chain balance for a vault asset from public RPC.
        SIMULATION: returns from core.state.PORTFOLIO["LEDGER_<token>"]
        LIVE: queries the appropriate chain RPC with the stored address
        """
        if self.simulation:
            from core.state import PORTFOLIO
            return PORTFOLIO.get(f"LEDGER_{token}", {}).get("balance", 0.0)

        address = self.addresses.get(token, "")
        if not address:
            return 0.0

        try:
            return self._fetch_onchain_balance(token, address)
        except Exception as e:
            activity(f"[LEDGER] get_balance {token} error: {e}", "ERROR")
            return 0.0

    def _fetch_onchain_balance(self, token: str, address: str) -> float:
        """
        Dispatch to correct chain RPC based on token.
        TODO: fill in live RPC calls per chain.
        """
        from config import WALLETS
        rpc_map = {
            # EVM chains — use web3.py
            "ETH":   ("evm",    WALLETS["metamask_eth"]["rpc_url"]),
            "MATIC": ("evm",    WALLETS["metamask_matic"]["rpc_url"]),
            "LINK":  ("evm",    WALLETS["metamask_eth"]["rpc_url"]),   # ERC-20 on ETH
            "XDC":   ("evm",    WALLETS["xdc"]["rpc_url"]),
            # Solana
            "SOL":   ("solana", WALLETS["phantom"]["rpc_url"]),
            # Cosmos
            "ATOM":  ("cosmos", WALLETS["keplr"]["rpc_url"]),
            # Others — TODO: add BTC (blockcypher), XRP (xrpl), ADA (cardano-node), VET (vechain)
        }
        chain_type, rpc_url = rpc_map.get(token, (None, None))
        if not chain_type:
            activity(f"[LEDGER] No RPC handler for {token}", "WARNING")
            return 0.0

        if chain_type == "evm":
            return _evm_balance(address, rpc_url)
        elif chain_type == "solana":
            return _solana_balance(address, rpc_url)
        elif chain_type == "cosmos":
            return _cosmos_balance(address, rpc_url)
        return 0.0

    def get_all_balances(self) -> dict:
        """Return dict of {symbol: balance} for all vault assets on Ledger."""
        result = {}
        for token, address in self.addresses.items():
            if address:
                result[token] = self.get_balance(token)
        return result

    # ── Ledger is read-only — these are disabled ──

    def get_pending_rewards(self) -> float:
        return 0.0  # Ledger doesn't auto-stake in this setup

    def claim_rewards(self) -> dict:
        raise PermissionError("Ledger is read-only. Rewards are not claimed automatically.")

    def send(self, to_address: str, amount: float, token: str = "native") -> dict:
        raise PermissionError("Ledger is read-only. Manual signing required on device.")


# ── Chain-specific balance helpers ──

def _evm_balance(address: str, rpc_url: str) -> float:
    """Fetch native coin balance from any EVM chain via web3.py."""
    try:
        from web3 import Web3
        w3  = Web3(Web3.HTTPProvider(rpc_url))
        wei = w3.eth.get_balance(Web3.to_checksum_address(address))
        return float(Web3.from_wei(wei, "ether"))
    except Exception as e:
        activity(f"[LEDGER][EVM] Balance fetch error ({address[:10]}): {e}", "ERROR")
        return 0.0


def _solana_balance(address: str, rpc_url: str) -> float:
    """Fetch SOL balance via Solana JSON-RPC."""
    try:
        import requests
        resp = requests.post(rpc_url, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [address]
        }, timeout=10)
        lamports = resp.json()["result"]["value"]
        return lamports / 1e9  # lamports → SOL
    except Exception as e:
        activity(f"[LEDGER][SOL] Balance fetch error ({address[:10]}): {e}", "ERROR")
        return 0.0


def _cosmos_balance(address: str, rpc_url: str) -> float:
    """Fetch ATOM balance via Cosmos REST API."""
    try:
        import requests
        url  = f"{rpc_url}/cosmos/bank/v1beta1/balances/{address}"
        resp = requests.get(url, timeout=10)
        bals = resp.json().get("balances", [])
        for b in bals:
            if b["denom"] == "uatom":
                return int(b["amount"]) / 1e6  # uatom → ATOM
        return 0.0
    except Exception as e:
        activity(f"[LEDGER][ATOM] Balance fetch error ({address[:10]}): {e}", "ERROR")
        return 0.0
