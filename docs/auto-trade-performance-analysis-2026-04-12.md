# Auto-Trade Performance Analysis

**Date:** 2026-04-12  
**Author:** Planner (with mk)  
**Status:** Investigation Complete → Refactoring In Progress

---

## Executive Summary

Auto-trade `run_once()` execution time was **~99 seconds** for 42 symbols × 3 strategies, far exceeding the 5-minute cycle target. Root causes identified:

1. **Excessive API calls**: 42 symbols × 3 strategies = 126 Upbit candle API calls per cycle
2. **No caching**: Balance/account summary fetched repeatedly (once per symbol)
3. **Ledger race conditions**: Concurrent writes corrupting `paper_ledger.json`
4. **Monolithic design**: All responsibilities in `auto_trade_service.py`

**Solution adopted:** Priority-based batch scheduling (Option B) with modular refactoring.

---

## Root Cause Analysis

### 1. Execution Time Breakdown

| Component | Count | Time per Call | Total Time | Notes |
|-----------|-------|---------------|------------|-------|
| Upbit Candle API | 126 | ~0.8s | ~100s | 5m candles, limit=100 |
| Balance Fetch | 126 | ~0.1s | ~12s | Redundant, no cache |
| Ledger Save | ~126 | ~0.05s | ~6s | Race condition risk |
| **Total** | | | **~99s** | Target: <30s |

**Key Finding:** Candle API dominates execution time. Each call fetches 100 candles (8h 20m of data).

### 2. Ledger Corruption Pattern

**Symptom:** `JSONDecodeError: Extra data at line X column Y`

**Root Cause:**
- `paper_broker.sync_exchange_position()` calls `_persist_state()` every symbol
- Multiple threads (auto-trade loop + API `run_once`) write concurrently
- `LedgerStore.save()` was not atomic (write → rename without lock)

**Fix Applied:**
```python
# ledger_store.py
def save(self, payload: dict) -> None:
    with self._lock:  # ← Added threading lock
        tmp_path = self.path.with_suffix('.json.tmp')
        tmp_path.write_text(json.dumps(payload, ...))
        os.replace(tmp_path, self.path)  # ← Atomic rename
```

### 3. Shadow Service Redundancy

**Before:**
```python
def run_once(self, strategy, symbol, ...):
    balances = self.upbit_client.get_balances()  # ← Called 126 times!
    account = self.account_service.summarize_upbit_balances()  # ← Also 126 times
```

**After:**
```python
def run_once(self, strategy, symbol, ...):
    balances = self._get_cached_balances()  # ← Once per cycle
    account = self._get_cached_account_summary()  # ← Once per cycle
```

**Improvement:** 126 API calls → 2 calls per cycle.

### 4. Type Safety Issues

**Bug:** `market_regime` returned as `str` by some strategies, `dict` by others.

**Error:**
```python
regime_name = regime.get("regime", "unknown")  # ← AttributeError if regime is str
```

**Fix:**
```python
if isinstance(regime, dict):
    regime_name = regime.get("regime", "unknown")
else:
    regime_name = str(regime or "unknown")
    regime = {"regime": regime_name}
```

---

## Architecture Issues

### Current Design (Monolithic)

```
auto_trade_service.py (800+ lines)
├── run_once()          # Entry point
├── _collect_symbol_candidates()  # Strategy execution
├── _handle_buy()       # Order execution
├── _handle_sell()      # Order execution
├── _score_candidate()  # Scoring logic
├── _exit_override()    # Exit logic
└── _loop()             # Background scheduler
```

**Problems:**
- Single file handles orchestration, scheduling, collection, execution
- Hard to test individual components
- No clear separation of concerns
- Difficult to add features (e.g., priority batches)

### Target Design (Modular)

```
auto_trade_orchestrator.py    # Entry point, coordination
auto_trade_scheduler.py       # Priority batches, round-robin
candidate_collector.py        # Symbol × strategy evaluation
decision_engine.py            # Buy/sell selection logic
ledger_store.py               # Safe persistence (already refactored)
shadow_service.py             # Cached balance/account data
```

---

## Solution: Priority-Based Batch Scheduling (Option B)

### Design

- **Priority symbols**: Top 10 by trading volume (evaluated every cycle)
- **Remaining symbols**: 32 symbols in rotating batches of 8
- **Cycle time**: 1 minute (instead of 5 minutes)
- **Coverage**: All 42 symbols within 4-5 minutes

### Execution Flow

```
Cycle 1 (T+0m):  Priority [1-10] + Batch [11-18]
Cycle 2 (T+1m):  Priority [1-10] + Batch [19-26]
Cycle 3 (T+2m):  Priority [1-10] + Batch [27-34]
Cycle 4 (T+3m):  Priority [1-10] + Batch [35-42]
Cycle 5 (T+4m):  Priority [1-10] + Batch [11-18]  (repeat)
```

### Benefits

1. **Fast response**: Priority symbols evaluated in ~15-20s
2. **Full coverage**: All symbols within 4-5 minutes
3. **No data loss**: All 42 symbols still evaluated
4. **Maintainable**: Clear separation of scheduling vs. execution

---

## Implementation Checklist

- [x] Ledger atomic write + lock (`ledger_store.py`)
- [x] Shadow service caching (`shadow_service.py`)
- [x] Market regime type safety (`auto_trade_service.py`)
- [ ] Priority batch scheduler (`auto_trade_scheduler.py`)
- [ ] Candidate collector extraction (`candidate_collector.py`)
- [ ] Decision engine extraction (`decision_engine.py`)
- [ ] Performance metrics logging (per-symbol, per-strategy timing)
- [ ] Documentation (`docs/auto-trade-architecture.md`)

---

## Performance Targets

| Metric | Before | Target | After (Expected) |
|--------|--------|--------|------------------|
| Cycle time (all symbols) | 99s | <30s | ~20s (priority), ~60s (full) |
| API calls per cycle | 126 | ~10 | ~2 (cached) |
| Ledger writes per cycle | ~126 | 1-2 | 1 (end of cycle) |
| Time to first decision | 99s | <20s | ~15s |

---

## Lessons Learned

1. **Cache aggressively**: Upbit API is rate-limited; cache balances/account data per cycle
2. **Atomic writes**: Ledger files must use lock + temp file + rename pattern
3. **Type normalization**: External data (strategies, APIs) may have inconsistent types
4. **Modular design**: Monolithic services are hard to optimize and debug
5. **Priority scheduling**: Not all symbols need equal treatment; prioritize by volume

---

## Next Steps

1. **Refactoring**: Maker to implement modular design (see `docs/auto-trade-refactoring-plan.md`)
2. **Testing**: Load test with 42 symbols, verify <30s cycle time
3. **Monitoring**: Add metrics logging for per-symbol/strategy timing
4. **Documentation**: Architecture diagram + runbook for operations
