# Auto-Trade Refactoring Plan

**Date:** 2026-04-12  
**Status:** Ready for Implementation  
**Assigned To:** Maker

---

## Overview

Refactor `auto_trade_service.py` (monolithic, 800+ lines) into modular components with clear separation of concerns.

**Goals:**
1. Improve maintainability (single responsibility per module)
2. Enable priority-based batch scheduling
3. Add performance metrics logging
4. Preserve existing functionality (no behavior changes except performance)

---

## Module Structure

### 1. `auto_trade_orchestrator.py` (NEW)

**Responsibility:** Entry point, coordination, lifecycle management

```python
class AutoTradeOrchestrator:
    def __init__(self, scheduler, collector, decision_engine, execution_service):
        self.scheduler = scheduler
        self.collector = collector
        self.decision_engine = decision_engine
        self.execution_service = execution_service
    
    def run_once(self) -> dict:
        """Main entry point for auto-trade cycle"""
        # 1. Get batch from scheduler
        # 2. Collect candidates
        # 3. Make decision
        # 4. Execute (if action)
        # 5. Return result
```

**Key Methods:**
- `run_once()` → Main cycle
- `start()` → Start background loop
- `stop()` → Stop background loop

---

### 2. `auto_trade_scheduler.py` (NEW)

**Responsibility:** Priority batch scheduling, round-robin for remaining symbols

```python
class AutoTradeScheduler:
    def __init__(self, symbols: list, priority_count: int = 10, batch_size: int = 8):
        self.all_symbols = symbols
        self.priority_symbols = symbols[:priority_count]
        self.remaining_symbols = symbols[priority_count:]
        self.batch_index = 0
        self.batch_size = batch_size
    
    def get_next_batch(self) -> list:
        """Return priority symbols + next batch of remaining symbols"""
        # Round-robin through remaining symbols
        start = self.batch_index * self.batch_size
        end = start + self.batch_size
        batch = self.remaining_symbols[start:end]
        
        # Wrap around
        if end >= len(self.remaining_symbols):
            self.batch_index = 0
        else:
            self.batch_index += 1
        
        return self.priority_symbols + batch
```

**Configuration (app.yml):**
```yaml
auto_trade:
  priority_count: 10      # Top symbols always evaluated
  batch_size: 8           # Remaining symbols per cycle
  interval_seconds: 60    # Cycle time
```

---

### 3. `candidate_collector.py` (NEW)

**Responsibility:** Evaluate symbols × strategies, collect candidates

```python
class CandidateCollector:
    def __init__(self, shadow_service, strategy_selection_service):
        self.shadow_service = shadow_service
        self.strategy_selection_service = strategy_selection_service
    
    def collect(self, symbols: list) -> list:
        """Evaluate all symbols and return candidates"""
        candidates = []
        for symbol in symbols:
            symbol_candidates = self._collect_for_symbol(symbol)
            candidates.extend(symbol_candidates)
        return candidates
    
    def _collect_for_symbol(self, symbol: str) -> list:
        """Evaluate single symbol across all strategies"""
        # Call shadow_service for each strategy
        # Apply exit overrides
        # Score candidates
        # Return best candidate per symbol
```

**Key Design:**
- Shadow service cache is shared across all symbols in a cycle
- Candle API calls are the bottleneck; cache at shadow level

---

### 4. `decision_engine.py` (NEW)

**Responsibility:** Select best action from candidates

```python
class DecisionEngine:
    def __init__(self, min_managed_position_notional: float):
        self.min_managed_position_notional = min_managed_position_notional
    
    def decide(self, candidates: list, account: dict) -> dict:
        """
        Select best action from candidates.
        
        Priority:
        1. Forced exits (stop_loss, etc.)
        2. Sell candidates
        3. Buy candidates
        4. Hold (no action)
        """
        # Filter sell candidates
        # Filter buy candidates
        # Score and select
        # Return decision dict
```

**Decision Flow:**
```
candidates → filter sells → check overrides → select best
         → if no sell → filter buys → select best
         → if no buy → return "hold"
```

---

### 5. `auto_trade_service.py` (REFACTORED)

