"""
Risk Governor per spec.
Circuit breaker: daily loss and drawdown limits.
Failure constraints: block if historical win rate in current conditions < 40% (stub).
Position limits and trade count.
"""
from config.settings import MAX_TRADES, MAX_DAILY_LOSS, MIN_WIN_RATE_PCT


class RiskGovernor:
    def __init__(self, max_trades=MAX_TRADES, max_daily_loss=MAX_DAILY_LOSS):
        self.trades = 0
        self.max_trades = max_trades
        self.max_daily_loss = max_daily_loss
        self.daily_pnl = 0  # running daily P&L (updated by execution layer)
        self._min_win_rate_pct = MIN_WIN_RATE_PCT

    def allow(self, daily_pnl=None):
        """Allow new trade only if under limits. Uses instance daily_pnl if not passed."""
        pnl = daily_pnl if daily_pnl is not None else self.daily_pnl
        if self.trades >= self.max_trades:
            return False
        if pnl is not None and pnl <= -self.max_daily_loss:
            return False
        return True

    def record_trade(self):
        self.trades += 1

    def update_daily_pnl(self, pnl):
        """Update running daily P&L (e.g. from position manager)."""
        self.daily_pnl = pnl

    def circuit_breaker_breached(self, daily_pnl=None):
        pnl = daily_pnl if daily_pnl is not None else self.daily_pnl
        return pnl is not None and pnl <= -self.max_daily_loss

    def failure_constraint_block(self, vix_regime, market_phase):
        """
        Per spec: block if historical win rate in current conditions < 40%.
        Stub: no historical DB; always returns False (do not block).
        """
        # TODO: query historical win rate by vix_regime + market_phase
        return False
