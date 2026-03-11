from dataclasses import dataclass

from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.metrics_service import MetricsService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.trading_cycle import TradingCycleService


@dataclass
class BacktestService:
    market_data_service: MarketDataService
    paper_broker: PaperBroker
    trading_cycle_service: TradingCycleService
    metrics_service: MetricsService

    def run_replay(self, strategy_name: str, symbol: str, timeframe: str, window: int, steps: int) -> dict:
        if window < 1:
            raise ValueError("window must be >= 1")
        if steps < 1:
            raise ValueError("steps must be >= 1")

        replay_adapter = self.market_data_service.registry.get("replay")
        replay_adapter._cursor[(symbol, timeframe)] = window

        runs = []
        for _ in range(steps):
            candles = self.market_data_service.get_recent_candles(
                adapter_name="replay",
                symbol=symbol,
                timeframe=timeframe,
                limit=window,
            )
            if len(candles) < window:
                raise ValueError("not enough replay candles for requested window")
            result = self.trading_cycle_service.run(strategy_name=strategy_name, candles=candles)
            runs.append(
                {
                    "timestamp": candles[-1].timestamp,
                    "close": candles[-1].close,
                    "signal": result["signal"],
                    "review": result["review"],
                    "portfolio": result["portfolio"],
                }
            )
            self.market_data_service.advance_replay(symbol=symbol, timeframe=timeframe, steps=1)

        final_portfolio = self.paper_broker.portfolio_snapshot()
        metrics = self.metrics_service.summarize_backtest(
            starting_cash=self.paper_broker.starting_cash,
            runs=runs,
            final_portfolio=final_portfolio,
        )
        return {
            "strategy": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "window": window,
            "steps": steps,
            "runs": runs,
            "metrics": metrics,
            "final_portfolio": final_portfolio,
        }
