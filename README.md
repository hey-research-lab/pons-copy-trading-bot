# pons.family copy trader (Robinhood Chain)

Python bot that watches leader wallets on **Robinhood Chain** (chain id `4663`) and copies their [pons.family](https://www.ponsfamily.com) fills.

It is **not** Robinhood brokerage Social copy-trading and **not** an official Pons or Robinhood product. Every live fill spends ETH from *your* wallet. Tokens can go to zero.

## What it copies

| Venue | How a leader fill is seen | How the bot copies |
| --- | --- | --- |
| Pons V1 | Uniswap V3 `Swap` on the launch pool | `SwapRouter02.exactInputSingle` (WETH pairs) |
| Pons V2 | Bonding-curve `CurveBuy` / `CurveSell` | `curve.buy` / `curve.sell` |

Graduated V2 Uniswap v4 routing is not enabled. Non-WETH quote assets (USDG, tokenized stocks) are skipped.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m bot.smoke
python -m bot
```

Dashboard: [http://127.0.0.1:8787](http://127.0.0.1:8787)

`DRY_RUN=true` (default) paper-trades only. Leave `PRIVATE_KEY` empty for watch-only mode.

Live fills require a **paid RPC**. The public endpoint is rate-limited and will be rejected when `DRY_RUN=false`.

Paste an Alchemy key (Robinhood's recommended provider) or any HTTPS RPC:

```
ALCHEMY_API_KEY=your_alchemy_key
DRY_RUN=false
PRIVATE_KEY=0x...
```

That expands to:

- HTTP `https://robinhood-mainnet.g.alchemy.com/v2/{key}`
- WSS `wss://robinhood-mainnet.g.alchemy.com/v2/{key}` (`newHeads` for faster copies)

QuickNode / Chainstack / dRPC work the same way via `PAID_RPC_URL` and `WS_URL`. Public RPC stays as a read failover only. Broadcasts never go through the public node.

Create an Alchemy app: [dashboard.alchemy.com](https://dashboard.alchemy.com) → Robinhood Chain mainnet (4663).

## Follow a wallet

Add leaders in the dashboard, or seed `.env`:

```
TARGET_WALLETS=0xLeaderOne...,0xLeaderTwo...
```

The watcher polls new blocks, keeps transactions from those addresses, and decodes Pons V1/V2 events from the receipt.

## Risk controls

- percent-of-leader or fixed ETH buy size
- per-trade and daily ETH caps
- min leader size / min V1 pool WETH depth
- launch-protection skip window
- cooldown between copies
- token blacklist
- mirror or flatten on sells
- slippage on quotes

State lives in `data/store.json` (shared schema with the TypeScript bot if you still run that).

## Commands

| Command | Purpose |
| --- | --- |
| `python -m bot` | watcher + dashboard |
| `python -m bot.smoke` | RPC + PONS token sanity check |
| `python -m bot.replay` | decode a recent PONS pool swap |
| `pytest` | sizing / risk / event decode tests |

Optional React UI (same API): `npm install` then `npm run dev:web` while the Python bot is on port `8787`.

## Contracts (Robinhood Chain)

- V1 factory `0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB`
- V1 legacy factory `0x0c37a24F5D23A486FA692d1500881d698B1F77a4`
- V2 factory `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e`
- WETH `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`
- SwapRouter02 `0xCaf681a66D020601342297493863E78C959E5cb2`

RPC: paid provider for live trading (Alchemy / QuickNode / Chainstack / dRPC); public `https://rpc.mainnet.chain.robinhood.com` is fallback for reads only. 
Explorer: [robinhoodchain.blockscout.com](https://robinhoodchain.blockscout.com)

This is software for your own wallet. It is not financial advice.
