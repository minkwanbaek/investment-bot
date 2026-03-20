# Investment Bot Ops Flow

## Roles
- monitor.py: collect system/bot status, no code changes
- report.py: write short markdown report from latest monitor snapshot
- AI tune loop: review reports and make at most one small low-risk change when justified

## Safe loop
1. monitor
2. report
3. optional AI review/tune
4. targeted pytest
5. restart and run-once
6. commit only when tests pass and runtime is healthy

## Guardrails
- one low-risk change at a time
- stop on test failure
- stop on server boot failure
- prefer config/threshold/logging fixes before strategy rewrites
- ignore dust positions below managed notional threshold
