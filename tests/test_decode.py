from eth_abi import encode

from bot.chain import CURVE_BUY_TOPIC, CURVE_SELL_TOPIC, SWAP_TOPIC
from bot.decode import decode_target_trades, topic_matches


class FakeLaunches:
    def __init__(self, launch):
        self.launch = launch

    def resolve_pool(self, _addr):
        return self.launch if self.launch.get("version") == 1 else None

    def resolve_curve(self, _addr):
        return self.launch if self.launch.get("version") == 2 else None


V1 = {
    "version": 1,
    "token": "0x39dBED3a2bd333467115dE45665cC57F813C4571",
    "pool": "0x10CC6BD38112cAc182db90B6a71d8Bb5939526bA",
    "pairToken": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
    "factory": "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB",
    "deployer": "0xB9F5f4Ea1AF1F5d3678470eb98e8FBdcadEb24b0",
    "isToken0": True,
    "poolFee": 10000,
    "symbol": "PONS",
    "name": "pons",
}

V2 = {
    "version": 2,
    "token": "0x1111111111111111111111111111111111111111",
    "curve": "0x2222222222222222222222222222222222222222",
    "pairToken": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
    "factory": "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e",
    "deployer": "0xB9F5f4Ea1AF1F5d3678470eb98e8FBdcadEb24b0",
    "poolFee": 0,
    "symbol": "MEME",
    "name": "meme",
}


def _tx():
    return {
        "hash": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "from": "0xB9F5f4Ea1AF1F5d3678470eb98e8FBdcadEb24b0",
    }


def test_topic_matching_accepts_with_or_without_prefix() -> None:
    raw = SWAP_TOPIC.hex()
    assert topic_matches(raw, SWAP_TOPIC)
    assert topic_matches("0x" + raw.replace("0x", ""), SWAP_TOPIC)


def test_v1_swap_buy_when_pool_receives_weth() -> None:
    data = encode(["int256", "int256", "uint160", "uint128", "int24"], [-(10**18), 2 * 10**17, 0, 0, 0])
    receipt = {
        "blockNumber": 99,
        "logs": [
            {
                "address": V1["pool"],
                "topics": [SWAP_TOPIC],
                "data": data,
            }
        ],
    }
    found = decode_target_trades(tx=_tx(), receipt=receipt, launches=FakeLaunches(V1))
    assert len(found) == 1
    trade, launch = found[0]
    assert trade["side"] == "buy"
    assert trade["venue"] == "v1-pool"
    assert trade["quoteAmountWei"] == str(2 * 10**17)
    assert launch["symbol"] == "PONS"


def test_curve_buy_and_sell() -> None:
    buy_data = encode(["uint256", "uint256", "uint256"], [10**17, 5000, 1])
    sell_data = encode(["uint256", "uint256", "uint256"], [4000, 8 * 10**16, 1])
    receipt = {
        "blockNumber": 101,
        "logs": [
            {"address": V2["curve"], "topics": [CURVE_BUY_TOPIC], "data": buy_data},
            {"address": V2["curve"], "topics": [CURVE_SELL_TOPIC], "data": sell_data},
        ],
    }
    found = decode_target_trades(tx=_tx(), receipt=receipt, launches=FakeLaunches(V2))
    assert [row[0]["side"] for row in found] == ["buy", "sell"]
    assert found[0][0]["quoteAmountWei"] == str(10**17)
    assert found[1][0]["tokenAmount"] == "4000"
