# Options Oracle – Complete Logic Flow & Line-by-Line Understanding

This document explains **every logical step** in the app so you have a full understanding of how it works.

---

## Table of contents

1. [High-level flow](#1-high-level-flow)
2. [Config (settings.py)](#2-config-settingspy)
3. [Main entry (main.py)](#3-main-entry-mainpy)
4. [Data layer](#4-data-layer)
5. [Engines (signals & metrics)](#5-engines-signals--metrics)
6. [Execution & risk](#6-execution--risk)
7. [End-to-end tick flow](#7-end-to-end-tick-flow)

---

## 1. High-level flow

```
Start
  → Login (Angel) → JWT + feed token
  → Start WebSocket in background thread (so main thread is not blocked)
  → Wait until WebSocket is connected (on_open sets is_connected)
  → Subscribe to tokens (Nifty 26000, VIX 26017, others) in SmartAPI format
  → Create strategy engines and execution/risk objects
  → Enter main loop (every 1 second):
        Wait for MARKET.spot (Nifty LTP)
        Check market hours (9:20–15:28 IST)
        Update price history
        Run context, participation, volatility, decay, structure
        Compute metrics (leading, lagging, PDR) → combined score
        Run decision engine (TRADE_CE / TRADE_PE / HOLD / EXIT_ALL)
        If trade signal: 7-step validation → position.enter + risk.record_trade
        If position active: trail stop, check exit (SL/target)
        If EXIT_ALL: close position
        Print debug line, sleep 1s, repeat
```

---

## 2. Config (config/settings.py)

| Line / block | What it does |
|--------------|--------------|
| `INDEX = "NIFTY"` | Underlying index name (standardized; could be BANKNIFTY later). |
| `BASE_RISK`, `TRAIL_FACTOR`, `DECAY_THRESHOLD`, `PARTICIPATION_STRONG` | Used in risk, trailing stop, decay logic, and participation thresholds. |
| `MARKET_OPEN_HOUR/MINUTE`, `MARKET_CLOSE_HOUR/MINUTE` | Market hours in IST (9:20–15:28). Used by `is_market_hours()` and market phase. |
| `VIX_ULTRA_LOW` (12), `VIX_NORMAL_LOW` (18), `VIX_SPIKING` (25), `VIX_PANIC` (30) | VIX levels to classify regime (ULTRA_LOW → PANIC). |
| `CONFIDENCE_ULTRA_LOW` (75) down to `CONFIDENCE_PANIC` (55) | Minimum confidence required to act in each VIX regime (used in 7-step validation). |
| `CONFIDENCE_FALLBACK` (50) | Used when decision engine fails (HOLD, below typical threshold). |
| `DECISION_INTERVAL_HIGH_VOL` (90), `DECISION_INTERVAL_LOW_VOL` (240) | Seconds between re-running the decision engine (90s in high vol, 240s in low). |
| `OPENING_VOLATILITY_THRESHOLD_PCT` (10) | Extra confidence required in first 30 min (e.g. +10%). |
| `STRIKE_DELTA_MIN`, `STRIKE_IV_MAX_PCT` | Strike guidance (Delta ≥ 0.25, IV ≤ 25%); used in validation. |
| `MAX_TRADES`, `MAX_DAILY_LOSS`, `MIN_WIN_RATE_PCT` | Circuit breaker: max trades per day, max daily loss, min win-rate (stub). |
| `API_KEY`, `CLIENT_ID`, `PASSWORD`, `TOTP_SECRET` | Angel One credentials (should be env vars in production). |
| `LOT_SIZE` (65) | Nifty lot size for position sizing. |

---

## 3. Main entry (main.py)

### 3.1 Imports (lines 1–55)

- **time, threading**: Sleep and running WebSocket in a background thread.
- **config.settings**: All constants above (INDEX, LOT_SIZE, credentials, intervals, limits).
- **AngelSession, AngelWS, AngelSubscribe**: Login, WebSocket, subscription.
- **MARKET**: Global market cache (spot, vix, option_chain, etc.).
- **ContextEngine, ParticipationEngine, VolatilityEngine, DecayEngine, StructureEngine**: Strategy engines.
- **metrics**: `rsi`, `ma_crossover_score`, `historical_volatility`, `leading_score`, `lagging_score`, `pdr_penalty`, `lms_score`, `ivs_score_stub`, `combined_score_fn`.
- **contextual_risk**: `vix_regime`, `market_phase`, `decision_interval_seconds`, `is_market_hours`.
- **decision_engine**: `rule_based_decision`, `ACTION_TRADE_CE`, `ACTION_TRADE_PE`, `ACTION_HOLD`, `ACTION_EXIT_ALL`.
- **PositionManager, StrikeEngine, PositionSizer, run_validation_chain**: Execution.
- **RiskGovernor**: Trade count and daily loss limits.

### 3.2 Login (lines 57–61)

```text
session = AngelSession(API_KEY, CLIENT_ID, PASSWORD, TOTP_SECRET)
api, jwt, feed = session.login()
```

- Creates an Angel session with credentials and TOTP secret.
- `login()` (see [4.1](#41-angel_loginpy)) retries until it gets JWT and feed token; returns `(api_object, jwt, feed)`.
- `api`: used later for order placement (stub). `jwt`, `feed`: used for WebSocket.

### 3.3 WebSocket (lines 63–75)

```text
ws_engine = AngelWS(jwt, API_KEY, CLIENT_ID, feed)
ws_thread = threading.Thread(target=ws_engine.connect, daemon=True)
ws_thread.start()
while not ws_engine.is_connected:
    time.sleep(0.2)
print("Connected to WebSocket - started")
subscriber = AngelSubscribe(ws_engine.ws)
subscriber.core()
print("Subscribed to tokens. Strategy loop starting...")
```

- **Why thread**: SmartAPI’s `connect()` calls `run_forever()` and blocks. Running it in a daemon thread lets the main thread continue.
- **Wait loop**: Main thread waits until `on_open` has set `is_connected = True`.
- **AngelSubscribe(ws_engine.ws).core()**: Subscribes to tokens in the format SmartAPI expects (list of `{exchangeType, tokens}`); see [4.3](#43-angel_subscribepy).
- After this, ticks for token 26000 (Nifty) and 26017 (VIX) start updating `MARKET.spot` and `MARKET.vix` in the WebSocket thread.

### 3.4 Strategy engines and execution (lines 76–98)

- **context_engine, participation_engine, volatility_engine, decay_engine, structure_engine**: One instance each; used every loop.
- **position**: Tracks one open position (entry, SL, target, trail).
- **strike_engine**: Picks strike (ATM vs ITM bias) using `GreekEngine.gamma_mode`.
- **sizer**: Position size from risk %, stop distance, and lot size (capital 200000).
- **risk**: Tracks trade count and daily PnL; allows/blocks new trades.
- **prices**, **prev_vix**, **last_decision_ts**, **decision_interval_sec**: In-loop state (price history, previous VIX, last decision time, current decision interval).

### 3.5 Main loop – wait for data (lines 106–114)

```text
if MARKET.spot is None:
    if time.time() - last_wait_print >= 5:
        print("Waiting for market data (Nifty spot token 26000)...")
        last_wait_print = time.time()
    time.sleep(1)
    continue
```

- If no spot price yet (no tick from token 26000), print at most once every 5 seconds, sleep 1s, and skip the rest of the loop.
- So the strategy logic runs only when `MARKET.spot` is set by the WebSocket.

### 3.6 Main loop – market hours (lines 115–118)

```text
if not is_market_hours():
    time.sleep(10)
    continue
```

- `is_market_hours()` is True only between 9:20 and 15:28 IST (from config).
- Outside that window the loop sleeps 10s and does not run strategy or place trades.

### 3.7 Main loop – price history (lines 120–124)

```text
prices.append(MARKET.spot)
if len(prices) > 300:
    prices.pop(0)
```

- Each tick (every 1s in the loop) appends current Nifty spot.
- Keeps only the last 300 points (~5 minutes at 1s granularity) for indicators and context.

### 3.8 Main loop – context and structure (lines 125–137)

- **context** = `context_engine.detect(prices)`: UPTREND / DOWNTREND / RANGE or WAIT (see [5.1](#51-context_engine)).
- **participation** = `participation_engine.score()`: 0–1 from `MARKET.heavy` (see [5.2](#52-participation_engine)).
- **vol_status** = `volatility_engine.check(prev_vix)`: SUPPORTIVE if VIX rose, else WEAK (see [5.3](#53-volatility_engine)).
- **prev_vix** is then set to current `MARKET.vix` for the next iteration.
- **decay_ok** = `decay_engine.allow(prices)`: True if recent price impulse > 20 (see [5.4](#54-decay_engine)).
- **vwap** = 20-bar average of `prices` (or spot if &lt; 20 bars); **bull** = spot > vwap, **bear** = spot &lt; vwap (see [5.5](#55-structure_engine)).

### 3.9 Main loop – metrics and combined score (lines 139–155)

- **vix_mom**: "SUPPORTIVE" if current VIX > previous VIX, else "WEAK".
- **volume_impulse**: |prices[-1] − prices[-5]| (or 0 if &lt; 5 bars).
- **opt_ltp_5m**: Last 300 seconds of LTP for first option token (for PDR); empty if no options.
- **depth_5m**: Last 300 seconds of depth (for LMS).
- **pdr_val** = `pdr_penalty(opt_ltp_5m)`: 0 to −10 from option premium decay (see [5.6](#56-metricspy)).
- **lms_val** = `lms_score(depth_5m)`: 0–10 from depth change (liquidity momentum).
- **ivs_val** = `ivs_score_stub()`: 7.5 (stub for IV skew).
- **lead_pts** = `leading_score(...)`: 0–65 from VIX momentum, participation, volume impulse, IVS, LMS, VWAP (bull).
- **rsi_val** = RSI(14) on `prices` (or 50 if not enough data).
- **ma_bull** = True if 9-bar MA > 21-bar MA.
- **hv** = historical volatility (20-bar).
- **lag_pts** = `lagging_score(rsi_val, ma_bull, hv)`: 0–35.
- **combined_score_val** = (Leading×0.65 + Lagging×0.35)×100 + PDR penalty (can go negative).

### 3.10 Main loop – decision engine (lines 157–174)

- **reg** = VIX regime (ULTRA_LOW / NORMAL_LOW / SPIKING / PANIC).
- **decision_interval_sec** = 90 or 240 depending on regime and market phase (opening vol → 90s).
- Only when `time.time() - last_decision_ts >= decision_interval_sec`:
  - **decision** = `rule_based_decision(context, participation, vol_status, decay_ok, bull, bear, combined_score_val, pdr_val)`.
  - Decision has: `action`, `confidence`, `reasoning`, `strikeGuidance`; we set `decision["timestamp"] = time.time()` and update `last_decision_ts`.
- Otherwise we keep **decision** = HOLD with 50% confidence and "Interval" reasoning (no new decision this tick).

### 3.11 Main loop – entry and 7-step validation (lines 176–204)

- Runs only if `decision["action"]` is TRADE_CE or TRADE_PE and there is no active position.
- **momentum** = |prices[-1] − prices[-5]| (or 0 if &lt; 10 bars).
- **strike** = `strike_engine.select(spot, context, momentum)`: ATM (round to 50) if gamma HIGH, else ITM bias (see [6.2](#62-strike_engine--greek_engine)).
- **stop_distance** = max(30, momentum×0.5).
- **qty** = `sizer.size(risk_pct=0.01, stop_distance, LOT_SIZE)`: from 1% risk and stop (see [6.3](#63-position_sizerpy)).
- **run_validation_chain(...)**: Steps 1–6 (see [6.4](#64-validation_chainpy)); step 7 (order) is not implemented here.
- If validation **passed** and **risk.allow(daily_pnl)**:
  - **side** = "CE" or "PE" from action.
  - Print trade message.
  - **position.enter(spot, stop_distance, qty, side=side)**.
  - **risk.record_trade()** (increment trade count).

### 3.12 Main loop – trailing and exit (lines 206–214)

- If **position.active**:
  - **position.trail(MARKET.spot)**: For CE, SL moves up with price (e.g. 0.99×price); for PE, SL moves down (see [6.1](#61-position_managerpy)).
  - **position.exit_check(MARKET.spot)**: True if SL or target hit; then we set `position.active = False` and print exit.
- If **decision["action"] == EXIT_ALL** and position is active: force close (active = False) and print EXIT_ALL.

### 3.13 Main loop – debug and sleep (lines 216–222)

- **part_val** / **score_val**: Safe values for participation and combined score (default 0).
- One debug print per tick: Context, Part, VIX, Vol status, Score.
- **time.sleep(1)**: Loop runs roughly every 1 second.

---

## 4. Data layer

### 4.1 angel_login.py

- **AngelSession(api, client, pwd, totp)**: Stores API key, client, password, TOTP secret.
- **login()**:
  - In a loop: create **SmartConnect(api_key)**, get current **otp** from **pyotp.TOTP(totp).now()**, call **obj.generateSession(client, pwd, otp)**.
  - On success: read **jwt** and **feed** from `data["data"]`, print "Angel login success", return **(obj, jwt, feed)**.
  - On exception: print "Retry login", sleep 5s, retry. So login blocks until success.

### 4.2 angel_ws.py

- **AngelWS(jwt, api_key, client, feed)**: Holds auth and feed; `ws = None`, `is_connected = False`, reconnect counters.
- **on_open(ws)**: Prints "WebSocket connection established", sets `is_connected = True`, resets reconnect count.
- **on_data(ws, message)**:
  - **token** = `str(message.get("token", ""))`.
  - If token == "26000": take **last_traded_price** (in paisa), divide by 100 → **MARKET.update_spot(price)**.
  - If token == "26017": same → **MARKET.update_vix(price)**.
  - Else: **MARKET.update_option(token, message)** (options/other symbols).
  - Any exception is printed; no re-raise so WebSocket keeps running.
- **on_error** / **on_close**: Set `is_connected = False`; on_close, optionally retry connect up to 5 times.
- **connect()**: Builds **SmartWebSocketV2** with auth, assigns **on_open, on_data, on_error, on_close** to our methods, then calls **self.ws.connect()** (which blocks in that thread with run_forever).
- **disconnect()**: Closes WebSocket and sets `is_connected = False`.

### 4.3 angel_subscribe.py

- **AngelSubscribe(ws)**: Holds the WebSocket instance.
- **core()**:
  - Prints "Subscribing to core data...".
  - **token_list** = list of dicts: `[{"exchangeType": 1, "tokens": ["26000", "26017", ...]}]`. exchangeType 1 = NSE CM (cash).
  - **self.ws.subscribe(correlation_id="core", mode=1, token_list=token_list)**. mode=1 = LTP. SmartAPI expects this structure; raw list of strings would cause "string indices must be integers" error.

### 4.4 market_cache.py

- **MarketCache**:
  - **spot**, **vix**: Latest Nifty and India VIX.
  - **heavy**: dict symbol → LTP (for participation; currently not populated by our WS, so participation stays 0 unless you set it elsewhere).
  - **option_chain**: token → tick (LTP, depth, etc.).
  - **put_oi_total**, **call_oi_total**: For PCR when set via **set_oi_totals**.
  - **_option_ltp_history**: token → deque of (timestamp, ltp), maxlen 300, for PDR.
  - **_depth_history**: deque of (ts, best_bid, best_ask, spread) for LMS.
- **update_spot(price)** / **update_vix(vix)**: Set spot/vix.
- **update_heavy(symbol, price)**: Set heavy[symbol].
- **update_option(token, tick)**: Store tick; if tick has last_traded_price/ltp, append (time, ltp) to _option_ltp_history[token]; if depth present, append one depth snapshot to _depth_history.
- **pcr**: property; put_oi_total / call_oi_total when call_oi_total > 0, else None.
- **get_option_ltp_history(token, window_sec=300)**: Returns list of (t, ltp) in last window_sec for that token.
- **get_depth_history(window_sec=300)**: Returns list of (t, bid, ask, spread) in last window_sec.
- **MARKET**: Single global instance used everywhere.

---

## 5. Engines (signals & metrics)

### 5.1 context_engine (context.py)

- **detect(prices)**:
  - If len(prices) &lt; 30: return **"WAIT"**.
  - **m** = prices[-1] − prices[-20] (20-bar move).
  - If m > 40: **"UPTREND"**; if m &lt; −40: **"DOWNTREND"**; else **"RANGE"**.

### 5.2 participation_engine (participation.py)

- **score()**:
  - If **MARKET.heavy** is empty: return **0**.
  - Else: count how many values in heavy are > 0 (bullish), return **bullish / len(MARKET.heavy)** (0–1). Right now heavy is not filled by our WebSocket, so score is 0.

### 5.3 volatility_engine (volatility.py)

- **check(prev)**:
  - If prev is None: **"UNKNOWN"**.
  - If **MARKET.vix > prev**: **"SUPPORTIVE"** (volatility increasing).
  - Else: **"WEAK"**.

### 5.4 decay_engine (decay.py)

- **allow(prices)**:
  - If len(prices) &lt; 10: False.
  - **impulse** = |prices[-1] − prices[-5]|.
  - Return **impulse > 20** (enough short-term movement to allow a trade).

### 5.5 structure_engine (structure.py)

- **vwap(prices)**: Average of last 20 prices.
- **bullish(price, vwap)**: price > vwap.
- **bearish(price, vwap)**: price &lt; vwap.

### 5.6 metrics (metrics.py)

- **rsi(prices, period=14)**: Standard RSI; if not enough data return 50.
- **ma_crossover_score(prices, 9, 21)**: 1.0 if MA9 > MA21, else 0.0; 0.5 if &lt; 21 bars.
- **historical_volatility(prices, 20)**: Annualized volatility proxy from last 20 returns.
- **leading_score(vix_mom, participation, volume_impulse, ivs_score, lms_score, vwap_bull)**: Points 0–65 from participation (up to 15), VIX (10/5), volume (up to 10), IVS (up to 15), LMS (up to 10), VWAP bull (5 or 0).
- **lagging_score(rsi_val, ma_bull, hv_normalized)**: 0–35 from RSI in 40–70 (12 pts), MA bullish (12), HV (up to 11).
- **pdr_penalty(option_ltp_history_5min)**: From first and last LTP in window; pct drop → 0 to −10 (e.g. 20% drop → about −5).
- **lms_score(depth_history_5min)**: Spread narrowing over 5 min → 0–10 (5 = neutral).
- **ivs_score_stub()**: Returns 7.5 (placeholder for IV skew).
- **combined_score(leading_pts, lagging_pts, pdr_penalty_val)**: (leading/65)×0.65 + (lagging/35)×0.35, scaled to 100, then **+ pdr_penalty_val** (so can go negative).

### 5.7 contextual_risk (contextual_risk.py)

- **vix_regime(vix)**: From config thresholds → "ULTRA_LOW" | "NORMAL_LOW" | "SPIKING" | "PANIC" (or "NORMAL_LOW" if vix is None).
- **required_confidence(regime)**: 75 / 70 / 60 / 55 for the four regimes.
- **market_phase()**: Current time in IST; 9:20–9:50 → "OPENING_VOLATILITY", 9:50–15:28 → "MIDDAY_LULL", else "CLOSED_OR_PREOPEN".
- **decision_interval_seconds(regime, phase)**: OPENING_VOLATILITY or SPIKING/PANIC → 90s; else 240s.
- **threshold_penalty_pct(phase)**: +10 in OPENING_VOLATILITY, else 0.
- **is_market_hours()**: True if current time (IST) is between 9:20 and 15:28.

### 5.8 decision_engine (decision_engine.py)

- **rule_based_decision(context, participation, vol_status, decay_ok, bull, bear, combined_score_val, pdr_penalty_val)**:
  - If **pdr_penalty_val ≤ −5**: return HOLD, confidence 45 (theta/IV risk).
  - If **combined_score_val is not None and &lt; 30**: return HOLD, 50.
  - If **context == "UPTREND"** and **participation > 0.6** and **vol_status == "SUPPORTIVE"** and **decay_ok** and **bull**: return **ACTION_TRADE_CE**, confidence 72.
  - If **context == "DOWNTREND"** and **participation &lt; 0.4** and **vol_status == "SUPPORTIVE"** and **decay_ok** and **bear**: return **ACTION_TRADE_PE**, confidence 72.
  - Else: HOLD, 50, "No clear signal".
  - On any exception: HOLD, CONFIDENCE_FALLBACK (50).
  - Every return includes **strikeGuidance** (e.g. delta_min=0.25, iv_max_pct=25).

---

## 6. Execution & risk

### 6.1 position_manager (position_manager.py)

- **enter(price, stop_distance, qty, side="CE", target_ratio=1.5)**:
  - Sets active=True, entry=price, qty, side.
  - **CE**: sl = price − stop_distance, target = price + stop_distance×target_ratio.
  - **PE**: sl = price + stop_distance, target = price − stop_distance×target_ratio.
- **trail(price)**:
  - CE: new_sl = price×0.99; if new_sl > sl, sl = new_sl (trail up).
  - PE: new_sl = price×1.01; if new_sl &lt; sl, sl = new_sl (trail down).
- **exit_check(price)**:
  - CE: exit if price ≤ sl or price ≥ target.
  - PE: exit if price ≥ sl or price ≤ target.
  - On exit, sets active=False and returns True.

### 6.2 strike_engine & greek_engine

- **GreekEngine.gamma_mode(context, momentum)**: "HIGH" if context == "UPTREND" and momentum > 40, else "NORMAL".
- **StrikeEngine.select(spot, context, momentum)**:
  - If gamma_mode == "HIGH": **strike = round(spot/50)*50** (ATM).
  - Else: **strike = round((spot−50)/50)*50** (slightly ITM bias for Nifty).

### 6.3 position_sizer (position_sizer.py)

- **size(risk_pct, stop_distance, lot_size)**:
  - risk_amount = capital × risk_pct (e.g. 200000×0.01 = 2000).
  - qty = risk_amount / stop_distance.
  - Round down to lot multiple; if &lt; lot_size, set to lot_size. So minimum 1 lot.

### 6.4 validation_chain (validation_chain.py)

- **step1_ai_gating(decision, vix, trade_count)**: Decision exists; age &lt; 120s; confidence ≥ required_confidence(regime) + opening penalty; action is TRADE_CE/PE or EXIT_ALL/REVERSE; trade_count &lt; MAX_TRADES for trade actions.
- **step2_strike_alignment(strike, spot, strikeGuidance)**: |spot − strike| ≤ 200 (proxy for not far OTM).
- **step3_margin_check()**: Stub, returns True.
- **step4_position_limits(active_positions, max_positions=1)**: active_positions &lt; max_positions.
- **step5_market_hours()**: is_market_hours().
- **step6_circuit_breaker(daily_pnl)**: daily_pnl not ≤ −MAX_DAILY_LOSS.
- **run_validation_chain(...)**: Runs steps 1–6 in order; returns (passed, failed_step 1–6 or 0, reason). Step 7 (actual order) is not implemented; caller only does position.enter() and risk.record_trade().

### 6.5 risk_governor (risk_governor.py)

- **allow(daily_pnl=None)**: False if trades ≥ max_trades or (daily_pnl or self.daily_pnl) ≤ −max_daily_loss; else True.
- **record_trade()**: Increments trades.
- **update_daily_pnl(pnl)**: Sets self.daily_pnl (for circuit breaker).
- **circuit_breaker_breached()**: True if daily PnL ≤ −max_daily_loss.
- **failure_constraint_block(vix_regime, market_phase)**: Stub, always False (no historical DB).

---

## 7. End-to-end tick flow

1. **WebSocket thread** receives a tick; if token 26000, **MARKET.spot** is updated; if 26017, **MARKET.vix** is updated.
2. **Main thread** (next iteration of the loop) sees **MARKET.spot** is not None.
3. **Market hours** checked; if outside 9:20–15:28 IST, sleep 10s and skip.
4. **prices** gets current spot appended (max 300).
5. **Context** (UPTREND/DOWNTREND/RANGE), **participation** (from heavy), **vol_status** (VIX vs prev), **decay_ok** (impulse > 20), **vwap/bull/bear** computed.
6. **Metrics**: leading/lagging/PDR/LMS/IVS → **combined_score_val**.
7. Every **decision_interval_sec** seconds, **rule_based_decision(...)** runs → **action** (TRADE_CE/PE or HOLD/EXIT_ALL), **confidence**, **reasoning**, **strikeGuidance**.
8. If **action** is TRADE_CE or TRADE_PE and **not position.active**:
   - **strike**, **stop_distance**, **qty** computed.
   - **run_validation_chain** runs steps 1–6; if passed and **risk.allow()**, **position.enter(...)** and **risk.record_trade()**.
9. If **position.active**: **position.trail(spot)** and **position.exit_check(spot)**; on exit, active set False and message printed.
10. If **action == EXIT_ALL** and position active: force close.
11. Debug print (context, part, VIX, vol, score), then **sleep(1)** and repeat.

This is the complete logic flow of the Options Oracle app from config and login through data, engines, decision, validation, and execution.
