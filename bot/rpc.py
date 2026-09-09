from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from web3.providers.rpc import HTTPProvider
from web3.types import RPCEndpoint, RPCResponse

from bot.logger import log

PUBLIC_HTTP = "https://rpc.mainnet.chain.robinhood.com"
PUBLIC_HOSTS = {
    "rpc.mainnet.chain.robinhood.com",
    "rpc.testnet.chain.robinhood.com",
}
ALCHEMY_HTTP = "https://robinhood-mainnet.g.alchemy.com/v2/{key}"
ALCHEMY_WS = "wss://robinhood-mainnet.g.alchemy.com/v2/{key}"


def is_public_rpc(url: str) -> bool:
    host = urlsplit(url.strip()).hostname or ""
    return host.lower() in PUBLIC_HOSTS


def mask_rpc(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    segments = [s for s in path.split("/") if s]
    if segments:
        last = segments[-1]
        if last.lower() not in {"http", "ws", "wss", "rpc"} and len(last) >= 8:
            segments[-1] = "***"
        path = "/" + "/".join(segments)
    query = "key=***" if parts.query else ""
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def resolve_rpc(
    *,
    rpc_url: str,
    paid_rpc_url: str = "",
    alchemy_api_key: str = "",
    ws_url: str = "",
    send_rpc_url: str = "",
) -> dict[str, Any]:
    key = (alchemy_api_key or "").strip()
    paid = (paid_rpc_url or "").strip()
    http = (rpc_url or "").strip() or PUBLIC_HTTP
    ws = (ws_url or "").strip()
    send = (send_rpc_url or "").strip()

    if key:
        if not paid:
            paid = ALCHEMY_HTTP.format(key=key)
        if not ws:
            ws = ALCHEMY_WS.format(key=key)

    primary = paid or http
    read_urls: list[str] = []
    for url in (primary, http, PUBLIC_HTTP):
        if url and url not in read_urls:
            read_urls.append(url)

    paid_active = not is_public_rpc(primary)
    write_url = send or (primary if paid_active else "")
    return {
        "primary": primary,
        "read_urls": read_urls,
        "write_url": write_url,
        "ws_url": ws,
        "paid": paid_active,
        "label": _label(primary),
    }


def _label(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if "alchemy.com" in host:
        return "alchemy"
    if "quiknode.pro" in host or "quicknode" in host:
        return "quicknode"
    if "chainstack" in host:
        return "chainstack"
    if "drpc.org" in host:
        return "drpc"
    if "blockdaemon" in host:
        return "blockdaemon"
    if is_public_rpc(url):
        return "public"
    return host or "custom"


class FailoverHTTPProvider(HTTPProvider):
    def __init__(self, urls: list[str], timeout: int = 12) -> None:
        if not urls:
            raise ValueError("at least one RPC URL is required")
        self._urls = urls
        self._index = 0
        super().__init__(urls[0], request_kwargs={"timeout": timeout})

    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        last_error: Exception | None = None
        for offset in range(len(self._urls)):
            idx = (self._index + offset) % len(self._urls)
            url = self._urls[idx]
            self.endpoint_uri = url
            try:
                result = super().make_request(method, params)
                if idx != self._index:
                    log.warn(f"rpc failed over to {mask_rpc(url)}")
                self._index = idx
                return result
            except Exception as error:
                last_error = error
                log.warn(f"rpc error {mask_rpc(url)}: {error}")
        assert last_error is not None
        raise last_error
