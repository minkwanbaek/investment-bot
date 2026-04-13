#!/usr/bin/env python3
"""Quick test for decimal formatting fix."""
import sys
sys.path.insert(0, "src")

from investment_bot.services.live_execution_service import _format_decimal, _price_str

# Test cases matching the failing order
print("=== Volume formatting ===")
print(f"148.5957739399999866 -> '{_format_decimal(148.5957739399999866)}'")
print(f"0.10158124 -> '{_format_decimal(0.10158124)}'")
print(f"0.00335935 -> '{_format_decimal(0.00335935)}'")

print("\n=== Price formatting ===")
print(f"141.9 tick=0.1 -> '{_price_str(141.9, 0.1)}'")
print(f"134300.0 tick=50 -> '{_price_str(134300.0, 50)}'")
print(f"3131000.0 tick=1000 -> '{_price_str(3131000.0, 1000)}'")
print(f"0.813 tick=0.001 -> '{_price_str(0.813, 0.001)}'")

print("\n=== Import check ===")
from investment_bot.services.live_execution_service import LiveExecutionService
print("LiveExecutionService imported OK")
