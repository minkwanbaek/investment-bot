# PRD Follow-Up Validation - 2026-05-14

## Current PRD vs Recent Evidence

- `config/prd.yml` now starts the 5m live experiment with `dynamic_symbol_selection: true`, `dynamic_symbol_top_n: 12`, 19 symbols, all three strategies enabled, `min_krw_balance: 10000`, `max_total_exposure_pct: 50.0`, and `min_managed_position_notional: 1500.0`.
- `logs/prd-launch.log` startup confirms the current PRD values are loaded, including `enabled_strategies: ['dca', 'mean_reversion', 'trend_following']`, `timeframe: 5m`, `limit: 100`, `dynamic_symbol_top_n: 12`, and 19 configured symbols.
- Older monitor evidence in `ops/latest_monitor.json` showed selector starvation / non-actionable operation under a different profile: 42 symbols, `dynamic_symbol_selection: false`, top 10 batch, and `reason: non_actionable_signal`.
- The current PRD is directionally safer than that older evidence: smaller symbol universe, dynamic selection enabled, ranked fallback code present, all three strategies enabled, and lower managed-position threshold.

## Commands Run

- PASS: `.venv/bin/python -m pytest tests/test_strategies.py tests/test_auto_trade_service.py::test_auto_trade_uses_ranked_dynamic_fallback_slice_when_selector_returns_zero tests/test_backtest.py::test_replay_backtest_lower_trend_gap_enters_early_continuation tests/test_backtest.py::test_replay_backtest_low_volatility_1p15_size_expands_smooth_continuation_profit tests/test_backtest.py::test_trading_cycle_applies_mean_reversion_managed_rebound_exit tests/test_backtest.py::test_trading_cycle_applies_dca_managed_rebound_exit -q`
  - Result: `26 passed in 0.22s`.
- PASS: replay-style 5m smoke for `trend_following`, `mean_reversion`, and `dca` using local replay candles.
  - `trend_following`: 5 steps, 5 holds, 0 orders, `return_pct=0.0`.
  - `mean_reversion`: 5 steps, 2 buys, 2 orders, `return_pct=0.0509`.
  - `dca`: 5 steps, 4 buys, 3 orders, `return_pct=0.1267`.
- FAIL: `.venv/bin/python -m pytest tests/test_strategies.py tests/test_backtest.py::test_replay_backtest_runs_multiple_steps_and_returns_summary tests/test_backtest.py::test_replay_backtest_lower_trend_gap_enters_early_continuation tests/test_backtest.py::test_replay_backtest_low_volatility_1p15_size_expands_smooth_continuation_profit tests/test_backtest.py::test_trading_cycle_applies_mean_reversion_managed_rebound_exit tests/test_backtest.py::test_trading_cycle_applies_dca_managed_rebound_exit tests/test_dynamic_symbol_selector.py -q`
  - Result: 62 passed, 1 failed.
  - Failure: `test_selector_volume_window_matches_trend_entry_gate_for_actionable_breakout` expected `TrendFollowingStrategy` to hold on stale volume, but it returned buy. This indicates selector volume gating is stricter than the strategy entry gate.

## Fetch-Error Symbol Cleanup

- Current `logs/prd-launch.log` only contains startup data, so repeated live fetch-error counts are not present in that file after the current launch.
- Earlier captured selector debug showed repeated fetch errors around `APT/KRW`, `SUI/KRW`, `AVAX/KRW`, `DOT/KRW`, `SEI/KRW`, and often `ONDO/KRW` / `ENA/KRW`.
- Do not remove symbols yet based only on the truncated current launch log. If the next live cycle repeats the same fetch-error set for 3 consecutive cycles, temporarily remove those symbols from `trading.symbols` and keep the liquid core: `BTC/KRW`, `ETH/KRW`, `SOL/KRW`, `XRP/KRW`, `ADA/KRW`, `DOGE/KRW`, `XLM/KRW`, `TRX/KRW`, `HBAR/KRW`, `LINK/KRW`.

## Next Safest Tuning Step

First config/code-level follow-up should be alignment, not loosening:

1. Align `TrendFollowingStrategy.min_entry_volume_ratio` with selector confirmation, or make both read the same config knob. Current selector stale-volume test shows the strategy can buy what the selector rejects.
2. Keep current PRD risk knobs unchanged for the next live observation window.
3. If `non_actionable_signal` remains dominant after selector alignment and fetch errors are clean, loosen only one knob: reduce `sideway_filter.trend_gap_threshold` from `0.0015` to `0.0012`.

## Rollback Criteria

- Roll back to the previous conservative PRD if live previews show more than 2 rejected/blocked order attempts in 1 hour, any unexpected live buy above `base_entry_notional`, repeated fetch errors for more than 30% of the symbol universe across 3 cycles, or a new unit failure outside the known selector/strategy volume-gate mismatch.
