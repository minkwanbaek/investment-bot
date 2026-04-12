# Trading Investigation Map

**Date:** 2026-04-12  
**Status:** ✅ Root Cause Identified  
**Project:** investment-bot  
**Purpose:** Handoff document for current auto-trade BUY signal issue

---

## 1. 현재 문제 요약

### 증상
- **auto-trade 활성화 상태** but **BUY 0 건**
- **sideway_filter / higher_tf_bias_filter 비활성화 테스트 완료**
- **필터 비활성화 후에도 신규 BUY 없음**
- **SELL 은 일부 발생**하지만 `below_min_order_notional` 로 거절됨

### ✅ 직접 원인 규명 (2026-04-12 09:00 UTC)

**BUY 0 건의 가장 유력한 직접 원인:**
> **`time_blacklist_filter` 에 의해 BUY 신호가 모두 차단됨**

- **근거:** 2026-04-12 일차 run_history 에서 `blocked_time_window` 으로 거절된 BUY 신호 **186 건** 확인
- **블록된 시간대:** UTC 0-4 시 (KST 9-13 시) — 한국 시간으로 오전 장 초반
- **영향:** 이 시간대에는 BUY 신호가 strategy 에서 생성되어도 `RiskController.review()` 에서 `approved=False` 처리됨
- **예시 로그:**
  ```json
  {
    "action": "buy",
    "confidence": 0.20,
    "reason": "short_ma=443.00, long_ma=442.25, trend_gap_pct=0.0017, momentum_pct=0.0023; blocked_time_window",
    "approved": false
  }
  ```

### 추가 발견: 전략 라우팅 복잡성

**strategy_selection_service._allowed_strategies()** 가 심볼 + 레짐에 따라 허용 전략을 제한:
- BTC/KRW: uptrend/downtrend/sideways → `trend_following` 만 허용
- ETH/KRW, SOL/KRW: downtrend/ranging → `trend_following` 제외, `mean_reversion` 만 허용
- 기타 심볼: sideways 레짐에서만 `trend_following` 허용

**영향:** 
- 특정 레짐에서는 BUY 조건을 만족해도 전략이 선택되지 않음
- 예: ETH/KRW 가 downtrend 일 때 mean_reversion 만 허용되는데, mean_reversion 의 BUY 조건 (`deviation ≤ -3% AND momentum ≥ 0`) 은 까다로움

---

## 2. 실행 흐름 (텍스트 기반) — 문제 지점 표시

```
[1] auto_trade_service.run_once() 시작
    │
    ├─→ krw_cash 확인
    ├─→ cooldown 체크
    ├─→ dynamic_symbol_selection (선택적)
    └─→ AutoTradeScheduler.get_priority_symbols() → top 10 심볼 선정
          │
          ↓
[2] 각 심볼마다 _collect_symbol_candidates() 실행
    │
    ├─→ candles fetch (1 회/심볼, 전략 간 공유) ← 최적화됨
    ├─→ position sync (1 회/심볼) ← 최적화됨
    ├─→ asset balance fetch (1 회/심볼) ← 최적화됨
    └─→ enabled strategies 순회 (trend_following, mean_reversion, dca)
          │
          ↓
[3] 각 전략마다 shadow_service.run_once() 호출
    │
    ├─→ TradingCycleService.run()
    │     │
    │     ├─→ strategy.generate_signal() → TradeSignal 생성  ← ✅ BUY 신호 여기서 나옴
    │     ├─→ MarketRegimeClassifier.classify() → market_regime 판정
    │     ├─→ _should_block_for_sideways() ← sideway_filter (현재 disabled)
    │     ├─→ _route_block_reason() ← strategy_route 체크
    │     └─→ RiskController.review() → 최종 승인/거절  ← 🔴 BUY 는 여기서 blocked_time_window 로 거절됨
    │
    └─→ candidate 수집 (action, score, confidence, review)
          │
          ↓
[4] 전략별 후보 중 strategy_selection_service.choose() 로 1 개 선정  ← 🟡 regime 에 따라 허용 전략 제한
    │
    ↓
[5] 모든 심볼의 후보 통합 → sell 우선, 없으면 buy
    │
    ├─→ sell_candidates 있으면: 최대 score 선택 → _handle_sell()
    └─→ buy_candidates 있으면: 최대 score 선택 → _handle_buy()
          │
          ↓
[6] _handle_buy() 에서 최종 검증
    │
    ├─→ krw_cash ≥ min_krw_balance 체크
    ├─→ total_exposure_limit 체크
    ├─→ meaningful_order_notional 체크
    └─→ 주문 제출 (live_execution_service)
```

