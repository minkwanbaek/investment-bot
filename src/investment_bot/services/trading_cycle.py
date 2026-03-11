from dataclasses import dataclass
from typing import Sequence

from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.strategies.registry import REGISTERED_STRATEGIES, list_enabled_strategies


@dataclass
class TradingCycleService:
    risk_controller: RiskController
    paper_broker: PaperBroker

    def run(self, strategy_name: str, candles: Sequence[Candle]) -> dict:
        strategy_cls = REGISTERED_STRATEGIES.get(strategy_name)
        if strategy_cls is None:
            raise ValueError(f"unknown strategy: {strategy_name}")
        if strategy_name not in list_enabled_strategies():
            raise ValueError(f"strategy disabled by config: {strategy_name}")

        strategy = strategy_cls()
        signal: TradeSignal = strategy.generate_signal(candles)
        latest_price = candles[-1].close
        review = self.risk_controller.review(
            signal,
            cash_balance=self.paper_broker.cash_balance,
            latest_price=latest_price,
        )
        self.paper_broker.mark_price(signal.symbol, latest_price)
        broker_result = self.paper_broker.submit(review, execution_price=latest_price) if review["approved"] else None

        return {
            "strategy": strategy_name,
            "signal": signal.model_dump(),
            "review": review,
            "broker_result": broker_result,
            "portfolio": self.paper_broker.portfolio_snapshot(),
        }
