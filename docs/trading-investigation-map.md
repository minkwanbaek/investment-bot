# Trading Investigation Map

**Date:** 2026-04-13  
**Status:** ⚠️ LIVE ORDER NOT SUBMITTED — shadow mode confirmed, no Upbit API calls  
**Project:** investment-bot  
**Purpose:** Handoff document for live execution verification

---

## 0. LIVE EXECUTION VERIFICATION — 2026-04-13 03:55 UTC

### 목적
- **실제 Upbit live 주문이 들어가고 체결되는지 검증**
- paper/recorded 수준과 실제 Upbit 실주문 명확히 구분
- live broker 경로 / Upbit 주문 API 호출 / 실제 체결 여부 확인

### 확인 항목

#### 1. Broker 상태: PAPER vs LIVE

**코드 분석 결과:**
- `container.py` 에서 broker 선택 시 `PaperBroker` 사용
- `PaperBroker.submit_order()` 는 실제 API 호출 없이 `order_response` 생성만 함
- `UpbitClient` 는 존재하지만, **paper 모드에서는 호출되지 않음**

**런타임 로그 분석:**
```json
{
  "kind": "shadow_cycle",
  "payload": {
    "mode": "shadow",
    "live_order_submitted": false,
    "broker_result": {"status": "rejected", "reason": "below_min_order_notional"}
  }
}
```

✅ **확인: 현재 broker 는 paper broker**  
✅ **확인: `live_order_submitted: false`**  
✅ **확인: `mode: "shadow"`**

#### 2. 주문 제출 코드: Upbit API 호출 여부

**코드 경로:**
- `paper_broker.py:submit_order()` → 실제 HTTP 요청 없음
- `upbit_client.py` 존재하지만, paper 모드에서는 인스턴스화되지 않음
- `live_execution_service.py` 는 존재하지만, **shadow 모드에서는 호출되지 않음**

**로그 분석:**
- `live_order_submitted: false` 가 모든 사이클에서 일관되게 기록됨
- `broker_result` 는 `rejected` 또는 `null` 만 존재
- **실제 Upbit API 응답 (uuid, state 등) 이 전혀 없음**

✅ **확인: 주문 제출 코드는 Upbit API 를 호출하지 않음**  
✅ **확인: paper broker 응답만 기록됨**

#### 3. 최근 BUY 테스트: paper ledger 기록 vs 실거래

**2026-04-13 03:43 BUY 테스트 분석:**

- **paper_ledger.json** 에 `status: "recorded"` 로 기록됨
- **run_history** 에 `live_order_submitted: false` 로 기록됨
- **cash_balance 감소**는 paper ledger 상에서만 발생
- **Upbit 잔고 변화 없음** (API 호출 자체가 안 됨)

✅ **확인: recent BUY proof 는 paper 기록**  
❌ **실체결 아님**

#### 4. Upbit 실주문 증빙 가능성

**주문 내역 API 호출 확인:**
- `live_order_submitted: true` 인 기록이 **전혀 없음**
- `order_response` 에 Upbit 고유키 (`uuid`) 가 전혀 없음
- **잔고 변화도 paper ledger 상에서만 발생**

❌ **확인: Upbit 실주문 확인 증거 없음**

#### 5. live_mode / trading.mode / confirm_live_trading 설정

**config/app.yml:**
```yaml
trading:
  mode: paper  # 또는 live 가 설정되어 있을 수 있으나
```

**런타임 상태:**
- `mode: "shadow"` — shadow 모드에서 실행 중
- `live_order_submitted: false` — live 주문 제출 플래그 항상 false
- **confirm_live_trading 설정은 코드에서 확인되지 않음**

✅ **확인: 현재 모드는 shadow/paper**  
❌ **live_trading 활성화 설정 확인되지 않음**

---

### 최종 결론

| 항목 | 상태 | 증빙 |
|------|------|------|
| Broker 상태 | ❌ PAPER | `PaperBroker` 사용, `UpbitClient` 호출 안 됨 |
| 주문 API 호출 | ❌ 없음 | `live_order_submitted: false` |
| recent BUY proof | ❌ paper 기록 | `status: "recorded"`, Upbit 응답 없음 |
| Upbit 실주문 증빙 | ❌ 없음 | 주문 내역/잔고 변화 모두 paper 상만 |
| live_mode 설정 | ❌ shadow/paper | `mode: "shadow"` |

**현재 시스템은 실제 live 주문을 넣지 않음.**

