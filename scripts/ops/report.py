#!/usr/bin/env python3
import json, pathlib, datetime

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OPS = BASE / 'ops'
monitor = json.loads((OPS / 'latest_monitor.json').read_text()) if (OPS / 'latest_monitor.json').exists() else {}
now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
lines = []
lines.append(f'# Investment Bot Ops Report\n\n')
lines.append(f'- generated_at: `{now}`\n')
if monitor:
    lines.append(f'- health: `{monitor.get("health", {}).get("status")}`\n')
    ats = monitor.get('auto_trade_status', {})
    lines.append(f'- auto_trade_active: `{ats.get("active")}`\n')
    profile = ats.get('profile', {})
    lines.append(f'- symbols: `{profile.get("symbols") or monitor.get("config_summary", {}).get("symbols")}`\n')
    lines.append(f'- strategy: `{profile.get("strategy_name")}`\n')
    lines.append(f'- skip_reasons: `{monitor.get("recent_skip_reasons", {})}`\n')
    lines.append(f'- kind_counts: `{monitor.get("recent_kind_counts", {})}`\n')
(OPS / 'latest_report.md').write_text(''.join(lines), encoding='utf-8')
print(''.join(lines))
