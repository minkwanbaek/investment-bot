from dataclasses import dataclass

from investment_bot.core.settings import get_settings
from investment_bot.services.market_data_service import MarketDataService
from investment_bot.services.metrics_service import MetricsService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.services.trading_cycle import TradingCycleService


@dataclass
class BacktestService:
    def run_walkforward(self, strategy_name: str, symbol: str, timeframe: str, window: int, train_steps: int, test_steps: int, segments: int) -> dict:
        results = []
        for segment in range(segments):
            result = self.run_standard_backtest(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                window=window,
                steps=test_steps,
            )
            results.append({
                'segment': segment + 1,
                'train_steps': train_steps,
                'test_steps': test_steps,
                'metrics': result['metrics'],
                'config_snapshot': result['config_snapshot'],
            })
        return {
            'strategy_name': strategy_name,
            'symbol': symbol,
            'timeframe': timeframe,
            'window': window,
            'segments': segments,
            'results': results,
        }

    market_data_service: MarketDataService
    paper_broker: PaperBroker
    trading_cycle_service: TradingCycleService
    metrics_service: MetricsService

    def run_standard_backtest(self, strategy_name: str, symbol: str, timeframe: str, window: int, steps: int) -> dict:
        settings = get_settings()
        result = self.run_replay(strategy_name=strategy_name, symbol=symbol, timeframe=timeframe, window=window, steps=steps)
        return {
            "run_id": f"{strategy_name}:{symbol}:{timeframe}:{window}:{steps}",
            "config_snapshot": {
                "strategy_name": strategy_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "window": window,
                "steps": steps,
                "fee_model": settings.standard_backtest_fee_model,
                "slippage_model": settings.standard_backtest_slippage_model,
            },
            **result,
        }

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
