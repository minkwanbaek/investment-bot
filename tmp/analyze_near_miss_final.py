#!/usr/bin/env python3
"""
Near-miss analysis script for investment-bot - Final Report Version
Collects structured near-miss metrics from run_history
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
run_history_file = project_root / "data" / "run_history" / "2026-04-12.jsonl"

# Counters
total_near_miss = 0
category_counts = defaultdict(int)
stage_counts = defaultdict(int)
trend_gap_bands = defaultdict(int)  # 0.10-0.12%, 0.12-0.15%, etc
momentum_fail_count = 0
route_filter_count = 0
confirm_fail_count = 0
execution_near_miss_count = 0

# Detailed samples
samples = []
symbols_with_near_miss = defaultdict(int)

with open(run_history_file, 'r') as f:
    for line in f:
        try:
            record = json.loads(line)
            payload = record.get("payload", {})
            
            # Check semi_live_cycle and shadow_cycle
            signal_meta = None
            symbol = payload.get("symbol", "unknown")
            strategy = payload.get("strategy", "unknown")
            
            if "signal" in payload:
                signal_meta = payload["signal"].get("meta", {})
            elif "decision" in payload:
                decision = payload["decision"]
                signal_meta = decision.get("signal", {}).get("meta", {})
            
            if not signal_meta:
                continue
            
            is_near_miss = signal_meta.get("is_near_miss", False)
            if not is_near_miss:
                continue
            
            total_near_miss += 1
            symbols_with_near_miss[symbol] += 1
            
            category = signal_meta.get("category", "unknown")
            stage = signal_meta.get("stage", "unknown")
            trend_gap_pct = signal_meta.get("trend_gap_pct", 0)
            trend_gap_to_threshold_pct = signal_meta.get("trend_gap_to_threshold_pct", 0)
            momentum_pct = signal_meta.get("momentum_pct", 0)
            block_reason = signal_meta.get("block_reason", "")
            
            category_counts[category] += 1
            stage_counts[stage] += 1
            
            # Count confirm_fail separately
            if category == "confirm_fail":
                confirm_fail_count += 1
            
            # Trend gap band analysis (convert to %)
            trend_gap_pct_val = abs(trend_gap_pct) * 100 if trend_gap_pct else 0
            if 0.10 <= trend_gap_pct_val < 0.12:
                trend_gap_bands["0.10-0.12%"] += 1
            elif 0.12 <= trend_gap_pct_val < 0.15:
                trend_gap_bands["0.12-0.15%"] += 1
            elif trend_gap_pct_val >= 0.15:
                trend_gap_bands[">=0.15%"] += 1
            else:
                trend_gap_bands["<0.10%"] += 1
            
            # Momentum fail check
            if momentum_pct is not None and momentum_pct <= 0:
                momentum_fail_count += 1
            
            # Route filter check
            if stage == "route_filter" or (block_reason and "route_blocked" in block_reason):
                route_filter_count += 1
            
            # Execution near-miss (would have bought if threshold relaxed)
            if category == "threshold" and momentum_pct > 0:
                execution_near_miss_count += 1
            
            # Collect sample
            if len(samples) < 15:
                samples.append({
                    "symbol": symbol,
                    "strategy": strategy,
                    "category": category,
                    "stage": stage,
                    "trend_gap_pct": trend_gap_pct,
                    "trend_gap_to_threshold_pct": trend_gap_to_threshold_pct,
                    "momentum_pct": momentum_pct,
                    "block_reason": block_reason,
                })
                
        except json.JSONDecodeError:
            continue
        except Exception as e:
            continue

# Calculate key metrics for threshold decision
threshold_category_count = category_counts.get("threshold", 0)
momentum_positive_in_threshold = sum(1 for s in samples if s["category"] == "threshold" and s["momentum_pct"] > 0)

# Top symbols
top_symbols = sorted(symbols_with_near_miss.items(), key=lambda x: -x[1])[:5]

# Print results
print("=" * 80)
print("NEAR-MISS ANALYSIS FINAL REPORT")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
print("=" * 80)

print(f"\n## 1. 누적 near-miss 건수")
print(f"   **총 건수: {total_near_miss}**")

print(f"\n## 2. Category 분포")
for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
    pct = count/total_near_miss*100
    print(f"   - {cat}: {count} ({pct:.1f}%)")

print(f"\n## 3. Stage 분포")
for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
    pct = count/total_near_miss*100
    print(f"   - {stage}: {count} ({pct:.1f}%)")

print(f"\n## 4. Trend gap band 분포 (threshold 근처 비중)")
for band, count in sorted(trend_gap_bands.items(), key=lambda x: -x[1]):
    pct = count/total_near_miss*100
    print(f"   - {band}: {count} ({pct:.1f}%)")

print(f"\n## 5. 주요 병목 지표")
print(f"   - Momentum fail (momentum <= 0): {momentum_fail_count} ({momentum_fail_count/total_near_miss*100:.1f}%)")
print(f"   - Route filter 병목: {route_filter_count} ({route_filter_count/total_near_miss*100:.1f}%)")
print(f"   - Confirm fail (regime/momentum 문제): {confirm_fail_count} ({confirm_fail_count/total_near_miss*100:.1f}%)")
print(f"   - Threshold near-miss (실제 진입 기회): {threshold_category_count} ({threshold_category_count/total_near_miss*100:.1f}%)")

print(f"\n## 6. Top 심볼 (near-miss 다발)")
for sym, count in top_symbols:
    print(f"   - {sym}: {count}회")

print(f"\n## 7. SAMPLE records")
for i, sample in enumerate(samples[:5], 1):
    print(f"\n   {i}. {sample['symbol']} ({sample['strategy']})")
    print(f"      Category: {sample['category']}, Stage: {sample['stage']}")
    print(f"      trend_gap: {sample['trend_gap_pct']*100:.3f}%, momentum: {sample['momentum_pct']*100:.3f}%")
    if sample['block_reason']:
        print(f"      block_reason: {sample['block_reason'][:60]}")

print("\n" + "=" * 80)
print("## 8. 판단: threshold 유지 vs 0.12% 완화")
print("=" * 80)

# Decision logic
threshold_near_miss_in_band = trend_gap_bands.get("0.10-0.12%", 0) + trend_gap_bands.get("0.12-0.15%", 0)
threshold_near_miss_ratio = threshold_near_miss_in_band / total_near_miss * 100 if total_near_miss > 0 else 0
route_filter_ratio = route_filter_count / total_near_miss * 100 if total_near_miss > 0 else 0
momentum_positive_ratio = (total_near_miss - momentum_fail_count) / total_near_miss * 100 if total_near_miss > 0 else 0

print(f"\n근거 데이터:")
print(f"  - 0.10~0.15% 구간 near-miss: {threshold_near_miss_in_band} ({threshold_near_miss_ratio:.1f}%)")
print(f"  - Route filter 병목 비중: {route_filter_ratio:.1f}%")
print(f"  - Momentum 양수 비중: {momentum_positive_ratio:.1f}%")
print(f"  - Threshold category (진입 기회): {threshold_category_count} ({threshold_category_count/total_near_miss*100:.1f}%)")

print(f"\n판단:")
if threshold_near_miss_ratio < 15 and route_filter_ratio > 90:
    print(f"  → **현행 유지 (0.15%)**")
    print(f"     근거: near-miss 대부분이 threshold 보다 route_filter 병목")
    print(f"     0.12% 완화해도 진입할 수 있는 샘플이 충분하지 않음")
elif threshold_near_miss_ratio >= 15 and momentum_positive_ratio > 60:
    print(f"  → **0.12% 완화 검토 가치 있음**")
    print(f"     근거: 0.10~0.15% 구간 누적 비중이 높고 momentum 도 양수")
else:
    print(f"  → **현행 유지 (0.15%)**")
    print(f"     근거: 시장 레짐 문제 (route_blocked, uncertain_regime) 가 threshold 문제보다 우세")

print("\n" + "=" * 80)
