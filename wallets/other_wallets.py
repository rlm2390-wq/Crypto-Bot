"""
wallets/phantom.py  — Solana wallet (Phantom-compatible)
wallets/keplr.py    — Cosmos wallet (Keplr-compatible)
"""

from wallets.base import BaseWallet
from core.logger  import activity


# ============================================================
#  PHANTOM — SOLANA
# ============================================================

class PhantomWallet(BaseWallet):
    name = "phantom"

    def __init__(self, wallet_cfg: dict, simulation: bool = True):
        self.address     = wallet_cfg.get("address", "")
        self.private_key = wallet_cfg.get("private_key", "")
        self.rpc_url     = wallet_cfg.get("rpc_url", "https://api.mainnet-beta.solana.com")
        self.read_only   = wallet_cfg.get("read_only", False)
        self.simulation  = simulation

    def is_available(self) -> bool:
        if self.simulation:
            return True
        try:
            import requests
            resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "id": 1, "method": "getHealth"
            }, timeout=5)
            return resp.json().get("result") == "ok"
        except Exception:
            return False

    def get_balance(self, token: str = "SOL") -> float:
        if self.simulation:
            from core.state import PORTFOLIO
            return PORTFOLIO.get("SOL", {}).get("balance", 0.0)
        if not self.address:
            return 0.0
        try:
            import requests
            resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getBalance",
                "params": [self.address]
            }, timeout=10)
            lamports = resp.json()["result"]["value"]
            return lamports / 1e9
        except Exception as e:
            activity(f"[PHANTOM] get_balance error: {e}", "ERROR")
            return 0.0

    def get_pending_rewards(self) -> float:
        """
        SOL staking rewards accrue automatically in the stake account.
        LIVE: query stake account inflation rewards via getInflationReward.
        """
        if self.simulation:
            from core.state import PORTFOLIO
            return PORTFOLIO.get("SOL", {}).get("rewards", 0.0)
        try:
            import requests
            # getInflationReward returns epoch rewards for stake accounts
            resp = requests.post(self.rpc_url, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getInflationReward",
                "params": [[self.address]]
            }, timeout=10)
            result = resp.json().get("result", [{}])
            if result and result[0]:
                return result[0].get("amount", 0) / 1e9
            return 0.0
        except Exception as e:
            activity(f"[PHANTOM] get_pending_rewards error: {e}", "ERROR")
            return 0.0

    def claim_rewards(self) -> dict:
        """
        SOL staking rewards don't require manual claiming — they auto-compound.
        This returns current reward amount for routing purposes.
        """
        rewards = self.get_pending_rewards()
        activity(f"[PHANTOM] SOL rewards auto-compound: {rewards:.6f} SOL")
        return {"tx_hash": "auto-compound", "amount": rewards, "status": "auto"}

    def send(self, to_address: str, amount: float, token: str = "SOL") -> dict:
        if self.read_only:
            raise PermissionError("Phantom wallet is read-only.")
        activity(f"[PHANTOM] SEND {amount:.6f} SOL → {to_address[:12]}...")

        if self.simulation:
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get("SOL", {"balance": 0.0})
            entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
            PORTFOLIO["SOL"] = entry
            return {"tx_hash": "sim", "amount": amount, "status": "simulated"}

        try:
            # Uses solders + solana-py for transaction signing
            from solders.keypair  import Keypair
            from solders.pubkey   import Pubkey
            from solana.rpc.api   import Client
            from solana.transaction import Transaction
            from spl.token.instructions import transfer

            import base58
            client  = Client(self.rpc_url)
            keypair = Keypair.from_bytes(base58.b58decode(self.private_key))
            # Build and send transfer transaction
            # TODO: construct full SOL transfer transaction
            activity("[PHANTOM] Live SOL transfer — TODO: complete transaction builder", "WARNING")
            return {}
        except Exception as e:
            activity(f"[PHANTOM] SEND failed: {e}", "ERROR")
            return {}


