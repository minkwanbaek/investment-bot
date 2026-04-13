import json
import os
import threading
from pathlib import Path
from typing import Any

from investment_bot.models.trade_log import TradeLogSchema


REQUIRED_TRADE_LOG_ENTRY_FIELDS = (
    "trade_id",
    "symbol",
    "side",
    "entry_time",
    "entry_price",
    "quantity",
)


class LedgerStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupted file - return empty ledger
            return {"cash_balance": 10000000.0, "starting_cash": 10000000.0, "orders": [], "positions": {}, "trade_logs": []}

    def save(self, payload: dict[str, Any]) -> None:
        # Atomic write with lock to prevent race conditions
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix('.json.tmp')
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(tmp_path, self.path)

    def _validate_trade_log_entry(self, entry: TradeLogSchema) -> None:
        payload = entry.model_dump(mode="python")
        missing = []
        for field in REQUIRED_TRADE_LOG_ENTRY_FIELDS:
            value = payload.get(field)
            if value is None:
                missing.append(field)
            elif isinstance(value, str) and not value.strip():
                missing.append(field)
        if missing:
            raise ValueError(f"missing required trade log fields: {', '.join(missing)}")

    def append_trade_log_entry(self, entry: TradeLogSchema) -> None:
        self._validate_trade_log_entry(entry)
        payload = self.load() or {}
        trade_logs = list(payload.get("trade_logs", []))
        trade_logs.append(entry.model_dump(mode="json"))
        payload["trade_logs"] = trade_logs
        self.save(payload)

    def update_latest_open_trade_log(self, symbol: str, side: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        payload = self.load() or {}
        trade_logs = list(payload.get("trade_logs", []))
        for index in range(len(trade_logs) - 1, -1, -1):
            entry = trade_logs[index]
            if entry.get("symbol") != symbol:
                continue
            if entry.get("side") != side:
                continue
            if entry.get("exit_time") is not None:
                continue
            updated = {**entry, **updates}
            trade_logs[index] = updated
            payload["trade_logs"] = trade_logs
            self.save(payload)
            return updated
        return None
