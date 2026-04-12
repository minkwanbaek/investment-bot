# trend_following BUY Threshold Design Alternatives

**Date:** 2026-04-12  
**Author:** Planner (subagent: maker-threshold-design-options)  
**Status:** ✅ Complete — Design comparison documented, ready for approval  

---

## 1. Current trend_following BUY Conditions

### Core Conditions
| Parameter | Current Value | Description |
|-----------|---------------|-------------|
| `min_trend_gap_pct` | `0.15%` (0.0015) | Short MA (3) vs Long MA (8) divergence threshold |
| `momentum_pct` | `> 0` | Latest close vs previous close must be positive |
| Confidence formula | `abs(trend_gap_pct) * 120` | Scaled to 0-1 range |

### Exit Conditions (for reference)
| Parameter | Value | Description |
|-----------|-------|-------------|
| `stop_loss_pct` | `-2%` | PnL-based stop loss |
| `take_profit_pct` | `+5%` | PnL-based take profit |
| Trend reversal | `short_ma < long_ma` | Exit when trend flips |

### Actual BUY Cases (Evidence)
| Symbol | Time (UTC) | trend_gap_pct | momentum_pct | Outcome |
|--------|-----------|---------------|--------------|---------|
| DOGE/KRW | 05:33 | **0.40%** | 0.74% | ✅ Executed (5,002 KRW) |
| MANA/KRW | 06:49 | **0.32%** | >0 | ✅ Executed |
| WLD/KRW | 09:18 | **0.27%** | >0 | ✅ Executed |
| THETA/KRW | 08:22 | **0.18%** | >0 | ✅ Executed |

**Observation:** All actual BUYs had `trend_gap_pct` between **0.18% - 0.40%**, comfortably above the 0.15% threshold.

### Current Market Conditions (No BUY)
| Symbol | trend_gap_pct | momentum_pct | Gap to Threshold |
|--------|---------------|--------------|------------------|
| BTC/KRW | **-0.02%** | -0.06% | -0.17% (negative trend) |
| ETH/KRW | **+0.03%** | 0.00% | -0.12% (below threshold) |
| THETA/KRW | **-0.20%** | 0.00% | -0.35% (negative trend) |

**Root Cause:** Current market is in **sideways/declining regime**, not lacking threshold strictness.

---

## 2. Design Alternatives Comparison

### Alternative A: Conservative — Maintain Current Threshold

| Aspect | Assessment |
|--------|------------|
| **Change** | None — keep `min_trend_gap_pct = 0.15%` |
| **Expected Effect** | BUY frequency unchanged (still 0 in current regime) |
| **Risk** | None — strategy character preserved |
| **Implementation** | N/A |
| **Recommendation** | ✅ **Recommended for now** |

**Rationale:**
- 0.15% is **achievable** (4 actual BUY cases proved this)
- Problem is **market regime**, not threshold strictness
- Lowering threshold now would increase false positives in sideways market
- Wait for natural uptrend regime transition

**When to reconsider:** If sideways regime persists >1 week with zero BUYs, revisit.

---

### Alternative B: Moderate — Reduce trend_gap_pct to 0.12%

| Aspect | Assessment |
|--------|------------|
| **Change** | `min_trend_gap_pct: 0.15% → 0.12%` (-20%) |
| **Expected Effect** | BUY frequency +30-50% in marginal conditions |
| **Risk** | 🟡 Moderate — may capture weaker trends, lower win rate |
| **Implementation** | Low (1-line config/code change) |
| **Recommendation** | ⚠️ **Conditional** — only if sideways persists >3-5 days |

**Rationale:**
- 0.12% is still above noise level for 5m candles
- Would have captured ETH/KRW at +0.03% gap (currently missed)
- But ETH's +0.03% is **weak signal** — high false positive risk
- Historical BUYs were all >0.18%, so 0.12% is untested territory

**Trade-off:**
- ✅ More BUY opportunities in marginal uptrends
- ❌ Lower average trend strength per trade
- ❌ Potential whipsaw in sideways markets

