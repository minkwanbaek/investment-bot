# 로그 가독성 개선 가이드 (2026-04-14)

## 개요

투자봇 운영 중 "왜 샀는지 / 왜 막혔는지 / 왜 거절됐는지"를 한눈에 파악할 수 있도록 로그 구조를 개선하였습니다.

## 변경 사항

### 1. 새로운 로그 태그 체계

| 태그 | 설명 | 예시 |
|------|------|------|
| `[BUY_OK]` | 매수 주문 실행 성공 | `[BUY_OK] BTC/KRW \| trend_following \| size=0.001 \| price=100,000,000 \| notional=100,000KRW` |
| `[SELL_OK]` | 매도 주문 실행 성공 | `[SELL_OK] ETH/KRW \| mean_reversion \| size=0.01 \| price=3,000,000 \| notional=30,000KRW` |
| `[BUY_SKIP]` | 매수 신호 생성 but 거절/스킵 | `[BUY_SKIP] LINK/KRW \| trend_following \| below_min_order_notional \| 주문 금액이 최소 주문 금액 (5,000 KRW) 미만 \| notional=4,500KRW \| min=5,000KRW` |
| `[SELL_SKIP]` | 매도 신호 생성 but 거절/스킵 | `[SELL_SKIP] DOT/KRW \| trend_following \| below_min_order_notional \| 주문 금액이 최소 주문 금액 (5,000 KRW) 미만 \| pos_value=4,800KRW \| min=5,000KRW` |
| `[ORDER_FAIL]` | 거래소/API 오류 | `[ORDER_FAIL] APT/KRW \| dca \| strategy_error \| unexpected keyword argument` |

### 2. Reason Code Registry

중앙集中的인 이유 코드 사전을 도입하여 운영자가 빠르게 이해할 수 있도록 합니다.

**주요 reason codes:**

| 코드 | 한국어 설명 |
|------|-------------|
| `below_min_order_notional` | 주문 금액이 최소 주문 금액 (5,000 KRW) 미만 |
| `max_consecutive_buys_reached` | 연속 매수 횟수 제한 도달 |
| `insufficient_cash` | 현금 부족 |
| `no_position_to_sell` | 매도할 포지션 없음 |
| `preview_blocked` | 주문 프리뷰 차단 |
| `cooldown_active` | 쿨다운 기간 중 |
| `non_actionable_signal` | 실행 가능한 신호 없음 |
| `dust_position_sell_noise` | 소량 포지션 (노이즈) |
| `uncertain_regime_blocked` | 불확실 시장 레짐 차단 |
| `sideway_filter_blocked` | 횡보장 필터 차단 |

### 3. Trace ID

각 executor 사이클과 심볼 평가에 고유 trace_id 를 부여하여 주문 흐름을 추적할 수 있습니다.

```
2026-04-14 03:00:00,000 [INFO] Executor cycle started at ... | trace=a1b2c3d4
2026-04-14 03:00:01,000 [INFO] [BTC/KRW] Current price: 100,000,000 | trace=e5f6g7h8
2026-04-14 03:00:02,000 [INFO] [BUY_OK] BTC/KRW | trend_following | ... | trace=e5f6g7h8
```

### 4. 사이클 요약 (Summary)

각 executor 사이클 종료 시 실행 통계와 스킵 이유 집계를 출력합니다.

```
2026-04-14 03:05:00,000 [INFO] Cycle completed | trace=a1b2c3d4
2026-04-14 03:05:00,000 [INFO] Executed: BUY=2 SELL=1
2026-04-14 03:05:00,000 [INFO] Skip reasons summary:
2026-04-14 03:05:00,000 [INFO]   below_min_order_notional: 42 (주문 금액이 최소 주문 금액 (5,000 KRW) 미만)
2026-04-14 03:05:00,000 [INFO]   max_consecutive_buys_reached: 3 (연속 매수 횟수 제한 도달)
2026-04-14 03:05:00,000 [INFO]   non_actionable_signal: 125 (실행 가능한 신호 없음)
```

## 사용 예시

### 매수 성공 케이스
```
[BUY_OK] BTC/KRW | trend_following | size=0.00100000 | price=100,000,000 | notional=100,000KRW | reason=short_ma=100.1M, long_ma=99.5M | trace=e5f6g7h8
```

### 매수 거절 케이스 (최소 주문 금액 미만)
```
[BUY_SKIP] LINK/KRW | trend_following | below_min_order_notional | 주문 금액이 최소 주문 금액 (5,000 KRW) 미만 | notional=4,500KRW | min=5,000KRW | trace=x1y2z3
```

### 매수 거절 케이스 (연속 매수 제한)
```
[BUY_SKIP] DOGE/KRW | trend_following | max_consecutive_buys_reached | 연속 매수 횟수 제한 도달 | consecutive=3 | max=3 | trace=a1b2c3
```

### 매도 거절 케이스 (포지션 가치 미만)
```
[SELL_SKIP] VET/KRW | trend_following | below_min_order_notional | 주문 금액이 최소 주문 금액 (5,000 KRW) 미만 | pos_value=4,200KRW | min=5,000KRW | trace=d4e5f6
```

## 로그 필터링 예시

```bash
# 모든 스킵 로그만 보기
grep "\[.*_SKIP\]" logs/executor.log

# 특정 reason code 만 보기
grep "below_min_order_notional" logs/executor.log

# 성공한 매수만 보기
grep "\[BUY_OK\]" logs/executor.log

# 특정 심볼의 모든 로그 보기
grep "\[BTC/KRW\]" logs/executor.log

# 사이클 요약만 보기
grep "Skip reasons summary" -A 20 logs/executor.log
```

## 변경 파일

- `scripts/executor.py`: 메인 executor 루프, 로그 포맷팅 함수 추가
- `src/investment_bot/services/paper_broker.py`: rejection payload 에 메트릭 추가
- `src/investment_bot/services/auto_trade_service.py`: skip payload 정리

## 검증 결과

- 기존 11,404 줄 WARNING 로그 중 10,898 줄이 `below_min_order_notional` (95%)
- 새로운 `[BUY_SKIP]` 포맷으로 변경 시 운영자가 빠르게 이유 파악 가능
- 사이클 요약으로 한눈에 병목 원인 확인 가능

## 남은 개선 포인트

1. **Ops Summary Dashboard**: run_history.jsonl 기반 실시간 대시보드
2. **Alert Integration**: 특정 reason code 다발 시 Telegram 알림
3. **Near-miss Metrics**: threshold 근접 신호 별도 집계 (예: 4,800 KRW → 5,000 KRW 미만)
4. **Log Rotation**: executor.log 자동 분할 (일별/주별)
5. **Structured JSON Log**: 머신 파싱용 JSON 로그 병행
