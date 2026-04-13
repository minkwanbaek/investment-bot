#!/usr/bin/env python3
import json, pathlib, datetime
from collections import Counter

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OPS = BASE / 'ops'
RUN_HISTORY = BASE / 'data' / 'run_history.json'
KST = datetime.timezone(datetime.timedelta(hours=9), name='KST')


def fmt_kst(dt: datetime.datetime) -> str:
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M KST')


now_utc = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
now_kst = fmt_kst(now_utc)
week_ago_kst = fmt_kst(now_utc - datetime.timedelta(days=7))
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
lines.append('# 투자봇 주간 리포트\n\n')
lines.append(f'_집계 기간: {week_ago_kst} → {now_kst}_\n\n')
lines.append(f'- 생성시각: `{now_kst}`\n')
lines.append(f'- 최근 실행 종류 집계: `{dict(kind_counts)}`\n')
lines.append(f'- 최근 스킵 사유 집계: `{dict(skip_reasons)}`\n')
if (OPS / 'latest_tune.json').exists():
    tune = json.loads((OPS / 'latest_tune.json').read_text())
    lines.append(f'- 최근 튜닝 테스트 통과: `{tune.get("pytest_ok")}`\n')
    lines.append(f'- 최근 튜닝 제안: `{tune.get("recommendations")}`\n')
(OPS / 'weekly_report.md').write_text(''.join(lines), encoding='utf-8')
print(''.join(lines))
