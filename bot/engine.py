from __future__ import annotations

import random
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from time import time
from typing import Any

from eth_account.signers.local import LocalAccount
from web3 import Web3

from bot.chain import ADDR, TOKEN_ABI, checksum
from bot.executor import Executor
from bot.launches import LaunchIndex
from bot.logger import log
from bot.risk import check_risk
from bot.sizing import format_ether, size_copy_buy, size_copy_sell
from bot.store import Store
from bot.types import ActivityEvent, CopyTrade, DetectedTrade, LaunchRecord, Position

Bus = Callable[[dict[str, Any]], None]


class CopyEngine:
    def __init__(
        self,
        w3: Web3,
        store: Store,
        launches: LaunchIndex,
        account: LocalAccount | None,
        emit: Bus,
        send_w3: Web3 | None = None,
    ) -> None:
        self.w3 = w3
        self.store = store
        self.launches = launches
        self.account = account
        self.emit = emit
        self.executor = Executor(w3, account, send_w3)
        self._queue: list[tuple[DetectedTrade, LaunchRecord]] = []
        self._lock = threading.Lock()
        self._busy = False
        self.last_copy_at = 0.0

    def enqueue(self, trade: DetectedTrade, launch: LaunchRecord) -> None:
        if self.store.has_source_tx(trade["sourceTx"]) and any(t.get("id") == trade["id"] for t in self.store.trades()):
            return
        self._queue.append((trade, launch))
        self._drain()

    def _drain(self) -> None:
        with self._lock:
            if self._busy:
                return
            self._busy = True
        try:
            while self._queue:
                trade, launch = self._queue.pop(0)
                self._handle(trade, launch)
        finally:
            self._busy = False

    def _handle(self, detected: DetectedTrade, launch: LaunchRecord) -> None:
        settings = self.store.settings()
        target = next(
            (t for t in self.store.targets() if t["address"].lower() == detected["sourceWallet"].lower()),
            None,
        )
        copy = self.store.add_trade({**detected, "status": "detected"})
        self.emit({"type": "trade", "trade": copy})
        self._note(
            "trade",
            f"{detected['side'].upper()} {detected['symbol']} by {detected['sourceWallet']}",
            {"sourceTx": detected["sourceTx"], "quoteEth": format_ether(int(detected["quoteAmountWei"]))},
        )

        if not settings["running"]:
            self._finish(copy["id"], {"status": "skipped", "reason": "bot paused"})
            return

        if launch.get("version") == 2 and not launch.get("curve"):
            self._finish(copy["id"], {"status": "skipped", "reason": "v2 curve missing; graduated v4 routing is not enabled"})
            return

        if detected["side"] == "buy" and launch.get("pairToken", "").lower() != ADDR["weth"].lower():
            self._finish(copy["id"], {"status": "skipped", "reason": "non-WETH pair not copied"})
            return

        position = self.store.get_position(detected["token"])
        copy_wei = size_copy_buy(detected, settings, target) if detected["side"] == "buy" else 0
        sell_amount = size_copy_sell(detected, settings, position) if detected["side"] == "sell" else 0
        amount_in = copy_wei if detected["side"] == "buy" else sell_amount

        if detected["side"] == "sell" and sell_amount == 0:
            self._finish(copy["id"], {"status": "skipped", "reason": "no local position"})
            return

        ok, reason = check_risk(
            trade=detected,
            launch=launch,
            settings=settings,
            copy_wei=copy_wei if detected["side"] == "buy" else int(detected["quoteAmountWei"]),
            spent_today=self.store.spent_today(),
            last_copy_at=self.last_copy_at,
            block_number=int(detected["blockNumber"]),
            w3=self.w3,
        )
        if not ok:
            self._finish(copy["id"], {"status": "skipped", "reason": reason})
            return

        copy = self._finish(
            copy["id"],
            {
                "status": "queued",
                "copyQuoteWei": str(copy_wei) if detected["side"] == "buy" else None,
                "copyTokenAmount": str(sell_amount) if detected["side"] == "sell" else None,
            },
        )
        if not copy:
            return

        try:
            result = self.executor.execute(
                trade=copy,
                launch=launch,
                amount_in=amount_in,
                slippage_bps=settings["slippageBps"],
                dry_run=settings["dryRun"] or not self.account,
            )
            self.last_copy_at = time() * 1000
            if detected["side"] == "buy" and not result["paper"]:
                self.store.spend_today(copy_wei)
            status = "paper" if result["paper"] else "filled"
            updated = self._finish(
                copy["id"],
                {
                    "status": status,
                    "ourTx": result["hash"],
                    "quotedOut": str(result["amountOut"]),
                    "minOut": str(result["minOut"]),
                    "copyQuoteWei": str(amount_in) if detected["side"] == "buy" else None,
                    "copyTokenAmount": str(amount_in) if detected["side"] == "sell" else str(result["amountOut"]),
                    "executedAt": datetime.now(timezone.utc).isoformat(),
                },
            )
            if updated:
                self._apply_position(updated, launch, amount_in, result["amountOut"], result["paper"])
            self._note(
                "info",
                f"{status} {detected['side']} {detected['symbol']}",
                {"ourTx": result["hash"], "amountIn": format_ether(amount_in)},
            )
        except Exception as error:
            message = str(error)
            self._finish(copy["id"], {"status": "failed", "reason": message, "executedAt": datetime.now(timezone.utc).isoformat()})
            self._note("error", f"copy failed: {message}", {"token": detected["token"]})
            log.error("copy execution failed", error)

    def _apply_position(
        self,
        trade: CopyTrade,
        launch: LaunchRecord,
        amount_in: int,
        amount_out: int,
        paper: bool,
    ) -> None:
        if paper:
            return
        current = self.store.get_position(trade["token"])
        if trade["side"] == "buy":
            next_pos: Position = {
                "token": trade["token"],
                "symbol": trade["symbol"],
                "name": trade["name"],
                "amount": str(int(current["amount"]) + amount_out if current else amount_out),
                "costWei": str(int(current["costWei"]) + amount_in if current else amount_in),
                "venue": trade["venue"],
                "pool": launch.get("pool"),
                "curve": launch.get("curve"),
                "pairToken": launch.get("pairToken") or "",
                "isToken0": launch.get("isToken0"),
                "poolFee": int(launch.get("poolFee") or 0),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            self.store.set_position(next_pos, trade["token"])
        elif current:
            sold = min(amount_in, int(current["amount"]))
            remain = int(current["amount"]) - sold
            remain_cost = 0 if int(current["amount"]) == 0 else (int(current["costWei"]) * remain) // int(current["amount"])
            self.store.set_position(
                None
                if remain == 0
                else {
                    **current,
                    "amount": str(remain),
                    "costWei": str(remain_cost),
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                },
                trade["token"],
            )
        self.emit({"type": "position", "positions": self.store.positions()})

    def sync_onchain_positions(self) -> None:
        if not self.account:
            return
        for position in self.store.positions():
            try:
                token = self.w3.eth.contract(address=checksum(position["token"]), abi=TOKEN_ABI)
                bal = int(token.functions.balanceOf(self.account.address).call())
                self.store.set_position(
                    None
                    if bal == 0
                    else {**position, "amount": str(bal), "updatedAt": datetime.now(timezone.utc).isoformat()},
                    position["token"],
                )
            except Exception:
                continue

    def _finish(self, trade_id: str, patch: dict[str, Any]) -> CopyTrade | None:
        updated = self.store.update_trade(trade_id, {k: v for k, v in patch.items() if v is not None})
        if updated:
            self.emit({"type": "trade", "trade": updated})
        return updated

    def _note(self, level: ActivityEvent["level"], message: str, meta: dict[str, Any] | None = None) -> None:
        event = self.store.push_activity(
            {
                "id": f"{int(time() * 1000)}-{random.randbytes(3).hex()}",
                "at": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "meta": meta or {},
            }
        )
        self.emit(event)
