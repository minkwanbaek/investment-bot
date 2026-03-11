from investment_bot.models.market import Candle
from investment_bot.services.ledger_store import LedgerStore


class CandleStore:
    def __init__(self, path: str):
        self.store = LedgerStore(path)

    def load(self) -> dict[str, list[dict]]:
        return self.store.load() or {}

    def append(self, symbol: str, timeframe: str, candles: list[Candle]) -> dict:
        payload = self.load()
        key = f"{symbol}|{timeframe}"
        existing = payload.get(key, [])
        merged = existing + [candle.model_dump() for candle in candles]

        deduped_by_timestamp: dict[str, dict] = {}
        for candle in merged:
            deduped_by_timestamp[candle["timestamp"]] = candle

        ordered = [deduped_by_timestamp[timestamp] for timestamp in sorted(deduped_by_timestamp.keys())]
        payload[key] = ordered
        self.store.save(payload)
        return {"key": key, "count": len(ordered)}

    def reset(self) -> dict:
        self.store.save({})
        return {"status": "cleared"}

    def export_state(self) -> dict:
        payload = self.load()
        return {
            "keys": sorted(payload.keys()),
            "total_series": len(payload),
            "payload": payload,
        }

    def list_recent(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        payload = self.load()
        key = f"{symbol}|{timeframe}"
        return [Candle.model_validate(item) for item in payload.get(key, [])[-limit:]]
