# Trading Investigation Map

**Date:** 2026-04-12  
**Status:** Investigation In Progress  
**Project:** investment-bot  
**Purpose:** Handoff document for current auto-trade BUY signal issue

---

## 1. 현재 문제 요약

### 증상
- **auto-trade 활성화 상태** but **BUY 0 건**
- **sideway_filter / higher_tf_bias_filter 비활성화 테스트 완료**
- **필터 비활성화 후에도 신규 BUY 없음**
- **SELL 은 일부 발생**하지만 `below_min_order_notional` 로 거절됨

### 영향
- 자동매매 사이클은 정상 실행됨 (성능 최적화 후 ~8.1s for 10 symbols)
- 진입 (BUY) 신호가 전혀 발생하지 않아 포지션 형성 안 됨
- 청산 (SELL) 신호는 발생하지만 최소 주문 금액 미달로 실행 안 됨

---

## 2. 실행 흐름 (텍스트 기반)

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
    │     ├─→ strategy.generate_signal() → TradeSignal 생성
    │     ├─→ MarketRegimeClassifier.classify() → market_regime 판정
    │     ├─→ _should_block_for_sideways() ← sideway_filter (현재 disabled)
    │     ├─→ _route_block_reason() ← strategy_route 체크
    │     └─→ RiskController.review() → 최종 승인/거절
    │
    └─→ candidate 수집 (action, score, confidence, review)
          │
          ↓
[4] 전략별 후보 중 strategy_selection_service.choose() 로 1 개 선정
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
    ├─→ meaningful_order_notional 체크 ← 여기서 거절됨
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

### ❓ 미확인 (조사 필요)

| 영역 | 조사 필요 항목 | 우선순위 |
|------|---------------|----------|
| trend_following BUY 조건 | 왜 BUY 신호가 안 나오는지 (candle 패턴 분석 필요) | 🔴 높음 |
| 후보 점수화 로직 | `_score_candidate()` 임계값 적정성 | 🟠 중음 |
| 전략 라우팅 | `strategy_selection_service.choose()` 선정 기준 | 🟠 중음 |
| 최종 주문 제출 흐름 | `_handle_buy()` 진입 전 추가 필터 존재 여부 | 🟡 중간 |
| dashboard 반영 | real-time signal 모니터링 경로 | 🟢 낮음 |

---

## 4. 파일/함수 기준 추적 포인트 표

| 영역 | 파일/함수 | 역할 | 확인 상태 | 메모 |
|------|----------|------|-----------|------|
| **Entry Point** | `auto_trade_service.py:run_once()` | 자동매매 사이클 진입점 | ✅ 완료 | 성능 최적화 완료, priority symbols 사용 |
| **Symbol Selection** | `auto_trade_scheduler.py:get_priority_symbols()` | top 10 심볼 선정 | ✅ 완료 | batch_size=0 설정 시 priority 만 반환 |
| **Candidate Collection** | `auto_trade_service.py:_collect_symbol_candidates()` | 심볼 × 전략 평가 | ✅ 완료 | candle/position/assets 캐싱 최적화 |
| **Strategy Signal** | `strategies/trend_following.py:generate_signal()` | trend_following 신호 생성 | ❓ 미확인 | BUY 조건: `trend_gap_pct ≥ 0.15% AND momentum_pct > 0` |
| **Strategy Signal** | `strategies/mean_reversion.py:generate_signal()` | mean_reversion 신호 생성 | ❓ 미확인 | 코드 확인 필요 |
| **Strategy Signal** | `strategies/dca.py:generate_signal()` | DCA 신호 생성 | ❓ 미확인 | 코드 확인 필요 |
| **Filter: Sideway** | `trading_cycle.py:_should_block_for_sideways()` | 횡보장 필터 | ✅ 완료 | `app.yml` 에서 disabled |
| **Filter: Higher TF** | `risk/controller.py:review()` | 상위 timeframe bias 필터 | ✅ 완료 | `app.yml` 에서 disabled |
| **Filter: Route** | `trading_cycle.py:_route_block_reason()` | 전략 - 레짐 라우팅 | ❓ 부분 | `strategy_route` 설정은 확인됨 |
| **Risk Review** | `risk/controller.py:review()` | 최종 승인/사이즈 결정 | ❓ 부분 | `approved` 로직 확인 필요 |
| **Strategy Selection** | `strategy_selection_service.py:choose()` | 전략별 후보 중 1 개 선정 | ❓ 미확인 | 심볼당 1 개 후보로 압축 |
| **Scoring** | `auto_trade_service.py:_score_candidate()` | 후보 점수 계산 | ❓ 미확인 | `confidence * 100 + min(target_notional/1000, 20)` |
| **Buy Handler** | `auto_trade_service.py:_handle_buy()` | BUY 주문 실행 | ❓ 부분 | `meaningful_order_notional` 체크 있음 |
| **Sell Handler** | `auto_trade_service.py:_handle_sell()` | SELL 주문 실행 | ✅ 완료 | `min_managed_position_notional` 체크로 거절됨 |
| **Market Regime** | `market_regime_classifier.py:classify()` | 시장 상태 분류 | ❓ 미확인 | `regime`, `volatility_state`, `higher_tf_bias` |
| **Dashboard** | `dashboard_service.py` | 대시보드 데이터 제공 | ❓ 미확인 | signal 반영 경로 확인 필요 |

