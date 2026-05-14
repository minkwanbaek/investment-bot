# AI-Friendly Architecture Working Docs

**Date:** 2026-05-13  
**Status:** Draft working set for TASK-001 ~ TASK-003

---

# TASK-001 — Current ownership and dependency map

## 1. Runtime flow snapshot

### Live auto-trade path today

```text
FastAPI route
  -> container.get_auto_trade_service()
  -> AutoTradeService.run_once()
  -> DynamicSymbolSelector.select()
  -> _collect_symbol_candidates(symbol)
  -> ShadowService.run_once(...)
  -> SemiLiveService.run_once(...)
  -> TradingCycleService.run(...)
  -> Strategy.generate_signal(...)
  -> PaperBroker.evaluate_exit_rules(...)
  -> RiskController.review(...)
  -> back to AutoTradeService candidate arbitration
  -> LiveExecutionService.preview_order()/submit_order()
```

### Core observation

One user-visible trade decision currently crosses all of these concerns in one chain:
- market data fetch
- strategy entry logic
- strategy exit logic
- broker exit rules
- risk policy
- exposure limits
- dust / managed position classification
- candidate ranking
- exchange execution

That is too much responsibility in one traversal.

---

## 2. Current owner table

| Concern | Current owner | Notes |
|---|---|---|
| API endpoints | `api/routes.py` | Thin entrypoints, but still coupled to container-level service graph |
| Object wiring | `services/container.py` | Global service locator style |
| Auto-trade orchestration | `services/auto_trade_service.py` | Too large; owns scheduling, candidate collection, ranking, buy/sell arbitration, exposure checks, execution handoff |
| Symbol selection | `services/dynamic_symbol_selector.py` | Entry pre-filter logic mixed with runtime debug info |
| Strategy choice | `services/strategy_selection_service.py` | Chooses best per-symbol candidate |
| Market regime normalization | `services/trading_cycle.py` + `core/trading_policy.py` | Mixed domain/runtime logic |
| Entry signal generation | `strategies/trend_following.py` | Strategy also owns some exit logic today |
| Exit signal generation | `strategies/trend_following.py`, `services/paper_broker.py`, `services/auto_trade_service.py`, `services/trading_cycle.py` | Split ownership; main structural problem |
| Risk approval / sizing | `risk/controller.py` | Reasonably central already |
| Position / portfolio state | `services/paper_broker.py` | Also owns exit rules and bookkeeping |
| Exposure policy | `services/auto_trade_service.py` | Buy-side exposure checks are orchestration-owned now |
| Live execution | `services/live_execution_service.py` | Good candidate for execution slice adapter |
| Account/exchange balances | `services/account_service.py` | Infrastructure concern |
| Candle access | `services/market_data_service.py` | Infrastructure concern |
| Run history / observability | `services/run_history_service.py` | Cross-cutting concern |

---

## 3. Current coupling hotspots

### Hotspot A — `auto_trade_service.py`
Current mixed responsibilities:
- scheduler lifecycle
- selected symbol list/debug state
- candidate collection
- sell filtering
- buy filtering
- exposure math
- symbol exposure math
- order preview/submit handoff
- cooldown
- result persistence

This file should become orchestration-only.

### Hotspot B — sell logic split across four owners
Current sell logic lives in:
- `strategies/trend_following.py`
- `services/paper_broker.py`
- `services/trading_cycle.py`
- `services/auto_trade_service.py`

This is the first thing to collapse.

### Hotspot C — `paper_broker.py`
This currently mixes:
- portfolio state
- paper execution bookkeeping
- exit rule policy
- trade log persistence side effects

### Hotspot D — strategy depends on broker state
`trend_following.generate_signal(..., broker=...)` allows position-aware signals, but that also encourages strategy-owned exits. We likely want:
- entry strategy -> market-focused
- exit policy -> position-aware

---

## 4. Proposed near-term dependency direction

Target direction after sell refactor:

