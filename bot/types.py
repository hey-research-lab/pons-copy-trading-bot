from __future__ import annotations

from typing import Any, Literal, TypedDict

Venue = Literal["v1-pool", "v2-curve"]
Side = Literal["buy", "sell"]
CopyMode = Literal["percent", "fixed"]
SellMode = Literal["mirror", "all"]
TradeStatus = Literal["detected", "skipped", "queued", "sent", "filled", "failed", "paper"]


class TargetWallet(TypedDict, total=False):
    address: str
    label: str
    enabled: bool
    copyPercent: float
    maxBuyEth: float


class LaunchRecord(TypedDict, total=False):
    version: int
    token: str
    pool: str
    curve: str
    pairToken: str
    factory: str
    deployer: str
    isToken0: bool
    poolFee: int
    restrictionsEndBlock: int
    name: str
    symbol: str


class DetectedTrade(TypedDict, total=False):
    id: str
    sourceTx: str
    sourceWallet: str
    blockNumber: str
    venue: Venue
    side: Side
    token: str
    symbol: str
    name: str
    quoteAmountWei: str
    tokenAmount: str
    pool: str
    curve: str
    pairToken: str
    isToken0: bool
    poolFee: int
    detectedAt: str


class CopyTrade(DetectedTrade, total=False):
    status: TradeStatus
    reason: str
    copyQuoteWei: str
    copyTokenAmount: str
    ourTx: str
    quotedOut: str
    minOut: str
    executedAt: str


class Position(TypedDict, total=False):
    token: str
    symbol: str
    name: str
    amount: str
    costWei: str
    venue: Venue
    pool: str
    curve: str
    pairToken: str
    isToken0: bool
    poolFee: int
    updatedAt: str


class BotSettings(TypedDict):
    dryRun: bool
    running: bool
    copyMode: CopyMode
    copyPercent: float
    fixedBuyEth: float
    sellMode: SellMode
    slippageBps: int
    maxBuyEth: float
    maxDailyEth: float
    minLeaderTradeEth: float
    minLiquidityEth: float
    maxPriceImpactBps: int
    skipLaunchProtection: bool
    cooldownMs: int
    tokenBlacklist: list[str]


class ActivityEvent(TypedDict, total=False):
    id: str
    at: str
    level: Literal["info", "warn", "error", "trade"]
    message: str
    meta: dict[str, Any]


class DailySpend(TypedDict):
    day: str
    spentWei: str
