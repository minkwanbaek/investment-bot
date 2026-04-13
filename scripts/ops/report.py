#!/usr/bin/env python3
import json, pathlib, datetime

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OPS = BASE / 'ops'
monitor = json.loads((OPS / 'latest_monitor.json').read_text()) if (OPS / 'latest_monitor.json').exists() else {}
KST = datetime.timezone(datetime.timedelta(hours=9), name='KST')
now_kst = datetime.datetime.now(datetime.timezone.utc).astimezone(KST).replace(microsecond=0).strftime('%Y-%m-%d %H:%M KST')
lines = []
lines.append('# 투자봇 운영 리포트\n\n')
lines.append(f'- 생성시각: `{now_kst}`\n')
if monitor:
    lines.append(f'- 상태: `{monitor.get("health", {}).get("status")}`\n')
    ats = monitor.get('auto_trade_status', {})
    lines.append(f'- 자동매매 활성화: `{ats.get("active")}`\n')
    profile = ats.get('profile', {})
    lines.append(f'- 대상 심볼: `{profile.get("symbols") or monitor.get("config_summary", {}).get("symbols")}`\n')
    lines.append(f'- 전략: `{profile.get("strategy_name")}`\n')
    lines.append(f'- 최근 스킵 사유: `{monitor.get("recent_skip_reasons", {})}`\n')
    lines.append(f'- 최근 실행 종류 집계: `{monitor.get("recent_kind_counts", {})}`\n')
(OPS / 'latest_report.md').write_text(''.join(lines), encoding='utf-8')
print(''.join(lines))
