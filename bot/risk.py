from __future__ import annotations

from time import time

from web3 import Web3

from bot.chain import ADDR, POOL_ABI
from bot.sizing import format_ether, parse_ether
from bot.types import BotSettings, DetectedTrade, LaunchRecord


def check_risk(
    *,
    trade: DetectedTrade,
    launch: LaunchRecord,
    settings: BotSettings,
    copy_wei: int,
    spent_today: int,
    last_copy_at: float,
    block_number: int,
    w3: Web3,
) -> tuple[bool, str]:
    if copy_wei <= 0 and trade["side"] == "buy":
        return False, "sized to zero"

    token = trade["token"].lower()
    if any(addr.lower() == token for addr in settings.get("tokenBlacklist") or []):
        return False, "token blacklisted"

    min_leader = parse_ether(settings["minLeaderTradeEth"])
    if int(trade["quoteAmountWei"]) < min_leader:
        return False, f"leader trade below {settings['minLeaderTradeEth']} ETH"

    if (time() * 1000) - last_copy_at < settings["cooldownMs"]:
        return False, "cooldown"

    if trade["side"] == "buy":
        daily_cap = parse_ether(settings["maxDailyEth"])
        if spent_today + copy_wei > daily_cap:
            return False, f"daily cap {settings['maxDailyEth']} ETH"

    end_block = launch.get("restrictionsEndBlock")
    if settings["skipLaunchProtection"] and end_block and block_number <= int(end_block):
        return False, f"launch protection until block {end_block}"

    if launch.get("version") == 1 and launch.get("pool"):
        liq = estimate_pool_weth(w3, launch)
        min_liq = parse_ether(settings["minLiquidityEth"])
        if liq < min_liq:
            return False, f"liquidity {format_ether(liq)} ETH below {settings['minLiquidityEth']}"

    return True, ""


def estimate_pool_weth(w3: Web3, launch: LaunchRecord) -> int:
    pool = launch.get("pool")
    if not pool:
        return 0
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(pool), abi=POOL_ABI)
        slot0 = contract.functions.slot0().call()
        liquidity = int(contract.functions.liquidity().call())
        sqrt = int(slot0[0])
        if sqrt == 0 or liquidity == 0:
            return 0
        token = launch["token"]
        token_is_0 = launch.get("isToken0")
        if token_is_0 is None:
            token_is_0 = token.lower() < ADDR["weth"].lower()
        if token_is_0:
            return (liquidity * sqrt) // (2**96)
        return (liquidity * (2**96)) // sqrt
    except Exception:
        return 0
