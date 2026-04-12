# trend_following BUY near-miss 관측 설계

**Date:** 2026-04-12  
**Author:** Planner subagent (maker-near-miss-observability)  
**Status:** 설계 완료 / 최소 수정 구현 가능 / 실제 코드 반영은 이번 문서 범위 밖

---

## 1. 목적

trend_following BUY 가 실제로 왜 탈락했는지, 특히 `trend_gap_pct` 가 임계값 근처(예: 0.10%~0.15%)였는데도 최종 BUY 로 이어지지 않은 케이스를 운영에서 바로 판단 가능하게 만드는 관측 설계다.

핵심은 다음 2가지다.

1. **threshold 완화가 필요한지**를 나중에 수치로 판단할 수 있어야 한다.
2. **과도한 로깅 없이** run_history 중심으로 집계 가능한 구조여야 한다.

---

## 2. 현재 상태에서 near-miss 판단이 어려운 이유

현재 `semi_live_cycle` / `executor_cycle` 로그만으로도 일부 힌트는 있으나, threshold 조정 판단용으로는 부족하다.

### 2.1 있는 정보
- `signal.reason` / `review.reason` 안에 문자열 형태로
  - `trend_gap_pct`
  - `momentum_pct`
  - route blocked 여부
  - 일부 risk 차단 이유
  가 섞여 있다.
- `review.approved`, `target_notional`, `broker_result.reason` 으로 최종 실행/거절은 알 수 있다.
- `market_regime`, `volatility_state`, `higher_tf_bias` 는 구조화되어 있다.

### 2.2 부족한 정보
- **near-miss 여부가 명시적으로 구조화되어 있지 않다.**
- `trend_gap_pct` / `momentum_pct` 가 문자열 reason 파싱 대상이라 일별 집계가 불편하다.
- **탈락 지점(stage)** 이 명확하지 않다.
  - strategy 조건 미달인지
  - strategy route 차단인지
  - risk review 차단인지
  - sizing/exposure 차단인지
  - executor 우선순위(sell 우선 등) 때문에 미선정인지
- threshold 근처 구간만 별도로 모아서 보기가 어렵다.
- `executor_cycle` 에서 **“그 사이클에 BUY near-miss 가 몇 건 있었는지”** 를 한눈에 볼 수 없다.

### 2.3 실무상 문제
이 상태에서는:
- `0.15% → 0.12%` 완화가 실제로 의미 있는지,
- 아니면 대부분이 `momentum <= 0` / `route_blocked` / `sideways` 때문에 어차피 못 샀을 케이스인지,
운영자가 빠르게 판단하기 어렵다.

---

## 3. near-miss 정의안

near-miss 는 “BUY 의도가 있었거나 BUY 근처였지만 최종 BUY 로 이어지지 않은 케이스”로 본다.

운영 판단용으로는 최소 3개 카테고리로 나누는 것이 좋다.

### A. Threshold near-miss
**정의:** `trend_gap_pct` 가 BUY threshold 아래지만 근접 구간에 위치한 경우

예시 조건:
- 현재 threshold = `0.0015` (0.15%)
- near-miss window = `0.0010 <= trend_gap_pct < 0.0015`
- action 은 hold 이거나 buy 미발생

의미:
- threshold 를 0.12% 또는 0.10%로 내렸을 때 살아날 가능성이 있는 후보군

권장 세부 필드:
- `trend_gap_pct`
- `trend_gap_to_threshold_pct = trend_gap_pct - buy_threshold`
- `momentum_pct`
- `market_regime`
- `volatility_state`

---

### B. Confirm-fail near-miss
**정의:** `trend_gap_pct` 는 threshold 근처 또는 초과했지만, 다른 확인 조건 때문에 탈락한 경우

예시:
- `trend_gap_pct >= 0.0010` 이지만 `momentum_pct <= 0`
- 또는 threshold 초과했지만 `trend_strategy_route_blocked`
- 또는 sideway filter / higher tf bias 에 의해 hold 전환

의미:
- threshold 완화가 아니라 **보조 조건이 병목**인지 구분 가능

권장 하위 유형:
- `confirm_fail_momentum`
- `confirm_fail_route`
- `confirm_fail_sideway`
- `confirm_fail_risk`

---

### C. Execution near-miss
**정의:** strategy/review 단계에서는 BUY 가능했거나 매우 근접했지만, 실행/선택 단계에서 탈락한 경우

예시:
- BUY review approved=true 였지만 `meaningful_order_notional` / `total_exposure_limit` 로 skip
- 여러 후보 중 더 높은 점수 후보에 밀려 선택되지 않음
- sell 우선 처리 때문에 buy 후보가 실행되지 않음