# ============================================================
#  KEPLR — COSMOS
# ============================================================

class KeplrWallet(BaseWallet):
    name = "keplr"

    def __init__(self, wallet_cfg: dict, simulation: bool = True):
        self.address     = wallet_cfg.get("address", "")
        self.private_key = wallet_cfg.get("private_key", "")
        self.rpc_url     = wallet_cfg.get("rpc_url", "https://rpc.cosmos.network")
        self.chain       = wallet_cfg.get("chain", "cosmoshub-4")
        self.read_only   = wallet_cfg.get("read_only", False)
        self.simulation  = simulation

    def is_available(self) -> bool:
        if self.simulation:
            return True
        try:
            import requests
            resp = requests.get(f"{self.rpc_url}/status", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_balance(self, token: str = "ATOM") -> float:
        if self.simulation:
            from core.state import PORTFOLIO
            return PORTFOLIO.get("ATOM", {}).get("balance", 0.0)
        if not self.address:
            return 0.0
        try:
            import requests
            url  = f"{self.rpc_url}/cosmos/bank/v1beta1/balances/{self.address}"
            resp = requests.get(url, timeout=10)
            bals = resp.json().get("balances", [])
            for b in bals:
                if b["denom"] == "uatom":
                    return int(b["amount"]) / 1e6
            return 0.0
        except Exception as e:
            activity(f"[KEPLR] get_balance error: {e}", "ERROR")
            return 0.0

    def get_pending_rewards(self) -> float:
        """Query outstanding staking delegation rewards."""
        if self.simulation:
            from core.state import PORTFOLIO
            return PORTFOLIO.get("ATOM", {}).get("rewards", 0.0)
        if not self.address:
            return 0.0
        try:
            import requests
            url  = f"{self.rpc_url}/cosmos/distribution/v1beta1/delegators/{self.address}/rewards"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            total = data.get("total", [])
            for t in total:
                if t["denom"] == "uatom":
                    return float(t["amount"]) / 1e6
            return 0.0
        except Exception as e:
            activity(f"[KEPLR] get_pending_rewards error: {e}", "ERROR")
            return 0.0

    def claim_rewards(self) -> dict:
        """Claim all outstanding delegation rewards."""
        pending = self.get_pending_rewards()
        activity(f"[KEPLR] Claiming {pending:.6f} ATOM rewards")

        if self.simulation:
            from core.state import PORTFOLIO
            entry   = PORTFOLIO.get("ATOM", {})
            claimed = entry.get("rewards", 0.0)
            entry["rewards"]  = 0.0
            entry["balance"]  = entry.get("balance", 0.0) + claimed
            PORTFOLIO["ATOM"] = entry
            return {"tx_hash": "sim", "amount": claimed, "status": "simulated"}

        try:
            # Uses cosmos-sdk tx via cosmpy or local CLI
            # TODO: build MsgWithdrawDelegatorReward transaction
            # pip install cosmpy
            activity("[KEPLR] Live reward claim — TODO: complete with cosmpy", "WARNING")
            return {}
        except Exception as e:
            activity(f"[KEPLR] claim_rewards failed: {e}", "ERROR")
            return {}

    def send(self, to_address: str, amount: float, token: str = "ATOM") -> dict:
        if self.read_only:
            raise PermissionError("Keplr wallet is read-only.")
        activity(f"[KEPLR] SEND {amount:.6f} ATOM → {to_address[:12]}...")

        if self.simulation:
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get("ATOM", {"balance": 0.0})
            entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
            PORTFOLIO["ATOM"] = entry
            return {"tx_hash": "sim", "amount": amount, "status": "simulated"}

        try:
            # TODO: build MsgSend transaction with cosmpy
            activity("[KEPLR] Live ATOM send — TODO: complete with cosmpy", "WARNING")
            return {}
        except Exception as e:
            activity(f"[KEPLR] SEND failed: {e}", "ERROR")
            return {}
