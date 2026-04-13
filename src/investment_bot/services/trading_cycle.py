from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.paper_broker import PaperBroker
from investment_bot.strategies.registry import REGISTERED_STRATEGIES, list_enabled_strategies


@dataclass
class TradingCycleService:
    risk_controller: RiskController
    paper_broker: PaperBroker
    live_execution_service: LiveExecutionService | None = None
    live_mode: str = "paper"
    confirm_live_trading: bool = False

    def run(self, strategy_name: str, candles: Sequence[Candle]) -> dict:
        strategy_cls = REGISTERED_STRATEGIES.get(strategy_name)
        if strategy_cls is None:
            raise ValueError(f"unknown strategy: {strategy_name}")
        if strategy_name not in list_enabled_strategies():
            raise ValueError(f"strategy disabled by config: {strategy_name}")

        strategy = strategy_cls()
        signal: TradeSignal = strategy.generate_signal(candles)
        latest_price = candles[-1].close
        regime = self._classify_market(candles)

        if strategy_name == "trend_following" and regime["regime"] == "ranging":
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"market_regime=ranging; {signal.reason}",
            )

        review = self.risk_controller.review(
            signal,
            cash_balance=self.paper_broker.cash_balance,
            latest_price=latest_price,
        )
        self.paper_broker.mark_price(signal.symbol, latest_price)
        
        # live 모드일 때 live_execution_service 사용, 아니면 paper_broker 사용
        broker_result = None
        if review["approved"]:
            if self.live_mode == "live" and self.confirm_live_trading and self.live_execution_service:
                # live Execution
                broker_result = self.live_execution_service.submit_order(
                    symbol=signal.symbol,
                    side=signal.action,
                    price=latest_price,
                    volume=review["size_scale"],
                )
            else:
                # paper execution
                broker_result = self.paper_broker.submit(review, execution_price=latest_price)

        return {
            "strategy": strategy_name,
            "signal": signal.model_dump(),
            "review": review,
            "market_regime": regime,
            "broker_result": broker_result,
            "portfolio": self.paper_broker.portfolio_snapshot(),
        }

    def _classify_market(self, candles: Sequence[Candle]) -> dict:
        closes = [c.close for c in candles]
        if len(closes) < 8:
            return {"regime": "unknown", "reason": "insufficient_data"}
        short_ma = mean(closes[-3:])
        long_ma = mean(closes[-8:])
        latest = closes[-1]
        prev = closes[-2]
        trend_gap_pct = ((short_ma - long_ma) / long_ma) if long_ma else 0.0
        range_pct = ((max(closes[-8:]) - min(closes[-8:])) / min(closes[-8:])) if min(closes[-8:]) else 0.0
        momentum_pct = ((latest - prev) / prev) if prev else 0.0
        if range_pct < 0.01 or abs(trend_gap_pct) < 0.0015:
            regime = "ranging"
        elif trend_gap_pct > 0 and momentum_pct > 0:
            regime = "uptrend"
        elif trend_gap_pct < 0 and momentum_pct < 0:
            regime = "downtrend"
        else:
            regime = "mixed"
        return {
            "regime": regime,
            "trend_gap_pct": round(trend_gap_pct, 6),
            "range_pct": round(range_pct, 6),
            "momentum_pct": round(momentum_pct, 6),
        }
