from bot.sizing import apply_slippage, quote_curve_buy, quote_curve_sell, size_copy_buy, size_copy_sell
from bot.types import BotSettings


def _settings(**overrides) -> BotSettings:
    base: BotSettings = {
        "dryRun": True,
        "running": True,
        "copyMode": "percent",
        "copyPercent": 10,
        "fixedBuyEth": 0.02,
        "sellMode": "mirror",
        "slippageBps": 150,
        "maxBuyEth": 0.05,
        "maxDailyEth": 0.25,
        "minLeaderTradeEth": 0.005,
        "minLiquidityEth": 0.3,
        "maxPriceImpactBps": 800,
        "skipLaunchProtection": True,
        "cooldownMs": 4000,
        "tokenBlacklist": [],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_percent_copy_is_capped() -> None:
    trade = {"quoteAmountWei": str(10**18)}
    sized = size_copy_buy(trade, _settings())  # type: ignore[arg-type]
    assert sized == int(0.05 * 10**18)


def test_percent_copy_without_cap() -> None:
    trade = {"quoteAmountWei": str(10**17)}  # 0.1 ETH
    sized = size_copy_buy(trade, _settings(maxBuyEth=1))  # type: ignore[arg-type]
    assert sized == 10**16  # 10%


def test_fixed_copy() -> None:
    trade = {"quoteAmountWei": str(10**18)}
    sized = size_copy_buy(trade, _settings(copyMode="fixed", fixedBuyEth=0.02, maxBuyEth=1))  # type: ignore[arg-type]
    assert sized == int(0.02 * 10**18)


def test_target_override_percent() -> None:
    trade = {"quoteAmountWei": str(10**18)}
    sized = size_copy_buy(
        trade,  # type: ignore[arg-type]
        _settings(maxBuyEth=1),
        {"address": "0x1", "label": "x", "enabled": True, "copyPercent": 25},
    )
    assert sized == int(0.25 * 10**18)


def test_sell_mirrors_leader_and_caps_to_bag() -> None:
    trade = {"tokenAmount": str(80)}
    assert size_copy_sell(trade, _settings(), {"amount": "50"}) == 50  # type: ignore[arg-type]
    assert size_copy_sell(trade, _settings(), {"amount": "100"}) == 80  # type: ignore[arg-type]
    assert size_copy_sell(trade, _settings(sellMode="all"), {"amount": "100"}) == 100  # type: ignore[arg-type]
    assert size_copy_sell(trade, _settings(), None) == 0  # type: ignore[arg-type]


def test_slippage_and_curve_quotes() -> None:
    assert apply_slippage(10_000, 150) == 9850
    tokens = quote_curve_buy(10**18, 10**18, 1_000_000 * 10**18, 100)
    assert tokens > 0
    quote = quote_curve_sell(tokens, 10**18 + int(0.99 * 10**18), 1_000_000 * 10**18 - tokens, 100)
    assert quote > 0
