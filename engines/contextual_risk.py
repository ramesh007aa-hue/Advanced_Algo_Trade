"""
Contextualization and Adaptive Risk per spec.
VIX Regime: ULTRA_LOW, NORMAL_LOW, SPIKING, PANIC -> adaptive AI confidence threshold.
Market Phase: OPENING_VOLATILITY, MIDDAY_LULL -> decision interval and threshold penalty.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config.settings import (
    VIX_ULTRA_LOW,
    VIX_NORMAL_LOW,
    VIX_SPIKING,
    VIX_PANIC,
    CONFIDENCE_ULTRA_LOW,
    CONFIDENCE_NORMAL_LOW,
    CONFIDENCE_SPIKING,
    CONFIDENCE_PANIC,
    CONFIDENCE_FALLBACK,
    DECISION_INTERVAL_HIGH_VOL,
    DECISION_INTERVAL_LOW_VOL,
    OPENING_VOLATILITY_THRESHOLD_PCT,
    MARKET_OPEN_HOUR,
    MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR,
    MARKET_CLOSE_MINUTE,
)

IST = ZoneInfo("Asia/Kolkata")


def vix_regime(vix):
    """Classify market as ULTRA_LOW, NORMAL_LOW, SPIKING, or PANIC based on India VIX."""
    if vix is None:
        return "NORMAL_LOW"
    if vix <= VIX_ULTRA_LOW:
        return "ULTRA_LOW"
    if vix <= VIX_NORMAL_LOW:
        return "NORMAL_LOW"
    if vix <= VIX_SPIKING:
        return "SPIKING"
    return "PANIC"


def required_confidence(vix_regime_name):
    """Required AI confidence threshold by VIX regime (e.g. 75% ULTRA_LOW to 55% PANIC)."""
    return {
        "ULTRA_LOW": CONFIDENCE_ULTRA_LOW,
        "NORMAL_LOW": CONFIDENCE_NORMAL_LOW,
        "SPIKING": CONFIDENCE_SPIKING,
        "PANIC": CONFIDENCE_PANIC,
    }.get(vix_regime_name, CONFIDENCE_NORMAL_LOW)


def market_phase():
    """Classify time of day: OPENING_VOLATILITY, MIDDAY_LULL, etc."""
    now = datetime.now(IST).time()
    open_t = datetime.strptime(
        f"{MARKET_OPEN_HOUR:02d}:{MARKET_OPEN_MINUTE:02d}", "%H:%M"
    ).time()
    # Opening volatility: first 30 min
    open_end = (datetime.combine(datetime.today(), open_t) + timedelta(minutes=30)).time()
    close_t = datetime.strptime(
        f"{MARKET_CLOSE_HOUR:02d}:{MARKET_CLOSE_MINUTE:02d}", "%H:%M"
    ).time()
    if open_t <= now <= open_end:
        return "OPENING_VOLATILITY"
    if open_end < now < close_t:
        return "MIDDAY_LULL"
    return "CLOSED_OR_PREOPEN"


def decision_interval_seconds(vix_regime_name, phase):
    """Decision interval: e.g. 90s high vol, 240s low volume; 90s in opening volatility."""
    if phase == "OPENING_VOLATILITY":
        return DECISION_INTERVAL_HIGH_VOL
    if vix_regime_name in ("SPIKING", "PANIC"):
        return DECISION_INTERVAL_HIGH_VOL
    return DECISION_INTERVAL_LOW_VOL


def threshold_penalty_pct(phase):
    """e.g. +10% threshold penalty in opening volatility."""
    if phase == "OPENING_VOLATILITY":
        return OPENING_VOLATILITY_THRESHOLD_PCT
    return 0


def is_market_hours():
    """Trade within 9:20 AM - 3:28 PM IST (per spec)."""
    now = datetime.now(IST).time()
    open_t = datetime.strptime(
        f"{MARKET_OPEN_HOUR:02d}:{MARKET_OPEN_MINUTE:02d}", "%H:%M"
    ).time()
    close_t = datetime.strptime(
        f"{MARKET_CLOSE_HOUR:02d}:{MARKET_CLOSE_MINUTE:02d}", "%H:%M"
    ).time()
    return open_t <= now <= close_t
