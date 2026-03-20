#!/usr/bin/env python3
import json, pathlib, subprocess, datetime

BASE = pathlib.Path('/home/javajinx7/.openclaw/workspace/projects/investment-bot')
OPS = BASE / 'ops'
OPS.mkdir(parents=True, exist_ok=True)
now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
monitor = json.loads((OPS / 'latest_monitor.json').read_text()) if (OPS / 'latest_monitor.json').exists() else {}
recommendations = []
skips = monitor.get('recent_skip_reasons', {})
if skips.get('preview_blocked', 0) > 0:
    recommendations.append('dust or minimum-order review needed')
if skips.get('non_actionable_signal', 0) > 10:
    recommendations.append('regime filter may be too strict or market is inactive')
if skips.get('below_meaningful_order_notional', 0) > 10:
    recommendations.append('meaningful_order_notional may be too high for current cash regime')

pytest_cmd = "source .venv/bin/activate && pytest -q tests/test_auto_trade_service.py tests/test_strategies.py tests/test_backtest.py"
proc = subprocess.run(['bash', '-lc', pytest_cmd], cwd=str(BASE), capture_output=True, text=True)
result = {
    'timestamp': now,
    'pytest_ok': proc.returncode == 0,
    'pytest_rc': proc.returncode,
    'recommendations': recommendations,
    'stdout_tail': proc.stdout[-4000:],
    'stderr_tail': proc.stderr[-4000:],
}
(OPS / 'latest_tune.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
with (OPS / 'tune_history.jsonl').open('a', encoding='utf-8') as f:
    f.write(json.dumps(result, ensure_ascii=False) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
