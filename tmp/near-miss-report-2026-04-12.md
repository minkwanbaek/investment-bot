# Near-Miss Observation Report (2026-04-12 14:52 UTC)

## Executive Summary

**Threshold Decision: 현행 유지 (0.15%)**

After analyzing 76 near-miss records and running 3 additional executor cycles, we recommend **keeping the current 0.15% threshold** rather than relaxing to 0.12%.

---

## Observation Results

### Data Collection
- **Period:** 2026-04-12 00:00 ~ 14:52 UTC
- **Total near-miss count:** 76 records
- **Method:** run_history.jsonl analysis + 3 executor_cycle runs

### Key Statistics

#### Category Distribution
- **threshold:** 50 (65.8%) — trend_gap below threshold but blocked by route_filter
- **confirm_fail:** 26 (34.2%) — trend_gap >= threshold or momentum <= 0

#### Stage Distribution
- **route_filter:** 76 (100.0%) — **ALL blocked by route_filter**

#### Trend Gap Band Distribution
- **<0.10%:** 45 (59.2%)
- **0.10-0.12%:** 6 (7.9%)
- **0.12-0.15%:** 2 (2.6%)
- **>=0.15%:** 23 (30.3%)

→ **0.10~0.15% band total: 8 records (10.5%)**

#### Bottleneck Analysis
- **Momentum fail (momentum <= 0):** 26 (34.2%)
- **Route filter bottleneck:** 76 (100.0%)
- **Confirm fail (regime/momentum issue):** 26 (34.2%)

#### Top Symbols (near-miss frequency)
1. XLM/KRW: 16 times
2. HBAR/KRW: 14 times
3. TRX/KRW: 12 times
4. ETH/KRW: 11 times
5. BTC/KRW: 10 times

---

## Most Common Pattern

```
Category: threshold
Stage: route_filter
block_reason: "trend_strategy_route_blocked"
trend_gap: 0.04~0.07%
momentum: 0.07~0.21% (positive)
```

**Interpretation:**
- Most cases have trend_gap far below 0.15% threshold
- Momentum is often positive
- **Problem is route_filter (sideways regime), not trend_gap**

---

## Decision Rationale

### Why Keep 0.15% Threshold?

1. **Low 0.10-0.15% band ratio (10.5%)**
   - Only 8 records would benefit from 0.12% relaxation
   - Even with relaxation, route_filter would still block most

2. **100% route_filter bottleneck**
   - All near-miss records blocked by route_filter
   - **Market regime (sideways) is root cause, not threshold**

3. **Momentum positive ratio is 65.8% but irrelevant**
   - Route_filter blocks before momentum matters
   - Only mean_reversion allowed in sideways regime

4. **34.2% confirm_fail is regime issue**
   - Trend_gap exceeds threshold or momentum is negative
   - Threshold relaxation wouldn't help these cases

---

## Recommendations

### Priority 1: Route Filter Relaxation
- Consider allowing trend_following in sideways regime under certain conditions
- Example: Allow when `volatility_state=low`

### Priority 2: Keep Current Threshold
- Maintain 0.15% threshold
- Re-evaluate after 3+ days of data accumulation

### Priority 3: Continue Near-Miss Monitoring
- Automate daily near-miss aggregation
- Reconsider 0.12% if 0.10-0.15% band exceeds 20%

---

## Deliverables

- ✅ Document updated: `docs/trading-investigation-map.md`
- ✅ Git commit completed
- ❌ Threshold value change: **None** (keeping 0.15%)

---

## Analysis Script

Location: `tmp/analyze_near_miss_final.py`

Run with:
```bash
python3 tmp/analyze_near_miss_final.py
```