---

## 5. 확인된 사실 (Fact) vs 가설 (Hypothesis)

### ✅ 확인된 사실

1. **필터는 비활성화됨**
   - `sideway_filter.enabled: false`
   - `higher_tf_bias_filter_enabled: false`
   - 필터 bypass 확인됨

2. **BUY 후보 자체가 안 나옴**
   - `buy_candidates = []` 상태 지속
   - 전략 `generate_signal()` 에서 `action="buy"` 를 리턴하지 않음

3. **SELL 은 나오지만 실행 안 됨**
   - SELL 신호는 발생
   - `managed_notional < min_managed_position_notional (5000 KRW)` 으로 거절
   - 현재 포지션이 없거나 dust 수준

4. **성능은 정상**
   - evaluation time: ~8.1s (10 symbols)
   - API calls: 10 (최적화됨)
   - ledger corruption 없음

### 🔶 가설 (검증 필요)

1. **가설 A: 현재 candle 패턴이 BUY 조건을 만족하지 않음**
   - trend_following: `trend_gap_pct ≥ 0.15% AND momentum_pct > 0` 필요
   - 현재 시장이 명확한 uptrend 가 아님
   - **검증 방법:** 최근 100 개 candle 로 수동 계산

2. **가설 B: mean_reversion/DCA 전략이 disabled 또는 BUY 조건 까다로움**
   - enabled strategies 에 포함되었지만 신호가 약함
   - **검증 방법:** `list_enabled_strategies()` 출력 확인

3. **가설 C: strategy_selection_service.choose() 가 BUY 후보를 걸러냄**
   - 심볼당 1 개 후보만 통과
   - sell 이 priority 일 경우 buy 가 선택 안 됨
   - **검증 방법:** `choose()` 로직 확인

4. **가설 D: RiskController.review() 에서 BUY 를 거절**
   - `approved = False` 되는 조건 존재
   - time_blacklist_filter, high_volatility_defense 등
   - **검증 방법:** `review["approved"]` 값 로깅 추가

---

## 6. 다음 액션

### 즉시 (Next 1-2 cycles)

- [ ] **로그 강화**: `_collect_symbol_candidates()` 에서 각 전략별 `action`, `confidence`, `reason` 출력
  ```python
  logger.info("strategy_signal | symbol=%s strategy=%s action=%s confidence=%.2f reason=%s",
              symbol, strategy_name, signal.action, signal.confidence, signal.reason)
  ```
- [ ] **candle 데이터 스냅샷**: 최근 100 개 candle 저장 (수동 분석용)
- [ ] **enabled strategies 확인**: `list_enabled_strategies()` 출력 캡처

### 단기 (Today)

- [ ] **trend_following BUY 조건 수동 검증**: 저장된 candle 로 `trend_gap_pct`, `momentum_pct` 계산
- [ ] **mean_reversion/dca 코드 리뷰**: BUY 조건 로직 확인
- [ ] **strategy_selection_service.choose() 로직 분석**: 심볼당 1 개 후보 선정 기준

### 중기 (This Week)

- [ ] **RiskController.review() 디버깅**: `approved=False` 되는 조건 식별
- [ ] **dashboard signal 반영**: real-time 모니터링 추가
- [ ] **백테스트**: 과거 데이터로 BUY 신호 발생 빈도 확인

---

## 7. 참고 문서

- 성능 분석: `docs/auto-trade-performance-analysis-2026-04-12.md`
- 최적화 완료: `docs/auto-trade-optimization-complete.md`
- 리팩토링 계획: `docs/auto-trade-refactoring-plan.md`
- 설정 파일: `config/app.yml`

---

## 8. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|----------|--------|
| 2026-04-12 | 초기 작성 (조사맵 + 확인상태 표) | Planner (subagent) |

---

**Notes:**
- 이 문서는 **이슈 중심**으로 작성됨 (전체 아키텍처 문서 아님)
- 확인된 사실과 가설을 명확히 구분
- 코드 리팩터링은 포함하지 않음 (문서화만)
- 추가 조사 결과는 이 문서에 계속 업데이트
