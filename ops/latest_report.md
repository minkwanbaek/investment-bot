# Investment Bot Tune Report

- generated_at: `2026-03-22T02:15:00Z`
- health: `ok`
- pytest: `28 passed` (0 failed)
- run-once: `skipped (non_actionable_signal)` — all 3 symbols hold, correct behavior

## Change Applied

**File:** `src/investment_bot/services/strategy_selection_service.py`
**Type:** strategy selection logic (low-risk)
**Description:** BTC/KRW was missing allowed strategies for `ranging` and `mixed` regimes (returned empty list → always skipped). Added `dca` as allowed strategy for these regimes, consistent with SOL/KRW's existing pattern.

**Before:** BTC/KRW ranging/mixed → `[]` (no strategy, always skipped)
**After:** BTC/KRW ranging/mixed → `["dca"]`

## Verification

- New test file: `tests/test_strategy_selection_service.py` (11 tests)
- All 28 tests passed (including existing strategy + auto-trade tests)
- Server restarted, health OK
- run-once confirmed BTC/KRW now evaluates `dca` in mixed regime (hold signal, no order — correct)

## Observations

- All 3 symbols in mixed regime currently, all holding — market quiet
- BTC position sold (was 0.00060394 BTC, now 0 in portfolio); KRW cash up to ~107K
- Total equity: ₩107,646
