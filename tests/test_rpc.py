from bot.rpc import is_public_rpc, mask_rpc, resolve_rpc


def test_alchemy_key_builds_paid_and_ws() -> None:
    cfg = resolve_rpc(
        rpc_url="https://rpc.mainnet.chain.robinhood.com",
        alchemy_api_key="abc123secretkey",
    )
    assert cfg["paid"] is True
    assert cfg["label"] == "alchemy"
    assert cfg["primary"].endswith("/v2/abc123secretkey")
    assert cfg["ws_url"].startswith("wss://")
    assert cfg["write_url"] == cfg["primary"]
    assert cfg["read_urls"][0] == cfg["primary"]
    assert "rpc.mainnet.chain.robinhood.com" in cfg["read_urls"][1]


def test_paid_url_beats_public() -> None:
    cfg = resolve_rpc(
        rpc_url="https://rpc.mainnet.chain.robinhood.com",
        paid_rpc_url="https://foo.robinhood-mainnet.quiknode.pro/tokentoken",
    )
    assert cfg["label"] == "quicknode"
    assert cfg["paid"] is True
    assert cfg["write_url"].startswith("https://foo.")


def test_public_only_is_not_paid() -> None:
    cfg = resolve_rpc(rpc_url="https://rpc.mainnet.chain.robinhood.com")
    assert cfg["paid"] is False
    assert cfg["write_url"] == ""
    assert is_public_rpc(cfg["primary"])


def test_mask_hides_api_key() -> None:
    masked = mask_rpc("https://robinhood-mainnet.g.alchemy.com/v2/supersecretapikey")
    assert "supersecretapikey" not in masked
    assert "***" in masked
