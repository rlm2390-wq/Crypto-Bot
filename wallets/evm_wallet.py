"""
wallets/evm_wallet.py — Generic EVM wallet connector.
Covers: MetaMask (ETH, MATIC, ARB, OP), Bifrost (SGB, FLR), XDC wallet.
All EVM-compatible chains use the same interface — just different RPC + chain_id.
"""

from wallets.base import BaseWallet
from core.logger  import activity


class EVMWallet(BaseWallet):

    def __init__(self, wallet_cfg: dict, simulation: bool = True):
        """
        wallet_cfg: entry from config.WALLETS, e.g. WALLETS["bifrost_sgb"]
        Fields: name, chain, chain_id, address, private_key, rpc_url, native_token
        """
        self.name         = wallet_cfg.get("chain", "evm")
        self.chain        = wallet_cfg.get("chain", "ethereum")
        self.chain_id     = wallet_cfg.get("chain_id", 1)
        self.address      = wallet_cfg.get("address", "")
        self.private_key  = wallet_cfg.get("private_key", "")
        self.rpc_url      = wallet_cfg.get("rpc_url", "")
        self.native_token = wallet_cfg.get("native_token", "ETH")
        self.read_only    = wallet_cfg.get("read_only", False)
        self.simulation   = simulation
        self._w3          = None

        if not simulation and self.rpc_url:
            self._init_web3()

    def _init_web3(self):
        try:
            from web3 import Web3
            self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self._w3.is_connected():
                activity(f"[{self.name.upper()}] Web3 connected. Chain ID: {self.chain_id}")
            else:
                activity(f"[{self.name.upper()}] Web3 NOT connected to {self.rpc_url}", "WARNING")
        except Exception as e:
            activity(f"[{self.name.upper()}] Web3 init failed: {e}", "ERROR")

    def is_available(self) -> bool:
        if self.simulation:
            return True
        return self._w3 is not None and self._w3.is_connected()

    def get_balance(self, token: str = "native") -> float:
        """Return native coin balance (ETH/MATIC/SGB/FLR/XDC etc.)"""
        if self.simulation:
            from core.state import PORTFOLIO, SIM_PRICES
            sym = self.native_token
            entry = PORTFOLIO.get(sym, {})
            return entry.get("balance", 0.0)

        if not self.address:
            return 0.0
        try:
            from web3 import Web3
            wei = self._w3.eth.get_balance(Web3.to_checksum_address(self.address))
            return float(Web3.from_wei(wei, "ether"))
        except Exception as e:
            activity(f"[{self.name.upper()}] get_balance error: {e}", "ERROR")
            return 0.0

    def get_pending_rewards(self) -> float:
        """
        For SGB/FLR: Flare/Songbird FTSO delegation rewards.
        For ETH: validator/staking rewards.
        LIVE: query chain-specific rewards contract.
        """
        if self.simulation:
            from core.state import PORTFOLIO
            sym = self.native_token
            return PORTFOLIO.get(sym, {}).get("rewards", 0.0)

        # SGB / FLR — FTSO delegation rewards contract
        if self.native_token in ("SGB", "FLR"):
            return self._get_ftso_rewards()

        # ETH staking rewards — TODO: query beacon chain or liquid staking protocol
        return 0.0

    def _get_ftso_rewards(self) -> float:
        """
        Query unclaimed FTSO delegation rewards for SGB or FLR.
        Uses the FtsoRewardManager contract on Songbird/Flare.
        """
        try:
            from web3 import Web3
            # FtsoRewardManager ABI (minimal — only getStateOfRewards)
            abi = [{
                "inputs": [
                    {"name": "_beneficiary", "type": "address"},
                    {"name": "_rewardEpoch",  "type": "uint256"}
                ],
                "name": "getStateOfRewards",
                "outputs": [
                    {"name": "_dataProviders",       "type": "address[]"},
                    {"name": "_rewardAmounts",        "type": "uint256[]"},
                    {"name": "_claimed",              "type": "bool[]"},
                    {"name": "_claimable",            "type": "bool[]"},
                ],
                "stateMutability": "view",
                "type": "function",
            }]
            # Contract addresses
            contracts = {
                "SGB": "0xc5738334b972745067fFa666040fdeADc66Cb925",
                "FLR": "0xc5738334b972745067fFa666040fdeADc66Cb925",  # TODO: confirm FLR address
            }
            addr    = contracts.get(self.native_token)
            if not addr:
                return 0.0
            contract = self._w3.eth.contract(
                address=Web3.to_checksum_address(addr), abi=abi
            )
            # Get current epoch - 1 (latest claimable)
            epoch    = self._w3.eth.get_block("latest")["number"] // 3600
            _, amounts, _, claimable = contract.functions.getStateOfRewards(
                Web3.to_checksum_address(self.address), epoch
            ).call()
            total = sum(a for a, c in zip(amounts, claimable) if c)
            return float(Web3.from_wei(total, "ether"))
        except Exception as e:
            activity(f"[{self.name.upper()}] FTSO rewards query failed: {e}", "WARNING")
            return 0.0

    def claim_rewards(self) -> dict:
        """Claim FTSO delegation rewards for SGB/FLR."""
        if self.read_only:
            raise PermissionError(f"{self.name} is read-only.")

        pending = self.get_pending_rewards()
        sym     = self.native_token
        activity(f"[{self.name.upper()}] Claiming {pending:.4f} {sym} rewards")

        if self.simulation:
            from core.state import PORTFOLIO
            entry   = PORTFOLIO.get(sym, {})
            claimed = entry.get("rewards", 0.0)
            entry["rewards"]  = 0.0
            entry["balance"]  = entry.get("balance", 0.0) + claimed
            PORTFOLIO[sym]    = entry
            return {"tx_hash": "sim", "amount": claimed, "status": "simulated"}

        if self.native_token in ("SGB", "FLR"):
            return self._claim_ftso_rewards()

        return {}

    def _claim_ftso_rewards(self) -> dict:
        """Submit claim transaction to FtsoRewardManager."""
        try:
            from web3 import Web3
            abi = [{
                "inputs": [
                    {"name": "_rewardEpochs", "type": "uint256[]"},
                    {"name": "_feePercentageBIPS", "type": "uint256"},
                    {"name": "_recipient", "type": "address"},
                ],
                "name": "claimReward",
                "outputs": [{"name": "_rewardAmount", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function",
            }]
            contracts = {
                "SGB": "0xc5738334b972745067fFa666040fdeADc66Cb925",
                "FLR": "0xc5738334b972745067fFa666040fdeADc66Cb925",
            }
            addr     = contracts.get(self.native_token)
            contract = self._w3.eth.contract(
                address=Web3.to_checksum_address(addr), abi=abi
            )
            epoch    = self._w3.eth.get_block("latest")["number"] // 3600
            acct     = self._w3.eth.account.from_key(self.private_key)
            tx       = contract.functions.claimReward(
                [epoch - 1], 0, Web3.to_checksum_address(self.address)
            ).build_transaction({
                "from":     acct.address,
                "nonce":    self._w3.eth.get_transaction_count(acct.address),
                "gas":      200_000,
                "chainId":  self.chain_id,
            })
            signed   = acct.sign_transaction(tx)
            tx_hash  = self._w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt  = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            activity(f"[{self.name.upper()}] Rewards claimed. TX: {tx_hash.hex()}")
            return {"tx_hash": tx_hash.hex(), "status": receipt.status}
        except Exception as e:
            activity(f"[{self.name.upper()}] Claim rewards failed: {e}", "ERROR")
            return {}

    def send(self, to_address: str, amount: float, token: str = "native") -> dict:
        """Send native coin to another address."""
        if self.read_only:
            raise PermissionError(f"{self.name} is read-only.")

        sym = self.native_token
        activity(f"[{self.name.upper()}] SEND {amount:.6f} {sym} → {to_address[:12]}...")

        if self.simulation:
            from core.state import PORTFOLIO
            entry = PORTFOLIO.get(sym, {"balance": 0.0})
            entry["balance"] = max(0.0, entry.get("balance", 0.0) - amount)
            PORTFOLIO[sym]   = entry
            return {"tx_hash": "sim", "amount": amount, "status": "simulated"}

        try:
            from web3 import Web3
            acct   = self._w3.eth.account.from_key(self.private_key)
            value  = Web3.to_wei(amount, "ether")
            nonce  = self._w3.eth.get_transaction_count(acct.address)
            gas_p  = self._w3.eth.gas_price
            tx     = {
                "to":       Web3.to_checksum_address(to_address),
                "value":    value,
                "gas":      21_000,
                "gasPrice": gas_p,
                "nonce":    nonce,
                "chainId":  self.chain_id,
            }
            signed  = acct.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            activity(f"[{self.name.upper()}] SEND complete. TX: {tx_hash.hex()}")
            return {"tx_hash": tx_hash.hex(), "amount": amount, "status": receipt.status}
        except Exception as e:
            activity(f"[{self.name.upper()}] SEND failed: {e}", "ERROR")
            return {}