```text
api -> application services -> domain policies -> infrastructure adapters
```

More concretely:

```text
auto_trade application
  -> exit application
  -> entry application
  -> portfolio application
  -> execution adapter

entry domain should not directly own exchange execution
exit domain should not directly own persistence
portfolio domain should not directly own HTTP/API concerns
```

---

# TASK-002 — Slice contract draft

## 1. `entry` slice

### Responsibility
Decide whether a symbol is worth entering now.

### Inputs
- candles / market snapshot
- regime snapshot
- strategy config
- optional portfolio context needed for entry suppression

### Outputs
- `EntryDecision`

### Proposed shape
```python
EntryDecision(
  symbol: str,
  action: Literal["buy", "hold"],
  confidence: float,
  score: float,
  reason: str,
  market_context: dict,
  sizing_hint: dict | None,
)
```

### Must not own
- exchange execution
- stop loss / trailing stop final sell logic
- run-history persistence

---

## 2. `exit` slice

### Responsibility
Decide whether an open position should be reduced or closed.

### Inputs
- open position snapshot
- latest price / candles / market state
- exit config
- optional strategy hints

### Outputs
- `ExitDecision`

### Proposed shape
```python
ExitDecision(
  symbol: str,
  action: Literal["sell", "hold"],
  priority: Literal["hard_stop", "protective", "profit_take", "soft_exit", "none"],
  quantity: float,
  confidence: float,
  reason: str,
  exit_reason: str | None,
  metadata: dict,
)
```

### Must own
- stop loss
- trailing stop
- partial take profit
- timeout exit
- trend reversal exit
- final exit precedence

### Must not own
- order submission
- API route logic

---

## 3. `portfolio` slice

### Responsibility
Provide reusable portfolio/exposure/position classification decisions.

### Inputs
- account balances
- open positions
- current prices
- config thresholds

### Outputs
- `ExposureDecision`
- `PositionClassification`
- `SellabilityDecision`

### Proposed shapes
```python
ExposureDecision(
  current_exposure: float,
  max_total_exposure_value: float,
  remaining_exposure_room: float,
  max_symbol_exposure_value: float,
  remaining_symbol_room: float,
  blocked: bool,
  blocker: str | None,
)

PositionClassification(
  symbol: str,
  managed: bool,
  dust: bool,
  executable: bool,
  estimated_value: float,
)
```

### Must not own
- entry signal semantics
- exit policy semantics

---

## 4. `execution` slice

### Responsibility
Turn approved trade intent into preview + submit actions against the exchange.

### Inputs
- symbol
- side
- price
- volume
- environment/mode

### Outputs
- preview result
- submit result

### Must own
- exchange-specific validation / rounding / preview
- transport to Upbit client

### Must not own
- buy/sell business priority logic
- exposure decision logic

---

## 5. `auto_trade` slice

### Responsibility
Coordinate slices and choose one action per cycle.

### Inputs
- configured symbols
- selector output
- entry decisions
- exit decisions
- portfolio decisions

### Outputs
- one cycle result (`submitted` / `skipped` / `error`)

### Must own
- scheduler loop
- candidate arbitration between entry and exit
- cooldown / batch orchestration
- observability envelope

### Must not own
- canonical exit policy
- canonical entry policy
- raw exchange behavior details

---

## 6. `market_data` slice

### Responsibility
Provide candles and market state in a stable form.

### Inputs
- symbol
- timeframe
- limit

### Outputs
- candles
- optional market snapshot / regime snapshot

---

# TASK-003 — Exit policy spec

## 1. Goal
Make `exit` the single source of truth for sell decisions.

## 2. Scope of exit policy
Exit policy should evaluate:
- hard stop loss
- ATR stop
- trailing stop
- partial take profit
- timeout exit
- trend reversal exit
- full position vs partial position quantity
- executable vs dust-aware sellability

## 3. Inputs required
- `PositionSnapshot`
- `MarketSnapshot`
- `ExitConfig`
- optional `StrategyExitHint`
- optional `PortfolioSellabilityDecision`