의미:
- threshold 문제가 아니라 **실행 정책/포트폴리오 제약** 문제인지 구분 가능

권장 하위 유형:
- `execution_fail_exposure`
- `execution_fail_meaningful_notional`
- `execution_fail_priority`
- `execution_fail_not_chosen`

---

## 4. 운영용 관측 설계

핵심 원칙:
- **기존 run_history 구조를 유지**한다.
- 전량 raw logging 대신, **near-miss 케이스만 얇게 구조화**한다.
- per-signal + per-cycle summary 2단으로 남긴다.

### 4.1 최소 필드: semi_live_cycle payload 내부
기존 `payload.signal.meta` 또는 `payload.review` 주변에 아래 구조를 추가 권장.

```json
"near_miss": {
  "is_near_miss": true,
  "category": "threshold",
  "subtype": "trend_gap_below_threshold",
  "stage": "strategy_signal",
  "buy_threshold_pct": 0.0015,
  "near_miss_floor_pct": 0.0010,
  "trend_gap_pct": 0.0012,
  "trend_gap_to_threshold_pct": -0.0003,
  "momentum_pct": 0.0001,
  "would_buy_if_gap_threshold_relaxed": true,
  "would_buy_if_only_gap_relaxed": true
}
```

### 4.2 최소 권장 필드 목록
가장 최소한으로 꼭 넣어야 할 필드:
- `near_miss.is_near_miss`
- `near_miss.category`
- `near_miss.stage`
- `near_miss.buy_threshold_pct`
- `near_miss.trend_gap_pct`
- `near_miss.trend_gap_to_threshold_pct`
- `near_miss.momentum_pct`

여유가 되면 추가:
- `near_miss.subtype`
- `near_miss.near_miss_floor_pct`
- `near_miss.would_buy_if_only_gap_relaxed`
- `near_miss.block_reason`
- `near_miss.market_regime`
- `near_miss.volatility_state`

---

### 4.3 stage 표준화 제안
문자열 파편화를 막기 위해 stage 를 표준 enum 비슷하게 두는 것이 좋다.

권장값:
- `strategy_signal`
- `route_filter`
- `risk_review`
- `strategy_selection`
- `execution_guard`
- `execution_priority`

이 값 하나만 있어도, threshold 문제인지 운영 정책 문제인지 바로 분리된다.

---

### 4.4 executor_cycle 요약 필드
각 cycle 끝에 summary 를 추가하면 운영자가 threshold 조정 필요성을 더 빨리 본다.

예시:

```json
"near_miss_summary": {
  "trend_following_buy": {
    "threshold_count": 3,
    "confirm_fail_count": 2,
    "execution_count": 1,
    "top_symbols": ["TRX/KRW", "HBAR/KRW"],
    "trend_gap_band_counts": {
      "0.10-0.12%": 2,
      "0.12-0.15%": 1
    }
  }
}
```

최소 summary 필드:
- `threshold_count`
- `confirm_fail_count`
- `execution_count`
- `trend_gap_band_counts`

---

## 5. 집계 단위 제안

### 5.1 심볼 단위
목적:
- 어떤 심볼에서 near-miss 가 반복되는지 파악

예시 지표:
- `symbol/day near_miss_count`
- `symbol/day threshold_near_miss_count`
- `symbol/day avg_trend_gap_to_threshold`

활용:
- 특정 심볼만 유독 threshold 근처를 반복하면 심볼별 민감도 차이 의심 가능

### 5.2 사이클 단위
목적:
- “이번 5분 사이클에 BUY 기회가 있었는가”를 운영에서 빠르게 확인

예시 지표:
- cycle당 `near_miss_count`
- cycle당 `near_miss_best_gap_pct`
- cycle당 `threshold_count / confirm_fail_count / execution_count`

활용:
- threshold 를 바꾸지 않아도 시장이 살아나는 중인지 파악 가능

### 5.3 일별 단위
목적:
- threshold 조정 판단의 근거 자료

가장 중요한 일별 지표:
- `trend_following_buy_threshold_near_miss_count`
- `trend_following_buy_confirm_fail_count`
- `trend_following_buy_execution_near_miss_count`
- `0.10%~0.12%`, `0.12%~0.15%` 구간 count
- near-miss 중 `momentum > 0` 비율
- near-miss 중 `sideways` 비율

운영 판단용 권장 해석:
- `0.12~0.15%` 구간이 많고 momentum도 양수면 → **threshold 완화 검토 가치 높음**
- near-miss 대부분이 momentum<=0 또는 route blocked 면 → **threshold 완화 효과 낮음**
- near-miss 가 execution_fail 위주면 → **threshold보다 실행 정책 조정 우선**

---

## 6. threshold 조정 판단에 바로 쓰는 형태

