from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import threading
import time

from investment_bot.core.settings import Settings

logger = logging.getLogger(__name__)
from investment_bot.services.account_service import AccountService
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.shadow_service import ShadowService
from investment_bot.services.strategy_selection_service import StrategySelectionService
from investment_bot.strategies.registry import list_enabled_strategies


@dataclass
class AutoTradeService:
    settings: Settings
    shadow_service: ShadowService
    live_execution_service: LiveExecutionService
    account_service: AccountService
    run_history_service: RunHistoryService
    strategy_selection_service: StrategySelectionService
    active: bool = False
    _thread: threading.Thread | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _last_submitted_at: datetime | None = field(default=None, init=False)
    _last_result: dict | None = field(default=None, init=False)
    _peak_price_by_symbol: dict[str, float] = field(default_factory=dict, init=False)

    def profile(self) -> dict:
        return {
            "enabled": self.settings.auto_trade_enabled,
            "symbol": self.settings.auto_trade_symbol,
            "symbols": self.settings.symbols,
            "enabled_strategies": list_enabled_strategies(),
            "strategy_name": self.settings.auto_trade_strategy_name,
            "timeframe": self.settings.auto_trade_timeframe,
            "limit": self.settings.auto_trade_limit,
            "interval_seconds": self.settings.auto_trade_interval_seconds,
            "min_krw_balance": self.settings.auto_trade_min_krw_balance,
            "target_allocation_pct": self.settings.auto_trade_target_allocation_pct,
            "meaningful_order_notional": self.settings.auto_trade_meaningful_order_notional,
            "max_pending_seconds": self.settings.auto_trade_max_pending_seconds,
            "cooldown_cycles": self.settings.auto_trade_cooldown_cycles,
            "stop_loss_pct": self.settings.auto_trade_stop_loss_pct,
            "partial_take_profit_pct": self.settings.auto_trade_partial_take_profit_pct,
            "trailing_stop_pct": self.settings.auto_trade_trailing_stop_pct,
            "partial_sell_ratio": self.settings.auto_trade_partial_sell_ratio,
            "max_total_exposure_pct": self.settings.auto_trade_max_total_exposure_pct,
            "min_managed_position_notional": self.settings.auto_trade_min_managed_position_notional,
        }

    def status(self) -> dict:
        return {
            "active": self.active,
            "profile": self.profile(),
            "last_submitted_at": self._last_submitted_at.isoformat() if self._last_submitted_at else None,
            "last_result": self._last_result,
        }

    def start(self) -> dict:
        with self._lock:
            if self.active:
                return {"status": "already_running", **self.status()}
            self.active = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="auto-trade-loop")
            self._thread.start()
        self.run_history_service.record(kind="auto_trade_start", payload={"profile": self.profile()})
        return {"status": "started", **self.status()}

    def stop(self) -> dict:
        with self._lock:
            self.active = False
        self.run_history_service.record(kind="auto_trade_stop", payload={"profile": self.profile()})
        return {"status": "stopped", **self.status()}

    def run_once(self) -> dict:
        account = self.account_service.summarize_upbit_balances()
        krw_cash = float(account.get("krw_cash", 0.0))
        logger.info("run_once started | krw_cash=%.2f symbols=%s", krw_cash, self.settings.symbols)

        if self._cooldown_active():
            logger.info("run_once skipped: cooldown_active")
            result = {"status": "skipped", "reason": "cooldown_active", "cooldown_cycles": self.settings.auto_trade_cooldown_cycles}
            return self._remember(result, record_kind="auto_trade_skip")

        candidates = []
        for symbol in self.settings.symbols:
            per_symbol = self._collect_symbol_candidates(symbol)
            candidates.extend(per_symbol)

        sell_candidates = [c for c in candidates if c["action"] == "sell"]
        if sell_candidates:
            chosen = max(sell_candidates, key=lambda c: (1 if c["override"] else 0, c["score"]))
            logger.info("sell candidate chosen | symbol=%s score=%.4f override=%s", chosen["symbol"], chosen["score"], chosen.get("override"))
            return self._handle_sell(chosen)

        buy_candidates = [c for c in candidates if c["action"] == "buy"]
        if buy_candidates:
            chosen = max(buy_candidates, key=lambda c: c["score"])
            logger.info("buy candidate chosen | symbol=%s score=%.4f confidence=%.4f", chosen["symbol"], chosen["score"], chosen["confidence"])
            return self._handle_buy(chosen, krw_cash=krw_cash, account=account)

        logger.info("run_once skipped: non_actionable_signal | %d candidates evaluated", len(candidates))
        result = {"status": "skipped", "reason": "non_actionable_signal", "candidates": candidates}
        return self._remember(result, record_kind="auto_trade_skip")

    def _collect_symbol_candidates(self, symbol: str) -> list[dict]:
        enabled = list_enabled_strategies()
        collected = []
        regime_name = "unknown"
        for strategy_name in enabled:
            shadow = self.shadow_service.run_once(strategy_name=strategy_name, symbol=symbol, timeframe=self.settings.auto_trade_timeframe, limit=self.settings.auto_trade_limit)
            review = shadow["decision"]["review"]
            regime = shadow["decision"].get("market_regime", {})
            regime_name = regime.get("regime", "unknown")
            asset = self.account_service.get_asset_balance(symbol)
            latest_price = float(review.get("latest_price", 0.0) or 0.0)
            managed_notional = float(asset.get("estimated_cost_basis", 0.0) or 0.0)
            if managed_notional < self.settings.auto_trade_min_managed_position_notional:
                asset = {**asset, "managed": False, "managed_notional": managed_notional}
                override = None
            else:
                asset = {**asset, "managed": True, "managed_notional": managed_notional}
                override = self._exit_override(symbol=symbol, asset=asset, latest_price=latest_price)
            action = override["action"] if override is not None else review.get("action")
            score = self._score_candidate(action=action, confidence=float(review.get("confidence", 0.0) or 0.0), review=review)
            collected.append({
                "symbol": symbol,
                "strategy_name": strategy_name,
                "shadow": shadow,
                "review": review,
                "asset": asset,
                "regime": regime,
                "override": override,
                "action": action,
                "confidence": float(review.get("confidence", 0.0) or 0.0),
                "latest_price": latest_price,
                "score": score,
            })
        chosen = self.strategy_selection_service.choose(symbol=symbol, regime=regime_name, candidates=collected)
        return [chosen] if chosen else []

    def _score_candidate(self, action: str, confidence: float, review: dict) -> float:
        if action == "hold":
            return 0.0
        target_notional = float(review.get("target_notional", 0.0) or 0.0)
        return round(confidence * 100 + min(target_notional / 1000.0, 20.0), 6)

    def _handle_buy(self, chosen: dict, krw_cash: float, account: dict) -> dict:
        if krw_cash < self.settings.auto_trade_min_krw_balance:
            result = {"status": "skipped", "reason": "insufficient_krw_balance", "krw_cash": krw_cash, "required_min_krw": self.settings.auto_trade_min_krw_balance, "chosen": chosen}
            return self._remember(result, record_kind="auto_trade_skip")
        current_exposure = sum(float(asset.get("estimated_cost_basis", 0.0) or 0.0) for asset in account.get("assets", []))
        total_equity = krw_cash + current_exposure
        allocation_cap = min(krw_cash * (self.settings.auto_trade_target_allocation_pct / 100), krw_cash)
        review = chosen["review"]
        reviewed_target = float(review.get("target_notional", 0.0) or 0.0)
        target_notional = min(allocation_cap, reviewed_target if reviewed_target > 0 else allocation_cap)
        max_total_exposure_value = total_equity * (self.settings.auto_trade_max_total_exposure_pct / 100)
        remaining_exposure_room = max(0.0, max_total_exposure_value - current_exposure)
        target_notional = min(target_notional, remaining_exposure_room)
        target_notional = max(target_notional, self.settings.min_order_notional) if remaining_exposure_room >= self.settings.min_order_notional else target_notional
        target_notional = min(target_notional, krw_cash)
        if target_notional < self.settings.auto_trade_meaningful_order_notional:
            blocker = "total_exposure_limit" if remaining_exposure_room < self.settings.auto_trade_meaningful_order_notional else "meaningful_order_notional"
            logger.info(
                "run_once skipped: below_meaningful_order_notional_or_total_exposure_limit | blocker=%s target_notional=%.4f remaining_exposure_room=%.4f current_exposure=%.4f max_total_exposure_value=%.4f",
                blocker,
                target_notional,
                remaining_exposure_room,
                current_exposure,
                max_total_exposure_value,
            )
            result = {"status": "skipped", "reason": "below_meaningful_order_notional_or_total_exposure_limit", "blocker": blocker, "target_notional": round(target_notional, 4), "remaining_exposure_room": round(remaining_exposure_room, 4), "meaningful_order_notional": self.settings.auto_trade_meaningful_order_notional, "current_exposure": round(current_exposure, 4), "max_total_exposure_value": round(max_total_exposure_value, 4), "chosen": chosen}
            return self._remember(result, record_kind="auto_trade_skip")
        price = chosen["latest_price"]
        volume = round(target_notional / price, 8)
        return self._submit_trade(symbol=chosen["symbol"], action="buy", price=price, volume=volume, shadow=chosen["shadow"], override=chosen["override"], extra={"chosen": chosen})

    def _handle_sell(self, chosen: dict) -> dict:
        asset = chosen["asset"]
        if asset.get("managed") is False:
            result = {"status": "skipped", "reason": "below_min_managed_position_notional", "chosen": chosen}
            return self._remember(result, record_kind="auto_trade_skip")
        available_volume = float(asset.get("balance", 0.0))
        if available_volume <= 0:
            result = {"status": "skipped", "reason": "insufficient_asset_balance", "chosen": chosen}
            return self._remember(result, record_kind="auto_trade_skip")
        sell_ratio = float(chosen["override"].get("sell_ratio", 1.0)) if chosen["override"] is not None else min(max(chosen["confidence"], 0.25), 1.0)
        volume = round(available_volume * sell_ratio, 8)
        if volume <= 0:
            result = {"status": "skipped", "reason": "sell_volume_zero_after_sizing", "chosen": chosen}
            return self._remember(result, record_kind="auto_trade_skip")
        return self._submit_trade(symbol=chosen["symbol"], action="sell", price=chosen["latest_price"], volume=volume, shadow=chosen["shadow"], override=chosen["override"], extra={"chosen": chosen})

    def _exit_override(self, symbol: str, asset: dict, latest_price: float) -> dict | None:
        balance = float(asset.get("balance", 0.0) or 0.0)
        avg_buy_price = float(asset.get("avg_buy_price", 0.0) or 0.0)
        if balance <= 0 or avg_buy_price <= 0 or latest_price <= 0:
            self._peak_price_by_symbol.pop(symbol, None)
            return None
        peak = self._peak_price_by_symbol.get(symbol, latest_price)
        peak = max(peak, latest_price)
        self._peak_price_by_symbol[symbol] = peak
        pnl_pct = ((latest_price - avg_buy_price) / avg_buy_price) * 100
        drawdown_from_peak_pct = ((peak - latest_price) / peak) * 100 if peak > 0 else 0.0
        if pnl_pct <= -self.settings.auto_trade_stop_loss_pct:
            return {"action": "sell", "override_reason": "stop_loss", "sell_ratio": 1.0, "pnl_pct": round(pnl_pct, 4), "drawdown_from_peak_pct": round(drawdown_from_peak_pct, 4)}
        if pnl_pct >= self.settings.auto_trade_partial_take_profit_pct and drawdown_from_peak_pct >= self.settings.auto_trade_trailing_stop_pct:
            return {"action": "sell", "override_reason": "take_profit_trailing_stop", "sell_ratio": self.settings.auto_trade_partial_sell_ratio, "pnl_pct": round(pnl_pct, 4), "drawdown_from_peak_pct": round(drawdown_from_peak_pct, 4)}
        return None

    def _submit_trade(self, symbol: str, action: str, price: float, volume: float, shadow: dict, override: dict | None = None, extra: dict | None = None) -> dict:
        preview = self.live_execution_service.preview_order(symbol=symbol, side=action, price=price, volume=volume)
        if not preview.get("allowed"):
            logger.warning("trade preview blocked | symbol=%s side=%s price=%.2f volume=%.8f", symbol, action, price, volume)
            result = {"status": "skipped", "reason": "preview_blocked", "preview": preview, "shadow": shadow, "override": override, **(extra or {})}
            return self._remember(result, record_kind="auto_trade_skip")
        submit = self.live_execution_service.submit_order(symbol=symbol, side=action, price=price, volume=volume)
        self._last_submitted_at = datetime.now(timezone.utc)
        logger.info("trade submitted | symbol=%s side=%s price=%.2f volume=%.8f", symbol, action, price, volume)
        result = {"status": "submitted", "symbol": symbol, "side": action, "shadow": shadow, "preview": preview, "submit": submit, "override": override, **(extra or {})}
        return self._remember(result, record_kind="auto_trade_submit")

    def _cooldown_active(self) -> bool:
        if not self._last_submitted_at or self.settings.auto_trade_cooldown_cycles <= 0:
            return False
        cooldown = self.settings.auto_trade_interval_seconds * self.settings.auto_trade_cooldown_cycles
        return datetime.now(timezone.utc) < self._last_submitted_at + timedelta(seconds=cooldown)

    def _loop(self) -> None:
        while self.active:
            try:
                self.run_once()
            except Exception as exc:
                logger.exception("auto_trade_loop error: %s", exc)
                self._remember({"status": "error", "reason": str(exc)}, record_kind="auto_trade_error")
            slept = 0
            while self.active and slept < self.settings.auto_trade_interval_seconds:
                time.sleep(1)
                slept += 1

    def _remember(self, result: dict, record_kind: str) -> dict:
        self._last_result = result
        self.run_history_service.record(kind=record_kind, payload=result)
        return result
