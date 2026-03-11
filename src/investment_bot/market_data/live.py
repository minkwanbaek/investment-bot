import httpx

from investment_bot.market_data.base import MarketDataAdapter
from investment_bot.models.market import Candle


class LiveMarketDataAdapter(MarketDataAdapter):
    name = "live"

    def __init__(self, base_url: str = "https://api.upbit.com"):
        self.base_url = base_url.rstrip("/")

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        market = self._to_upbit_market(symbol)
        unit = self._timeframe_to_minutes(timeframe)
        url = f"{self.base_url}/v1/candles/minutes/{unit}"
        response = httpx.get(
            url,
            params={"market": market, "count": limit},
            headers={"accept": "application/json"},
            timeout=10.0,
        )
        response.raise_for_status()
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
