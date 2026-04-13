#!/usr/bin/env python3
"""
Near-miss analysis script for investment-bot
Collects structured near-miss metrics from run_history
"""

import json
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent
run_history_file = project_root / "data" / "run_history" / "2026-04-12.jsonl"

# Counters
total_near_miss = 0
category_counts = defaultdict(int)
stage_counts = defaultdict(int)
trend_gap_bands = defaultdict(int)  # 0.10-0.12%, 0.12-0.15%, etc
momentum_fail_count = 0
route_filter_count = 0

# Detailed samples
samples = []

with open(run_history_file, 'r') as f:
    for line in f:
        try:
            record = json.loads(line)
            payload = record.get("payload", {})
            
            # Check semi_live_cycle and shadow_cycle
            signal_meta = None
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
            
            category = signal_meta.get("category", "unknown")
            stage = signal_meta.get("stage", "unknown")
            trend_gap_pct = signal_meta.get("trend_gap_pct", 0)
            trend_gap_to_threshold_pct = signal_meta.get("trend_gap_to_threshold_pct", 0)
            momentum_pct = signal_meta.get("momentum_pct", 0)
            
            category_counts[category] += 1
            stage_counts[stage] += 1
            
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
            if stage == "route_filter" or signal_meta.get("block_reason", "").startswith("trend_strategy_route_blocked"):
                route_filter_count += 1
            
            # Collect sample
            if len(samples) < 10:
                samples.append({
                    "symbol": payload.get("symbol", "unknown"),
                    "strategy": payload.get("strategy", "unknown"),
                    "category": category,
                    "stage": stage,
                    "trend_gap_pct": trend_gap_pct,
                    "trend_gap_to_threshold_pct": trend_gap_to_threshold_pct,
                    "momentum_pct": momentum_pct,
                    "block_reason": signal_meta.get("block_reason", ""),
                })
                
        except json.JSONDecodeError:
            continue
        except Exception as e:
            continue

# Print results
print("=" * 70)
print("NEAR-MISS ANALYSIS SUMMARY (2026-04-12)")
print("=" * 70)
print(f"\nTotal near-miss count: {total_near_miss}")
print(f"\nCategory distribution:")
for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count} ({count/total_near_miss*100:.1f}%)")

print(f"\nStage distribution:")
for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
    print(f"  {stage}: {count} ({count/total_near_miss*100:.1f}%)")

print(f"\nTrend gap band distribution:")
for band, count in sorted(trend_gap_bands.items(), key=lambda x: -x[1]):
    print(f"  {band}: {count} ({count/total_near_miss*100:.1f}%)")

print(f"\nMomentum fail count (momentum <= 0): {momentum_fail_count} ({momentum_fail_count/total_near_miss*100:.1f}%)")
print(f"Route filter count: {route_filter_count} ({route_filter_count/total_near_miss*100:.1f}%)")

print("\n" + "=" * 70)
print("SAMPLE NEAR-MISS RECORDS")
print("=" * 70)
for i, sample in enumerate(samples, 1):
    print(f"\n{i}. {sample['symbol']} ({sample['strategy']})")
    print(f"   Category: {sample['category']}, Stage: {sample['stage']}")
    print(f"   trend_gap_pct: {sample['trend_gap_pct']:.4f} ({sample['trend_gap_pct']*100:.2f}%)")
    print(f"   trend_gap_to_threshold_pct: {sample['trend_gap_to_threshold_pct']:.4f}")
    print(f"   momentum_pct: {sample['momentum_pct']:.4f} ({sample['momentum_pct']*100:.2f}%)")
    if sample['block_reason']:
        print(f"   block_reason: {sample['block_reason']}")