### Proposed snapshots
```python
PositionSnapshot(
  symbol: str,
  quantity: float,
  average_price: float,
  opened_at: datetime | None,
  trailing_active: bool,
  trailing_stop_price: float | None,
  tp1_done: bool,
  tp1_price: float | None,
  stop_price: float | None,
)

MarketSnapshot(
  latest_price: float,
  candles: list,
  regime: str,
  volatility_state: str,
  higher_tf_bias: str,
)
```

---

## 4. Exit precedence

Recommended precedence:

1. **hard_stop**
   - loss threshold breach
   - ATR stop breach
2. **protective**
   - active trailing stop hit
   - timeout with insufficient progress
3. **profit_take**
   - partial take profit trigger
4. **soft_exit**
   - trend reversal / strategy deterioration
5. **none**
   - keep holding

Why this order:
- safety exits must always beat opportunistic entries
- once a position is in danger, orchestration should not be allowed to keep it just because a buy somewhere else scores higher

---

## 5. Rule definitions

### Rule E1 — Hard stop loss
Trigger when pnl falls below configured stop loss threshold.

Output:
- `action = sell`
- `priority = hard_stop`
- `quantity = full position`
- `exit_reason = stop_loss`

### Rule E2 — ATR stop
Trigger when market price falls below stop price maintained for the position.

Output:
- `action = sell`
- `priority = hard_stop`
- `quantity = full position`
- `exit_reason = atr_stop`

### Rule E3 — Trailing stop
If trailing is active and market price <= trailing stop, exit.

Output:
- `action = sell`
- `priority = protective`
- `quantity = full position`
- `exit_reason = trailing_stop`

### Rule E4 — Partial take profit
If TP1 target is reached and not already done, sell configured partial size.

Output:
- `action = sell`
- `priority = profit_take`
- `quantity = partial size`
- `exit_reason = partial_take_profit`

### Rule E5 — Timeout exit
If holding time exceeds max and progress is still below threshold, exit.

Output:
- `action = sell`
- `priority = protective`
- `quantity = full position`
- `exit_reason = timeout`

### Rule E6 — Trend reversal exit
If position exists and market/strategy state indicates reversal, allow soft exit.

Output:
- `action = sell`
- `priority = soft_exit`
- `quantity = full position by default`
- `exit_reason = trend_reversal`

---

## 6. Dust and executability policy

Exit policy should return a sell intent even when the position is dust-sized.
But a separate sellability decision should classify:
- executable now
- managed but below minimum
- dust/unmanaged

This keeps business intent separate from exchange executability.

That separation matters because right now dust handling leaks into orchestration and suppresses understanding of what the policy actually wanted to do.

---

## 7. Orchestrator arbitration rule

Recommended rule:
- any `hard_stop` or `protective` exit beats any buy candidate
- `profit_take` beats buy unless explicitly configured otherwise
- `soft_exit` may be compared against buy score, but the comparison must happen at orchestration level, not inside exit policy

This keeps domain ownership clear:
- exit policy decides **what exit means**
- orchestrator decides **which cycle action wins** when there are multiple valid actions

---

## 8. Migration notes

### Before migration
Current exit ownership is duplicated.

### After Wave 2 target
- `trend_following.py` keeps entry logic and optional exit hint generation only
- `paper_broker.py` keeps state/bookkeeping only
- `auto_trade_service.py` stops owning exit policy
- `exit` slice becomes the canonical exit decision owner

---

## 9. Approval questions for next implementation step

These are the only policy questions still worth confirming before code movement:

1. Should `profit_take` always beat buy, or can a stronger buy outrank it?
2. Should `trend_reversal` remain a full exit, or become configurable partial exit?
3. Should dust-sized exit intents still be logged as first-class exit decisions even when not executable?

Current recommended defaults:
- Q1: yes, profit_take beats buy
- Q2: full exit for now
- Q3: yes, log them explicitly
