"""
Metrics Calculation Layer per spec.
Combined Score = (Leading Score × 0.65) + (Lagging Score × 0.35) + PDR Penalty
Leading: VIX momentum, OI dynamics, volume impulse, IVS, LMS, VWAP factor (max 65).
Lagging: RSI(14), MA crossover 9/21, Historical Volatility (max 35).
PDR Penalty: 0 to -10 (premium decay over 5 min).
"""
import time
from data.cache.market_cache import MARKET


def rsi(prices, period=14):
    """RSI(14) for lagging score."""
    if len(prices) < period + 1:
        return 50.0  # neutral
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def ma_crossover_score(prices, fast=9, slow=21):
    """MA crossover 9/21: bullish = positive score component (0-~12 of lagging)."""
    if len(prices) < slow:
        return 0.5  # neutral
    ma_fast = sum(prices[-fast:]) / fast
    ma_slow = sum(prices[-slow:]) / slow
    if ma_fast > ma_slow:
        return 1.0  # bullish
    return 0.0  # bearish or neutral


def historical_volatility(prices, period=20):
    """Simple historical volatility (annualized proxy) for lagging."""
    if len(prices) < period + 1:
        return 0.0
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
    if not returns:
        return 0.0
    import math
    mean_ret = sum(returns[-period:]) / min(period, len(returns))
    variance = sum((r - mean_ret) ** 2 for r in returns[-period:]) / min(period, len(returns))
    return math.sqrt(variance * 252) * 100 if variance > 0 else 0.0


def leading_score(vix_momentum, participation, volume_impulse, ivs_score, lms_score, vwap_bull):
    """
    Leading Score max 65: VIX momentum, OI dynamics (participation), volume impulse,
    IVS (0-15), LMS (0-10), VWAP factor. Normalized to 0-65.
    """
    # Simple weighting: participation ~15, vix_momentum ~10, volume_impulse ~10, ivs ~15, lms ~10, vwap ~5
    part_pts = min(15, participation * 15) if participation is not None else 7.5
    vix_pts = 10 if vix_momentum == "SUPPORTIVE" else 5
    vol_pts = min(10, volume_impulse * 0.1) if volume_impulse is not None else 5
    ivs_pts = min(15, ivs_score) if ivs_score is not None else 7.5
    lms_pts = min(10, lms_score) if lms_score is not None else 5
    vwap_pts = 5 if vwap_bull else 0
    return part_pts + vix_pts + vol_pts + ivs_pts + lms_pts + vwap_pts


def lagging_score(rsi_val, ma_bull, hv_normalized):
    """Lagging Score max 35: RSI, MA crossover, HV. Normalized to 0-35."""
    # RSI: 0-70 bullish zone good; 30-50 neutral
    rsi_pts = 12 if rsi_val is not None and 40 <= rsi_val <= 70 else 6
    ma_pts = 12 if ma_bull else 0
    hv_pts = min(11, hv_normalized) if hv_normalized is not None else 5
    return rsi_pts + ma_pts + hv_pts


def pdr_penalty(option_ltp_history_5min):
    """
    PDR Penalty 0 to -10: percentage drop in option LTP over last 5 minutes.
    High decay -> strong penalty -> HOLD/EXIT.
    """
    if not option_ltp_history_5min or len(option_ltp_history_5min) < 2:
        return 0
    _, ltp_old = option_ltp_history_5min[0]
    _, ltp_new = option_ltp_history_5min[-1]
    if ltp_old <= 0:
        return 0
    pct_drop = (ltp_old - ltp_new) / ltp_old
    # Map to 0 .. -10: e.g. 20% drop -> -4, 50% -> -10
    penalty = -min(10, int(pct_drop * 25))
    return penalty


def lms_score(depth_history_5min):
    """
    Liquidity Momentum Score 0-10: rate of change in 5-level depth over last 5 min.
    Positive = institutional liquidity inflow.
    """
    if not depth_history_5min or len(depth_history_5min) < 2:
        return 5.0  # neutral
    # Use spread narrowing as proxy for liquidity improvement
    spreads = [s for (_, _, _, s) in depth_history_5min if s is not None]
    if len(spreads) < 2:
        return 5.0
    old_avg = sum(spreads[: len(spreads) // 2]) / (len(spreads) // 2)
    new_avg = sum(spreads[len(spreads) // 2 :]) / (len(spreads) - len(spreads) // 2)
    if old_avg <= 0:
        return 5.0
    change = (old_avg - new_avg) / old_avg  # narrowing = positive
    return max(0, min(10, 5 + change * 50))


def ivs_score_stub():
    """
    IV Skew (IVS) 0-15: back-solving IV from OTM call/put LTP (Black-Scholes).
    High IV_call > IV_put = bullish options bias. Stub when no option chain.
    """
    # Stub: when we have option chain we can compute; for now return neutral
    return 7.5


def combined_score(
    leading_pts,
    lagging_pts,
    pdr_penalty_val,
):
    """Combined Score = (Leading × 0.65) + (Lagging × 0.35) + PDR Penalty (per spec)."""
    max_leading = 65
    max_lagging = 35
    lead_n = min(max_leading, leading_pts) / max_leading
    lag_n = min(max_lagging, lagging_pts) / max_lagging
    return (lead_n * 0.65 + lag_n * 0.35) * 100 + pdr_penalty_val
