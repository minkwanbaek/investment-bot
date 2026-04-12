#!/usr/bin/env python3
"""
Analyze volatility and exception pass conditions in detail
"""
import json
from pathlib import Path
from collections import Counter

data_dir = Path("data/run_history")
stats = {
    "total_signals": 0,
    "sideways_signals": 0,
    "trend_following_signals": 0,
    "exception_pass_candidates": 0,
    "exception_pass_granted": 0,
    "blocked_by_volatility_low": 0,
    "volatility_states": Counter(),
    "momentum_distribution": {"positive": 0, "negative": 0, "zero": 0},
    "trend_gap_distribution": {"above_threshold": 0, "near_threshold": 0, "below_threshold": 0},
    "higher_tf_bias": Counter(),
    "sample_details": [],
}

TREND_GAP_THRESHOLD = 0.0015
TREND_GAP_RATIO = 0.7
MIN_TREND_GAP = TREND_GAP_THRESHOLD * TREND_GAP_RATIO  # 0.00105

# Read today's run_history
jsonl_file = data_dir / "2026-04-12.jsonl"
with open(jsonl_file, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        try:
            record = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        
        payload = record.get("payload", {})
        results = payload.get("results", [])
        
        for result in results:
            signal = result.get("signal", {})
            meta = signal.get("meta", {})
            
            market_regime = meta.get("market_regime", "unknown")
            volatility_state = meta.get("volatility_state", "unknown")
            strategy = result.get("strategy", "")
            
            stats["total_signals"] += 1
            stats["volatility_states"][volatility_state] += 1
            
            if market_regime == "sideways":
                stats["sideways_signals"] += 1
            
            if strategy == "trend_following":
                stats["trend_following_signals"] += 1
            
            # Analyze conditions for exception pass
            trend_gap_pct = float(meta.get("trend_gap_pct", 0.0) or 0.0)
            momentum_pct = float(meta.get("momentum_pct", 0.0) or 0.0)
            higher_tf_bias = meta.get("higher_tf_bias", "neutral")
            
            stats["higher_tf_bias"][higher_tf_bias] += 1
            
            if momentum_pct > 0:
                stats["momentum_distribution"]["positive"] += 1
            elif momentum_pct < 0:
                stats["momentum_distribution"]["negative"] += 1
            else:
                stats["momentum_distribution"]["zero"] += 1
            
            if trend_gap_pct >= TREND_GAP_THRESHOLD:
                stats["trend_gap_distribution"]["above_threshold"] += 1
            elif trend_gap_pct >= MIN_TREND_GAP:
                stats["trend_gap_distribution"]["near_threshold"] += 1
            else:
                stats["trend_gap_distribution"]["below_threshold"] += 1
            
            # Check if this could be an exception pass candidate
            if (market_regime == "sideways" and 
                strategy == "trend_following" and
                momentum_pct > 0 and
                trend_gap_pct >= MIN_TREND_GAP):
                
                stats["exception_pass_candidates"] += 1
                
                # Check why it would fail
                fail_reasons = []
                if volatility_state == "low":
                    fail_reasons.append("volatility_low")
                    stats["blocked_by_volatility_low"] += 1
                if higher_tf_bias == "bearish":
                    fail_reasons.append("higher_tf_bearish")
                
                if not fail_reasons and len(stats["sample_details"]) < 20:
                    stats["exception_pass_granted"] += 1
                    stats["sample_details"].append({
                        "id": record.get("id"),
                        "symbol": result.get("symbol"),
                        "trend_gap_pct": trend_gap_pct,
                        "momentum_pct": momentum_pct,
                        "volatility_state": volatility_state,
                        "higher_tf_bias": higher_tf_bias,
                        "action": signal.get("action"),
                        "approved": result.get("review", {}).get("approved"),
                    })
                elif len(stats["sample_details"]) < 20:
                    stats["sample_details"].append({
                        "id": record.get("id"),
                        "symbol": result.get("symbol"),
                        "trend_gap_pct": trend_gap_pct,
                        "momentum_pct": momentum_pct,
                        "volatility_state": volatility_state,
                        "higher_tf_bias": higher_tf_bias,
                        "fail_reasons": fail_reasons,
                        "action": signal.get("action"),
                        "approved": result.get("review", {}).get("approved"),
                    })

# Print summary
print("=" * 80)
print("VOLATILITY & EXCEPTION PASS DETAILED ANALYSIS")
print("=" * 80)
print(f"\nTotal signals: {stats['total_signals']}")
print(f"Sideways signals: {stats['sideways_signals']} ({stats['sideways_signals']/stats['total_signals']*100:.1f}%)")
print(f"Trend following signals: {stats['trend_following_signals']}")

print(f"\n--- Volatility State Distribution ---")
for state, count in stats["volatility_states"].most_common():
    pct = count / stats["total_signals"] * 100
    print(f"  {state}: {count} ({pct:.1f}%)")

print(f"\n--- Momentum Distribution ---")
for category, count in stats["momentum_distribution"].items():
    pct = count / stats["total_signals"] * 100
    print(f"  {category}: {count} ({pct:.1f}%)")

print(f"\n--- Trend Gap Distribution ---")
print(f"  Threshold: {TREND_GAP_THRESHOLD}, Near threshold ratio: {TREND_GAP_RATIO}")
print(f"  Min trend gap for exception: {MIN_TREND_GAP}")
for category, count in stats["trend_gap_distribution"].items():
    pct = count / stats["total_signals"] * 100
    print(f"  {category}: {count} ({pct:.1f}%)")

print(f"\n--- Higher TF Bias Distribution ---")
for bias, count in stats["higher_tf_bias"].most_common():
    pct = count / stats["total_signals"] * 100
    print(f"  {bias}: {count} ({pct:.1f}%)")

print(f"\n--- Exception Pass Analysis ---")
print(f"Candidates (sideways + trend_following + momentum>0 + trend_gap>=min): {stats['exception_pass_candidates']}")
print(f"Would pass all conditions: {stats['exception_pass_granted']}")
print(f"Blocked by volatility_state=low: {stats['blocked_by_volatility_low']}")

if stats["exception_pass_candidates"] > 0:
    pct_blocked_by_vol = stats["blocked_by_volatility_low"] / stats["exception_pass_candidates"] * 100
    print(f"Percentage of candidates blocked by low volatility: {pct_blocked_by_vol:.1f}%")

print(f"\n--- Sample Details (first 20) ---")
for detail in stats["sample_details"][:20]:
    print(f"\n  ID: {detail['id']}, Symbol: {detail['symbol']}")
    print(f"    trend_gap: {detail['trend_gap_pct']:.6f}, momentum: {detail['momentum_pct']:.6f}")
    print(f"    volatility: {detail['volatility_state']}, higher_tf: {detail['higher_tf_bias']}")
    if "fail_reasons" in detail:
        print(f"    Fail reasons: {', '.join(detail['fail_reasons'])}")
    print(f"    Action: {detail['action']}, Approved: {detail['approved']}")
