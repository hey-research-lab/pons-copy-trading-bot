from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.types import BotSettings, TargetWallet

ROOT = Path(__file__).resolve().parents[1]


class Env(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    rpc_url: str = "https://rpc.mainnet.chain.robinhood.com"
    paid_rpc_url: str = ""
    alchemy_api_key: str = ""
    ws_url: str = ""
    send_rpc_url: str = ""
    rpc_timeout_s: int = 12
    private_key: str = ""
    dry_run: bool = True
    target_wallets: str = ""
    copy_mode: str = "percent"
    copy_percent: float = 10
    fixed_buy_eth: float = 0.02
    sell_mode: str = "mirror"
    slippage_bps: int = 150
    max_buy_eth: float = 0.05
    max_daily_eth: float = 0.25
    min_leader_trade_eth: float = 0.005
    min_liquidity_eth: float = 0.3
    max_price_impact_bps: int = 800
    skip_launch_protection: bool = True
    cooldown_ms: int = 4000
    token_blacklist: str = ""
    port: int = 8787
    host: str = "127.0.0.1"

    @field_validator("private_key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        raw = (value or "").strip()
        if not raw or raw in {"0xYOUR_PRIVATE_KEY", "YOUR_PRIVATE_KEY"}:
            return ""
        return raw if raw.startswith("0x") else f"0x{raw}"

    @field_validator("copy_mode")
    @classmethod
    def validate_copy_mode(cls, value: str) -> str:
        if value not in {"percent", "fixed"}:
            raise ValueError("COPY_MODE must be percent or fixed")
        return value

    @field_validator("sell_mode")
    @classmethod
    def validate_sell_mode(cls, value: str) -> str:
        if value not in {"mirror", "all"}:
            raise ValueError("SELL_MODE must be mirror or all")
        return value


env = Env()


def _split_addresses(raw: str) -> list[str]:
    out: list[str] = []
    for item in (raw or "").split(","):
        addr = item.strip()
        if len(addr) == 42 and addr.startswith("0x"):
            out.append(addr)
    return out


def short_address(address: str) -> str:
    if len(address) < 10:
        return address
    return f"{address[:6]}…{address[-4:]}"


def default_settings() -> BotSettings:
    return {
        "dryRun": env.dry_run,
        "running": True,
        "copyMode": env.copy_mode,  # type: ignore[typeddict-item]
        "copyPercent": env.copy_percent,
        "fixedBuyEth": env.fixed_buy_eth,
        "sellMode": env.sell_mode,  # type: ignore[typeddict-item]
        "slippageBps": env.slippage_bps,
        "maxBuyEth": env.max_buy_eth,
        "maxDailyEth": env.max_daily_eth,
        "minLeaderTradeEth": env.min_leader_trade_eth,
        "minLiquidityEth": env.min_liquidity_eth,
        "maxPriceImpactBps": env.max_price_impact_bps,
        "skipLaunchProtection": env.skip_launch_protection,
        "cooldownMs": env.cooldown_ms,
        "tokenBlacklist": _split_addresses(env.token_blacklist),
    }


def default_targets() -> list[TargetWallet]:
    return [
        {"address": addr, "label": short_address(addr), "enabled": True}
        for addr in _split_addresses(env.target_wallets)
    ]
