# Options Oracle – Architecture & Flow Diagram

## 1. Mermaid diagram (copy into Mermaid Live Editor or VS Code)

```mermaid
flowchart TB
    subgraph startup["1. STARTUP"]
        A[AngelSession.login] --> B[JWT, feed token]
        B --> C[AngelWS.connect in background thread]
        C --> D[Wait is_connected]
        D --> E[AngelSubscribe.core - token_list by exchangeType]
        E --> F[Strategy loop starts]
    end

    subgraph datalayer["2. DATA LAYER"]
        WS[WebSocket SmartAPI] --> |on_data| MC[MARKET cache]
        MC --> |spot, vix, option_chain| LOOP
    end

    subgraph loop["3. MAIN LOOP (every 1s)"]
        LOOP[Entry]
        LOOP --> G{MARKET.spot?}
        G -->|None| WAIT[Wait 5s msg, sleep 1s]
        WAIT --> LOOP
        G -->|OK| H{Market hours 9:20-3:28 IST?}
        H -->|No| SLEEP[Sleep 10s]
        SLEEP --> LOOP
        H -->|Yes| I[Append price history]
        I --> J[ContextEngine: UPTREND/DOWNTREND/RANGE]
        I --> K[ParticipationEngine: score from MARKET.heavy]
        I --> L[VolatilityEngine: VIX supportive/weak]
        I --> M[DecayEngine: allow by impulse]
        I --> N[StructureEngine: VWAP, bull/bear vs VWAP]
        J --> O[Metrics: Leading 0.65 + Lagging 0.35 + PDR]
        K --> O
        L --> O
        N --> O
        O --> P[Contextual risk: VIX regime, market phase, decision interval]
        P --> Q[Decision engine: TRADE_CE / TRADE_PE / HOLD / EXIT_ALL]
        Q --> R{Action trade?}
        R -->|Yes| S[StrikeEngine, PositionSizer]
        S --> T[7-step validation chain]
        T --> U{Pass?}
        U -->|Yes| V[Position.enter, risk.record_trade]
        U -->|No| W[Skip]
        R -->|No| W
        V --> X[Position.trail + exit_check]
        W --> X
        X --> Y[Debug print]
        Y --> LOOP
    end

    subgraph validation["7-STEP VALIDATION"]
        T1[1. AI gating: confidence, age, action]
        T2[2. Strike alignment]
        T3[3. Margin check]
        T4[4. Position limits]
        T5[5. Market hours]
        T6[6. Circuit breaker / daily loss]
        T7[7. Order execution - stub]
        T1 --> T2 --> T3 --> T4 --> T5 --> T6 --> T7
    end

    subgraph risk["RISK & EXECUTION"]
        RG[RiskGovernor: daily PnL, max trades, allow]
        PM[PositionManager: entry, SL, target, trail, exit]
        T --> RG
        V --> PM
    end
```

## 2. High-level flow (text)

```
[Angel Login] → [WebSocket connect - background thread] → [Subscribe tokens NSE]
       ↓
[Main loop]
   → Wait for MARKET.spot (Nifty 26000, VIX 26017)
   → Check market hours (9:20–15:28 IST)
   → Build price history
   → Context (UPTREND/DOWNTREND/RANGE)
   → Participation score
   → Volatility (VIX)
   → Decay allow
   → Structure (VWAP, bull/bear)
   → Combined Score (Leading×0.65 + Lagging×0.35 + PDR)
   → Decision: TRADE_CE / TRADE_PE / HOLD / EXIT_ALL
   → If trade: 7-step validation → Position.enter + RiskGovernor
   → Position trail + exit check
   → Debug print, sleep 1s, repeat
```

## 3. Component map

| Layer        | Module / Class           | Role |
|-------------|--------------------------|------|
| Data        | AngelSession             | Login, JWT, feed |
| Data        | AngelWS                  | WebSocket (background thread), on_data → MARKET |
| Data        | AngelSubscribe           | subscribe(token_list by exchangeType) |
| Data        | MARKET (MarketCache)     | spot, vix, heavy, option_chain, PDR/LMS history |
| Engines     | ContextEngine            | detect(prices) → UPTREND/DOWNTREND/RANGE |
| Engines     | ParticipationEngine      | score() from MARKET.heavy |
| Engines     | VolatilityEngine         | check(prev_vix) → SUPPORTIVE/WEAK |
| Engines     | DecayEngine              | allow(prices) by impulse |
| Engines     | StructureEngine          | vwap, bullish, bearish |
| Engines     | metrics                  | RSI, MA crossover, HV, leading/lagging, PDR, LMS, combined_score |
| Engines     | contextual_risk          | vix_regime, market_phase, decision_interval_seconds, is_market_hours |
| Engines     | decision_engine          | rule_based_decision → action, confidence, reasoning, strikeGuidance |
| Execution   | StrikeEngine             | select(spot, context, momentum) |
| Execution   | PositionSizer            | size(risk_pct, stop_distance, lot_size) |
| Execution   | validation_chain         | run_validation_chain (7 steps) |
| Execution   | PositionManager          | enter, trail, exit_check (SL/target) |
| Risk        | RiskGovernor             | allow, daily_pnl, circuit breaker, record_trade |
| Config      | config.settings          | INDEX, market hours, VIX regimes, LOT_SIZE, etc. |
```

## 4. Data flow (simplified)

```
Angel API → WebSocket ticks → MARKET (spot, vix, options)
    → prices[] in main
    → ContextEngine, ParticipationEngine, VolatilityEngine, DecayEngine, StructureEngine
    → metrics (leading, lagging, PDR) → combined_score
    → decision_engine (action, confidence, strikeGuidance)
    → validation_chain → PositionManager.enter / RiskGovernor
    → PositionManager.trail & exit_check
```
