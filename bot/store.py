from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bot.config import ROOT, default_settings, default_targets
from bot.types import ActivityEvent, BotSettings, CopyTrade, DailySpend, LaunchRecord, Position, TargetWallet

FILE = ROOT / "data" / "store.json"
MAX_TRADES = 400
MAX_ACTIVITY = 300


def utc_day(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m-%d")


def _empty() -> dict[str, Any]:
    return {
        "settings": default_settings(),
        "targets": default_targets(),
        "launches": {},
        "trades": [],
        "positions": {},
        "activity": [],
        "daily": {"day": utc_day(), "spentWei": "0"},
        "lastBlock": "0",
    }


def _serialize_launch(launch: LaunchRecord) -> dict[str, Any]:
    row = dict(launch)
    end = row.get("restrictionsEndBlock")
    if end is not None:
        row["restrictionsEndBlock"] = str(end)
    return row


def _deserialize_launch(launch: dict[str, Any]) -> LaunchRecord:
    row = dict(launch)
    end = row.get("restrictionsEndBlock")
    if end not in (None, ""):
        row["restrictionsEndBlock"] = int(end)
    return row  # type: ignore[return-value]


class Store:
    def __init__(self) -> None:
        self.data = self._load()
        self._merge_env_defaults()

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(FILE.read_text(encoding="utf-8"))
            base = _empty()
            base.update(raw)
            base["settings"] = {**_empty()["settings"], **(raw.get("settings") or {})}
            return base
        except (OSError, json.JSONDecodeError):
            return _empty()

    def _merge_env_defaults(self) -> None:
        existing = {str(t.get("address", "")).lower() for t in self.data["targets"]}
        for target in default_targets():
            if target["address"].lower() not in existing:
                self.data["targets"].append(target)

    def persist(self) -> None:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(FILE)

    def settings(self) -> BotSettings:
        return self.data["settings"]

    def patch_settings(self, patch: dict[str, Any]) -> BotSettings:
        self.data["settings"] = {**self.data["settings"], **patch}
        self.persist()
        return self.data["settings"]

    def targets(self) -> list[TargetWallet]:
        return self.data["targets"]

    def upsert_target(self, target: TargetWallet) -> list[TargetWallet]:
        idx = next(
            (i for i, row in enumerate(self.data["targets"]) if row["address"].lower() == target["address"].lower()),
            -1,
        )
        if idx >= 0:
            self.data["targets"][idx] = {**self.data["targets"][idx], **target}
        else:
            self.data["targets"].append(target)
        self.persist()
        return self.data["targets"]

    def remove_target(self, address: str) -> list[TargetWallet]:
        self.data["targets"] = [t for t in self.data["targets"] if t["address"].lower() != address.lower()]
        self.persist()
        return self.data["targets"]

    def enabled_targets(self) -> set[str]:
        return {t["address"].lower() for t in self.data["targets"] if t.get("enabled")}

    def remember_launch(self, launch: LaunchRecord) -> None:
        serialized = _serialize_launch(launch)
        self.data["launches"][launch["token"].lower()] = serialized
        if launch.get("pool"):
            self.data["launches"][launch["pool"].lower()] = serialized
        if launch.get("curve"):
            self.data["launches"][launch["curve"].lower()] = serialized
        self.persist()

    def launch_by_key(self, key: str) -> LaunchRecord | None:
        found = self.data["launches"].get(key.lower())
        return _deserialize_launch(found) if found else None

    def recent_launches(self, limit: int = 40) -> list[LaunchRecord]:
        unique: dict[str, LaunchRecord] = {}
        for item in self.data["launches"].values():
            unique[item["token"].lower()] = _deserialize_launch(item)
        rows = list(unique.values())
        return list(reversed(rows[-limit:]))

    def add_trade(self, trade: CopyTrade) -> CopyTrade:
        self.data["trades"].insert(0, trade)
        self.data["trades"] = self.data["trades"][:MAX_TRADES]
        self.persist()
        return trade

    def update_trade(self, trade_id: str, patch: dict[str, Any]) -> CopyTrade | None:
        idx = next((i for i, row in enumerate(self.data["trades"]) if row.get("id") == trade_id), -1)
        if idx < 0:
            return None
        self.data["trades"][idx] = {**self.data["trades"][idx], **patch}
        self.persist()
        return self.data["trades"][idx]

    def trades(self, limit: int = 80) -> list[CopyTrade]:
        return self.data["trades"][:limit]

    def has_source_tx(self, tx_hash: str) -> bool:
        needle = tx_hash.lower()
        return any(str(t.get("sourceTx", "")).lower() == needle for t in self.data["trades"])

    def positions(self) -> list[Position]:
        return list(self.data["positions"].values())

    def get_position(self, token: str) -> Position | None:
        return self.data["positions"].get(token.lower())

    def set_position(self, position: Position | None, token: str) -> None:
        key = token.lower()
        if not position or int(position.get("amount") or "0") == 0:
            self.data["positions"].pop(key, None)
        else:
            self.data["positions"][key] = position
        self.persist()

    def push_activity(self, event: ActivityEvent) -> ActivityEvent:
        self.data["activity"].insert(0, event)
        self.data["activity"] = self.data["activity"][:MAX_ACTIVITY]
        self.persist()
        return event

    def activity(self, limit: int = 80) -> list[ActivityEvent]:
        return self.data["activity"][:limit]

    def last_block(self) -> int:
        return int(self.data.get("lastBlock") or 0)

    def set_last_block(self, block: int) -> None:
        self.data["lastBlock"] = str(block)
        self.persist()

    def spend_today(self, wei: int) -> None:
        day = utc_day()
        daily: DailySpend = self.data["daily"]
        if daily.get("day") != day:
            daily = {"day": day, "spentWei": "0"}
        daily["spentWei"] = str(int(daily.get("spentWei") or 0) + wei)
        self.data["daily"] = daily
        self.persist()

    def spent_today(self) -> int:
        day = utc_day()
        daily: DailySpend = self.data["daily"]
        if daily.get("day") != day:
            return 0
        return int(daily.get("spentWei") or 0)