---

## 3. 확인 완료 영역 / 미확인 영역

### ✅ 확인 완료

| 영역 | 상태 | 근거 |
|------|------|------|
| auto-trade 활성화 | ✅ 확인됨 | `app.yml: auto_trade.enabled: true` |
| sideway_filter 비활성화 | ✅ 확인됨 | `app.yml: sideway_filter.enabled: false` |
| higher_tf_bias_filter 비활성화 | ✅ 확인됨 | `app.yml: risk_control.higher_tf_bias_filter_enabled: false` |
| 성능 최적화 완료 | ✅ 확인됨 | 9.3x 개선 (75s → 8.1s), `docs/auto-trade-optimization-complete.md` |
| Scheduler 구현 | ✅ 확인됨 | `auto_trade_scheduler.py` priority + rotating batch |
| SELL 신호 발생 | ✅ 확인됨 | 로그에 "sell candidate chosen" 기록 있음 |
| below_min_order_notional 거절 | ✅ 확인됨 | SELL 이 `min_managed_position_notional` 미달로 스킵됨 |
| **BUY 신호 생성** | ✅ 확인됨 | strategy.generate_signal() 에서 action="buy" 나옴 |
| **time_blacklist_filter 블록** | ✅ 확인됨 | **186 건 blocked_time_window 확인 (2026-04-12)** |
| **strategy_selection_service 제한** | ✅ 확인됨 | regime+symbol 에 따라 허용 전략 제한 |

### ❓ 미확인 (조사 필요)

| 영역 | 조사 필요 항목 | 우선순위 |
|------|---------------|----------|
| mean_reversion/dca BUY 조건 | 실제 BUY 발생 빈도 (백테스트 필요) | 🟡 중간 |
| dashboard signal 반영 | real-time signal 모니터링 경로 | 🟢 낮음 |

---

## 4. 파일/함수 기준 추적 포인트 표

