"""
Position Manager per spec.
Tracks entry, stop-loss, target. Two-leg GTT (Good Till Triggered) for SL + Target
is set at order placement (stub when broker does not support GTT).
"""
from config.settings import TRAIL_FACTOR


class PositionManager:
    def __init__(self):
        self.active = False
        self.entry = 0
        self.sl = 0
        self.target = 0  # per spec: two-leg GTT SL + Target
        self.qty = 0
        self.side = None  # "CE" or "PE"
        self._realized_pnl = 0  # for risk governor daily PnL

    def enter(self, price, stop_distance, qty, side="CE", target_ratio=1.5):
        """
        Enter position. target_ratio = target distance / stop distance (e.g. 1.5R).
        Two-leg GTT (SL + Target) should be placed by execution layer after order.
        """
        self.active = True
        self.entry = price
        self.qty = qty
        self.side = side
        if side == "CE":
            self.sl = price - stop_distance
            self.target = price + (stop_distance * target_ratio)
        else:
            self.sl = price + stop_distance
            self.target = price - (stop_distance * target_ratio)

    def trail(self, price):
        """Trailing stop: move SL in favor (CE: raise SL when price rises; PE: lower SL when price falls)."""
        if not self.active:
            return
        if self.side == "CE" or self.side is None:
            new_sl = price * 0.99
            if new_sl > self.sl:
                self.sl = new_sl
        else:
            new_sl = price * 1.01
            if new_sl < self.sl:
                self.sl = new_sl

    def exit_check(self, price):
        """
        Check SL hit or target hit. Returns True if position should be closed.
        """
        if not self.active:
            return False
        if self.side == "CE" or self.side is None:
            if price <= self.sl:
                self.active = False
                return True
            if self.target and price >= self.target:
                self.active = False
                return True
        else:
            if price >= self.sl:
                self.active = False
                return True
            if self.target and price <= self.target:
                self.active = False
                return True
        return False

    def set_realized_pnl(self, pnl):
        self._realized_pnl = pnl

    @property
    def unrealized_pnl(self):
        """Stub: would need current price and side."""
        return 0
