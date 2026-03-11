from dataclasses import dataclass

from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.trading_cycle import TradingCycleService


@dataclass
class SemiLiveService:
    market_data_service: MarketDataService
    trading_cycle_service: TradingCycleService
    run_history_service: RunHistoryService

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5) -> dict:
        candles = self.market_data_service.get_recent_candles(
            adapter_name="live",
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        result = {
            "adapter": "live",
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            **self.trading_cycle_service.run(strategy_name=strategy_name, candles=candles),
        }
        self.run_history_service.record(kind="semi_live_cycle", payload=result)
        return result
