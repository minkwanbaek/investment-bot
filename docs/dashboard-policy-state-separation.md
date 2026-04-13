# Dashboard Policy/State Separation

## 개요

운영 대시보드에서 **정책 (policy)**과 **상태 (state)**를 명시적으로 분리하여 표시함으로써, 시스템의 현재 동작 원리와 차단/허용 판단의 근거를 빠르게 파악할 수 있도록 한다.

## 설계 원칙

### Policy (정책)
런타임 동안 참조되는 **불변 규칙** 또는 **설정값**.
- 예: `max_consecutive_buys = 5`
- 예: `sideway_filter_enabled = true`
- 예: `max_symbol_exposure_pct = 25.0`

### State (상태)
실행 중 계속 바뀌는 **가변 값**.
- 예: `consecutive_buys = 2`
- 예: `losing_streak = 1`
- 예: `cash_balance = 100000`
- 예: `positions_count = 3`

### Observations (관측)
각 거래 사이클에서 정책 평가 결과를 기록한 **이력**.
- `policy_name`: 어떤 정책이 평가되었는지
- `policy_value`: 정책 기준값
- `current_state`: 평가 당시 상태
- `block_reason`: 차단 사유 (None 이면 통과)

---

## API 변경

### `/operator/live-dashboard`

응답 구조 확장:

```json
{
  "summary_cards": { ... },
  "equity_curve": [ ... ],
  "recent_trades": [ ... ],
  "by_strategy_version": { ... },
  "by_market_regime": { ... },
  "policy_snapshot": {
    "policy": {
      "max_consecutive_buys": 5,
      "sideway_filter_enabled": true,
      "uncertain_block_enabled": true,
      "high_volatility_defense_enabled": true,
      "volatility_size_multipliers": { "low": 1.0, "normal": 1.0, "high": 0.5 },
      "meaningful_order_notional": 10000,
      "min_managed_position_notional": 5000,
      "max_symbol_exposure_pct": 25.0,
      "max_total_exposure_pct": 80.0,
      "target_allocation_pct": 70.0,
      ...
    },
    "state": {
      "consecutive_buys": 2,
      "losing_streak": 0,
      "total_equity": 1234567,
      "cash_balance": 71071,
      "positions_count": 0
    }
  },
  "policy_observations": [
    {
      "policy_name": "route_filter",
      "policy_value": "regime-based routing rules",
      "current_state": "sideways",
      "block_reason": "sideway_filter_blocked",
      "timestamp": "2026-04-13T03:00:00Z",
      "symbol": "BTC/KRW"
    },
    {
      "policy_name": "risk_mode",
      "policy_value": "normal",
      "current_state": {
        "losing_streak": 0,
        "volatility_state": "normal"
      },
      "block_reason": null,
      "timestamp": "2026-04-13T03:01:00Z",
      "symbol": "ETH/KRW"
    }
  ]
}
```

---

## UI 변경

### 대시보드 섹션 추가

1. **정책 기준점 (Policy Snapshot)**
   - 주요 정책값 일괄 표시
   - 운영 중 변경된 설정 확인 가능
   - 예: 필터 활성화 상태, 노출 한도, 주문 최소 단위

2. **최근 정책 관측 (Latest Observations)**
   - 최근 5 건의 정책 평가 이력
   - BLOCK/PASS 배지로 결과 시각화
   - 차단 사유 즉시 확인 가능

---

## 구현 위치

### Backend

- `src/investment_bot/services/dashboard_service.py`
  - `extract_policy_observations()`: trade logs 에서 정책 관측 추출
  - `build_trade_log_dashboard()`: policy_snapshot 파라미터 추가

- `src/investment_bot/api/routes.py`
  - `/operator/live-dashboard`: policy snapshot 구성, current state 추출

### Frontend

- `src/investment_bot/static/dashboard.html`
  - policy-snapshot, policy-observations 섹션 추가

- `src/investment_bot/static/dashboard.js`
  - `renderPolicyState()`: policy/state/observations 렌더링

---

## 운영 관점 이점

### 1. 문제 진단 속도 향상
- "왜 매수가 안 되지?" → policy_observations 에서 block_reason 즉시 확인
- 예: `sideway_filter_blocked`, `max_consecutive_buys_reached`

### 2. 설정/상태 혼동 방지
- 정책값 (설정) 과 현재값 (상태) 이 명확히 분리
- "consecutive_buys 가 5 로 제한된 건 설정인가, 현재값인가?" 혼동 방지

### 3. 유지보수 용이성
- 정책 변경 시 대시보드에서 즉시 반영 확인
- 상태 이상 시 policy vs state 대조로 원인 추적

### 4. 감사 (Audit) 지원
- 모든 거래 사이클의 정책 평가 이력 기록
- "어떤 정책이 작동했는지" 소급 분석 가능

---

## 확장 포인트

### 향후 추가 가능한 정책 관측
- `AutoTradeService` 의 exposure/allocation 차단
- `RiskController` 의 time_blacklist, higher_tf_bias
- `TradingCycleService` 의 route 정책 (trend/range 허용 regime)

### PolicyObservation 표준화
- `PolicyObservation` 타입을 전체 서비스에서 일관되게 사용
- block_reason 문자열을 enum 또는 상수로 정리

---

## 한계

- 이번 구현은 **최소 범위**에 집중
- 전면 프론트엔드 개편은 하지 않음
- policy_observations 는 최근 10 건 기준, 중복 제거 후 5 건 표시
- 모든 정책 축이 관측되는 것은 아님 (후속 확장 필요)

---

## 관련 문서

- `docs/trading-policy-centralization.md`: 정책 중앙화 설계
- `src/investment_bot/core/trading_policy.py`: TradingPolicy 구현
- `trend-following-near-miss-observability-design.md`: near-miss 관측성 설계