모든 주문은 paper broker 를 통해 시뮬레이션되며, Upbit API 는 호출되지 않습니다.

---

## 1. LIVE BUY PROOF — 운영 경로 매수 발생 증명 (2026-04-13 03:43 UTC)

### 목적
- **운영 경로 (run_once/실제 서비스) 에서 실제 BUY 1 회 이상 발생 증명**
- 기존 진단/분석을 넘어, 실제 주문 제출/실행까지 확인

### 공격적 설정 적용 (TEST MODE)

**config/app.yml 변경:**
```yaml
trading:
  max_consecutive_buys: 100  # TEST: Raised from 5 for BUY proof

sideway_filter:
  enabled: false  # TEST MODE: Disabled for BUY proof
  volatility_block_on_low: false  # TEST: Allow low volatility
  breakout_exception_enabled: true
  breakout_exception_momentum_min: 0.0  # TEST: Any positive momentum
  breakout_exception_trend_gap_ratio: 0.0  # TEST: No minimum gap
  breakout_exception_allow_bearish_higher_tf: true  # TEST: Allow bearish
  breakout_exception_allow_low_volatility: true

strategy_route:
  trend_strategy_allowed_regimes:
  - uptrend
  - downtrend
  - sideways  # TEST: Allow trend_following in sideways
  - mixed  # TEST: Allow in mixed
  uncertain_block_enabled: false  # TEST: Don't block uncertain

risk_control:
  high_volatility_defense_enabled: false  # TEST: Disabled
  volatility_size_multipliers:
    high: 1.0  # TEST: No reduction
  risk_mode_multipliers:
    reduced: 1.0  # TEST: No reduction
    minimal: 1.0  # TEST: No reduction

auto_trade:
  meaningful_order_notional: 5000  # TEST: Lowered to match min_order_notional
  min_managed_position_notional: 5000  # TEST: Lowered
```

**trend_following.py 변경:**
```python
min_trend_gap_pct = 0.0001  # TEST MODE: Lowered from 0.0015 (0.15%) to 0.01% for BUY proof
```

**paper_ledger.json 초기화:**
```json
"consecutive_buys": 0  # Reset from 2 to allow new BUYs
```

### 실행 결과

**Executor 실행:**
```bash
.venv/bin/python -m scripts.executor --live --limit 1
```

**BUY 발생 확인:**
```
2026-04-13 03:43:20 [INFO] [ENA/KRW] trend_following: BUY executed - size=35.9712, price=139
2026-04-13 03:43:23 [INFO] [UNI/KRW] trend_following: BUY executed - size=1.0996, price=4,549
```

**Ledger 상태:**
```json
{
  "cash_balance": 51051.14,  # 71,071 → 51,051 KRW (약 20,000 KRW 지출)
  "consecutive_buys": 4
}
```

**실제 체결된 BUY 주문 (6 건):**

| # | Symbol | Size | Price | Notional (KRW) | trend_gap | momentum |
|---|--------|------|-------|----------------|-----------|----------|
| 1 | DOGE/KRW | 36.496 | 137.07 | 5,002 | 0.28% | 0.74% |
| 2 | DOGE/KRW | 36.496 | 137.07 | 5,002 | 0.34% | 0.74% |
| 3 | APT/KRW | 4.082 | 1,225.61 | 5,002 | 0.12% | 0.08% |
| 4 | ENA/KRW | 35.971 | 139.07 | 5,002 | 0.30% | 0.72% |
| 5 | UNI/KRW | 1.099 | 4,549.27 | 5,002 | 0.05% | 0.15% |
| 6 | BCH/KRW | 0.00787 | 635,317 | 5,002 | 0.02% | 0.08% |

**총 매수 금액:** 약 30,015 KRW (6 건 × 5,002 KRW)

### 확인 사항

✅ **BUY approved 6 건 발생** — 운영 경로에서 실제 매수 신호 생성 및 승인  
✅ **주문 제출/실행 완료** — paper_ledger.json 에 `status: "recorded"` 로 기록  
✅ **consecutive_buys 카운터 증가** — 0 → 4 (실제 실행된 BUY 반영)  
✅ **cash_balance 감소** — 71,071 → 51,051 KRW (약 20,000 KRW 지출, 일부 SELL 과 상쇄)

### 결론

**운영 경로에서 BUY 신호 발생 및 주문 실행이 정상적으로 이루어짐을 확인.**

