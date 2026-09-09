from __future__ import annotations

import json

from bot.chain import ADDR, SWAP_TOPIC, create_web3
from bot.decode import decode_target_trades
from bot.launches import LaunchIndex
from bot.sizing import format_ether
from bot.store import Store


def main() -> None:
    w3 = create_web3()
    store = Store()
    launches = LaunchIndex(w3, store)
    head = int(w3.eth.block_number)
    logs = w3.eth.get_logs(
        {
            "address": ADDR["ponsPool"],
            "fromBlock": max(head - 4000, 0),
            "toBlock": head,
            "topics": [SWAP_TOPIC],
        }
    )
    if not logs:
        print("no recent PONS swaps in the last 4000 blocks")
        return
    last = logs[-1]
    tx_hash = last["transactionHash"]
    hex_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not hex_hash.startswith("0x"):
        hex_hash = "0x" + hex_hash
    tx = dict(w3.eth.get_transaction(tx_hash))
    receipt = dict(w3.eth.get_transaction_receipt(tx_hash))
    decoded = decode_target_trades(tx=tx, receipt=receipt, launches=launches)
    print(
        json.dumps(
            {
                "source": hex_hash,
                "from": tx.get("from"),
                "decoded": [
                    {
                        "side": trade["side"],
                        "symbol": trade["symbol"],
                        "venue": trade["venue"],
                        "quoteEth": format_ether(int(trade["quoteAmountWei"])),
                    }
                    for trade, _launch in decoded
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