---

### Alternative C: Aggressive — Reduce trend_gap_pct to 0.10% + Add Momentum Filter

| Aspect | Assessment |
|--------|------------|
| **Change** | `min_trend_gap_pct: 0.15% → 0.10%` (-33%) <br> `momentum_pct: > 0 → ≥ 0.05%` (stricter) |
| **Expected Effect** | BUY frequency +50-80%, but stricter momentum filter offsets some |
| **Risk** | 🔴 High — fundamentally changes strategy character |
| **Implementation** | Low (2-line change) |
| **Recommendation** | ❌ **Not recommended** — too aggressive for current mandate |

**Rationale:**
- 0.10% approaches noise level for 5m candles
- Adding momentum filter (≥0.05%) helps, but doesn't fully compensate
- This becomes a **different strategy** (scalping vs trend following)
- Would require fresh backtesting to validate

**When to consider:** Only if explicitly pivoting to shorter-timeframe strategy.

---

### Alternative D: Hybrid — Keep 0.15% but Add Volatility-Adjusted Threshold

| Aspect | Assessment |
|--------|------------|
| **Change** | `min_trend_gap_pct = 0.15% * volatility_multiplier` <br> - Low vol: ×0.8 → 0.12% <br> - Normal vol: ×1.0 → 0.15% <br> - High vol: ×1.2 → 0.18% |
| **Expected Effect** | Adaptive BUY frequency — more signals in calm markets, fewer in volatile |
| **Risk** | 🟡 Low-Moderate — adds complexity but preserves intent |
| **Implementation** | Medium (requires volatility calculation + config) |
| **Recommendation** | 🟢 **Recommended for future enhancement** |

**Rationale:**
- Current fixed threshold doesn't account for changing market volatility
- In low-vol regimes, 0.15% may be too strict (trends are smaller)
- In high-vol regimes, 0.15% may be too loose (more false breakouts)
- Uses existing `volatility_state` from `market_regime_classifier`

**Implementation sketch:**
```python
vol_multiplier = {"low": 0.8, "normal": 1.0, "high": 1.2}[volatility_state]
adjusted_threshold = self.min_trend_gap_pct * vol_multiplier
if trend_gap_pct >= adjusted_threshold and momentum_pct > 0:
    action = "buy"
```

**Trade-off:**
- ✅ More adaptive to market conditions
- ✅ Preserves strategy intent (trend following)
- ❌ Adds complexity (new config, testing burden)
- ❌ Requires backtesting to tune multipliers

---

## 3. Comparison Summary

| Alternative | trend_gap_pct | Momentum Filter | BUY Freq ↑ | False Positive Risk | Strategy Change | Recommendation |
|-------------|---------------|-----------------|------------|---------------------|-----------------|----------------|
| **A: Current** | 0.15% | > 0 | — | — | None | ✅ **Now** |
| **B: Moderate** | 0.12% | > 0 | +30-50% | 🟡 Moderate | Minor | ⚠️ If sideways >3-5 days |
| **C: Aggressive** | 0.10% | ≥ 0.05% | +50-80% | 🔴 High | Significant | ❌ Not now |
| **D: Vol-Adjusted** | 0.12-0.18% (adaptive) | > 0 | Variable | 🟡 Low-Moderate | Moderate | 🟢 Future enhancement |

---

## 4. Recommendation

### Primary Recommendation: **Alternative A (Maintain Current)**

**Why:**
1. **0.15% is proven achievable** — 4 actual BUY cases (0.18%-0.40% range)
2. **Current problem is regime, not threshold** — market is sideways/declining
3. **No evidence of false negatives** — all BUYs that met 0.15% were executed successfully
4. **Premature optimization** — lowering threshold before regime change = chasing signals

**Action:**
- ✅ Keep `min_trend_gap_pct = 0.15%`
- ✅ Monitor for regime transition (sideways → uptrend)
- ✅ Revisit if zero BUYs persist >1 week in clearly trending market

