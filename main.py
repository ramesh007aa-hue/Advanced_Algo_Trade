"""
Options Oracle - Algo Trading System (per Technical Specification).
Multi-layered, event-driven: data -> metrics -> contextual risk -> decision -> 7-step validation -> execution.
"""
import time
import threading
from config.settings import (
    INDEX,
    LOT_SIZE,
    API_KEY,
    CLIENT_ID,
    PASSWORD,
    TOTP_SECRET,
    DECISION_INTERVAL_LOW_VOL,
    LIVE_TRADING,
    OPTION_EXPIRY_DDMMMYY,
)
from data.angel.angel_login import AngelSession
from data.angel.angel_ws import AngelWS
from data.angel.angel_subscribe import AngelSubscribe
from data.cache.market_cache import MARKET

from engines.context import ContextEngine
from engines.participation import ParticipationEngine
from engines.volatility import VolatilityEngine
from engines.decay import DecayEngine
from engines.structure import StructureEngine
from engines.metrics import (
    rsi,
    ma_crossover_score,
    historical_volatility,
    leading_score,
    lagging_score,
    pdr_penalty,
    lms_score,
    ivs_score_stub,
    combined_score as combined_score_fn,
)
from engines.contextual_risk import (
    vix_regime,
    market_phase,
    decision_interval_seconds,
    is_market_hours,
)
from engines.decision_engine import (
    rule_based_decision,
    ACTION_TRADE_CE,
    ACTION_TRADE_PE,
    ACTION_HOLD,
    ACTION_EXIT_ALL,
)

from execution.position_manager import PositionManager
from execution.strike_engine import StrikeEngine
from execution.position_sizer import PositionSizer
from execution.validation_chain import run_validation_chain
from execution.order_manager import OrderManager
from execution.option_symbol import get_option_symbol_token

from risk.risk_governor import RiskGovernor

# ===============================
# 1. LOGIN
# ===============================
session = AngelSession(API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET)
api, jwt, feed = session.login()

# ===============================
# 2. WEBSOCKET (run in background - SmartAPI connect() blocks with run_forever())
# ===============================
ws_engine = AngelWS(jwt, API_KEY, CLIENT_ID, feed)
ws_thread = threading.Thread(target=ws_engine.connect, daemon=True)
ws_thread.start()
# Wait for connection to be established (on_open sets is_connected)
while not ws_engine.is_connected:
    time.sleep(0.2)
print("Connected to WebSocket - started")
subscriber = AngelSubscribe(ws_engine.ws)
subscriber.core()
print("Subscribed to tokens. Strategy loop starting...")

# ===============================
# 3. STRATEGY ENGINES
# ===============================
context_engine = ContextEngine()
participation_engine = ParticipationEngine()
volatility_engine = VolatilityEngine()
decay_engine = DecayEngine()
structure_engine = StructureEngine()

position = PositionManager()
strike_engine = StrikeEngine()
sizer = PositionSizer(capital=200000)
risk = RiskGovernor()
order_manager = OrderManager(api) if LIVE_TRADING else None

# ===============================
# 4. MEMORY & DECISION INTERVAL
# ===============================
prices = []
prev_vix = None
last_decision_ts = 0
decision_interval_sec = DECISION_INTERVAL_LOW_VOL

# ===============================
# 5. MAIN LOOP
# ===============================
print("Options Oracle running (per spec)...")
last_wait_print = 0

