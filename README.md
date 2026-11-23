[![make.fun](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Riial/makefun-btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Riial/makefun-btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)

# BTC momentum bot — btc-race-24h-20261123-0511

A long-only momentum bot that trades Coinbase Wrapped BTC (cbBTC) against
USDC on 1-minute bars, built for make.fun's
["Race a BTC trading bot live for 24 hours" bounty](https://make.fun/bounty/btc-race-24h-20261123-0511).
It starts with $1,000 of paper money and races only if it made money on the
dev window.

## Strategy

One full-size long position at a time, decided on each bar's close and
filled at the next bar's open:

- **Enter:** buy with all available cash when the close is more than
  **30 bps** above the close two bars earlier (a 2-bar momentum burst).
- **Exit:** sell the whole position when that 2-bar return turns below
  **-20 bps**, or when the close falls **100 bps** under the price the
  entry filled at (stop loss).
- Every order carries `max_slippage_bps = 100` and at most one order is
  sent per reply.

A full round trip costs about 26 bps in fees, slippage and pool impact,
so a trade has to catch a move larger than that — the 30 bps entry bar is
set just above it.

## Files

- `main.py` — the bot. Standard library only, deterministic (no clock, no
  network, no randomness, integer arithmetic throughout), so two runs on
  the same bars send identical orders.
- `vendor/makefun_bars.py` — byte-identical copy of the kit's Python shim
  for the `agent-fun/bars-replay/v1` protocol.

## Grade locally

From the inner kit directory:

```sh
node cli/makefun.mjs grade-local --kit . --bot /path/to/this/repo --driver process
```

It replays the frozen 24-hour dev window (1,440 one-minute bars) and
reports net PnL, trades, max drawdown and whether the guardrails are met.
