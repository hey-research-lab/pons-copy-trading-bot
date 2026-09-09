from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep

from web3 import Web3

from bot.chain import ADDR, V1_LAUNCH_TOPIC, V2_LAUNCH_TOPIC, checksum
from bot.decode import decode_target_trades
from bot.engine import CopyEngine
from bot.launches import LaunchIndex
from bot.logger import log
from bot.rpc import mask_rpc
from bot.store import Store

POLL_S = 0.2
MAX_CATCHUP = 80
PARALLEL = 8


class BlockWatcher:
    def __init__(
        self,
        w3: Web3,
        store: Store,
        launches: LaunchIndex,
        engine: CopyEngine,
        ws_url: str = "",
    ) -> None:
        self.w3 = w3
        self.store = store
        self.launches = launches
        self.engine = engine
        self.ws_url = ws_url
        self.stopped = False
        self._pulse = threading.Event()

    def start(self) -> None:
        if self.ws_url:
            threading.Thread(target=self._ws_loop, name="heads", daemon=True).start()
            log.info(f"watcher ws {mask_rpc(self.ws_url)}")
        head = int(self.w3.eth.block_number)
        saved = self.store.last_block()
        start = head if saved == 0 else saved + 1
        log.info(f"watcher live from block {start} (head {head})")
        nxt = start
        while not self.stopped:
            try:
                nxt = self.tick(nxt)
                self._pulse.wait(timeout=POLL_S)
                self._pulse.clear()
            except Exception as error:
                log.error("watcher tick failed", error)
                sleep(2.5)

    def stop(self) -> None:
        self.stopped = True
        self._pulse.set()

    def _ws_loop(self) -> None:
        while not self.stopped:
            try:
                asyncio.run(self._ws_once())
            except Exception as error:
                if self.stopped:
                    return
                log.warn(f"ws heads reconnect: {error}")
                sleep(2)

    async def _ws_once(self) -> None:
        import websockets

        async with websockets.connect(self.ws_url, ping_interval=20, open_timeout=15) as ws:
            await ws.send(
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["newHeads"]})
            )
            await ws.recv()
            log.info("ws subscribed to newHeads")
            async for _message in ws:
                self._pulse.set()
                if self.stopped:
                    return

    def tick(self, from_block: int) -> int:
        head = int(self.w3.eth.block_number)
        if head < from_block:
            return from_block

        end = from_block + MAX_CATCHUP - 1 if head - from_block > MAX_CATCHUP else head
        targets = self.store.enabled_targets()
        numbers = list(range(from_block, end + 1))

        for i in range(0, len(numbers), PARALLEL):
            slice_n = numbers[i : i + PARALLEL]
            blocks = self._fetch_blocks(slice_n)
            self._ingest_launches(slice_n[0], slice_n[-1])
            for block in blocks:
                if targets:
                    for tx in block.get("transactions") or []:
                        if not isinstance(tx, dict):
                            continue
                        sender = str(tx.get("from") or "").lower()
                        if sender not in targets:
                            continue
                        try:
                            receipt = dict(self.w3.eth.get_transaction_receipt(tx["hash"]))
                            decoded = decode_target_trades(tx=tx, receipt=receipt, launches=self.launches)
                            for trade, launch in decoded:
                                self.engine.enqueue(trade, launch)
                        except Exception as error:
                            log.warn(f"failed to decode {tx.get('hash')}: {error}")
                self.store.set_last_block(int(block["number"]))
        return end + 1

    def _fetch_blocks(self, numbers: list[int]) -> list[dict]:
        out: dict[int, dict] = {}
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            futures = {pool.submit(self._get_block, n): n for n in numbers}
            for future in as_completed(futures):
                block = future.result()
                out[int(block["number"])] = block
        return [out[n] for n in numbers if n in out]

    def _get_block(self, number: int) -> dict:
        return dict(self.w3.eth.get_block(number, full_transactions=True))

    def _ingest_launches(self, from_block: int, to_block: int) -> None:
        try:
            v1_logs = self.w3.eth.get_logs(
                {
                    "address": [ADDR["v1Factory"], ADDR["v1FactoryLegacy"]],
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": [V1_LAUNCH_TOPIC],
                }
            )
            for item in v1_logs:
                topics = item.get("topics") or []
                if len(topics) < 2:
                    continue
                token = checksum("0x" + topics[1].hex()[-40:])
                launch = self.launches.resolve_token(token)
                if launch:
                    log.info(f"new pons launch {token} pool={launch.get('pool') or '?'}")
        except Exception:
            pass

        try:
            v2_logs = self.w3.eth.get_logs(
                {
                    "address": ADDR["v2Factory"],
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": [V2_LAUNCH_TOPIC],
                }
            )
            for item in v2_logs:
                topics = item.get("topics") or []
                if len(topics) < 2:
                    continue
                token = checksum("0x" + topics[1].hex()[-40:])
                launch = self.launches.resolve_token(token)
                if launch:
                    log.info(f"new pons v2 launch {token} curve={launch.get('curve') or '?'}")
        except Exception:
            pass
