from bot.risk import check_risk
from bot.types import BotSettings, DetectedTrade, LaunchRecord


class _NoW3:
    pass


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
        "tokenBlacklist": ["0xdead000000000000000000000000000000000000"],
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _trade(**overrides) -> DetectedTrade:
    row: DetectedTrade = {
        "id": "1",
        "sourceTx": "0xabc",
        "sourceWallet": "0xB9F5f4Ea1AF1F5d3678470eb98e8FBdcadEb24b0",
        "blockNumber": "100",
        "venue": "v2-curve",
        "side": "buy",
        "token": "0x39dBED3a2bd333467115dE45665cC57F813C4571",
        "symbol": "PONS",
        "name": "pons",
        "quoteAmountWei": str(10**17),
        "tokenAmount": "1",
        "detectedAt": "2026-09-09T00:00:00Z",
    }
    row.update(overrides)  # type: ignore[typeddict-item]
    return row


def _launch(**overrides) -> LaunchRecord:
    row: LaunchRecord = {
        "version": 2,
        "token": "0x39dBED3a2bd333467115dE45665cC57F813C4571",
        "pairToken": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
        "factory": "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e",
        "deployer": "0xB9F5f4Ea1AF1F5d3678470eb98e8FBdcadEb24b0",
        "poolFee": 0,
    }
    row.update(overrides)  # type: ignore[typeddict-item]
    return row


def _check(**kwargs):
    defaults = {
        "trade": _trade(),
        "launch": _launch(),
        "settings": _settings(),
        "copy_wei": 10**16,
        "spent_today": 0,
        "last_copy_at": 0,
        "block_number": 100,
        "w3": _NoW3(),
    }
    defaults.update(kwargs)
    return check_risk(**defaults)


def test_rejects_zero_size() -> None:
    ok, reason = _check(copy_wei=0)
    assert ok is False
    assert "zero" in reason


def test_rejects_blacklist() -> None:
    ok, reason = _check(trade=_trade(token="0xdead000000000000000000000000000000000000"))
    assert ok is False
    assert "blacklist" in reason


def test_rejects_dust_leader_trade() -> None:
    ok, reason = _check(trade=_trade(quoteAmountWei="1"))
    assert ok is False
    assert "below" in reason


def test_rejects_daily_cap() -> None:
    ok, reason = _check(spent_today=int(0.25 * 10**18), copy_wei=10**16)
    assert ok is False
    assert "daily" in reason


def test_rejects_launch_protection() -> None:
    ok, reason = _check(launch=_launch(restrictionsEndBlock=200), block_number=150)
    assert ok is False
    assert "protection" in reason


def test_allows_healthy_buy() -> None:
    ok, reason = _check()
    assert ok is True
    assert reason == ""
