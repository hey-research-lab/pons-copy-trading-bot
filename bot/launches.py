from __future__ import annotations

from typing import Any

from web3 import Web3

from bot.chain import (
    ADDR,
    CURVE_ABI,
    FACTORY_ABI,
    POOL_ABI,
    TOKEN_ABI,
    V2_FACTORY_ABI,
    ZERO,
    checksum,
)
from bot.logger import log
from bot.store import Store
from bot.types import LaunchRecord


def _field(row: Any, name: str, index: int) -> Any:
    if hasattr(row, name):
        return getattr(row, name)
    if isinstance(row, dict):
        return row[name]
    return row[index]


class LaunchIndex:
    def __init__(self, w3: Web3, store: Store) -> None:
        self.w3 = w3
        self.store = store

    def resolve_token(self, token: str) -> LaunchRecord | None:
        token = checksum(token)
        cached = self.store.launch_by_key(token)
        if cached:
            return cached

        v1 = self._read_v1(token)
        if v1:
            self.store.remember_launch(v1)
            return v1

        v2 = self._read_v2(token)
        if v2:
            self.store.remember_launch(v2)
            return v2
        return None

    def resolve_pool(self, pool: str) -> LaunchRecord | None:
        pool = checksum(pool)
        cached = self.store.launch_by_key(pool)
        if cached:
            return cached
        try:
            contract = self.w3.eth.contract(address=pool, abi=POOL_ABI)
            token0 = checksum(contract.functions.token0().call())
            token1 = checksum(contract.functions.token1().call())
            if token0.lower() == ADDR["weth"].lower():
                candidate = token1
            elif token1.lower() == ADDR["weth"].lower():
                candidate = token0
            else:
                return None
            launch = self.resolve_token(candidate)
            if launch and launch.get("pool") and launch["pool"].lower() == pool.lower():
                return launch
            return launch
        except Exception:
            return None

    def resolve_curve(self, curve: str) -> LaunchRecord | None:
        curve = checksum(curve)
        cached = self.store.launch_by_key(curve)
        if cached:
            return cached
        try:
            contract = self.w3.eth.contract(address=curve, abi=CURVE_ABI)
            token = checksum(contract.functions.token().call())
            return self.resolve_token(token)
        except Exception:
            return None

    def _read_v1(self, token: str) -> LaunchRecord | None:
        for factory in (ADDR["v1Factory"], ADDR["v1FactoryLegacy"]):
            try:
                contract = self.w3.eth.contract(address=factory, abi=FACTORY_ABI)
                launched = contract.functions.getLaunchedToken(token).call()
                if not _field(launched, "exists", 11):
                    continue
                name, symbol, pool = self._token_meta(token)
                return {
                    "version": 1,
                    "token": token,
                    "pool": None if pool.lower() == ZERO.lower() else pool,
                    "pairToken": checksum(_field(launched, "pairedToken", 2)),
                    "factory": factory,
                    "deployer": checksum(_field(launched, "deployer", 1)),
                    "isToken0": bool(_field(launched, "isToken0", 9)),
                    "poolFee": int(_field(launched, "poolFee", 10)),
                    "restrictionsEndBlock": int(_field(launched, "restrictionsEndBlock", 7)),
                    "name": name,
                    "symbol": symbol,
                }
            except Exception:
                continue
        return None

    def _read_v2(self, token: str) -> LaunchRecord | None:
        try:
            contract = self.w3.eth.contract(address=ADDR["v2Factory"], abi=V2_FACTORY_ABI)
            launched = contract.functions.getLaunchedToken(token).call()
            if not _field(launched, "exists", 14):
                return None
            name, symbol, _pool = self._token_meta(token)
            pair = _field(launched, "pairToken", 4)
            pair_addr = ADDR["weth"] if str(pair).lower() == ZERO.lower() else checksum(pair)
            return {
                "version": 2,
                "token": token,
                "curve": checksum(_field(launched, "curve", 1)),
                "pairToken": pair_addr,
                "factory": ADDR["v2Factory"],
                "deployer": checksum(_field(launched, "deployer", 2)),
                "poolFee": int(_field(launched, "poolFee", 6)),
                "name": name,
                "symbol": symbol,
            }
        except Exception as error:
            log.debug(f"v2 factory lookup failed for {token}: {error}")
            return None

    def _token_meta(self, token: str) -> tuple[str, str, str]:
        try:
            contract = self.w3.eth.contract(address=token, abi=TOKEN_ABI)
            name = contract.functions.name().call()
            symbol = contract.functions.symbol().call()
            try:
                pool = checksum(contract.functions.liquidityPool().call())
            except Exception:
                pool = ZERO
            return str(name), str(symbol), pool
        except Exception:
            return "unknown", "???", ZERO