### Conservative Alternative: **Alternative A + Enhanced Monitoring**

If concerned about missing opportunities:
- Add logging: `near_miss_buy` when `trend_gap_pct` is 0.10%-0.15% (close but rejected)
- Track near-miss frequency to quantify opportunity cost
- Use data to inform future threshold decisions

### Aggressive Alternative (if explicitly requested): **Alternative B**

Only if:
- Sideways regime persists >3-5 consecutive days
- Near-miss analysis shows consistent 0.12%-0.14% gaps that would have been profitable
- User explicitly accepts higher false positive risk

---

## 5. Evidence-Based Threshold Estimation

### Question: "How much relaxation is needed to generate signals?"

**Answer based on current market data:**

| Required Relaxation | Symbols That Would Trigger | Estimated BUY Frequency |
|---------------------|---------------------------|-------------------------|
| None (0.15%) | 0 symbols | 0 / day (current) |
| 0.12% (-20%) | ETH/KRW (+0.03% still no), marginal cases | +1-2 / day (estimate) |
| 0.10% (-33%) | More marginal cases | +2-4 / day (estimate) |
| 0.08% (-47%) | Approaching noise level | +4-6 / day (high risk) |

**Current market gaps (09:30 UTC):**
- Best case: ETH/KRW +0.03% (needs -0.12% relaxation)
- Most symbols: Negative trend_gap (relaxation won't help — need trend reversal)

**Conclusion:** Even dropping to 0.10% would only capture **marginal cases** in current market. The real issue is **trend direction**, not threshold strictness.

### Historical Context

**When BUYs occurred (05:33-09:18 UTC):**
- Market had clear uptrend pockets
- trend_gap consistently 0.18%-0.40%
- 0.15% threshold was **not** the limiting factor

**Current market (09:30+ UTC):**
- Market transitioned to sideways/declining
- trend_gap mostly negative or <0.05%
- No threshold relaxation will fix this — need **trend reversal**

---

## 6. Implementation Notes

### If Alternative B or D is Approved

**Files to modify:**
1. `src/investment_bot/strategies/trend_following.py` — threshold constant
2. `config/app.yml` — optional: add `strategy.trend_following.min_trend_gap_pct` for runtime config
3. `docs/trading-investigation-map.md` — update with decision rationale

**Testing:**
- Run semi-live backtest on recent 7-day data
- Compare BUY count, win rate, avg trend_gap between old/new thresholds
- Check for increased whipsaw (quick exit after entry)

**Rollback plan:**
- Git revert if false positives exceed tolerance
- Or add temporary `threshold_mode: conservative|moderate` config switch

---

## 7. Decision Checklist

Before approving any threshold change:

- [ ] **Confirm regime diagnosis:** Is market truly sideways, or early uptrend?
- [ ] **Check near-miss log:** Are there 0.12%-0.14% gaps being rejected?
- [ ] **Review recent BUY outcomes:** Were 0.15%+ BUYs profitable? (If yes, threshold is fine)
- [ ] **Consider time horizon:** Is this a 1-day drought or 1-week drought?
- [ ] **Evaluate alternatives:** Would DCA/mean_reversion threshold tweaks be better?

---

## 8. Final Summary

| Item | Status |
|------|--------|
| **Current threshold** | 0.15% (proven achievable) |
| **Root cause of BUY drought** | Market regime (sideways), not threshold |
| **Recommended action** | ✅ Maintain 0.15%, wait for regime change |
| **Fallback (if persists >3-5 days)** | ⚠️ Consider 0.12% (Alternative B) |
| **Future enhancement** | 🟢 Volatility-adjusted threshold (Alternative D) |
| **Document updated** | ✅ `docs/trading-investigation-map.md` |
| **Git commit** | ⏳ Pending approval |

---

**Notes:**
- This analysis is **evidence-based** (4 actual BUY cases, current market snapshots)
- Recommendation prioritizes **strategy integrity** over signal frequency
- Threshold changes should be **regime-aware**, not reactive to short-term droughts
