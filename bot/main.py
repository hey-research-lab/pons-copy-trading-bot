from __future__ import annotations

import signal
import threading

from bot.api import create_app, serve
from bot.chain import RPC, ROBINHOOD_CHAIN_ID, create_send_web3, create_web3, load_account, require_paid_rpc_for_live
from bot.config import short_address
from bot.engine import CopyEngine
from bot.launches import LaunchIndex
from bot.logger import log
from bot.rpc import mask_rpc
from bot.store import Store
from bot.watcher import BlockWatcher


def main() -> None:
    w3 = create_web3()
    send_w3 = create_send_web3()
    chain_id = int(w3.eth.chain_id)
    if chain_id != ROBINHOOD_CHAIN_ID:
        raise SystemExit(f"expected Robinhood Chain {ROBINHOOD_CHAIN_ID}, got {chain_id}")

    account = load_account()
    store = Store()
    if not store.settings()["dryRun"]:
        require_paid_rpc_for_live()
    launches = LaunchIndex(w3, store)

    def get_head() -> int:
        return int(w3.eth.block_number)

    app, hub = create_app(store, w3, account.address if account else None, get_head)
    engine = CopyEngine(w3, store, launches, account, hub.broadcast, send_w3)
    engine.sync_onchain_positions()

    watcher = BlockWatcher(w3, store, launches, engine, ws_url=str(RPC.get("ws_url") or ""))
    thread = threading.Thread(target=watcher.start, name="watcher", daemon=True)
    thread.start()

    log.info(
        " · ".join(
            [
                "pons copy trader ready",
                f"dryRun={store.settings()['dryRun']}",
                f"rpc={RPC['label']} {mask_rpc(str(RPC['primary']))}",
                f"paid={RPC['paid']}",
                f"ws={'on' if RPC.get('ws_url') else 'off'}",
                f"wallet={short_address(account.address)}" if account else "wallet=watch-only",
                f"targets={len(store.enabled_targets())}",
            ]
        )
    )
    log.info("this bot copies on-chain pons trades. it is not an official pons or robinhood product.")

    def shutdown(*_args: object) -> None:
        watcher.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    serve(app)


if __name__ == "__main__":
    main()
