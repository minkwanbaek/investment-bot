from dataclasses import dataclass
from typing import Sequence

from investment_bot.core.settings import get_settings

from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.market_regime_classifier import MarketRegimeClassifier
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
        signal: TradeSignal = strategy.generate_signal(candles, broker=self.paper_broker)
        latest_price = candles[-1].close
        market_info = MarketRegimeClassifier().classify(candles)

        # Regime names are now unified to enum values (sideways, trend_up, trend_down, uncertain)
        # No legacy mapping needed
        market_regime = market_info.get("regime", "uncertain")
        
        # Near-miss observability for trend_following
        signal = self._enrich_near_miss(signal, market_info)

        route_block_reason = self._route_block_reason(strategy_name=strategy_name, market_info=market_info)
        force_exit = bool(getattr(signal, "meta", {}).get("force_exit", False))
        if not force_exit and self._should_block_for_sideways(strategy_name=strategy_name, market_info=market_info):
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"market_regime=sideways; sideway_filter_blocked; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason="sideway_filter_blocked"),
            )
        elif not force_exit and route_block_reason:
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"{route_block_reason}; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason=route_block_reason),
            )
        elif not force_exit and strategy_name == "trend_following" and market_info.get("regime") == "sideways":
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"market_regime=sideways; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason="market_regime_sideways_hold"),
            )

        signal.meta = {
            **getattr(signal, "meta", {}),
            "market_regime": market_regime,
            "volatility_state": market_info.get("volatility_state", "normal"),
            "higher_tf_bias": market_info.get("higher_tf_bias", "neutral"),
            "losing_streak": getattr(self.paper_broker, "losing_streak", 0),
        }
        review = self.risk_controller.review(
            signal,
            cash_balance=self.paper_broker.cash_balance,
            latest_price=latest_price,
        )
        # Attach market context to review for downstream use (e.g. trade logging)
        review["market_regime"] = market_regime
        review["volatility_state"] = market_info.get("volatility_state", "normal")
        review["higher_tf_bias"] = market_info.get("higher_tf_bias", "neutral")

        self.paper_broker.mark_price(signal.symbol, latest_price)
        if review["approved"] and review.get("force_exit") and review["action"] == "sell":
            position_qty = float(self.paper_broker.positions.get(signal.symbol, {}).get("quantity", 0.0) or 0.0)
            review["size_scale"] = position_qty
            review["target_notional"] = round(position_qty * latest_price, 4)

        broker_result = self.paper_broker.submit(review, execution_price=latest_price) if review["approved"] else None

        return {
            "strategy": strategy_name,
            "signal": signal.model_dump(),
            "review": review,
            "market_regime": market_regime,
            "volatility_state": market_info.get("volatility_state", "normal"),
            "higher_tf_bias": market_info.get("higher_tf_bias", "neutral"),
            "broker_result": broker_result,
            "portfolio": self.paper_broker.portfolio_snapshot(),
        }

    def _route_block_reason(self, strategy_name: str, market_info: dict) -> str | None:
        settings = get_settings()
        regime = market_info.get("regime")
        if settings.uncertain_block_enabled and regime in {"mixed", "unknown"}:
            return "uncertain_regime_blocked"
        if strategy_name == "trend_following" and regime not in set(settings.trend_strategy_allowed_regimes):
            return "trend_strategy_route_blocked"
        if strategy_name == "mean_reversion" and regime not in set(settings.range_strategy_allowed_regimes):
            return "range_strategy_route_blocked"
        return None

    def _should_block_for_sideways(self, strategy_name: str, market_info: dict) -> bool:
        settings = get_settings()
        if not settings.sideway_filter_enabled:
            return False
        if strategy_name != "trend_following":
            return False
        if market_info.get("regime") != "sideways":
            return False
        if settings.sideway_filter_volatility_block_on_low and market_info.get("volatility_state") == "low":
            return True
        if abs(float(market_info.get("trend_gap_pct", 0.0) or 0.0)) < settings.sideway_filter_trend_gap_threshold:
            return True
        if float(market_info.get("range_pct", 0.0) or 0.0) < settings.sideway_filter_range_threshold:
            return True
        return False

    def _enrich_near_miss(self, signal: TradeSignal, market_info: dict) -> TradeSignal:
        """Add near-miss observability for trend_following hold signals."""
        if signal.strategy_name != "trend_following":
            return signal

        meta = getattr(signal, "meta", {})
        trend_gap_pct = float(meta.get("trend_gap_pct", 0.0) or 0.0)
        momentum_pct = float(meta.get("momentum_pct", 0.0) or 0.0)
        buy_threshold_pct = float(meta.get("buy_threshold_pct", 0.0015) or 0.0015)

        if signal.action == "hold":
            if 0.0 <= trend_gap_pct < buy_threshold_pct and momentum_pct > 0:
                meta = self._mark_near_miss_stage(meta, category="threshold", stage="strategy_signal")
            elif trend_gap_pct >= buy_threshold_pct and momentum_pct <= 0:
                meta = self._mark_near_miss_stage(
                    meta,
                    category="confirm_fail",
                    stage="strategy_signal",
                    block_reason="momentum_not_positive",
                )

        signal.meta = meta
        return signal

    def _mark_near_miss_stage(
        self,
        meta: dict,
        *,
        category: str,
        stage: str,
        block_reason: str | None = None,
    ) -> dict:
        if "trend_gap_pct" not in meta or "momentum_pct" not in meta or "buy_threshold_pct" not in meta:
            return meta

        next_meta = {**meta}
        if not next_meta.get("is_near_miss"):
            next_meta.update({"is_near_miss": True, "category": category, "stage": stage})
        if block_reason:
            existing = next_meta.get("block_reason")
            if existing and existing != block_reason:
                next_meta["block_reason"] = f"{existing},{block_reason}"
            else:
                next_meta["block_reason"] = block_reason
        return next_meta

    def _append_near_miss_block_reason(self, meta: dict, *, stage: str, block_reason: str) -> dict:
        if not meta.get("is_near_miss"):
            return meta

        next_meta = {**meta, "stage": stage}
        existing = next_meta.get("block_reason")
        if existing and existing != block_reason:
            next_meta["block_reason"] = f"{existing},{block_reason}"
        else:
            next_meta["block_reason"] = block_reason
        return next_meta

