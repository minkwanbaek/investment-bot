from dataclasses import dataclass

from investment_bot.services.run_history_store import RunHistoryStore


@dataclass
class RunHistoryService:
    store: RunHistoryStore

    def record(self, kind: str, payload: dict) -> dict:
        return self.store.append(kind=kind, payload=payload)

    def list_recent(self, limit: int = 20) -> list[dict]:
        return self.store.list_recent(limit=limit)

    def reset(self) -> dict:
        return self.store.reset()
