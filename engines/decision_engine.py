"""
AI Decision Engine (per spec).
Output: action (TRADE_CE, TRADE_PE, HOLD, EXIT_ALL, REVERSE), confidence (0-100),
reasoning, strikeGuidance (e.g. Delta >= 0.25, IV <= 25%).
Safety fallback: on failure -> HOLD, 50% confidence (below execution threshold).
Rule-based implementation; can be replaced by GPT-4o-mini with same schema.
"""
from config.settings import CONFIDENCE_FALLBACK


# Valid actions per spec
ACTION_TRADE_CE = "TRADE_CE"
ACTION_TRADE_PE = "TRADE_PE"
ACTION_HOLD = "HOLD"
ACTION_EXIT_ALL = "EXIT_ALL"
ACTION_REVERSE = "REVERSE"


def strike_guidance(delta_min=0.25, iv_max_pct=25):
    """Strike alignment guidance per spec: Delta >= 0.25, IV <= 25%."""
    return {"delta_min": delta_min, "iv_max_pct": iv_max_pct}


def rule_based_decision(
    context,
    participation,
    vol_status,
    decay_ok,
    bull,
    bear,
    combined_score_val,
    pdr_penalty_val,
):
    """
    Rule-based decision matching spec schema.
    Returns dict: action, confidence (0-100), reasoning, strikeGuidance.
    """
    try:
        # Strong PDR penalty -> HOLD or EXIT
        if pdr_penalty_val <= -5:
            return {
                "action": ACTION_HOLD,
                "confidence": 45,
                "reasoning": "PDR penalty high; theta/IV crush risk.",
                "strikeGuidance": strike_guidance(),
            }
        if combined_score_val is not None and combined_score_val < 30:
            return {
                "action": ACTION_HOLD,
                "confidence": 50,
                "reasoning": "Combined score below threshold.",
                "strikeGuidance": strike_guidance(),
            }
        # BUY -> TRADE_CE
        if (
            context == "UPTREND"
            and participation is not None
            and participation > 0.6
            and vol_status == "SUPPORTIVE"
            and decay_ok
            and bull
        ):
            return {
                "action": ACTION_TRADE_CE,
                "confidence": 72,
                "reasoning": "Uptrend, strong participation, supportive VIX, decay ok, price above VWAP.",
                "strikeGuidance": strike_guidance(),
            }
        # SELL -> TRADE_PE
        if (
            context == "DOWNTREND"
            and participation is not None
            and participation < 0.4
            and vol_status == "SUPPORTIVE"
            and decay_ok
            and bear
        ):
            return {
                "action": ACTION_TRADE_PE,
                "confidence": 72,
                "reasoning": "Downtrend, weak participation, supportive VIX, decay ok, price below VWAP.",
                "strikeGuidance": strike_guidance(),
            }
        # Default
        return {
            "action": ACTION_HOLD,
            "confidence": 50,
            "reasoning": "No clear signal; conditions not met.",
            "strikeGuidance": strike_guidance(),
        }
    except Exception:
        return {
            "action": ACTION_HOLD,
            "confidence": CONFIDENCE_FALLBACK,
            "reasoning": "Decision engine fallback (error).",
            "strikeGuidance": strike_guidance(),
        }
