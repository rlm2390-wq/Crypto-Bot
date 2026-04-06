"""wallets/__init__.py — Wallet registry. Returns active connectors."""

from config import WALLETS, SIMULATION_MODE
from wallets.ledger      import LedgerWallet
from wallets.evm_wallet  import EVMWallet
from wallets.other_wallets import PhantomWallet, KeplrWallet

_registry: dict = {}


def get_wallet(name: str):
    return _registry.get(name)


def get_all_wallets() -> dict:
    return _registry


def init_wallets():
    """Initialize all enabled wallet connectors."""
    from core.logger import activity

    # Ledger — always init (read-only, no keys needed)
    _registry["ledger"] = LedgerWallet(
        addresses  = WALLETS["ledger"]["addresses"],
        simulation = SIMULATION_MODE,
    )

    # Phantom (Solana)
    if WALLETS["phantom"]["enabled"] or SIMULATION_MODE:
        _registry["phantom"] = PhantomWallet(WALLETS["phantom"], simulation=SIMULATION_MODE)

    # MetaMask — ETH
    if WALLETS["metamask_eth"]["enabled"] or SIMULATION_MODE:
        _registry["metamask_eth"] = EVMWallet(WALLETS["metamask_eth"], simulation=SIMULATION_MODE)

    # MetaMask — MATIC
    if WALLETS["metamask_matic"]["enabled"] or SIMULATION_MODE:
        _registry["metamask_matic"] = EVMWallet(WALLETS["metamask_matic"], simulation=SIMULATION_MODE)

    # MetaMask — ARB
    if WALLETS["metamask_arb"]["enabled"] or SIMULATION_MODE:
        _registry["metamask_arb"] = EVMWallet(WALLETS["metamask_arb"], simulation=SIMULATION_MODE)

    # MetaMask — OP
    if WALLETS["metamask_op"]["enabled"] or SIMULATION_MODE:
        _registry["metamask_op"] = EVMWallet(WALLETS["metamask_op"], simulation=SIMULATION_MODE)

    # Keplr (Cosmos / ATOM)
    if WALLETS["keplr"]["enabled"] or SIMULATION_MODE:
        _registry["keplr"] = KeplrWallet(WALLETS["keplr"], simulation=SIMULATION_MODE)

    # Bifrost SGB
    if WALLETS["bifrost_sgb"]["enabled"] or SIMULATION_MODE:
        _registry["bifrost_sgb"] = EVMWallet(WALLETS["bifrost_sgb"], simulation=SIMULATION_MODE)

    # Bifrost FLR
    if WALLETS["bifrost_flr"]["enabled"] or SIMULATION_MODE:
        _registry["bifrost_flr"] = EVMWallet(WALLETS["bifrost_flr"], simulation=SIMULATION_MODE)

    # XDC
    if WALLETS["xdc"]["enabled"] or SIMULATION_MODE:
        _registry["xdc"] = EVMWallet(WALLETS["xdc"], simulation=SIMULATION_MODE)

    activity(f"[WALLETS] Initialized: {list(_registry.keys())}")