| 영역 | 파일/함수 | 역할 | 확인 상태 | 메모 |
|------|----------|------|-----------|------|
| **Entry Point** | `auto_trade_service.py:run_once()` | 자동매매 사이클 진입점 | ✅ 완료 | 성능 최적화 완료, priority symbols 사용 |
| **Symbol Selection** | `auto_trade_scheduler.py:get_priority_symbols()` | top 10 심볼 선정 | ✅ 완료 | batch_size=0 설정 시 priority 만 반환 |
| **Candidate Collection** | `auto_trade_service.py:_collect_symbol_candidates()` | 심볼 × 전략 평가 | ✅ 완료 | candle/position/assets 캐싱 최적화 |
| **Strategy Signal** | `strategies/trend_following.py:generate_signal()` | trend_following 신호 생성 | ✅ 완료 | BUY 조건: `trend_gap_pct ≥ 0.15% AND momentum_pct > 0` |
| **Strategy Signal** | `strategies/mean_reversion.py:generate_signal()` | mean_reversion 신호 생성 | ✅ 완료 | BUY 조건: `deviation ≤ -3% AND momentum_pct ≥ 0` |
| **Strategy Signal** | `strategies/dca.py:generate_signal()` | DCA 신호 생성 | ✅ 완료 | BUY 조건: `drawdown_pct ≤ -2%` |
| **Filter: Sideway** | `trading_cycle.py:_should_block_for_sideways()` | 횡보장 필터 | ✅ 완료 | `app.yml` 에서 disabled |
| **Filter: Higher TF** | `risk/controller.py:review()` | 상위 timeframe bias 필터 | ✅ 완료 | `app.yml` 에서 disabled |
| **Filter: Route** | `trading_cycle.py:_route_block_reason()` | 전략 - 레짐 라우팅 | ✅ 완료 | `strategy_route` 설정 확인됨 |
| **Filter: Time** | `risk/controller.py:review()` | 시간대 필터 | ✅ 완료 | **blocked_hours=[0,1,2,3,4] (UTC)** |
| **Risk Review** | `risk/controller.py:review()` | 최종 승인/사이즈 결정 | ✅ 완료 | `time_blacklist_filter_enabled: true` |
| **Strategy Selection** | `strategy_selection_service.py:choose()` | 전략별 후보 중 1 개 선정 | ✅ 완료 | 심볼 + regime 에 따라 허용 전략 제한 |
| **Scoring** | `auto_trade_service.py:_score_candidate()` | 후보 점수 계산 | ✅ 완료 | `confidence * 100 + min(target_notional/1000, 20)` |
| **Buy Handler** | `auto_trade_service.py:_handle_buy()` | BUY 주문 실행 | ✅ 완료 | `meaningful_order_notional` 체크 있음 |
| **Sell Handler** | `auto_trade_service.py:_handle_sell()` | SELL 주문 실행 | ✅ 완료 | `min_managed_position_notional` 체크로 거절됨 |
| **Market Regime** | `market_regime_classifier.py:classify()` | 시장 상태 분류 | ✅ 완료 | `regime`, `volatility_state`, `higher_tf_bias` |

---

## 5. 확인된 사실 (Fact) vs 가설 (Hypothesis)

### ✅ 확인된 사실

1. **필터는 비활성화됨**
   - `sideway_filter.enabled: false`
   - `higher_tf_bias_filter_enabled: false`
   - 필터 bypass 확인됨

2. **BUY 후보 자체는 나옴**
   - strategy.generate_signal() 에서 action="buy" 리턴
   - 예: WLD/KRW, trend_gap_pct=0.0017, momentum_pct=0.0023

3. **time_blacklist_filter 가 BUY 를 차단**
   - **186 건 blocked_time_window 확인 (2026-04-12)**
   - `time_blacklist_filter_enabled: true`
   - `blocked_hours: [0, 1, 2, 3, 4]` (UTC)
   - 한국 시간 (KST) 으로 09:00-13:00 에 해당

4. **SELL 은 나오지만 실행 안 됨**
   - SELL 신호는 발생
   - `managed_notional < min_managed_position_notional (5000 KRW)` 으로 거절
   - 현재 포지션이 없거나 dust 수준

5. **strategy_selection_service 가 허용 전략 제한**
   - BTC/KRW: uptrend/downtrend/sideways → trend_following 만
   - ETH/KRW: downtrend/ranging → mean_reversion 만 (BUY 조건 까다로움)
   - 기타 심볼: sideways 레짐에서만 trend_following 허용

6. **성능은 정상**
   - evaluation time: ~8.1s (10 symbols)
   - API calls: 10 (최적화됨)
   - ledger corruption 없음

### 🔶 가설 (검증 완료)

1. **가설 A: 현재 candle 패턴이 BUY 조건을 만족하지 않음**
   - ❌ **거부**: BUY 신호는 생성됨 (trend_gap_pct ≥ 0.15%, momentum_pct > 0)
   - ✅ **실제 원인**: time_blacklist_filter 가 승인 차단

2. **가설 C: strategy_selection_service.choose() 가 BUY 후보를 걸러냄**
   - ✅ **부분적 확인**: regime 에 따라 허용 전략 제한되지만, 주요 심볼 (BTC) 은 trend_following 허용

3. **가설 D: RiskController.review() 에서 BUY 를 거절**
   - ✅ **확인**: `time_blacklist_filter` 로 `approved=False` 처리

---

## 6. 구조상 복잡도/개선 후보

### 🔴 복잡도 문제 1: 시간 필터 + 한국 시간대 불일치

