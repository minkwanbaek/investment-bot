# Trading Policy Centralization (minimal scope)

## 목적
이번 정리는 전면 리팩터링이 아니라, 실제 병목이 되었던 핵심 트레이딩 정책 축을 한곳에서 읽고 해석할 수 있게 만드는 최소 구조 개선이다.

## 이번에 한 일
- `src/investment_bot/core/trading_policy.py` 추가
- 정책(policy)과 상태(state) 개념을 분리해 문서화
- route / sideways exception / volatility / exposure / allocation / meaningful order 관련 정책을 정책 스냅샷으로 묶음
- regime 명칭을 단일 규격으로 정규화
  - `trend_up`
  - `trend_down`
  - `sideways`
  - `uncertain`
- 최소 관측성 포맷 추가
  - `policy_name`
  - `policy_value`
  - `current_state`
  - `block_reason`

---

## 정책 인벤토리

### 1) consecutive buy 축
- 정책
  - `max_consecutive_buys`
- 상태
  - `consecutive_buys`
- 현재 책임 위치
  - 정책 값 소스: `Settings` → `TradingPolicy.snapshot.max_consecutive_buys`
  - 상태 저장/변경: `PaperBroker`
- 분리 원칙
  - 정책은 설정/정책 모듈에서만 정의
  - 상태는 broker/ledger에서만 유지

### 2) route 허용 정책
- `trend_strategy_allowed_regimes`
- `range_strategy_allowed_regimes`
- `uncertain_block_enabled`
- 사용 위치
  - `TradingCycleService._route_block_reason`
  - `StrategySelectionService._allowed_strategies`
- 개선 포인트
  - regime alias(`uptrend`, `ranging`, `mixed` 등)를 정책 모듈에서 정규화

### 3) sideways exception 정책
- `sideway_filter_enabled`
- `sideway_filter_trend_gap_threshold`
- `sideway_filter_range_threshold`
- `sideway_filter_volatility_block_on_low`
- `sideway_filter_breakout_exception_enabled`
- `sideway_filter_breakout_exception_momentum_min`
- `sideway_filter_breakout_exception_trend_gap_ratio`
- `sideway_filter_breakout_exception_allow_bearish_higher_tf`
- `sideway_filter_breakout_exception_allow_low_volatility`
- 사용 위치
  - `TradingCycleService._should_block_for_sideways`
  - `TradingCycleService._check_sideways_exception_pass`

### 4) volatility 관련 정책
- `high_volatility_defense_enabled`
- `volatility_size_multipliers`
- 사용 위치
  - `RiskController.review`
  - `MarketRegimeClassifier.classify` 는 상태/분류 결과를 생성하고, 정책은 아님

### 5) meaningful order / exposure / allocation 관련 정책
- `meaningful_order_notional`
- `min_managed_position_notional`
- `max_symbol_exposure_pct`
- `max_total_exposure_pct`
- `target_allocation_pct`
- 사용 위치
  - `AutoTradeService._handle_buy`
  - `AutoTradeService._handle_sell`
  - `PaperBroker.submit`

---

## 단일 정책 소스 설계

### 새 구조
- 파일: `src/investment_bot/core/trading_policy.py`
- 핵심 타입
  - `TradingPolicy`
  - `TradingPolicySnapshot`
  - `PolicyObservation`

### 역할
- `TradingPolicy`
  - 설정값을 정책 의미 단위로 묶음
  - regime alias를 단일 규격으로 정규화
- `TradingPolicySnapshot`
  - 런타임에서 읽기 전용 정책 집합
- `PolicyObservation`
  - 차단/제한 판단을 로그/응답에 남길 최소 포맷

### 왜 최소 구조인가
- 기존 `Settings`를 없애지 않음
- 기존 서비스 구조를 갈아엎지 않음
- 우선 "정책 해석 계층"만 추가해서 분산된 의미를 모음

---

## 정책 vs 상태 분리 기준

### 정책(policy)
런타임 동안 참조되는 제한/허용 규칙.
예:
- `max_consecutive_buys = 5`
- `max_symbol_exposure_pct = 25.0`
- `trend_strategy_allowed_regimes = [trend_up, trend_down]`

### 상태(state)
실행 중 계속 바뀌는 값.
예:
- `consecutive_buys = 2`
- `losing_streak = 1`
- `current_position_value`
- `volatility_state = high`
- `market_regime = sideways`

### 이번 수정의 핵심 사례
- `max_consecutive_buys`는 정책
- `consecutive_buys`는 상태
- `PaperBroker`는 상태를 유지하지만, 정책 위반 시 `PolicyObservation` 형식으로 차단 사유를 반환

---

## 관측성 규격

최소 표준 포맷:

```json
{
  "policy_name": "max_consecutive_buys",
  "policy_value": 5,
  "current_state": 5,
  "block_reason": "max_consecutive_buys_reached"
}
```

현재 적용한 곳:
- `PaperBroker.submit`
  - `max_consecutive_buys_reached`
  - `max_symbol_exposure_reached`

다음 확장 추천:
- `AutoTradeService._handle_buy`의
  - `meaningful_order_notional`
  - `max_total_exposure_pct`
  - `target_allocation_pct`
- `RiskController.review`의
  - `blocked_time_window`
  - `higher_tf_bias_mismatch`
  - `high_volatility_defense`
- `TradingCycleService`의
  - `trend_strategy_route_blocked`
  - `range_strategy_route_blocked`
  - `uncertain_regime_blocked`
  - `sideway_filter_blocked`
  - `sideways_breakout_exception`

---

## 구조적으로 어긋남을 줄이기 위한 포인트

1. **regime 문자열은 정책 모듈을 통해서만 해석**
   - 서비스마다 `uptrend/ranging/mixed`를 직접 비교하지 않기
2. **정책값 직접 접근 대신 snapshot 우선**
   - 새 정책 축은 `Settings`에서 흩어 꺼내지 말고 `TradingPolicy.snapshot`에 추가
3. **차단 응답은 가능한 한 `PolicyObservation` 형태로 통일**
   - 운영 중 원인 분석 속도가 빨라짐
4. **상태는 broker/account/runtime 쪽에만 남기기**
   - 정책 모듈은 상태를 저장하지 않음
5. **정책 축별 소유권 유지**
   - route/sideways: trading cycle
   - sizing/volatility: risk controller
   - execution/exposure: broker + auto trade

---

## 이번 변경의 한계
- `AutoTradeService`의 allocation/exposure/meaningful-order 차단 응답은 아직 완전히 `PolicyObservation`으로 통일하지 않음
- `Settings` 자체를 정책 섹션 중심으로 재편하지는 않음
- route 정책과 symbol별 전략 허용 규칙은 아직 일부 하드코딩이 남아 있음

이유:
- 이번 범위는 병목 정책 축 정리와 최소 구조 개선에 집중
- 전면 구조 개편은 후속 이슈로 분리하는 것이 안전함
