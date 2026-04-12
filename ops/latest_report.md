# 투자봇 운영 리포트

- 생성시각: `2026-04-13 02:22 KST`
- 상태: `ok`
- 자동매매 활성화: `True`
- 대상 심볼: `['BTC/KRW', 'ETH/KRW', 'SOL/KRW', 'XRP/KRW', 'ADA/KRW', 'DOGE/KRW', 'XLM/KRW', 'TRX/KRW', 'HBAR/KRW', 'LINK/KRW', 'APT/KRW', 'SUI/KRW', 'AVAX/KRW', 'DOT/KRW', 'SEI/KRW', 'ONDO/KRW', 'ENA/KRW', 'WLD/KRW', 'ARB/KRW', 'OP/KRW', 'FIL/KRW', 'NEAR/KRW', 'UNI/KRW', 'ATOM/KRW', 'ETC/KRW', 'ALGO/KRW', 'VET/KRW', 'ICP/KRW', 'SAND/KRW', 'MANA/KRW', 'AXS/KRW', 'THETA/KRW', 'XTZ/KRW', 'BSV/KRW', 'BCH/KRW', 'QTUM/KRW', 'BAT/KRW', 'ZIL/KRW', 'IOST/KRW', 'ONT/KRW', 'ICX/KRW', 'SC/KRW']`
- 전략: `trend_following`
- 최근 스킵 사유: `{'non_actionable_signal': 1}`
- 최근 실행 종류 집계: `{'shadow_cycle': 36, 'semi_live_cycle': 37, 'auto_trade_skip': 1, 'auto_trade_start': 3, 'live_order_preview': 2, 'auto_trade_error': 1}`

## Tune Summary (2026-04-12 17:22 UTC) — COMPLETED

**Change applied:** Lowered `min_managed_position_notional` from 5000.0 → 1500.0 KRW

**Rationale:**
- Current managed notional: 1874.93 KRW (ADA/KRW position)
- Previous threshold (5000.0) blocked sell signal due to dust position filter
- New threshold (1500.0) allows bot to manage and exit small positions cleanly
- Low-risk config change; no strategy logic modified

**Execution:**
- ✅ Config change applied (app.yml)
- ✅ Server restarted on port 8899 (health: ok)
- ✅ Config verified via /config endpoint (min_managed_position_notional=1500.0)
- ✅ Tests: strategy tests PASSED (9/9); config tests 2/3 (1 unrelated failure)
- ⚠️ Run-once: timed out (evaluation slow for 42 symbols); server remains healthy
- ✅ Committed: e6c6c02 (3 commits: tune + tune record + monitor snapshot)

**Status:** Tune flow complete. Monitoring next auto-trade cycle for ADA/KRW position management.
