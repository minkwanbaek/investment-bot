#!/usr/bin/env python3
import json, pathlib, datetime
from collections import Counter

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OPS = BASE / 'ops'
RUN_HISTORY = BASE / 'data' / 'run_history.json'
now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
run_history = json.loads(RUN_HISTORY.read_text()) if RUN_HISTORY.exists() else []
recent = run_history[-300:]
kind_counts = Counter()
skip_reasons = Counter()
for row in recent:
    kind = row.get('kind', 'unknown')
    kind_counts[kind] += 1
    if kind == 'auto_trade_skip':
        skip_reasons[(row.get('payload') or {}).get('reason', 'unknown')] += 1
lines = []
lines.append(f'# Weekly Investment Bot Report\n\n')
lines.append(f'- generated_at: `{now}`\n')
lines.append(f'- recent_kind_counts: `{dict(kind_counts)}`\n')
lines.append(f'- recent_skip_reasons: `{dict(skip_reasons)}`\n')
if (OPS / 'latest_tune.json').exists():
    tune = json.loads((OPS / 'latest_tune.json').read_text())
    lines.append(f'- latest_tune_pytest_ok: `{tune.get("pytest_ok")}`\n')
    lines.append(f'- latest_tune_recommendations: `{tune.get("recommendations")}`\n')
(OPS / 'weekly_report.md').write_text(''.join(lines), encoding='utf-8')
print(''.join(lines))
