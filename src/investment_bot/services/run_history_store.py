from datetime import datetime, timezone

from investment_bot.services.ledger_store import LedgerStore


class RunHistoryStore:
    def __init__(self, path: str = "data/run_history.json"):
        self.store = LedgerStore(path)

    def load(self) -> list[dict]:
        return self.store.load() or []

    def append(self, kind: str, payload: dict) -> dict:
        history = self.load()
        entry = {
            "id": len(history) + 1,
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        history.append(entry)
        self.store.save(history)
        return entry

    def list_recent(self, limit: int = 20) -> list[dict]:
        history = self.load()
        return history[-limit:]

    def reset(self) -> dict:
        self.store.save([])
        return {"status": "cleared"}