일별 리포트에 아래 표가 있으면 가장 실용적이다.

| 지표 | 값 | 해석 |
|---|---:|---|
| threshold near-miss 수 | 18 | threshold 바로 아래 후보량 |
| 이 중 momentum>0 비율 | 72% | threshold 완화 시 살아날 가능성 |
| confirm-fail(route/risk) 수 | 11 | threshold 외 병목 규모 |
| execution near-miss 수 | 4 | 포트폴리오/실행 정책 병목 |
| 0.12~0.15% band 수 | 9 | 0.12% 완화 효과 추정 |
| 0.10~0.12% band 수 | 3 | 0.10%까지 내려야만 살아나는 구간 |

권장 판정 규칙 예시:
- **3일 연속** `0.12~0.15% band` 가 유의미하고,
- 그중 `momentum>0` 비율이 높고,
- route/risk 차단보다 threshold 차단 비중이 높으면,
- `0.15% → 0.12%` 완화 검토.

---

## 7. 최소 수정 구현안

### 7.1 낮은 난이도
문서 목적상 가장 추천되는 1차안.

변경 포인트:
1. `TrendFollowingStrategy.generate_signal()` 에서
   - `trend_gap_pct`, `momentum_pct`, `buy_threshold_pct` 를 `signal.meta` 로 구조화
2. `TradingCycleService.run()` 에서
   - trend_following BUY hold 케이스에 대해 near-miss 판정 함수 호출
   - `signal.meta["near_miss"]` 추가
3. run_history 는 기존 `semi_live_cycle` payload 저장 그대로 활용

장점:
- 코드 침습 적음
- reason 문자열 파싱 없이 집계 가능
- 기존 구조와 충돌 적음

한계:
- strategy_selection / execution 단계 near-miss 까지는 아직 부족

---

### 7.2 중간 난이도
운영용으로 더 완성도 높은 안.

변경 포인트:
1. 낮은 난이도 항목 포함
2. `AutoTradeService._handle_buy()` / `run_once()` 에서
   - `execution near-miss` summary 생성
3. `executor_cycle` payload 에 `near_miss_summary` 추가
4. stage / subtype 표준화

장점:
- threshold 문제와 실행 정책 문제를 함께 볼 수 있음
- 운영 리포트 자동화에 바로 유리

단점:
- 수정 파일 범위가 넓어짐
- 테스트 보강 필요

---

## 8. 과도한 로깅 방지 원칙

- 모든 hold 를 추가 로그로 남기지 말고, **near-miss window 해당 케이스만 구조화**
- 별도 텍스트 로그 spam 대신 `run_history` JSON에 포함
- band 는 2~3개만 유지
  - `0.10~0.12%`
  - `0.12~0.15%`
  - optional: `>=0.15% but blocked`
- executor summary 는 cycle당 1회만 저장

---

## 9. 바로 구현해도 되는가?

**예, 낮은 난이도 안은 지금 바로 구현해도 된다.**

이유:
- 기존 `signal.meta`, `review`, `run_history` 구조를 재사용 가능
- 텍스트 로그 증가 없이 JSON payload 확장 수준
- threshold 조정 판단 근거를 빠르게 쌓을 수 있음

다만,
- 이번 단계에서는 **문서/설계 우선**이므로
- 실제 구현은 `낮은 난이도 안`부터 시작하는 것이 적절하다.

---

## 10. 최종 권장안

### 우선순위 1
`semi_live_cycle` 에 아래 최소 near-miss 필드 추가:
- `is_near_miss`
- `category`
- `stage`
- `trend_gap_pct`
- `trend_gap_to_threshold_pct`
- `momentum_pct`
- `buy_threshold_pct`

### 우선순위 2
`executor_cycle` 에 cycle summary 추가:
- `threshold_count`
- `confirm_fail_count`
- `execution_count`
- `trend_gap_band_counts`

### 우선순위 3
일별 집계/리포트 반영:
- `0.12~0.15%` 누적 빈도
- momentum 양수 비율
- route/risk/execution 병목 분리

---

## 11. 결론

이번 관측 설계의 핵심은 다음이다.

1. **near-miss 를 문자열이 아니라 구조화된 필드로 남긴다.**
2. **threshold / confirm-fail / execution** 으로 카테고리를 나눈다.
3. threshold 조정은 단순 빈도가 아니라
   - near-miss band 분포
   - momentum 동반 여부
   - 다른 병목(stage) 비중
   로 판단한다.
4. 가장 현실적인 1차 구현은 `signal.meta.near_miss` 추가다.

이 정도만 해도 `0.15%를 0.12%로 낮춰야 하는가?`에 대해 며칠 내 운영 근거를 만들 수 있다.
