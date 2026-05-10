# Ralph Loop Dev/PRD Harness

## Goal
Make Ralph operate in `dev` while promotion to `prd` happens through git.

## Files
- `config/dev.yml`: Ralph loop experiment profile
- `config/prd.yml`: production profile
- `ops/ralph/RUN_CONTEXT.md`: stable loop rules
- `ops/ralph/CURRENT_STRATEGY.md`: Ralph dev-loop strategy snapshot generated from the current loop config, not the production source of truth
- `ops/ralph/BACKTEST_SUMMARY.md`: latest backtest candidate summary
- `ops/ralph/RALPH_LOG.md`: append-only loop log

## Refresh loop context
```bash
python scripts/ops/refresh_ralph_context.py --config config/dev.yml
```

## Run environments
```bash
bash scripts/ops/run_dev.sh
bash scripts/ops/run_prd.sh
```

## Production operations policy
- Keep production startup simple: `scripts/ops/run_prd.sh` is the canonical PRD entrypoint.
- `scripts/ops/run_prd.sh` is responsible for pinning `config/prd.yml` and the default bind target `127.0.0.1:8000`.
- Operator checks should use the same runtime surface: `GET /health`, `GET /auto-trade/status`, and `GET /config` on that bound address.
- `scripts/ops/monitor.py` reads that same operator surface and should only diverge when `INVESTMENT_BOT_HOST` / `INVESTMENT_BOT_PORT` are intentionally overridden.
- If host/port must change, override with `INVESTMENT_BOT_HOST` / `INVESTMENT_BOT_PORT` so startup and monitoring stay aligned.
- Production truth comes from `config/prd.yml` plus the live operator endpoints above. `ops/ralph/CURRENT_STRATEGY.md` remains a dev-loop working snapshot for Ralph context only.

## Ralph loop shape
1. Read `ops/ralph/*.md`
2. Make exactly one modification
3. Run the relevant backtest/verification
4. Update `BACKTEST_SUMMARY.md`
5. Append `RALPH_LOG.md`
6. Repeat

## Verdict philosophy
- The loop should not reward one-off local wins.
- A good candidate is not just a high-return candidate; it is a lower-regret candidate that still looks useful after costs, slippage, minimum-order constraints, and mild stress.
- `promising` means realized improvement with enough realism to justify more trust.
- `unclear` means maybe useful, but still too narrow, too structural, too brittle, or too mixed.
- `reject` means the candidate worsens deployability, realized outcome, or robustness.

## Preferred evidence
- Realized replay/backtest improvement over baseline
- Better drawdown-adjusted outcome, not just larger nominal size
- Evidence that survives mild stress assumptions
- More than a pure boundary relaxation or pure aggression increase

## Promotion
- Ralph works in `dev`
- candidate changes are validated in `dev`
- approved changes move to `prd` through git


## Ralph execution
```bash
bash scripts/ops/run_ralph_loop.sh 10
```

Continuous mode:
```bash
bash scripts/ops/run_ralph_loop.sh infinite
```

Optional model override:
```bash
RALPH_CODEX_MODEL=gpt-5.4 bash scripts/ops/run_ralph_loop.sh 10
```

Useful env knobs:
```bash
RALPH_ITERATION_TIMEOUT_SECONDS=420
RALPH_RECENT_LOG_COUNT=8
```
