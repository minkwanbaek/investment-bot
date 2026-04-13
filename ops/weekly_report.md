# Investment Bot Weekly Report
**Period:** March 17 - March 24, 2026  
**Generated:** April 13, 2026 09:00 UTC

---

## Executive Summary

The bot operated in **live mode** with auto-trade enabled for most of the week. Primary activity centered on **SOL/KRW** position building via trend-following signals, while BTC and ETH remained largely inactive due to exposure limits and non-actionable signals.

**Portfolio Status (Latest):**
- Total Equity: ~₩106,852
- Realized PnL: +₩150.94
- Unrealized PnL: +₩275.82
- Cash Balance: ₩43,644
- Managed Position: SOL/KRW (₩63,207 market value)

---

## Top Skip Reasons

| Reason | Count | Context |
|--------|-------|---------|
| `below_meaningful_order_notional_or_total_exposure_limit` | ~15+ | Exposure cap (60%) reached; remaining room < ₩1,000 vs ₩10,000 minimum order size |
| `non_actionable_signal` | ~10+ | DCA/Mean-reversion strategies returned hold signals with low confidence |
| `max_consecutive_buys_reached` | ~6+ | Broker rejected buys after 3 consecutive purchases |
| `below_min_managed_position_notional` | 2 | BTC position closed; below ₩10,000 threshold |

**Key Constraint:** The bot consistently hit the **total exposure limit** (₩64,227 max, ~₩63,600 current), leaving insufficient room for new ₩10,000+ orders.

---

## Runtime Issues

### 1. Exposure Cap Binding
- **Symptom:** Approved buy signals rejected at broker level
- **Root Cause:** `max_total_exposure_pct: 60.0` with current equity leaves only ~₩800-₹1,000 room
- **Impact:** Trend-following buys on SOL/KRW blocked despite positive signals (confidence 0.40-0.74)

### 2. Consecutive Buy Limit
- **Symptom:** `max_consecutive_buys_reached` rejections
- **Threshold:** 3 consecutive buys triggers cooldown
- **Affected:** SOL/KRW accumulation attempts on March 21

### 3. Strategy Signal Quality
- **DCA:** Consistently returned `hold` (confidence: 0.0) — no drawdown windows triggered
- **Mean Reversion:** Low confidence signals (0.01-0.06) — deviation too small
- **Trend Following:** Only actionable strategy; generated multiple approved buys

---

## Strategy Behavior

### Trend Following (Primary Actor)
- **Symbols:** SOL/KRW, BTC/KRW, ETH/KRW
- **Performance:** Generated valid buy signals with confidence 0.40-0.75
- **Outcome:** Successfully built SOL position (0.469 SOL @ avg ₩134,112); BTC/ETH buys blocked by exposure limits
- **Market Regime Detection:** Correctly identified uptrend conditions (trend_gap: 0.3-0.6%, momentum: 0.2-0.4%)

### DCA (Inactive)
- **Status:** No trades executed
- **Reason:** Drawdown thresholds not met (observed drawdown: 0.1-0.7% vs required deeper dips)
- **Signals:** All `hold` with 0.0 confidence

### Mean Reversion (Inactive)
- **Status:** No trades executed
- **Reason:** Price deviation from mean too small (<1%)
- **Signals:** Low confidence holds (0.01-0.06)

---

## Next Safe Tuning Ideas

### 1. Adjust Exposure Limits (Low Risk)
```json
// Current: max_total_exposure_pct: 60.0
// Proposal: Increase to 70-75% or reduce min_managed_position_notional
```
**Rationale:** Bot is capital-constrained, not signal-constrained. Small increase would enable execution of validated trend signals.

### 2. Reduce Meaningful Order Notional (Medium Risk)
```json
// Current: meaningful_order_notional: 10000.0
// Proposal: Test ₩5,000-₩7,500 for smaller position increments
```
**Rationale:** Would allow partial fills when near exposure cap; reduces granularity problem.

### 3. Relax Consecutive Buy Limit (Medium Risk)
```json
// Current: max_consecutive_buys: 3
// Proposal: Increase to 4-5 or add time-based cooldown instead
```
**Rationale:** Prevents premature stopping during strong trending periods.

### 4. Add ETH/KRW Starter Position (Low Risk)
- **Observation:** ETH has zero position despite valid trend signals
- **Proposal:** Manual seed position (₩10,000-₩20,000) to enable strategy participation
- **Alternative:** Lower `min_managed_position_notional` for ETH specifically

### 5. DCA Parameter Review (Exploratory)
- **Issue:** DCA never triggers — may be over-conservative for current market
- **Proposal:** Review drawdown threshold logic; consider adding time-based DCA fallback

---

## Recommendations Priority

1. **Immediate:** Raise `max_total_exposure_pct` to 70% (unlocks existing signals)
2. **Short-term:** Reduce `meaningful_order_notional` to ₩7,500 (improves execution granularity)
3. **Monitor:** Watch SOL/KRW position for take-profit triggers (set at +2.0%)
4. **Optional:** Seed ETH position manually if trend continuation expected

---

*Report generated from `/data/run_history.json` (IDs 2239+) and `/ops/monitor_history.jsonl` (March 20-24 entries)*
