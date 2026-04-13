# Weekly Report — 2026-03-21 ~ 2026-04-06

Generated: 2026-04-06 09:00 UTC

---

## Portfolio Summary

| Metric | Value |
|---|---|
| Starting Equity (Mar 21) | ~107,480 KRW |
| Ending Equity (Apr 6) | ~103,148 KRW |
| Peak Equity | ~107,744 KRW (Mar 24) |
| Low Equity | ~88,866 KRW (Apr 5 am) |
| Realized P&L (net) | **-39,338 KRW** |
| Unrealized P&L (current) | ~+53 KRW |
| Live orders submitted (week) | 9 (`auto_trade_start` events) |
| Actual live fills (broker accepted) | 0 |

**Net performance: -4.0% over ~16 days.** The bulk of realized losses came from a single large SOL sell event (~Mar 28) that racked up -2,306 KRW in one shot, with further cascading losses until positions were largely exited.

---

## Top Skip Reasons

| Reason | Count | Description |
|---|---|---|
| `non_actionable_signal` | 536 | DCA windows closed / mean_reversion deviations too small / no signal at all |
| `below_meaningful_order_notional_or_total_exposure_limit` | 201 | Target notional (~600–800 KRW) below `meaningful_order_notional=10000; also triggered when total exposure is near cap |
| `below_min_managed_position_notional` | 114 | Position already exceeds `min_managed_position_notional=10000`, so no new buys on that symbol |

**Note:** These are cumulative since the bot started; the skip distribution is consistent across the week.

---

## Live Trade Attempted — What Happened

1. **Mar 21–23**: BTC held (avg ~104.5M KRW). SOL trending; SOL signals repeatedly fired but blocked by `max_consecutive_buys=3` or exposure limit.
2. **Mar 23 16:20 KST**: SOL buy submitted (live fill). SOL avg price ~134,112 KRW. BTC was sold near the same time.
3. **Mar 24**: Partial SOL sell executed (position: 0.469→0.446 SOL, realized +150 KRW). BTC had been fully sold.
4. **Mar 28**: Large SOL sell — realized loss ~-2,306 KRW. **No stop-loss triggered** based on the drawdown reported (~0.5%). This event needs post-mortem.
5. **Mar 29 onwards**: Almost no managed positions. Most cycles: `non_actionable_signal` or `below_min_managed_position_notional`.

**Last 5 days (Apr 1–6):** `auto_trade_status.active=true` but `exposure=0` — no live positions held. Bot is cycling without filling anything.

---

## Strategy Behavior

| Strategy | Status | Notes |
|---|---|---|
| `trend_following` | Active signals, few fills | Triggers correctly on MA cross; blocked by broker guard `max_consecutive_buys` and exposure cap |
| `mean_reversion` | Silent | All hold signals; deviation ~0.001–0.005, momentum overriding |
| `dca` | Silent | `no_dca_window` — drawdown threshold not met in current ranging regime |

**Market regime this week:** BTC/SOL mostly ranging to slight uptrend. No strong directional move that DCA or mean_reversion could exploit.

---

## Runtime Issues

1. **`max_consecutive_buys=3` guard** — fires every cycle when SOL is in a slow uptrend. Legitimate signals are being rejected by the broker guard (not the auto-trader) before the size/exposure check even runs. This is the top blocker for trend-following buys.
2. **`meaningful_order_notional=10000`** — target notional for SOL-sized signals is ~600–800 KRW, which is consistently below this threshold. The bot generates a signal, gets a `hold` from review, and then the auto-trader skips it. The signal approval layer (`approved=true`) is separate from this skip, suggesting the auto-trade guard is the real gate.
3. **`no live fills despite active=true`** — since ~Apr 1, exposure=0 and no orders are being placed. The `semi_live` cycles show `broker_result` null or `max_consecutive_buys_reached`. The bot is running but not trading.
4. **SOL partial sell (Mar 24) root cause unclear** — partial take-profit or trailing stop likely triggered, but the drawdown at trigger (~0.5%) is much smaller than stop_loss_pct=1.5 or trailing_stop_pct=1.0. Either a manual override fired or the partial sell logic used a different threshold.

---

## Next Safe Tuning Ideas

1. **Lower `meaningful_order_notional` to 3000–5000 KRW**
   - Current value (10,000) far exceeds the natural signal size for SOL/ETH at current prices. Every signal's target notional is ~500–800 KRW.
   - Risk: more small orders → more fees, more noise. Tune conservatively (e.g., 5,000 first).

2. **Reset `max_consecutive_buys` counter after cooldown or partial sell**
   - The guard is a blunt instrument. After a partial sell reduces position, the buy count should decrement. Investigate whether this is a broker-level or bot-level setting.
   - Until fixed: consider increasing `cooldown_cycles` to 2–3 so buys don't stack so fast.

3. **Increase `max_total_exposure_pct` from 60% to 65–70% (or convert to absolute)**
   - At 10M KRW base, 60% = 6M cap. SOL signal target ~800 KRW is <1% of portfolio. The cap is fine in principle, but the exposure tracking may be including non-managed assets.
   - Verify whether `current_exposure` includes only managed positions or all exchange balances. If it includes the full SOL holding (even small ones), it may be understating available room.

4. **Add logging for the Mar 28 large sell event**
   - The -2,306 KRW realized loss on SOL needs post-mortem. Was it a manual intervention, a stop-loss that fired, or a misconfigured partial sell? Add structured log output for `broker_result.status=accepted` with `action=sell` and `reason`.

5. **Lower `min_managed_position_notional` to 5,000 or remove per-symbol gating**
   - Currently at 10,000. If the bot is already holding SOL above this threshold, it blocks new buys even when the position could be scaled up. Consider scaling logic instead of binary blocking.

---

## Config Snapshot (current)

```
trend_following  | BTC/ETH/SOL @ 1h
limit: 8 | max_consecutive_buys: 3 | cooldown_cycles: 1
meaningful_order_notional: 10000
min_managed_position_notional: 10000
max_total_exposure_pct: 60%
stop_loss_pct: 1.5 | partial_take_profit_pct: 2.0 | trailing_stop_pct: 1.0
partial_sell_ratio: 0.5
min_krw_balance: 15000
```

---

*Report generated by weekly-review cron. Data: run_history.json (3.2M entries) + monitor_history.jsonl.*
