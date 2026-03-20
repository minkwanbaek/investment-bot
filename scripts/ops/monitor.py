#!/usr/bin/env python3
import json, urllib.request, pathlib, datetime
from collections import Counter

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OUT = BASE / 'ops'
OUT.mkdir(parents=True, exist_ok=True)
RUN_HISTORY = BASE / 'data' / 'run_history.json'
TS = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode())

health = fetch('http://localhost:8899/health')
status = fetch('http://localhost:8899/auto-trade/status')
config = fetch('http://localhost:8899/config')
run_history = json.loads(RUN_HISTORY.read_text()) if RUN_HISTORY.exists() else []
recent = run_history[-80:]
skip_reasons = Counter()
kind_counts = Counter()
for row in recent:
    kind = row.get('kind', 'unknown')
    kind_counts[kind] += 1
    payload = row.get('payload', {}) or {}
    if kind == 'auto_trade_skip':
        skip_reasons[payload.get('reason', 'unknown')] += 1

snapshot = {
    'timestamp': TS,
    'health': health,
    'auto_trade_status': status,
    'config_summary': {
        'symbols': config.get('symbols'),
        'strategy': config.get('auto_trade_strategy_name'),
        'limit': config.get('auto_trade_limit'),
        'stop_loss_pct': config.get('auto_trade_stop_loss_pct'),
        'partial_take_profit_pct': config.get('auto_trade_partial_take_profit_pct'),
        'trailing_stop_pct': config.get('auto_trade_trailing_stop_pct'),
        'max_total_exposure_pct': config.get('auto_trade_max_total_exposure_pct'),
        'min_managed_position_notional': config.get('auto_trade_min_managed_position_notional'),
    },
    'recent_kind_counts': dict(kind_counts),
    'recent_skip_reasons': dict(skip_reasons),
}
(OUT / 'latest_monitor.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
with (OUT / 'monitor_history.jsonl').open('a', encoding='utf-8') as f:
    f.write(json.dumps(snapshot, ensure_ascii=False) + '\n')
print(json.dumps(snapshot, ensure_ascii=False, indent=2))