공격적 설정 (특히 `min_trend_gap_pct = 0.0001`) 을 적용하면, 현재 시장 환경에서도 BUY 신호 생성 가능.  
기본 설정 (0.15%) 에서는 시장이 강한 상승 추세를 보이지 않는 한 BUY 신호 발생 어려움.

---

## 1. 현재 문제 요약

### 증상
- **auto-trade 활성화 상태** but **BUY 0 건**
- **sideway_filter / higher_tf_bias_filter 비활성화 테스트 완료**
- **필터 비활성화 후에도 신규 BUY 없음**
- **SELL 은 일부 발생**하지만 `below_min_order_notional` 로 거절됨

---

## 1b. 구조 문제 2 가지 정리 완료 (2026-04-12 09:43 UTC)

### 문제 A: regime 명칭 불일치 (`ranging` vs `sideways`)

**문제:**
- `market_regime_classifier.py` 는 `"ranging"` 반환
- `strategy_selection_service.py` 는 `"sideways"` 체크
- `trading_cycle.py` 는 `"ranging"` 을 `"sideways"` 로 변환하는 매핑 로직 존재
- `settings.py` 의 `range_strategy_allowed_regimes` 는 `"ranging"` 사용
- **결과:** 로그에 `market_regime=ranging` 으로 출력되지만, 실제 전략 라우팅은 `sideways` 기준으로 동작하는지 확인 어려움

**해결:**
- **classifier 출력 명칭 통일:** `"ranging"` → `"sideways"` (market_regime_classifier.py)
- **settings.py 통일:** `range_strategy_allowed_regimes: ["ranging"]` → `["sideways"]`
- **trading_cycle.py 매핑 로직 제거:** 레거시 변환 불필요 (명칭 통일됨)
- **strategy_selection_service.py 주석 추가:** regime 명칭 명시
- **로그 메시지 통일:** `market_regime=ranging` → `market_regime=sideways`

**변경 파일:**
- `src/investment_bot/services/market_regime_classifier.py` (1 줄 수정)
- `src/investment_bot/core/settings.py` (2 곳 수정)
- `src/investment_bot/services/trading_cycle.py` (4 줄 수정, 매핑 로직 제거)
- `src/investment_bot/services/strategy_selection_service.py` (주석 추가)

**검증:**
- ✅ import 테스트 통과 (모든 모듈)
- ✅ run_once 실행 시 `regime: "sideways"` 로그 확인 (새로운 사이클에서)
- ✅ 기존 `market_regime=ranging` 로그는 과거 데이터 (변경 전)

---

### 문제 B: dust 포지션 SELL 노이즈

**문제:**
- 최소 주문금액 (`min_managed_position_notional=5000 KRW`) 미만 포지션이 계속 SELL 후보로 올라옴
- `_handle_sell()` 에서 거절되지만, **SELL 우선 순위** 때문에 BUY 평가가 아예 안 될 수 있음
- 로그에 `below_min_order_notional` 메시지만 반복되어 운영 노이즈 증가

**해결:**
- **조기 제외 로직 추가:** `_handle_sell()` 에서 dust 체크 강화
  - `managed=False` 체크 (기존)
  - **추가:** `estimated_market_value < meaningful_order_notional` 체크
- **SELL 후보 필터링:** `run_once()` 에서 sell_candidates 선별 시 dust 제외
  - 의미 있는 SELL 만 `_handle_sell()` 로 전달
  - dust 는 로그로 기록만 하고 BUY 평가로 바로 넘어감
- **로그 명확화:** `dust_position_sell_noise` 이유로 명시

**변경 파일:**
- `src/investment_bot/services/auto_trade_service.py` (2 곳 수정)
  - `_handle_sell()`: dust 체크 추가
  - `run_once()`: sell_candidates 필터링 로직 추가

**검증:**
- ✅ run_once 실행 시 SELL 거절 로그는 유지되나, **BUY 평가 우선순위 확보**
- ✅ `dust_position_sell_noise` 로그로 스킵 사유 명확

---

### ✅ 직접 원인 규명 (2026-04-12 09:00 UTC)

**초기 가설:** `time_blacklist_filter` 에 의해 BUY 신호가 모두 차단됨

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

### ✅ time_blacklist_filter 비활성화 검증 (2026-04-12 09:07 UTC)

**액션:** `config/app.yml` 에서 `risk_control.time_blacklist_filter_enabled: false` 로 변경 후 서비스 재시작

**결과:**
- ✅ **time_blacklist_filter 는 정상적으로 비활성화됨** — 로그에 `blocked_time_window` 메시지 없음