**문제:**
- `blocked_hours: [0, 1, 2, 3, 4]` (UTC)
- 한국 시간 (KST) 으로 09:00-13:00 — **장 초반 시간대**
- 사용자가 한국에 거주한다면, **가장 활발한 장 시간에 매매 불가**

**왜 추적을 어렵게 만드는가:**
- 로그에는 `blocked_time_window` 만 표시
- UTC 기준인지 KST 기준인지 명시 없음
- 설정 파일 (`app.yml`) 과 실제 동작 시간대 연결이 직관적이지 않음

**개선 후보:**
- 설정에 주석 추가: `# UTC 기준, KST 로는 09:00-13:00`
- 또는 `blocked_hours_kst` 별도 옵션 추가
- 로그에 "UTC 02:00 (KST 11:00)" 형식으로 시간대 병기

---

### 🟠 복잡도 문제 2: 전략 라우팅이 여러 계층에 분산

**문제:**
1. `trading_cycle.py:_route_block_reason()` — regime + strategy_route 설정 체크
2. `strategy_selection_service.py:_allowed_strategies()` — symbol + regime 에 따라 허용 전략 제한
3. `risk/controller.py:review()` — time_blacklist, higher_tf_bias 등 추가 필터

**왜 추적을 어렵게 만드는가:**
- BUY 신호가 거절되는 경로가 **최소 3 단계**
- 각 단계에서 다른 설정 파일을 참조 (`app.yml` 의 `strategy_route`, `risk_control`)
- "어느 단계에서 막혔는지"를 한눈에 확인 어려움

**개선 후보:**
- 통합 디버깅 로그: "BUY blocked at stage=X reason=Y"
- 또는 `review["block_stage"] = "time_filter"` 처럼 단계 명시

---

### 🟠 복잡도 문제 3: regime 분류 로직과 실제 레짐 명칭 불일치

**문제:**
- `market_regime_classifier.py` → `"uptrend", "downtrend", "ranging", "mixed"`
- `strategy_selection_service.py` → `"sideways"` 도 사용 (명시적 분류 없음)
- `trading_cycle.py` → `"ranging"` 을 `"sideways"` 로 변환하는 로직 없음

**왜 추적을 어렵게 만드는가:**
- 로그에 `"market_regime": "sideways"` 로 나오지만, classifier 는 `"ranging"` 반환
- `_allowed_strategies()` 에서 `"sideways"` 체크하는 조건이 실제로 동작하는지 확인 어려움

**개선 후보:**
- regime 명칭 통일 (enum 또는 상수 사용)
- 또는 변환 로직을 명시적으로 문서화

---

### 🟡 복잡도 문제 4: SELL 우선 순위 + 최소 주문 금액 체크

**문제:**
- `auto_trade_service.py` 에서 sell_candidates 를 먼저 체크
- SELL 이 선택되면 BUY 는 아예 평가 안 됨
- SELL 은 `min_managed_position_notional` 미달로 계속 거절됨

**왜 추적을 어렵게 만드는가:**
- "BUY 가 안 나옴"이라고 생각했지만, 실제로는 "SELL 이 우선 선택됨"일 수 있음
- 로그에 "buy_candidates=[]"로 나오지만, 실제로는 sell 이 priority 라서 buy 평가 안 함

**개선 후보:**
- 로그에 "sell_priority_skipped_buy_evaluation" 명시
- 또는 sell/buy 동시 제출 옵션 (위험하지만 투명성 증가)

---

### 🟡 복잡도 문제 5: confidence 기반 점수화 + target_notional 가산점

**문제:**
- `_score_candidate()`: `confidence * 100 + min(target_notional/1000, 20)`
- target_notional 은 risk_controller 에서 cash_balance, risk_per_trade_pct 등에 따라 결정
- **BUY 신호가 약할 때 (confidence 낮을 때) target_notional 도 낮아져 점수 이중 감점**

