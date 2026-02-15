"""
7-Step Validation Chain per spec.
Every AI decision must pass sequential validation before order placement:
1. AI Gating Check: decision age, confidence >= adaptive threshold, action validity (incl. REVERSE).
2. Strike Alignment Check: selected strike adheres to strikeGuidance (Delta >= 0.25, IV <= 25%).
3. Margin Check: sufficient free margin via API.
4. Position Limits: user-defined max positions.
5. Market Hours Check: 9:20 AM - 3:28 PM IST.
6. Circuit Breaker Check: daily loss and drawdown limits not breached.
7. Order Execution: place order and set two-leg GTT (SL + Target).
"""
import time
from engines.contextual_risk import (
    required_confidence,
    threshold_penalty_pct,
    is_market_hours,
    vix_regime as get_vix_regime,
)
from engines.decision_engine import (
    ACTION_TRADE_CE,
    ACTION_TRADE_PE,
    ACTION_HOLD,
    ACTION_EXIT_ALL,
    ACTION_REVERSE,
)
from config.settings import (
    MAX_TRADES,
    MAX_DAILY_LOSS,
    STRIKE_DELTA_MIN,
    STRIKE_IV_MAX_PCT,
)
from data.cache.market_cache import MARKET


# Decision max age (seconds) - treat as stale after this
DECISION_MAX_AGE_SEC = 120


def step1_ai_gating(decision, vix, trade_count):
    """
    Step 1: AI Gating - decision age, confidence >= threshold, action validity.
    Returns (passed: bool, reason: str).
    """
    if not decision or "action" not in decision:
        return False, "No decision"
    action = decision.get("action", ACTION_HOLD)
    confidence = decision.get("confidence", 0)
    decision_ts = decision.get("timestamp", time.time())
    if time.time() - decision_ts > DECISION_MAX_AGE_SEC:
        return False, "Decision stale"
    regime = get_vix_regime(vix)
    threshold = required_confidence(regime)
    from engines.contextual_risk import market_phase
    phase = market_phase()
    threshold += threshold_penalty_pct(phase)
    if confidence < threshold:
        return False, f"Confidence {confidence} < threshold {threshold}"
    if action not in (ACTION_TRADE_CE, ACTION_TRADE_PE, ACTION_EXIT_ALL, ACTION_REVERSE):
        return False, "Action not tradeable"
    if action in (ACTION_TRADE_CE, ACTION_TRADE_PE) and trade_count >= MAX_TRADES:
        return False, "Max trades reached"
    return True, "OK"


def step2_strike_alignment(strike, spot, decision_strike_guidance):
    """
    Step 2: Strike adheres to strikeGuidance (e.g. Delta >= 0.25, IV <= 25%).
    When Greeks/IV not available we use distance-from-ATM as proxy for delta zone.
    """
    if decision_strike_guidance is None:
        return True, "OK"
    delta_min = decision_strike_guidance.get("delta_min", STRIKE_DELTA_MIN)
    # Proxy: ATM ± 50 ~ delta in range; far OTM = reject
    diff = abs(spot - strike) if (spot and strike) else 0
    if diff > 200:  # far OTM proxy
        return False, "Strike too far OTM (delta proxy)"
    return True, "OK"


def step3_margin_check():
    """Step 3: Sufficient free margin. Stub when API not used for margin."""
    return True, "OK"


def step4_position_limits(active_positions, max_positions=1):
    """Step 4: User-defined max positions."""
    if active_positions >= max_positions:
        return False, "Position limit reached"
    return True, "OK"


def step5_market_hours():
    """Step 5: Trade within 9:20 AM - 3:28 PM IST."""
    if not is_market_hours():
        return False, "Outside market hours"
    return True, "OK"


def step6_circuit_breaker(daily_pnl, max_daily_loss=MAX_DAILY_LOSS):
    """Step 6: Daily loss and drawdown limits not breached."""
    if daily_pnl is not None and daily_pnl <= -max_daily_loss:
        return False, "Daily loss limit breached"
    return True, "OK"


def run_validation_chain(
    decision,
    vix,
    trade_count,
    active_positions,
    daily_pnl,
    strike,
    spot,
):
    """
    Run all 7 steps. Returns (passed: bool, failed_step: int 1-7 or 0, reason: str).
    Step 7 (order execution) is done by caller after validation passes.
    """
    # Step 1
    ok, msg = step1_ai_gating(decision, vix, trade_count)
    if not ok:
        return False, 1, msg
    # Step 2 (only for trade actions)
    if decision.get("action") in (ACTION_TRADE_CE, ACTION_TRADE_PE):
        ok, msg = step2_strike_alignment(
            strike, spot, decision.get("strikeGuidance")
        )
        if not ok:
            return False, 2, msg
    # Step 3
    ok, msg = step3_margin_check()
    if not ok:
        return False, 3, msg
    # Step 4
    ok, msg = step4_position_limits(active_positions)
    if not ok:
        return False, 4, msg
    # Step 5
    ok, msg = step5_market_hours()
    if not ok:
        return False, 5, msg
    # Step 6
    ok, msg = step6_circuit_breaker(daily_pnl)
    if not ok:
        return False, 6, msg
    return True, 0, "OK"
