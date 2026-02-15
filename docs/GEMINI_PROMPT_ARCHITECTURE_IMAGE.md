# Prompt for Gemini AI – Options Oracle Architecture Diagram

Use this prompt in Gemini (or any image-generation AI) to get an architecture/flow diagram image.

---

## Prompt (copy-paste)

```
Create a clean, professional **architecture flow diagram** for an algo trading system named "Options Oracle". Use a white or light gray background, black/dark gray text, and clear boxes with arrows. Style: technical flowchart, not cartoon.

**Top section – Startup (left to right):**
1. Box: "Angel Login" → arrow → "JWT, Feed Token"
2. Arrow → "WebSocket Connect (background thread)"
3. Arrow → "Subscribe Tokens (NSE: Nifty 26000, VIX 26017)"
4. Arrow → "Main Strategy Loop Starts"

**Center – Main loop (vertical flow, one column):**
5. Box: "Wait for Market Data (spot price)"
6. Arrow down → "Market Hours Check (9:20–15:28 IST)"
7. Arrow down → "Price History + 5 Engines: Context (UPTREND/RANGE/DOWNTREND), Participation, Volatility, Decay, Structure (VWAP, bull/bear)"
8. Arrow down → "Metrics: Combined Score = Leading×0.65 + Lagging×0.35 + PDR"
9. Arrow down → "Contextual Risk: VIX regime, market phase, decision interval"
10. Arrow down → "Decision Engine → Output: TRADE_CE / TRADE_PE / HOLD / EXIT_ALL (confidence, strikeGuidance)"
11. Arrow down → Diamond: "Trade signal?" 
    - Yes → "7-Step Validation (AI gating, strike alignment, margin, position limits, market hours, circuit breaker, order)"
    - Yes (after pass) → "Position.enter + RiskGovernor"
    - No → "Position.trail + exit_check (SL/target)"
12. Arrow down → "Debug print, sleep 1s → back to Wait for Market Data"

**Right side – Data & risk (small boxes):**
- "WebSocket ticks" → "MARKET cache (spot, VIX, option_chain)"
- "RiskGovernor: daily PnL, max trades, circuit breaker"
- "PositionManager: entry, SL, target, trail"

**Labels:**
- Title at top: "Options Oracle – Algo Trading Architecture"
- Optional footnote: "Data → Metrics → Contextual Risk → Decision → 7-Step Validation → Execution"

Output as a single, readable flowchart image. No code snippets inside the image; only short labels in boxes and arrows.
```

---

## Shorter alternative prompt (if character limit)

```
Draw a technical flowchart for "Options Oracle" algo trading system. White background, black text, clear boxes and arrows.

Flow: (1) Angel Login → JWT → WebSocket (background) → Subscribe NSE tokens → (2) Main loop: Wait for spot → Market hours → Price history → Engines (Context, Participation, Volatility, Decay, Structure) → Metrics (Combined Score) → Decision (TRADE_CE/PE or HOLD) → If trade: 7-Step Validation → Position.enter → Position.trail & exit. Side: WebSocket → MARKET cache; RiskGovernor; PositionManager. Title: Options Oracle Architecture. Style: professional flowchart.
```

---

## Notes for best results

- Ask for **one image** with the full flow; if the output is too dense, ask for "same diagram in 2 parts: Part 1 Startup + Main loop, Part 2 Validation + Risk."
- You can paste the Mermaid or text flow from `ARCHITECTURE_FLOW.md` and add: "Turn this into a clear flowchart image with boxes and arrows."
- If using Gemini with diagram support, you can say: "Generate a flowchart from this Mermaid code: [paste the Mermaid block from ARCHITECTURE_FLOW.md]."
```
