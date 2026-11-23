"""A long-only momentum bot for cbBTC on the make.fun bars replay.

The bot reads one 1-minute bar of CBBTC per batch and answers with at most
one order. It holds at most one full-size long position:

- It buys with all available cash when the close has risen more than 30 bps
  over the close two bars earlier (a 2-bar momentum burst).
- It sells the whole position when that 2-bar return turns below -20 bps,
  or when the close drops 100 bps under the price the entry filled at
  (a stop loss that caps how far a bad entry can run).

Orders decided on one bar fill at the next bar's open, so every signal is
judged on closes already seen and nothing peeks at the bar being filled
against. The bot is deterministic: only the standard library, no clock,
no network, no randomness, and every amount is integer arithmetic, so two
runs on the same bars send the same orders.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
# 2-bar return above this (in basis points) opens the long.
ENTRY_BPS = 30
# 2-bar return below this closes the long.
EXIT_BPS = -20
# Close this far (in basis points) under the entry fill closes the long.
STOP_BPS = 100
# Slippage allowance on every order, measured from the latest close.
MAX_SLIPPAGE_BPS = 100
# Smallest buy the replay accepts, in quote units (1 USDC).
MIN_NOTIONAL = 1_000_000
BPS = 10_000


class MomentumBot:
    """Keeps the last closes and the fill price of the open long."""

    def __init__(self):
        # Last three closes, oldest first; only bars actually seen go in.
        self.closes = []
        # Fill price (price-scale ints) of the open long, or None.
        self.entry_fill = None

    def _learn_fills(self, batch):
        """Fold this batch's fills into the entry price."""
        for fill in batch.get("fills", []):
            if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
                continue
            if fill.get("side") == "buy":
                self.entry_fill = int(fill["price"])
            elif fill.get("side") == "sell":
                self.entry_fill = None

    def _two_bar_return_bps(self):
        """Return of the latest close against the close two bars back, in bps.

        Exact integer comparison form: the caller compares the returned
        numerator against a threshold times the base close, so no division
        bias ever moves a signal. Returns None until three closes are seen.
        """
        if len(self.closes) < 3:
            return None
        now = self.closes[-1]
        base = self.closes[-3]
        if base <= 0:
            return None
        return (now - base, base)

    def _above(self, pair, bps):
        """True when the return pair is strictly above bps basis points."""
        if pair is None:
            return False
        diff, base = pair
        return diff * BPS > bps * base

    def _below(self, pair, bps):
        """True when the return pair is strictly below bps basis points."""
        if pair is None:
            return False
        diff, base = pair
        return diff * BPS < bps * base

    def _entry_price(self, state, holding):
        """The price the open long was bought at, for the stop loss.

        Normally the fill's own price, learned from the batch that reports
        it. If that record were ever missed, the position's cost basis
        gives the same number: cost per unit at the symbol's scales.
        """
        if self.entry_fill is not None:
            return self.entry_fill
        if holding is None or holding.qty <= 0:
            return None
        symbol = state.symbols.get(SYMBOL)
        if symbol is None:
            return None
        scale = 10 ** (symbol["qty_scale"] + symbol["price_scale"])
        quote = 10 ** state.hello["capital"]["quote_scale"]
        return holding.cost * scale // (holding.qty * quote)

    def on_batch(self, state, batch):
        self._learn_fills(batch)

        # A minute with no bar for the symbol: no decision, state kept.
        bar = None
        for candidate in batch.get("bars", []):
            if candidate.get("symbol") == SYMBOL:
                bar = candidate
                break
        if bar is None:
            return []

        close = int(bar["c"])
        self.closes.append(close)
        if len(self.closes) > 3:
            self.closes.pop(0)

        # Warm-up bars exist to build history; no order may trade on them.
        if state.warming_up:
            return []

        holding = state.positions.get(SYMBOL)
        holding_qty = holding.qty if holding is not None else 0
        ret = self._two_bar_return_bps()

        if holding_qty > 0:
            # Exit: momentum turned, or the stop loss tripped.
            if self._below(ret, EXIT_BPS):
                return [self._sell_all(holding_qty)]
            entry_price = self._entry_price(state, holding)
            if entry_price is not None and close * BPS < entry_price * (BPS - STOP_BPS):
                return [self._sell_all(holding_qty)]
            return []

        # Flat: enter on a 2-bar burst, with everything on hand.
        if self._above(ret, ENTRY_BPS) and state.cash >= MIN_NOTIONAL:
            return [
                {
                    "side": "buy",
                    "symbol": SYMBOL,
                    "notional_quote_units": state.cash,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            ]
        return []

    def _sell_all(self, qty):
        return {
            "side": "sell",
            "symbol": SYMBOL,
            "qty": qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }


def main():
    makefun_bars.run(MomentumBot().on_batch)


if __name__ == "__main__":
    main()
