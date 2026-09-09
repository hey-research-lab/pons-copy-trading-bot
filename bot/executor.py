from __future__ import annotations

from typing import Any, TypedDict

from eth_account.signers.local import LocalAccount
from web3 import Web3

from bot.chain import ADDR, CURVE_ABI, QUOTER_ABI, ROUTER_ABI, TOKEN_ABI, WETH_ABI, checksum, require_paid_rpc_for_live
from bot.logger import log
from bot.sizing import apply_slippage, format_ether, quote_curve_buy, quote_curve_sell
from bot.types import CopyTrade, LaunchRecord


class ExecutionResult(TypedDict):
    hash: str | None
    amountOut: int
    minOut: int
    paper: bool


class Executor:
    def __init__(self, w3: Web3, account: LocalAccount | None, send_w3: Web3 | None = None) -> None:
        self.w3 = w3
        self.send_w3 = send_w3 or w3
        self.account = account

    def execute(
        self,
        *,
        trade: CopyTrade,
        launch: LaunchRecord,
        amount_in: int,
        slippage_bps: int,
        dry_run: bool,
    ) -> ExecutionResult:
        if not dry_run:
            require_paid_rpc_for_live()
        if launch.get("version") == 2:
            return self._execute_v2(trade, launch, amount_in, slippage_bps, dry_run)
        return self._execute_v1(trade, launch, amount_in, slippage_bps, dry_run)

    def _execute_v1(
        self,
        trade: CopyTrade,
        launch: LaunchRecord,
        amount_in: int,
        slippage_bps: int,
        dry_run: bool,
    ) -> ExecutionResult:
        token_in = ADDR["weth"] if trade["side"] == "buy" else checksum(trade["token"])
        token_out = checksum(trade["token"]) if trade["side"] == "buy" else ADDR["weth"]
        fee = int(launch.get("poolFee") or 10_000)
        quoted = self._quote_v3(token_in, token_out, amount_in, fee)
        min_out = apply_slippage(quoted, slippage_bps)

        if dry_run or not self.account:
            log.info(f"paper {trade['side']} {trade['symbol']} in={format_ether(amount_in)} quotedOut={quoted}")
            return {"hash": None, "amountOut": quoted, "minOut": min_out, "paper": True}

        if trade["side"] == "sell":
            self._approve(trade["token"], ADDR["swapRouter02"], amount_in)
        else:
            self._ensure_weth(amount_in)
            self._approve(ADDR["weth"], ADDR["swapRouter02"], amount_in)

        router = self.w3.eth.contract(address=ADDR["swapRouter02"], abi=ROUTER_ABI)
        tx_hash = self._send(
            router.functions.exactInputSingle(
                (
                    token_in,
                    token_out,
                    fee,
                    self.account.address,
                    amount_in,
                    min_out,
                    0,
                )
            )
        )
        if trade["side"] == "sell":
            self._unwrap_all()
        return {"hash": tx_hash, "amountOut": quoted, "minOut": min_out, "paper": False}

    def _execute_v2(
        self,
        trade: CopyTrade,
        launch: LaunchRecord,
        amount_in: int,
        slippage_bps: int,
        dry_run: bool,
    ) -> ExecutionResult:
        curve_addr = launch.get("curve")
        if not curve_addr:
            raise RuntimeError("missing curve")
        curve = self.w3.eth.contract(address=checksum(curve_addr), abi=CURVE_ABI)
        reserves = curve.functions.getReserves().call()
        fee_bps = int(curve.functions.feeBps().call())
        tax_bps = int(curve.functions.creatorTaxBps().call())
        native = bool(curve.functions.isNativeQuote().call())
        total_fee = fee_bps + tax_bps
        quoted = (
            quote_curve_buy(amount_in, int(reserves[0]), int(reserves[1]), total_fee)
            if trade["side"] == "buy"
            else quote_curve_sell(amount_in, int(reserves[0]), int(reserves[1]), total_fee)
        )
        min_out = apply_slippage(quoted, slippage_bps)

        if dry_run or not self.account:
            return {"hash": None, "amountOut": quoted, "minOut": min_out, "paper": True}

        if trade["side"] == "buy":
            if not native:
                self._approve(launch["pairToken"], curve_addr, amount_in)
            tx_hash = self._send(
                curve.functions.buy(amount_in, min_out, self.account.address),
                value=amount_in if native else 0,
            )
            return {"hash": tx_hash, "amountOut": quoted, "minOut": min_out, "paper": False}

        self._approve(trade["token"], curve_addr, amount_in)
        tx_hash = self._send(curve.functions.sell(amount_in, min_out, self.account.address))
        return {"hash": tx_hash, "amountOut": quoted, "minOut": min_out, "paper": False}

    def _quote_v3(self, token_in: str, token_out: str, amount_in: int, fee: int) -> int:
        quoter = self.w3.eth.contract(address=ADDR["quoterV2"], abi=QUOTER_ABI)
        result = quoter.functions.quoteExactInputSingle((token_in, token_out, amount_in, fee, 0)).call()
        return int(result[0])

    def _approve(self, token: str, spender: str, amount: int) -> None:
        if not self.account:
            return
        token_c = checksum(token)
        spender_c = checksum(spender)
        contract = self.w3.eth.contract(address=token_c, abi=TOKEN_ABI)
        allowance = int(contract.functions.allowance(self.account.address, spender_c).call())
        if allowance >= amount:
            return
        self._send(contract.functions.approve(spender_c, amount))

    def _ensure_weth(self, amount: int) -> None:
        if not self.account:
            return
        weth = self.w3.eth.contract(address=ADDR["weth"], abi=WETH_ABI)
        bal = int(weth.functions.balanceOf(self.account.address).call())
        if bal >= amount:
            return
        self._send(weth.functions.deposit(), value=amount - bal)

    def _unwrap_all(self) -> None:
        if not self.account:
            return
        weth = self.w3.eth.contract(address=ADDR["weth"], abi=WETH_ABI)
        bal = int(weth.functions.balanceOf(self.account.address).call())
        if bal == 0:
            return
        self._send(weth.functions.withdraw(bal))

    def _send(self, fn: Any, value: int = 0) -> str:
        if not self.account:
            raise RuntimeError("wallet required")
        nonce = self.send_w3.eth.get_transaction_count(self.account.address, "pending")
        tx = fn.build_transaction(
            {
                "from": self.account.address,
                "value": value,
                "nonce": nonce,
                "chainId": self.send_w3.eth.chain_id,
            }
        )
        signed = self.account.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        tx_hash = self.send_w3.eth.send_raw_transaction(raw)
        receipt = self.send_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        hex_hash = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
        if not hex_hash.startswith("0x"):
            hex_hash = "0x" + hex_hash
        if int(receipt["status"]) != 1:
            raise RuntimeError(f"tx reverted {hex_hash}")
        return hex_hash
