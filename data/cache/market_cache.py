"""
Market cache for Options Oracle.
Holds spot, VIX, option chain (LTP, OI), and time-series for PDR/LMS per spec.
"""
from collections import deque
import time

# 5 min of 1s ticks ≈ 300; keep last 300 for PDR/LMS (5 min window)
PDR_LMS_WINDOW = 300


class MarketCache:
    def __init__(self):
        self.spot = None
        self.vix = None
        self.heavy = {}  # symbol -> LTP (for participation)
        self.option_chain = {}  # token -> { ltp, oi, depth, ... }
        # Put/Call OI for PCR (when available)
        self.put_oi_total = 0
        self.call_oi_total = 0
        # Time-series for PDR (premium decay) and LMS (liquidity momentum)
        self._option_ltp_history = {}  # token -> deque of (ts, ltp)
        self._depth_history = deque(maxlen=PDR_LMS_WINDOW)  # (ts, best_bid, best_ask, spread)

    def update_spot(self, price):
        self.spot = price

    def update_vix(self, vix):
        self.vix = vix

    def update_heavy(self, symbol, price):
        self.heavy[symbol] = price

    def update_option(self, token, tick):
        """Update option tick; maintain LTP history for PDR."""
        self.option_chain[token] = tick
        ltp = tick.get("last_traded_price") or tick.get("ltp")
        if ltp is not None:
            if token not in self._option_ltp_history:
                self._option_ltp_history[token] = deque(maxlen=PDR_LMS_WINDOW)
            self._option_ltp_history[token].append((time.time(), ltp))
        # Depth if present (for LMS)
        depth = tick.get("depth") or tick.get("market_depth")
        if depth:
            best_bid = depth.get("buy", [{}])[0].get("price", 0) if isinstance(depth.get("buy"), list) else 0
            best_ask = depth.get("sell", [{}])[0].get("price", 0) if isinstance(depth.get("sell"), list) else 0
            spread = best_ask - best_bid if (best_bid and best_ask) else 0
            self._depth_history.append((time.time(), best_bid, best_ask, spread))

    def set_oi_totals(self, put_oi, call_oi):
        self.put_oi_total = put_oi
        self.call_oi_total = call_oi

    @property
    def pcr(self):
        """Put-Call Ratio from OI (per spec)."""
        if self.call_oi_total and self.call_oi_total > 0:
            return self.put_oi_total / self.call_oi_total
        return None

    def get_option_ltp_history(self, token, window_sec=300):
        """Last N seconds of LTP for PDR calculation."""
        if token not in self._option_ltp_history:
            return []
        now = time.time()
        return [(t, ltp) for t, ltp in self._option_ltp_history[token] if now - t <= window_sec]

    def get_depth_history(self, window_sec=300):
        """Last N seconds of depth for LMS."""
        now = time.time()
        return [(t, b, a, s) for t, b, a, s in self._depth_history if now - t <= window_sec]


MARKET = MarketCache()