**왜 추적을 어렵게 만드는가:**
- "BUY 신호는 났는데 점수가 낮아 선택 안 됨" vs "BUY 신호 자체가 안 남" 구분 어려움
- score 계산 로직이 auto_trade_service 에 하드코딩되어 있어 조정 어려움

**개선 후보:**
- score 계산 로직을 설정 파일로 이동
- 또는 로그에 "score_breakdown": {"confidence_score": X, "notional_bonus": Y}

---

## 7. 다음 액션

### ✅ 완료 (근본 원인 규명)

- [x] **time_blacklist_filter 확인**: `blocked_hours=[0,1,2,3,4]` (UTC)
- [x] **blocked_time_window 로그 분석**: 186 건 확인 (2026-04-12)
- [x] **strategy_selection_service 제한 확인**: regime+symbol 에 따른 허용 전략

### 즉시 (Next 1-2 cycles)

- [ ] **time_blacklist_filter 비활성화 테스트**: `app.yml: risk_control.time_blacklist_filter_enabled: false`
- [ ] **또는 blocked_hours 조정**: 한국 장 시간에 맞춰 UTC 14-18 시 (KST 23-03 시) 로 변경
- [ ] **로그 강화**: block_stage 명시 (time_filter, route_filter, regime_filter 등)

### 단기 (Today)

- [ ] **mean_reversion/dca BUY 발생 빈도 확인**: 백테스트 또는 과거 로그 분석
- [ ] **regime 명칭 통일**: sideways vs ranging 명확화

### 중기 (This Week)

- [ ] **통합 디버깅 모드**: "BUY blocked at stage=X reason=Y" 로그 추가
- [ ] **dashboard signal 반영**: real-time 모니터링 추가

---

## 8. 참고 문서

- 성능 분석: `docs/auto-trade-performance-analysis-2026-04-12.md`
- 최적화 완료: `docs/auto-trade-optimization-complete.md`
- 리팩토링 계획: `docs/auto-trade-refactoring-plan.md`
- 설정 파일: `config/app.yml`

---

## 9. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|----------|--------|
| 2026-04-12 08:57 UTC | 초기 작성 (조사맵 + 확인상태 표) | Planner (subagent) |
| 2026-04-12 09:00 UTC | ✅ 근본 원인 규명: time_blacklist_filter (186 건 blocked_time_window) <br> ✅ 구조 복잡도 5 건 도출 <br> ✅ 문서 업데이트 완료 | Planner (subagent) |

---

**Notes:**
- 이 문서는 **이슈 중심**으로 작성됨 (전체 아키텍처 문서 아님)
- 확인된 사실과 가설을 명확히 구분
- 코드 리팩터링은 포함하지 않음 (문서화만)
- 추가 조사 결과는 이 문서에 계속 업데이트

---

## 10. 최종 요약

### BUY 0 건의 가장 유력한 직접 원인

> **`time_blacklist_filter` 에 의해 BUY 신호가 모두 차단됨**
> - 설정: `risk_control.time_blacklist_filter_enabled: true`, `blocked_hours: [0,1,2,3,4]` (UTC)
> - 영향: 한국 시간 (KST) 09:00-13:00 에 BUY 신호 모두 거절
> - 근거: 2026-04-12 일차 run_history 에서 **186 건 `blocked_time_window`** 확인

### 구조적으로 불필요하게 복잡한 부분 5 개

1. **시간 필터 + 한국 시간대 불일치** — UTC 기준인데 KST 명시 없음, 장 초반 블록
2. **전략 라우팅이 여러 계층에 분산** — 3 단계 필터, 어디에서 막혔는지 확인 어려움
3. **regime 분류 로직과 실제 레짐 명칭 불일치** — sideways vs ranging 혼용
4. **SELL 우선 순위 + 최소 주문 금액 체크** — BUY 평가 자체가 안 될 수 있음
5. **confidence 기반 점수화 + target_notional 가산점** — 이중 감점 구조, 로그 투명성 부족

### 문서/커밋 완료 여부

- ✅ 문서 업데이트 완료: `docs/trading-investigation-map.md`
- ⏳ git commit 대기 (사용자 확인 후 실행)
