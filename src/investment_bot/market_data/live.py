import threading
import time

import httpx

from investment_bot.market_data.base import MarketDataAdapter
from investment_bot.models.market import Candle


class LiveMarketDataAdapter(MarketDataAdapter):
    name = "live"

    def __init__(self, base_url: str = "https://api.upbit.com", cache_ttl_seconds: float = 55.0, min_request_gap_seconds: float = 0.15):
        self.base_url = base_url.rstrip("/")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.min_request_gap_seconds = min_request_gap_seconds
        self._cache: dict[tuple[str, str, int], tuple[float, list[Candle]]] = {}
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        cache_key = (symbol, timeframe, limit)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and (now - cached[0]) <= self.cache_ttl_seconds:
                return list(cached[1])
            wait_seconds = self.min_request_gap_seconds - (now - self._last_request_at)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        market = self._to_upbit_market(symbol)
        unit = self._timeframe_to_minutes(timeframe)
        url = f"{self.base_url}/v1/candles/minutes/{unit}"
        try:
            response = httpx.get(
                url,
                params={"market": market, "count": limit},
                headers={"accept": "application/json"},
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                with self._lock:
                    stale = self._cache.get(cache_key)
                    if stale:
                        return list(stale[1])
            raise
        rows = response.json()
        candles = [
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=row["opening_price"],
                high=row["high_price"],
                low=row["low_price"],
                close=row["trade_price"],
                volume=row["candle_acc_trade_volume"],
                timestamp=row["candle_date_time_utc"],
            )
            for row in reversed(rows)
        ]
        with self._lock:
            self._last_request_at = time.monotonic()
            self._cache[cache_key] = (self._last_request_at, candles)
        return candles

    def _to_upbit_market(self, symbol: str) -> str:
        if "/" not in symbol:
            raise ValueError(f"unsupported symbol format: {symbol}")
        base, quote = symbol.split("/", 1)
        return f"{quote}-{base}"

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        mapping = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "10m": 10,
            "15m": 15,
            "30m": 30,
            "60m": 60,
            "1h": 60,
            "240m": 240,
            "4h": 240,
        }
        if timeframe not in mapping:
            raise ValueError(f"unsupported live timeframe: {timeframe}")
        return mapping[timeframe]
