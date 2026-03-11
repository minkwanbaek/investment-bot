from dataclasses import dataclass

from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class LiveExecutionService:
    upbit_client: UpbitClient
    exchange_rules_service: ExchangeRulesService
    run_history_service: RunHistoryService
    live_mode: str = "shadow"
    confirm_live_trading: bool = False

    def preview_order(self, symbol: str, side: str, price: float, volume: float) -> dict:
        normalized = self.exchange_rules_service.normalize_upbit_price(symbol=symbol, price=price)
        rules = self.exchange_rules_service.get_upbit_market_rules(symbol=symbol)
        notional = round(normalized["normalized_price"] * volume, 8)
        allowed = notional >= rules["min_order_notional"]
        payload = {
            "exchange": "upbit",
            "mode": self.live_mode,
            "confirm_live_trading": self.confirm_live_trading,
            "symbol": symbol,
            "side": side,
            "requested_price": price,
            "normalized_price": normalized["normalized_price"],
            "tick_size": normalized["tick_size"],
            "volume": volume,
            "notional": notional,
            "min_order_notional": rules["min_order_notional"],
            "would_submit_live": self.live_mode == "live" and self.confirm_live_trading and allowed,
            "allowed": allowed,
        }
        self.run_history_service.record(kind="live_order_preview", payload=payload)
        return payload

    def submit_order(self, symbol: str, side: str, price: float, volume: float) -> dict:
        preview = self.preview_order(symbol=symbol, side=side, price=price, volume=volume)
        if self.live_mode != "live":
            return {**preview, "status": "blocked", "reason": "live_mode_disabled"}
        if not self.confirm_live_trading:
            return {**preview, "status": "blocked", "reason": "live_trading_not_confirmed"}
        return {**preview, "status": "not_implemented", "reason": "live_order_adapter_not_implemented_yet"}
