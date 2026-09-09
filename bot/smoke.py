from __future__ import annotations

import json

from bot.chain import ADDR, FACTORY_ABI, ROBINHOOD_CHAIN_ID, RPC, TOKEN_ABI, create_web3
from bot.rpc import mask_rpc


def main() -> None:
    w3 = create_web3()
    chain_id = int(w3.eth.chain_id)
    token = w3.eth.contract(address=ADDR["ponsToken"], abi=TOKEN_ABI)
    factory = w3.eth.contract(address=ADDR["v1FactoryLegacy"], abi=FACTORY_ABI)
    launched = factory.functions.getLaunchedToken(ADDR["ponsToken"]).call()
    payload = {
        "id": chain_id,
        "expected": ROBINHOOD_CHAIN_ID,
        "rpc": mask_rpc(str(RPC["primary"])),
        "paid": bool(RPC["paid"]),
        "ws": bool(RPC.get("ws_url")),
        "name": token.functions.name().call(),
        "symbol": token.functions.symbol().call(),
        "exists": bool(launched[11]),
        "isToken0": bool(launched[9]),
        "poolFee": int(launched[10]),
        "paired": launched[2],
        "deployer": launched[1],
    }
    print(json.dumps(payload, indent=2, default=str))
    if chain_id != ROBINHOOD_CHAIN_ID:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
