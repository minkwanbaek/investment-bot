[RUN_CONTEXT]
mission: 업비트 자동매매 전략의 절대 수익률을 높일 가능성이 가장 큰 다음 수정안 1개를 찾고 검증한다.

environment_split:
- dev: 랄프가 수정, 백테스트, 시뮬레이션, 로그를 수행하는 실험 환경
- prd: 승인된 전략만 운영하는 실제 주문 환경

rules:
- 한 번에 한 수정만 적용
- 수정 후 즉시 백테스트 또는 관련 검증을 실행
- 결과는 BACKTEST_SUMMARY.md 에 구조화해서 기록
- 루프 로그는 RALPH_LOG.md 에 append
- 출력은 수정안 한 줄 또는 <promise>STUCK</promise> 만 사용
- 턴 단위 판정은 최종 수익 확정이 아니라 candidate 판정이다

evaluation_target:
- 최종 목표: 절대 수익률 극대화
- 턴 단위 verdict: promising | unclear | reject

execution_constraints:
- upbit authenticated markets available
- fee must be included
- slippage must be included
- liquidity must be considered
- minimum order constraints must be considered
- dev changes promote to prd through git, not by ad-hoc copying

files:
- read: RUN_CONTEXT.md, CURRENT_STRATEGY.md, BACKTEST_SUMMARY.md, RALPH_LOG.md
- update: CURRENT_STRATEGY.md, BACKTEST_SUMMARY.md
- append: RALPH_LOG.md

[/RUN_CONTEXT]
