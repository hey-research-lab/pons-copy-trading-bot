from __future__ import annotations

from bot.types import BotSettings, DetectedTrade, Position, TargetWallet

WEI = 10**18


def parse_ether(value: float | str) -> int:
    return int(float(value) * WEI)


def format_ether(wei: int) -> str:
    return format(wei / WEI, "f").rstrip("0").rstrip(".") or "0"


def size_copy_buy(trade: DetectedTrade, settings: BotSettings, target: TargetWallet | None = None) -> int:
    leader = int(trade["quoteAmountWei"])
    percent = float(target.get("copyPercent") if target and target.get("copyPercent") is not None else settings["copyPercent"])
    if settings["copyMode"] == "fixed":
        raw = parse_ether(settings["fixedBuyEth"])
    else:
        raw = (leader * int(round(percent * 100))) // 10_000
    cap_eth = target.get("maxBuyEth") if target and target.get("maxBuyEth") is not None else settings["maxBuyEth"]
    cap = parse_ether(float(cap_eth))  # type: ignore[arg-type]
    return cap if raw > cap else raw


def size_copy_sell(trade: DetectedTrade, settings: BotSettings, position: Position | None) -> int:
    if not position:
        return 0
    bag = int(position.get("amount") or 0)
    if bag == 0:
        return 0
    if settings["sellMode"] == "all":
        return bag
    leader_tokens = int(trade.get("tokenAmount") or 0)
    if leader_tokens == 0:
        return bag // 2
    return bag if leader_tokens >= bag else leader_tokens


def apply_slippage(amount_out: int, slippage_bps: int) -> int:
    return (amount_out * (10_000 - slippage_bps)) // 10_000


def quote_curve_buy(quote_in: int, quote_reserve: int, token_reserve: int, fee_bps: int) -> int:
    if quote_reserve == 0 or token_reserve == 0:
        return 0
    net = (quote_in * (10_000 - fee_bps)) // 10_000
    k = quote_reserve * token_reserve
    new_quote = quote_reserve + net
    if new_quote == 0:
        return 0
    new_token = k // new_quote
    return token_reserve - new_token if token_reserve > new_token else 0


def quote_curve_sell(tokens_in: int, quote_reserve: int, token_reserve: int, fee_bps: int) -> int:
    if quote_reserve == 0 or token_reserve == 0:
        return 0
    k = quote_reserve * token_reserve
    new_token = token_reserve + tokens_in
    new_quote = k // new_token
    gross = quote_reserve - new_quote if quote_reserve > new_quote else 0
    return (gross * (10_000 - fee_bps)) // 10_000
