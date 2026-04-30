# Ralph Loop Dev/PRD Harness

## Goal
Make Ralph operate in `dev` while promotion to `prd` happens through git.

## Files
- `config/dev.yml`: Ralph loop experiment profile
- `config/prd.yml`: production profile
- `ops/ralph/RUN_CONTEXT.md`: stable loop rules
- `ops/ralph/CURRENT_STRATEGY.md`: current strategy snapshot
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

## Ralph loop shape
1. Read `ops/ralph/*.md`
2. Make exactly one modification
3. Run the relevant backtest/verification
4. Update `BACKTEST_SUMMARY.md`
5. Append `RALPH_LOG.md`
6. Repeat

## Promotion
- Ralph works in `dev`
- candidate changes are validated in `dev`
- approved changes move to `prd` through git


## Ralph execution
```bash
bash scripts/ops/run_ralph_loop.sh 10
```

Optional model override:
```bash
RALPH_CODEX_MODEL=gpt-5.4 bash scripts/ops/run_ralph_loop.sh 10
```
