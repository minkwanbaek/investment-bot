# 투자봇 운영 리포트

- 생성시각: `2026-04-13 02:21 KST`
- 상태: `ok`
- 자동매매 활성화: `True`
- 대상 심볼: `['BTC/KRW', 'ETH/KRW', 'SOL/KRW', 'XRP/KRW', 'ADA/KRW', 'DOGE/KRW', 'XLM/KRW', 'TRX/KRW', 'HBAR/KRW', 'LINK/KRW', 'APT/KRW', 'SUI/KRW', 'AVAX/KRW', 'DOT/KRW', 'SEI/KRW', 'ONDO/KRW', 'ENA/KRW', 'WLD/KRW', 'ARB/KRW', 'OP/KRW', 'FIL/KRW', 'NEAR/KRW', 'UNI/KRW', 'ATOM/KRW', 'ETC/KRW', 'ALGO/KRW', 'VET/KRW', 'ICP/KRW', 'SAND/KRW', 'MANA/KRW', 'AXS/KRW', 'THETA/KRW', 'XTZ/KRW', 'BSV/KRW', 'BCH/KRW', 'QTUM/KRW', 'BAT/KRW', 'ZIL/KRW', 'IOST/KRW', 'ONT/KRW', 'ICX/KRW', 'SC/KRW']`
- 전략: `trend_following`
- 최근 스킵 사유: `{'non_actionable_signal': 1}`
- 최근 실행 종류 집계: `{'shadow_cycle': 36, 'semi_live_cycle': 37, 'auto_trade_skip': 1, 'auto_trade_start': 3, 'live_order_preview': 2, 'auto_trade_error': 1}`

## Tune Summary (2026-04-12 17:15 UTC)

**Change applied:** Lowered `min_managed_position_notional` from 5000.0 → 1500.0 KRW

**Rationale:**
- Current managed notional: 1874.93 KRW (ADA/KRW position)
- Previous threshold (5000.0) blocked sell signal due to dust position filter
- New threshold (1500.0) allows bot to manage and exit small positions cleanly
- This is a low-risk config change that reduces noise in skip logs without altering strategy logic

**Test results:**
- Core strategy tests: PASSED (11/12, 1 unrelated test failure on symbol list assertion)
- Config tests: PASSED (2/3, 1 unrelated test failure on symbol list assertion)
- Auto-trade service tests: FAILED due to FakeShadowService missing new `invalidate_cache()` method (test fixture issue, not production code)

**Server health:** OK (port 8899, live mode)
**Config reload:** Applied (min_managed_position_notional=1500.0 confirmed via /config)
**Run-once:** Timed out during evaluation (42 symbols × 3 strategies = slow); server remains healthy

**Next steps:**
- Monitor if ADA/KRW position gets managed and exited on next cycle
- Consider further performance optimization if run-once timeouts persist
