from dataclasses import dataclass
from pathlib import Path
import json


DEFAULT_DEPLOY_CHECKS = [
    'backtest_completed',
    'out_of_sample_checked',
    'walkforward_checked',
    'paper_trading_checked',
    'fees_and_slippage_checked',
    'max_loss_checked',
    'feature_flag_ready',
    'rollback_ready',
]


@dataclass
class LiveDeployChecklistService:
    def build(self, version: str, completed: dict[str, bool] | None = None, approver: str | None = None) -> dict:
        completed = completed or {}
        items = [{
            'name': item,
            'completed': bool(completed.get(item, False)),
        } for item in DEFAULT_DEPLOY_CHECKS]
        return {
            'deploy_candidate_version': version,
            'items': items,
            'all_completed': all(item['completed'] for item in items),
            'approver': approver,
        }

    def save(self, path: str, payload: dict) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    def load(self, path: str) -> dict | None:
        p = Path(path)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding='utf-8'))