**After Refactoring:**
```python
# Thin wrapper around orchestrator
class AutoTradeService:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
    
    def run_once(self) -> dict:
        return self.orchestrator.run_once()
    
    def start(self) -> dict:
        # Start background loop
        # Call orchestrator.start()
    
    def stop(self) -> dict:
        # Stop background loop
        # Call orchestrator.stop()
```

**Before:** 800+ lines, handles everything  
**After:** ~100 lines, delegates to components

---

### 6. `ledger_store.py` (ALREADY REFACTORED)

**Current Status:** ✅ Done

- Atomic write (temp file + rename)
- Threading lock for concurrent access
- Corruption recovery (return empty ledger on JSONDecodeError)

---

### 7. `shadow_service.py` (ALMOST DONE)

**Current Status:** ✅ Caching added

- `_get_cached_balances()` → Cache per cycle
- `_get_cached_account_summary()` → Cache per cycle
- `invalidate_cache()` → Clear cache at cycle start

---

## Implementation Order

1. **Phase 1: Foundation** (Already Done)
   - [x] `ledger_store.py` atomic write + lock
   - [x] `shadow_service.py` caching
   - [x] Type safety fixes (`market_regime`, etc.)

2. **Phase 2: Core Modules** (Maker to Implement)
   - [ ] `auto_trade_scheduler.py`
   - [ ] `candidate_collector.py`
   - [ ] `decision_engine.py`

3. **Phase 3: Orchestrator** (Maker to Implement)
   - [ ] `auto_trade_orchestrator.py`
   - [ ] Wire components together

4. **Phase 4: Refactor Service** (Maker to Implement)
   - [ ] `auto_trade_service.py` → thin wrapper
   - [ ] Update container.py dependencies

5. **Phase 5: Testing & Metrics** (Maker to Implement)
   - [ ] Add timing metrics (per-symbol, per-strategy)
   - [ ] Load test with 42 symbols
   - [ ] Verify <30s cycle time

---

## Code Style Guidelines

### Logging

```python
logger.info("run_once started | symbols=%d priority=%d batch=%d", 
            len(symbols), len(priority), len(batch))

logger.info("candidate collection | symbol=%s strategy=%s elapsed=%.2fs",
            symbol, strategy_name, elapsed)

logger.info("decision | action=%s symbol=%s score=%.2f",
            action, symbol, score)
```

### Type Hints

```python
def collect(self, symbols: list[str]) -> list[dict]:
    ...

def decide(self, candidates: list[dict], account: dict) -> dict:
    ...
```

### Error Handling

```python
try:
    result = self.shadow_service.run_once(...)
except Exception as e:
    logger.exception("shadow error for %s: %s", symbol, e)
    continue  # Skip this symbol, continue with others
```

---

## Testing Checklist

- [ ] Unit test: `AutoTradeScheduler.get_next_batch()` (round-robin logic)
- [ ] Unit test: `DecisionEngine.decide()` (priority ordering)
- [ ] Integration test: Full cycle with 42 symbols
- [ ] Performance test: Verify <30s cycle time
- [ ] Ledger test: Concurrent writes don't corrupt file
- [ ] Recovery test: Corrupted ledger → auto-recover

---

## Migration Notes

**No Breaking Changes:**
- API endpoints remain the same (`/auto-trade/run-once`, `/auto-trade/status`)
- Config structure remains the same (new fields are optional)
- Ledger format unchanged

**Backward Compatibility:**
- If `priority_count` not in config, default to 10
- If `batch_size` not in config, default to 8
- Old behavior (all symbols every cycle) is deprecated but still works

---

## Success Criteria

1. **Performance:** Cycle time <30s for 42 symbols
2. **Stability:** No ledger corruption after 100+ cycles
3. **Maintainability:** Each module <200 lines, single responsibility
4. **Observability:** Logs show per-symbol timing, decision rationale

---

## References

- Performance Analysis: `docs/auto-trade-performance-analysis-2026-04-12.md`
- Architecture Overview: `docs/auto-trade-architecture.md` (to be created)
- Original Issue: Ledger corruption + 99s cycle time
