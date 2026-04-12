#!/usr/bin/env python3
"""
Analyze exception pass / blocked statistics from run_history
"""
import json
from pathlib import Path
from collections import Counter

data_dir = Path("data/run_history")
stats = {
    "exception_pass": 0,
    "exception_blocked": 0,
    "blocked_reasons": Counter(),
    "volatility_state_low_blocked": 0,
    "total_signals": 0,
    "volatility_states": Counter(),
    "market_regimes": Counter(),
    "exception_details": [],
}

# Read today's run_history
jsonl_file = data_dir / "2026-04-12.jsonl"
if not jsonl_file.exists():
    print(f"File not found: {jsonl_file}")
    exit(1)

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
            review = result.get("review", {})
            
            # Track market regime and volatility
            market_regime = meta.get("market_regime", "unknown")
            volatility_state = meta.get("volatility_state", "unknown")
            stats["market_regimes"][market_regime] += 1
            stats["volatility_states"][volatility_state] += 1
            
            # Check for exception pass
            route_exception_pass = meta.get("route_exception_pass", False)
            exception_reason = meta.get("exception_reason", None)
            
            if route_exception_pass:
                stats["exception_pass"] += 1
                stats["exception_details"].append({
                    "id": record.get("id"),
                    "symbol": result.get("symbol"),
                    "strategy": result.get("strategy"),
                    "exception_reason": exception_reason,
                    "volatility_state": volatility_state,
                    "market_regime": market_regime,
                    "trend_gap_pct": meta.get("trend_gap_pct"),
                    "momentum_pct": meta.get("momentum_pct"),
                    "action": signal.get("action"),
                    "approved": review.get("approved"),
                })
            
            # Check for blocked signals
            approved = review.get("approved", False)
            action = signal.get("action", "hold")
            
            if action == "hold" or not approved:
                reason = signal.get("reason", "")
                
                # Categorize block reasons
                if "sideway_filter_blocked" in reason or "market_regime=sideways" in reason:
                    stats["exception_blocked"] += 1
                    stats["blocked_reasons"]["sideways"] += 1
                    
                    if volatility_state == "low":
                        stats["volatility_state_low_blocked"] += 1
                
                elif "blocked_time_window" in reason:
                    stats["blocked_reasons"]["time_window"] += 1
                elif "high_volatility_defense" in reason:
                    stats["blocked_reasons"]["high_volatility"] += 1
                elif "higher_tf_bias" in reason:
                    stats["blocked_reasons"]["higher_tf_bias"] += 1
                else:
                    stats["blocked_reasons"]["other"] += 1
            
            stats["total_signals"] += 1

# Print summary
print("=" * 80)
print("EXCEPTION PASS / BLOCKED ANALYSIS")
print("=" * 80)
print(f"\nTotal signals analyzed: {stats['total_signals']}")
print(f"\n--- Exception Pass ---")
print(f"Exception pass count: {stats['exception_pass']}")
print(f"\n--- Exception Blocked ---")
print(f"Exception blocked count: {stats['exception_blocked']}")
print(f"\n--- Blocked Reason Distribution ---")
for reason, count in stats["blocked_reasons"].most_common():
    pct = (count / stats["exception_blocked"] * 100) if stats["exception_blocked"] > 0 else 0
    print(f"  {reason}: {count} ({pct:.1f}%)")

print(f"\n--- Volatility State Low as Bottleneck ---")
print(f"Blocked with volatility_state=low: {stats['volatility_state_low_blocked']}")
if stats["exception_blocked"] > 0:
    pct = stats["volatility_state_low_blocked"] / stats["exception_blocked"] * 100
    print(f"Percentage of sideways blocks: {pct:.1f}%")

print(f"\n--- Market Regime Distribution ---")
for regime, count in stats["market_regimes"].most_common():
    pct = count / stats["total_signals"] * 100
    print(f"  {regime}: {count} ({pct:.1f}%)")

print(f"\n--- Volatility State Distribution ---")
for state, count in stats["volatility_states"].most_common():
    pct = count / stats["total_signals"] * 100
    print(f"  {state}: {count} ({pct:.1f}%)")

print(f"\n--- Exception Pass Details (first 10) ---")
for detail in stats["exception_details"][:10]:
    print(f"\n  ID: {detail['id']}")
    print(f"    Symbol: {detail['symbol']}, Strategy: {detail['strategy']}")
    print(f"    Exception: {detail['exception_reason']}")
    print(f"    Volatility: {detail['volatility_state']}, Regime: {detail['market_regime']}")
    print(f"    trend_gap_pct: {detail['trend_gap_pct']}, momentum_pct: {detail['momentum_pct']}")
    print(f"    Action: {detail['action']}, Approved: {detail['approved']}")

# Save detailed data for reference
output_file = Path("tmp/exception_pass_analysis.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2, default=str)
print(f"\n\nDetailed data saved to: {output_file}")
