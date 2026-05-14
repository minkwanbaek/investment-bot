from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from investment_bot.core.settings import get_settings
from investment_bot.core.trading_policy import build_trading_policy

from investment_bot.features.exit.application.evaluator import ExitEvaluator
from investment_bot.features.exit.domain.models import MarketSnapshot, PositionSnapshot
from investment_bot.models.market import Candle
from investment_bot.models.signal import TradeSignal
from investment_bot.risk.controller import RiskController
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.market_regime_classifier import MarketRegimeClassifier
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
        signal: TradeSignal = strategy.generate_signal(candles, broker=self.paper_broker)
        latest_price = candles[-1].close
        cycle_time = self._parse_candle_timestamp(candles[-1].timestamp)
        policy = build_trading_policy(get_settings())
        market_info = policy.normalize_market_info(MarketRegimeClassifier().classify(candles))
        market_regime = market_info.get("regime", "uncertain")
        
        # Near-miss observability for trend_following
        signal = self._enrich_near_miss(signal, market_info)
        signal = self._resolve_exit_signal(
            strategy_name=strategy_name,
            signal=signal,
            latest_price=latest_price,
            cycle_time=cycle_time,
        )

        try:
            route_block_reason = self._route_block_reason(strategy_name=strategy_name, market_info=market_info, action=signal.action)
        except TypeError:
            route_block_reason = self._route_block_reason(strategy_name=strategy_name, market_info=market_info)
        force_exit = bool(getattr(signal, "meta", {}).get("force_exit", False))
        policy_snapshot = policy.snapshot
        sideways_allowed_for_trend = (
            strategy_name == "trend_following"
            and market_info.get("regime") == "sideways"
            and "sideways" in set(policy_snapshot.trend_strategy_allowed_regimes)
        )

        # Check for sideways exception pass before blocking
        exception_pass = None
        if not force_exit and strategy_name == "trend_following" and market_info.get("regime") == "sideways":
            exception_pass = self._check_sideways_exception_pass(strategy_name=strategy_name, market_info=market_info)
        
        if not force_exit and self._should_block_for_sideways(strategy_name=strategy_name, market_info=market_info) and not exception_pass:
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"market_regime=sideways; sideway_filter_blocked; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason="sideway_filter_blocked"),
            )
        elif not force_exit and route_block_reason and not exception_pass:
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"{route_block_reason}; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason=route_block_reason),
            )
        elif not force_exit and strategy_name == "trend_following" and market_info.get("regime") == "sideways" and not exception_pass and not sideways_allowed_for_trend:
            signal = TradeSignal(
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                action="hold",
                confidence=signal.confidence,
                reason=f"market_regime=sideways; {signal.reason}",
                meta=self._append_near_miss_block_reason(getattr(signal, "meta", {}), stage="route_filter", block_reason="market_regime_sideways_hold"),
            )
        elif exception_pass and signal.action != "hold":
            # Exception pass applied - log it for observability only when it actually preserves
            # an actionable strategy signal instead of annotating an already-held signal.
            signal.meta = {
                **getattr(signal, "meta", {}),
                "route_exception_pass": True,
                "exception_reason": exception_pass,
            }

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

        # Handle force_exit and live/paper execution
        broker_result = None
        if review["approved"]:
            if review["action"] == "sell":
                position_qty = float(self.paper_broker.positions.get(signal.symbol, {}).get("quantity", 0.0) or 0.0)
                exit_size = getattr(signal, "meta", {}).get("exit_size_scale") if review.get("force_exit") else position_qty
                review["size_scale"] = min(float(exit_size or position_qty), position_qty)
                review["target_notional"] = round(review["size_scale"] * latest_price, 4)

            # Live or paper execution
            if self.live_mode == "live" and self.confirm_live_trading and self.live_execution_service:
                broker_result = self.live_execution_service.submit_order(
                    symbol=signal.symbol,
                    side=signal.action,
                    price=latest_price,
                    volume=review["size_scale"],
                )
            else:
                broker_result = self.paper_broker.submit(review, execution_price=latest_price, now=cycle_time)

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

    def _resolve_exit_signal(self, strategy_name: str, signal: TradeSignal, latest_price: float, cycle_time: datetime | None) -> TradeSignal:
        strategy_exit_signal = self._apply_strategy_exit(
            strategy_name=strategy_name,
            signal=signal,
            latest_price=latest_price,
            cycle_time=cycle_time,
        )
        broker_exit_signal = self._apply_broker_exit(
            signal=strategy_exit_signal,
            latest_price=latest_price,
            cycle_time=cycle_time,
        )
        return self._choose_preferred_exit_signal(
            base_signal=signal,
            candidates=[strategy_exit_signal, broker_exit_signal],
        )

    def _apply_strategy_exit(self, strategy_name: str, signal: TradeSignal, latest_price: float, cycle_time: datetime | None) -> TradeSignal:
        if strategy_name not in {"trend_following", "mean_reversion", "dca"}:
            return signal

        position = self.paper_broker.positions.get(signal.symbol, {})
        position_qty = float(position.get("quantity", 0.0) or 0.0)
        if position_qty <= 0:
            return signal

        opened_at = position.get("opened_at")
        if isinstance(opened_at, str):
            opened_at = self._parse_candle_timestamp(opened_at)

        evaluator = ExitEvaluator(
            settings=get_settings(),
            min_order_notional=self.paper_broker.min_order_notional,
            slippage_pct=self.paper_broker.slippage_pct,
        )
        decision = evaluator.evaluate_strategy_exit(
            position=PositionSnapshot(
                symbol=signal.symbol,
                quantity=position_qty,
                average_price=float(position.get("average_price", 0.0) or 0.0),
                opened_at=opened_at,
            ),
            market=MarketSnapshot(
                latest_price=latest_price,
                now=cycle_time,
                trend_reversal=bool(getattr(signal, "meta", {}).get("trend_reversal_hint", False)),
            ),
            stop_loss_pct=getattr(signal, "meta", {}).get("strategy_stop_loss_pct"),
            take_profit_pct=getattr(signal, "meta", {}).get("strategy_take_profit_pct"),
            managed_rebound_exit_threshold=getattr(signal, "meta", {}).get("managed_rebound_exit_threshold"),
            managed_rebound_exit_reason=getattr(signal, "meta", {}).get("managed_rebound_exit_reason"),
        )
        if not decision.triggered:
            return signal
        return self._build_force_exit_signal(
            signal=signal,
            source="strategy",
            exit_reason=decision.exit_reason or decision.reason,
            exit_size_scale=decision.quantity,
            confidence=decision.confidence,
        )

    def _apply_broker_exit(self, signal: TradeSignal, latest_price: float, cycle_time: datetime | None) -> TradeSignal:
        exit_rule = self.paper_broker.evaluate_exit_rules(signal.symbol, latest_price, now=cycle_time)
        if exit_rule.get("status") != "triggered":
            return signal
        resolved_source = str(exit_rule.get("exit_source", "broker") or "broker")
        forced_signal = self._build_force_exit_signal(
            signal=signal,
            source=resolved_source,
            exit_reason=str(exit_rule.get("exit_reason", exit_rule.get("reason", "broker_exit")) or "broker_exit"),
            exit_size_scale=float(exit_rule.get("exit_size_scale", exit_rule.get("size_scale", 0.0)) or 0.0),
            confidence=float(exit_rule.get("confidence", 1.0) or 1.0),
        )
        forced_signal.meta["exit_priority"] = int(exit_rule.get("exit_priority", forced_signal.meta.get("exit_priority", 0)) or 0)
        if exit_rule.get("exit_priority_label"):
            forced_signal.meta["exit_priority_label"] = exit_rule.get("exit_priority_label")
        return forced_signal

    def _build_force_exit_signal(
        self,
        *,
        signal: TradeSignal,
        source: str,
        exit_reason: str,
        exit_size_scale: float,
        confidence: float,
    ) -> TradeSignal:
        return TradeSignal(
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            action="sell",
            confidence=confidence,
            reason=f"{source}_exit:{exit_reason}; {signal.reason}",
            meta={
                **getattr(signal, "meta", {}),
                "force_exit": True,
                "exit_reason": exit_reason,
                "exit_size_scale": exit_size_scale,
                "exit_source": source,
                "exit_priority": self._exit_priority(source),
            },
        )

    def _choose_preferred_exit_signal(self, base_signal: TradeSignal, candidates: list[TradeSignal]) -> TradeSignal:
        force_exit_candidates = [candidate for candidate in candidates if bool(getattr(candidate, "meta", {}).get("force_exit", False))]
        if not force_exit_candidates:
            return candidates[-1] if candidates else base_signal
        return max(
            force_exit_candidates,
            key=lambda candidate: (
                int(getattr(candidate, "meta", {}).get("exit_priority", 0) or 0),
                float(candidate.confidence or 0.0),
            ),
        )

    def _exit_priority(self, source: str) -> int:
        priorities = {
            "strategy": 100,
            "broker": 200,
            "live_override": 300,
        }
        return priorities.get(source, 0)

    def _route_block_reason(self, strategy_name: str, market_info: dict, action: str | None = None) -> str | None:
        if action == "sell":
            return None
        policy_snapshot = build_trading_policy(get_settings()).snapshot
        regime = build_trading_policy(get_settings()).normalize_regime(market_info.get("regime"))
        range_strategies = {"mean_reversion", "dca"}
        if policy_snapshot.uncertain_block_enabled and regime == "uncertain" and strategy_name not in range_strategies:
            return "uncertain_regime_blocked"
        if strategy_name == "trend_following" and regime not in set(policy_snapshot.trend_strategy_allowed_regimes):
            return "trend_strategy_route_blocked"
        if strategy_name in range_strategies and regime not in (set(policy_snapshot.range_strategy_allowed_regimes) | {"uncertain"}):
            return "range_strategy_route_blocked"
        return None

    def _parse_candle_timestamp(self, timestamp: str | None) -> datetime | None:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return None

    def _should_block_for_sideways(self, strategy_name: str, market_info: dict) -> bool:
        policy_snapshot = build_trading_policy(get_settings()).snapshot
        if not policy_snapshot.sideway_filter_enabled:
            return False
        if strategy_name != "trend_following":
            return False
        if build_trading_policy(get_settings()).normalize_regime(market_info.get("regime")) != "sideways":
            return False
        if policy_snapshot.sideway_filter_volatility_block_on_low and market_info.get("volatility_state") == "low":
            return True
        if abs(float(market_info.get("trend_gap_pct", 0.0) or 0.0)) < policy_snapshot.sideway_filter_trend_gap_threshold:
            return True
        if policy_snapshot.sideway_filter_range_threshold and float(market_info.get("range_pct", 0.0) or 0.0) < policy_snapshot.sideway_filter_range_threshold:
            return True
        return False

    def _check_sideways_exception_pass(self, strategy_name: str, market_info: dict) -> str | None:
        """Check if sideways trend_following should be allowed via narrow exception window.
        
        Returns exception reason string if pass granted, None otherwise.
        """
        policy_snapshot = build_trading_policy(get_settings()).snapshot
        if not policy_snapshot.sideway_filter_breakout_exception_enabled:
            return None
        if strategy_name != "trend_following":
            return None
        if build_trading_policy(get_settings()).normalize_regime(market_info.get("regime")) != "sideways":
            return None
        
        trend_gap_pct = float(market_info.get("trend_gap_pct", 0.0) or 0.0)
        momentum_pct = float(market_info.get("momentum_pct", 0.0) or 0.0)
        volatility_state = market_info.get("volatility_state", "normal")
        higher_tf_bias = market_info.get("higher_tf_bias", "neutral")
        
        # Check momentum: must be positive
        if momentum_pct <= policy_snapshot.sideway_filter_breakout_exception_momentum_min:
            return None
        
        # Check trend_gap: must be near threshold (at least ratio × threshold)
        min_trend_gap = policy_snapshot.sideway_filter_trend_gap_threshold * policy_snapshot.sideway_filter_breakout_exception_trend_gap_ratio
        if trend_gap_pct < min_trend_gap:
            return None
        
        # Check higher_tf_bias: must not be bearish (unless explicitly allowed)
        if not policy_snapshot.sideway_filter_breakout_exception_allow_bearish_higher_tf:
            if higher_tf_bias == "bearish":
                return None
        
        # Check volatility: must not be low (unless explicitly allowed)
        if not policy_snapshot.sideway_filter_breakout_exception_allow_low_volatility:
            if volatility_state == "low":
                return None
        
        # All conditions passed - grant exception pass
        reasons = []
        if momentum_pct > 0:
            reasons.append("momentum_positive")
        if trend_gap_pct >= min_trend_gap:
            reasons.append(f"trend_gap_near_threshold({trend_gap_pct:.4f})")
        if higher_tf_bias != "bearish":
            reasons.append(f"higher_tf_bias={higher_tf_bias}")
        if volatility_state != "low":
            reasons.append(f"volatility={volatility_state}")
        
        return "sideways_breakout_exception: " + ", ".join(reasons)

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