while True:
    # -------- WAIT FOR LIVE DATA --------
    if MARKET.spot is None:
        if time.time() - last_wait_print >= 5:
            print("Waiting for market data (Nifty spot token 26000)...")
            last_wait_print = time.time()
        time.sleep(1)
        continue

    # -------- MARKET HOURS --------
    if not is_market_hours():
        time.sleep(10)
        continue

    # -------- PRICE HISTORY --------
    prices.append(MARKET.spot)
    if len(prices) > 300:
        prices.pop(0)

    # -------- CONTEXT --------
    context = context_engine.detect(prices)
    participation = participation_engine.score()
    vol_status = volatility_engine.check(prev_vix)
    prev_vix = MARKET.vix
    decay_ok = decay_engine.allow(prices)

    if len(prices) > 20:
        vwap = structure_engine.vwap(prices)
    else:
        vwap = MARKET.spot
    bull = structure_engine.bullish(MARKET.spot, vwap)
    bear = structure_engine.bearish(MARKET.spot, vwap)

    # -------- METRICS LAYER (Combined Score) --------
    vix_mom = "SUPPORTIVE" if (prev_vix and MARKET.vix and MARKET.vix > prev_vix) else "WEAK"
    volume_impulse = abs(prices[-1] - prices[-5]) if len(prices) >= 5 else 0
    opt_tokens = list(MARKET.option_chain.keys())
    opt_ltp_5m = MARKET.get_option_ltp_history(opt_tokens[0], 300) if opt_tokens else []
    depth_5m = MARKET.get_depth_history(300)
    pdr_val = pdr_penalty(opt_ltp_5m)
    lms_val = lms_score(depth_5m)
    ivs_val = ivs_score_stub()
    lead_pts = leading_score(
        vix_mom, participation, volume_impulse, ivs_val, lms_val, bull
    )
    rsi_val = rsi(prices, 14) if len(prices) >= 15 else 50
    ma_bull = ma_crossover_score(prices, 9, 21) > 0.5
    hv = historical_volatility(prices, 20)
    lag_pts = lagging_score(rsi_val, ma_bull, min(11, hv))
    combined_score_val = combined_score_fn(lead_pts, lag_pts, pdr_val)

    # -------- DECISION ENGINE (per spec: action, confidence, reasoning, strikeGuidance) --------
    reg = vix_regime(MARKET.vix)
    decision_interval_sec = decision_interval_seconds(reg, market_phase())
    if time.time() - last_decision_ts >= decision_interval_sec:
        decision = rule_based_decision(
            context,
            participation,
            vol_status,
            decay_ok,
            bull,
            bear,
            combined_score_val,
            pdr_val,
        )
        decision["timestamp"] = time.time()
        last_decision_ts = time.time()
    else:
        decision = {"action": ACTION_HOLD, "confidence": 50, "reasoning": "Interval", "strikeGuidance": {}}

    # -------- ENTRY: 7-STEP VALIDATION THEN EXECUTE --------
    if decision.get("action") in (ACTION_TRADE_CE, ACTION_TRADE_PE) and not position.active:
        if len(prices) > 10:
            momentum = abs(prices[-1] - prices[-5])
        else:
            momentum = 0
        strike = strike_engine.select(MARKET.spot, context, momentum)
        stop_distance = max(30, momentum * 0.5)
        qty = sizer.size(risk_pct=0.01, stop_distance=stop_distance, lot_size=LOT_SIZE)

        passed, failed_step, reason = run_validation_chain(
            decision,
            MARKET.vix,
            risk.trades,
            1 if position.active else 0,
            risk.daily_pnl,
            strike,
            MARKET.spot,
        )
        if passed and risk.allow(risk.daily_pnl):
            side = "CE" if decision["action"] == ACTION_TRADE_CE else "PE"
            print(
                f"TRADE → {decision['action']} | Spot: {MARKET.spot} | Strike: {strike} | Qty: {qty}"
            )
            position.enter(MARKET.spot, stop_distance, qty, side=side)
            risk.record_trade()
            if LIVE_TRADING and order_manager:
                symbol, token = get_option_symbol_token(
                    api, INDEX, strike, side, OPTION_EXPIRY_DDMMMYY
                )
                if symbol and token:
                    if side == "CE":
                        order_id = order_manager.buy(symbol, token, qty)
                    else:
                        order_id = order_manager.sell(symbol, token, qty)
                    if order_id:
                        print(f"Broker order placed: {side} {symbol} qty={qty} order_id={order_id}")
                    else:
                        print(f"Broker order failed: {side} {symbol} qty={qty}")
                else:
                    print(f"Could not resolve option symbol/token for strike={strike} {side}")
        elif not passed:
            pass  # optional: log validation failure (failed_step, reason)

    # -------- TRAILING + EXIT --------
    if position.active:
        position.trail(MARKET.spot)
        if position.exit_check(MARKET.spot):
            print("EXIT TRADE at", MARKET.spot)

    # -------- EXIT_ALL (per spec) --------
    if decision.get("action") == ACTION_EXIT_ALL and position.active:
        position.active = False
        print("EXIT_ALL at", MARKET.spot)
    
    # -------- DEBUG --------
    part_val = participation if participation is not None else 0
    score_val = combined_score_val if combined_score_val is not None else 0
    print(
        f"Context: {context} | Part: {part_val:.2f} "
        f"| VIX: {MARKET.vix} | Vol: {vol_status} | Score: {score_val:.1f}"
    )

    time.sleep(1)
