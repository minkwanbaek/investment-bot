from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading
import time

from investment_bot.core.settings import Settings
from investment_bot.services.account_service import AccountService
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.shadow_service import ShadowService


@dataclass
class AutoTradeService:
    settings: Settings
    shadow_service: ShadowService
    live_execution_service: LiveExecutionService
    account_service: AccountService
    run_history_service: RunHistoryService
    active: bool = False
    _thread: threading.Thread | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _last_submitted_at: datetime | None = field(default=None, init=False)
    _last_result: dict | None = field(default=None, init=False)

    def profile(self) -> dict:
        return {
            "enabled": self.settings.auto_trade_enabled,
            "symbol": self.settings.auto_trade_symbol,
            "strategy_name": self.settings.auto_trade_strategy_name,
            "timeframe": self.settings.auto_trade_timeframe,
            "limit": self.settings.auto_trade_limit,
            "interval_seconds": self.settings.auto_trade_interval_seconds,
            "min_krw_balance": self.settings.auto_trade_min_krw_balance,
            "target_allocation_pct": self.settings.auto_trade_target_allocation_pct,
            "meaningful_order_notional": self.settings.auto_trade_meaningful_order_notional,
            "max_pending_seconds": self.settings.auto_trade_max_pending_seconds,
            "cooldown_cycles": self.settings.auto_trade_cooldown_cycles,
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

        if self._cooldown_active():
            result = {
                "status": "skipped",
                "reason": "cooldown_active",
                "cooldown_cycles": self.settings.auto_trade_cooldown_cycles,
            }
            return self._remember(result, record_kind="auto_trade_skip")

        shadow = self.shadow_service.run_once(
            strategy_name=self.settings.auto_trade_strategy_name,
            symbol=self.settings.auto_trade_symbol,
            timeframe=self.settings.auto_trade_timeframe,
            limit=self.settings.auto_trade_limit,
        )
        review = shadow["decision"]["review"]
        action = review.get("action")

        if action == "buy":
            if krw_cash < self.settings.auto_trade_min_krw_balance:
                result = {
                    "status": "skipped",
                    "reason": "insufficient_krw_balance",
                    "krw_cash": krw_cash,
                    "required_min_krw": self.settings.auto_trade_min_krw_balance,
                    "shadow": shadow,
                }
                return self._remember(result, record_kind="auto_trade_skip")

            allocation_cap = min(
                krw_cash * (self.settings.auto_trade_target_allocation_pct / 100),
                krw_cash,
            )
            reviewed_target = float(review.get("target_notional", 0.0) or 0.0)
            target_notional = min(allocation_cap, reviewed_target if reviewed_target > 0 else allocation_cap)
            target_notional = max(target_notional, self.settings.min_order_notional)
            target_notional = min(target_notional, krw_cash)
            if target_notional < self.settings.auto_trade_meaningful_order_notional:
                result = {
                    "status": "skipped",
                    "reason": "below_meaningful_order_notional",
                    "target_notional": round(target_notional, 4),
                    "meaningful_order_notional": self.settings.auto_trade_meaningful_order_notional,
                    "shadow": shadow,
                }
                return self._remember(result, record_kind="auto_trade_skip")

            price = review["latest_price"]
            volume = round(target_notional / price, 8)
            return self._submit_trade(action="buy", price=price, volume=volume, shadow=shadow)

        if action == "sell":
            asset = self.account_service.get_asset_balance(self.settings.auto_trade_symbol)
            available_volume = float(asset.get("balance", 0.0))
            if available_volume <= 0:
                result = {
                    "status": "skipped",
                    "reason": "insufficient_asset_balance",
                    "asset": asset,
                    "shadow": shadow,
                }
                return self._remember(result, record_kind="auto_trade_skip")
            price = review["latest_price"]
            confidence = float(review.get("confidence", 0.0) or 0.0)
            sell_ratio = min(max(confidence, 0.25), 1.0)
            volume = round(available_volume * sell_ratio, 8)
            if volume <= 0:
                result = {
                    "status": "skipped",
                    "reason": "sell_volume_zero_after_sizing",
                    "asset": asset,
                    "shadow": shadow,
                }
                return self._remember(result, record_kind="auto_trade_skip")
            return self._submit_trade(action="sell", price=price, volume=volume, shadow=shadow)

        result = {
            "status": "skipped",
            "reason": "non_actionable_signal",
            "shadow": shadow,
        }
        return self._remember(result, record_kind="auto_trade_skip")

    def _submit_trade(self, action: str, price: float, volume: float, shadow: dict) -> dict:
        preview = self.live_execution_service.preview_order(
            symbol=self.settings.auto_trade_symbol,
            side=action,
            price=price,
            volume=volume,
        )
        if not preview.get("allowed"):
            result = {
                "status": "skipped",
                "reason": "preview_blocked",
                "preview": preview,
                "shadow": shadow,
            }
            return self._remember(result, record_kind="auto_trade_skip")

        submit = self.live_execution_service.submit_order(
            symbol=self.settings.auto_trade_symbol,
            side=action,
            price=price,
            volume=volume,
        )
        self._last_submitted_at = datetime.now(timezone.utc)
        result = {
            "status": "submitted",
            "side": action,
            "shadow": shadow,
            "preview": preview,
            "submit": submit,
        }
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
                self._remember({"status": "error", "reason": str(exc)}, record_kind="auto_trade_error")
            slept = 0
            while self.active and slept < self.settings.auto_trade_interval_seconds:
                time.sleep(1)
                slept += 1

    def _remember(self, result: dict, record_kind: str) -> dict:
        self._last_result = result
        self.run_history_service.record(kind=record_kind, payload=result)
        return result
