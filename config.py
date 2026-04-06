"""
config.py — Master configuration for Rizz Engine.
Edit this file to change asset rules, reward routing, and milestones.
All values can be overridden by environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  ENGINE SETTINGS
# ============================================================

SIMULATION_MODE      = os.environ.get("SIMULATION_MODE", "true").lower() == "true"
LOOP_INTERVAL        = int(os.environ.get("LOOP_INTERVAL", 60))
APPROVAL_TIMEOUT     = int(os.environ.get("APPROVAL_TIMEOUT", 300))
LARGE_MOVE_USD       = float(os.environ.get("LARGE_MOVE_USD", 100.0))
SIDE_BET_ROTATE_USD  = float(os.environ.get("SIDE_BET_ROTATE_USD", 50.0))
SIDE_BET_ROTATE_DAYS = int(os.environ.get("SIDE_BET_ROTATE_DAYS", 30))
MAX_ACTIVE_SIDE_BETS = 3
SWING_REINVEST_PCT   = 0.50
SWING_TRADE_SIZE_PCT = 0.10
PORT                 = int(os.environ.get("PORT", 5000))
DASHBOARD_SECRET     = os.environ.get("DASHBOARD_SECRET", "changeme")

# ============================================================
#  TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ============================================================
#  SAFETY THRESHOLDS
# ============================================================

MAX_GAS_GWEI       = float(os.environ.get("MAX_GAS_GWEI", 80))
MAX_VOLATILITY_PCT = float(os.environ.get("MAX_VOLATILITY_PCT", 15.0))
MIN_LIQUIDITY_USD  = float(os.environ.get("MIN_LIQUIDITY_USD", 50_000))

# ============================================================
#  EXCHANGE CREDENTIALS
# ============================================================

EXCHANGES = {
    "coinbase": {
        "api_key":    os.environ.get("COINBASE_API_KEY", ""),
        "api_secret": os.environ.get("COINBASE_API_SECRET", ""),
        "password":   os.environ.get("COINBASE_PASSPHRASE", ""),
        "enabled":    bool(os.environ.get("COINBASE_API_KEY")),
    },
    "kraken": {
        "api_key":    os.environ.get("KRAKEN_API_KEY", ""),
        "api_secret": os.environ.get("KRAKEN_API_SECRET", ""),
        "enabled":    bool(os.environ.get("KRAKEN_API_KEY")),
    },
    "binance": {
        "api_key":    os.environ.get("BINANCE_API_KEY", ""),
        "api_secret": os.environ.get("BINANCE_API_SECRET", ""),
        "enabled":    bool(os.environ.get("BINANCE_API_KEY")),
    },
    "uphold": {
        "api_key":    os.environ.get("UPHOLD_API_KEY", ""),
        "api_secret": os.environ.get("UPHOLD_API_SECRET", ""),
        "enabled":    bool(os.environ.get("UPHOLD_API_KEY")),
    },
    "bitrue": {
        "api_key":    os.environ.get("BITRUE_API_KEY", ""),
        "api_secret": os.environ.get("BITRUE_API_SECRET", ""),
        "enabled":    bool(os.environ.get("BITRUE_API_KEY")),
    },
}

# ============================================================
#  WALLET CREDENTIALS
# ============================================================

WALLETS = {
    "ledger": {
        "type":    "ledger",
        "enabled": bool(os.environ.get("LEDGER_ETH_ADDRESS")),
        "addresses": {
            "ETH":   os.environ.get("LEDGER_ETH_ADDRESS", ""),
            "BTC":   os.environ.get("LEDGER_BTC_ADDRESS", ""),
            "SOL":   os.environ.get("LEDGER_SOL_ADDRESS", ""),
            "XRP":   os.environ.get("LEDGER_XRP_ADDRESS", ""),
            "ADA":   os.environ.get("LEDGER_ADA_ADDRESS", ""),
            "ATOM":  os.environ.get("LEDGER_ATOM_ADDRESS", ""),
            "MATIC": os.environ.get("LEDGER_MATIC_ADDRESS", ""),
            "LINK":  os.environ.get("LEDGER_LINK_ADDRESS", ""),
            "VET":   os.environ.get("LEDGER_VET_ADDRESS", ""),
            "XDC":   os.environ.get("LEDGER_XDC_ADDRESS", ""),
        },
        # Ledger is ALWAYS read-only — engine never signs Ledger transactions
        "read_only": True,
    },
    "phantom": {
        "type":        "solana",
        "enabled":     bool(os.environ.get("PHANTOM_SOL_ADDRESS")),
        "address":     os.environ.get("PHANTOM_SOL_ADDRESS", ""),
        "private_key": os.environ.get("PHANTOM_SOL_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("SOL_RPC_URL", "https://api.mainnet-beta.solana.com"),
        "read_only":   False,
    },
    "metamask_eth": {
        "type":        "evm",
        "chain":       "ethereum",
        "chain_id":    1,
        "enabled":     bool(os.environ.get("METAMASK_ETH_ADDRESS")),
        "address":     os.environ.get("METAMASK_ETH_ADDRESS", ""),
        "private_key": os.environ.get("METAMASK_ETH_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("ETH_RPC_URL", "https://mainnet.infura.io/v3/YOUR_KEY"),
        "read_only":   False,
    },
    "metamask_matic": {
        "type":        "evm",
        "chain":       "polygon",
        "chain_id":    137,
        "enabled":     bool(os.environ.get("METAMASK_MATIC_ADDRESS")),
        "address":     os.environ.get("METAMASK_MATIC_ADDRESS", ""),
        "private_key": os.environ.get("METAMASK_MATIC_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("MATIC_RPC_URL", "https://polygon-rpc.com"),
        "read_only":   False,
    },
    "metamask_arb": {
        "type":        "evm",
        "chain":       "arbitrum",
        "chain_id":    42161,
        "enabled":     bool(os.environ.get("METAMASK_ARB_ADDRESS")),
        "address":     os.environ.get("METAMASK_ARB_ADDRESS", ""),
        "private_key": os.environ.get("METAMASK_ARB_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("ARB_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "read_only":   False,
    },
    "metamask_op": {
        "type":        "evm",
        "chain":       "optimism",
        "chain_id":    10,
        "enabled":     bool(os.environ.get("METAMASK_OP_ADDRESS")),
        "address":     os.environ.get("METAMASK_OP_ADDRESS", ""),
        "private_key": os.environ.get("METAMASK_OP_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("OP_RPC_URL", "https://mainnet.optimism.io"),
        "read_only":   False,
    },
    "keplr": {
        "type":        "cosmos",
        "chain":       "cosmoshub-4",
        "enabled":     bool(os.environ.get("KEPLR_ATOM_ADDRESS")),
        "address":     os.environ.get("KEPLR_ATOM_ADDRESS", ""),
        "private_key": os.environ.get("KEPLR_ATOM_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("ATOM_RPC_URL", "https://rpc.cosmos.network"),
        "read_only":   False,
    },
    "bifrost_sgb": {
        "type":        "evm",
        "chain":       "songbird",
        "chain_id":    19,
        "enabled":     bool(os.environ.get("BIFROST_SGB_ADDRESS")),
        "address":     os.environ.get("BIFROST_SGB_ADDRESS", ""),
        "private_key": os.environ.get("BIFROST_SGB_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("SGB_RPC_URL", "https://songbird-api.flare.network/ext/C/rpc"),
        "native_token": "SGB",
        "read_only":   False,
    },
    "bifrost_flr": {
        "type":        "evm",
        "chain":       "flare",
        "chain_id":    14,
        "enabled":     bool(os.environ.get("BIFROST_FLR_ADDRESS")),
        "address":     os.environ.get("BIFROST_FLR_ADDRESS", ""),
        "private_key": os.environ.get("BIFROST_FLR_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("FLR_RPC_URL", "https://flare-api.flare.network/ext/C/rpc"),
        "native_token": "FLR",
        "read_only":   False,
    },
    "xdc": {
        "type":        "evm",
        "chain":       "xdc",
        "chain_id":    50,
        "enabled":     bool(os.environ.get("XDC_ADDRESS")),
        "address":     os.environ.get("XDC_ADDRESS", ""),
        "private_key": os.environ.get("XDC_PRIVATE_KEY", ""),
        "rpc_url":     os.environ.get("XDC_RPC_URL", "https://rpc.xinfin.network"),
        "native_token": "XDC",
        "read_only":   False,
    },
}

# ============================================================
#  ASSET DEFINITIONS
# ============================================================

VAULT_ASSETS = ["BTC","ETH","SOL","XRP","VET","LINK","XDC","ADA","ATOM","MATIC"]
YIELD_ASSETS = ["HBAR","DOT","ALGO","NEAR","EGLD","SGB","FLR"]
YIELD_PHASE_OUT = ["ALGO"]

SIDE_BET_POOL = [
    "SHIB","SUI","BONK","DOGE","PEPE",
    "JUP","FET","AGIX","RNDR","APT","OP","ARB"
]

# ============================================================
#  MILESTONE LADDERS
# ============================================================

MILESTONES = {
    "BTC":   [0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
    "ETH":   [0.1,  0.5,  1.0, 2.5,  5.0, 10.0],
    "SOL":   [1.0,  5.0,  10,  25,   50,  100],
    "XRP":   [100,  500,  1000,2500, 5000,10000],
    "VET":   [1000, 5000, 10000,25000,50000,100000],
    "LINK":  [5,    25,   50,  100,  250,  500],
    "XDC":   [1000, 5000, 10000,25000,50000,100000],
    "ADA":   [100,  500,  1000,2500, 5000, 10000],
    "ATOM":  [5,    25,   50,  100,  250,  500],
    "MATIC": [100,  500,  1000,2500, 5000, 10000],
}

# ============================================================
#  REWARD ROUTING
#  Per-asset: where do claimed rewards go?
#  "exchange" = route to your primary exchange (Coinbase)
#  "ledger"   = route directly to Ledger vault
#  Edit this to change routing per asset.
# ============================================================

REWARD_ROUTING = {
    # Yield assets
    "HBAR":  "exchange",   # Claim → Coinbase
    "DOT":   "exchange",   # Claim → Coinbase
    "ALGO":  "exchange",   # Claim → Coinbase (phase-out)
    "NEAR":  "exchange",   # Claim → Coinbase
    "EGLD":  "exchange",   # Claim → Coinbase
    "SGB":   "exchange",   # Bifrost SGB staking → Coinbase
    "FLR":   "exchange",   # Bifrost FLR staking → Coinbase
    # Vault assets (staking rewards if any)
    "ETH":   "ledger",     # ETH staking rewards → Ledger
    "SOL":   "exchange",   # SOL staking → Coinbase swing stack
    "ATOM":  "ledger",     # ATOM staking → Ledger
    "MATIC": "exchange",   # MATIC staking → Coinbase
    "ADA":   "ledger",     # ADA staking → Ledger
}

# Which exchange receives routed rewards (when routing = "exchange")
PRIMARY_EXCHANGE = "coinbase"
