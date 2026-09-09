from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from web3 import Web3

from bot.chain import ADDR, EXPLORER, PONS_SITE, ROBINHOOD_CHAIN_ID, RPC, WETH_ABI, explorer_address, explorer_tx, is_address, pons_token_url, require_paid_rpc_for_live
from bot.config import ROOT, env, short_address
from bot.logger import log
from bot.rpc import mask_rpc
from bot.sizing import format_ether
from bot.store import Store
from bot.static_page import DASHBOARD_HTML

STATIC = Path(__file__).resolve().parent / "static"
REACT_DIST = ROOT / "web" / "dist"


class Hub:
    def __init__(self) -> None:
        self.sockets: list[WebSocket] = []
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self.sockets.append(socket)

    def disconnect(self, socket: WebSocket) -> None:
        if socket in self.sockets:
            self.sockets.remove(socket)

    def broadcast(self, payload: Any) -> None:
        raw = json.dumps(payload, default=str)
        loop = self.loop
        if loop is None:
            return

        async def _send_all() -> None:
            stale: list[WebSocket] = []
            for socket in list(self.sockets):
                try:
                    await socket.send_text(raw)
                except Exception:
                    stale.append(socket)
            for socket in stale:
                self.disconnect(socket)

        loop.call_soon_threadsafe(lambda: loop.create_task(_send_all()))


def create_app(
    store: Store,
    w3: Web3,
    wallet_address: str | None,
    get_head: Callable[[], int],
) -> tuple[FastAPI, Hub]:
    hub = Hub()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        hub.loop = asyncio.get_running_loop()
        yield

    app = FastAPI(title="pons copy trader", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def wallet_balances() -> dict[str, Any]:
        if not wallet_address:
            return {"address": None, "label": None, "eth": "0", "weth": "0"}
        eth = w3.eth.get_balance(wallet_address)
        weth = w3.eth.contract(address=ADDR["weth"], abi=WETH_ABI).functions.balanceOf(wallet_address).call()
        return {
            "address": wallet_address,
            "label": short_address(wallet_address),
            "eth": format_ether(int(eth)),
            "weth": format_ether(int(weth)),
        }

    def snapshot() -> dict[str, Any]:
        return {
            "chainId": ROBINHOOD_CHAIN_ID,
            "rpc": mask_rpc(str(RPC["primary"])),
            "rpcPaid": bool(RPC["paid"]),
            "rpcWs": bool(RPC.get("ws_url")),
            "explorer": EXPLORER,
            "pons": PONS_SITE,
            "settings": store.settings(),
            "wallet": wallet_balances(),
            "targets": store.targets(),
            "trades": store.trades(),
            "positions": store.positions(),
            "activity": store.activity(),
            "launches": store.recent_launches(),
            "dailySpentEth": format_ether(store.spent_today()),
            "lastBlock": str(store.last_block()),
            "headBlock": str(get_head()),
            "contracts": ADDR,
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "chainId": ROBINHOOD_CHAIN_ID,
            "rpc": mask_rpc(str(RPC["primary"])),
            "paid": bool(RPC["paid"]),
            "ws": bool(RPC.get("ws_url")),
        }

    @app.get("/api/snapshot")
    def get_snapshot() -> dict[str, Any]:
        return snapshot()

    @app.patch("/api/settings")
    async def patch_settings(body: dict[str, Any]) -> Any:
        if body.get("dryRun") is False:
            try:
                require_paid_rpc_for_live()
            except RuntimeError as error:
                return JSONResponse({"error": str(error)}, status_code=400)
        next_settings = store.patch_settings(body)
        hub.broadcast({"type": "settings", "settings": next_settings})
        return next_settings

    @app.post("/api/control/{action}")
    def control(action: str) -> Any:
        if action == "start":
            store.patch_settings({"running": True})
        elif action == "stop":
            store.patch_settings({"running": False})
        else:
            return JSONResponse({"error": "unknown action"}, status_code=400)
        hub.broadcast({"type": "settings", "settings": store.settings()})
        return store.settings()

    @app.post("/api/targets")
    async def add_target(body: dict[str, Any]) -> Any:
        address = body.get("address")
        if not address or not is_address(address):
            return JSONResponse({"error": "invalid address"}, status_code=400)
        targets = store.upsert_target(
            {
                "address": Web3.to_checksum_address(address),
                "label": body.get("label") or short_address(address),
                "enabled": body.get("enabled", True) is not False,
                "copyPercent": body.get("copyPercent"),
                "maxBuyEth": body.get("maxBuyEth"),
            }
        )
        hub.broadcast({"type": "targets", "targets": targets})
        return targets

    @app.delete("/api/targets/{address}")
    def drop_target(address: str) -> Any:
        if not is_address(address):
            return JSONResponse({"error": "invalid address"}, status_code=400)
        targets = store.remove_target(address)
        hub.broadcast({"type": "targets", "targets": targets})
        return targets

    @app.get("/api/links/tx/{tx_hash}")
    def link_tx(tx_hash: str) -> dict[str, str]:
        return {"url": explorer_tx(tx_hash)}

    @app.get("/api/links/address/{address}")
    def link_address(address: str) -> dict[str, str]:
        return {"url": explorer_address(address)}

    @app.get("/api/links/token/{token}")
    def link_token(token: str) -> dict[str, str]:
        return {"url": pons_token_url(token)}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await hub.connect(socket)
        try:
            await socket.send_text(json.dumps({"type": "snapshot", "state": snapshot()}, default=str))
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(socket)
        except Exception:
            hub.disconnect(socket)

    if REACT_DIST.exists():
        app.mount("/", StaticFiles(directory=REACT_DIST, html=True), name="web")
    else:
        @app.get("/")
        def dashboard() -> HTMLResponse:
            return HTMLResponse(DASHBOARD_HTML)

        if STATIC.exists():
            app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/{path:path}")
        def spa(path: str) -> Any:
            if path.startswith("api") or path == "ws":
                return JSONResponse({"error": "not found"}, status_code=404)
            return HTMLResponse(DASHBOARD_HTML)

    return app, hub


def serve(app: FastAPI) -> None:
    import uvicorn

    log.info(f"dashboard http://{env.host}:{env.port}")
    uvicorn.run(app, host=env.host, port=env.port, log_level="warning")
