from dataclasses import dataclass

from investment_bot.services.account_service import AccountService
from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class LiveExecutionService:
    upbit_client: UpbitClient
    exchange_rules_service: ExchangeRulesService
    run_history_service: RunHistoryService
    account_service: AccountService | None = None
    live_mode: str = "shadow"
    confirm_live_trading: bool = False

    def preview_order(self, symbol: str, side: str, price: float, volume: float) -> dict:
        normalized = self.exchange_rules_service.normalize_upbit_price(symbol=symbol, price=price)
        rules = self.exchange_rules_service.get_upbit_market_rules(symbol=symbol)
        market = rules["market"]
        notional = round(normalized["normalized_price"] * volume, 8)
        allowed = notional >= rules["min_order_notional"]
        account_summary = self.account_service.summarize_upbit_balances() if self.account_service else None
        asset_summary = self.account_service.get_asset_balance(symbol) if self.account_service else None
        krw_cash = account_summary["krw_cash"] if account_summary else None
        asset_balance = asset_summary["balance"] if asset_summary else None
        if side == "buy" and krw_cash is not None and notional > krw_cash:
            allowed = False
        if side == "sell" and asset_balance is not None and volume > asset_balance:
            allowed = False
        payload = {
            "exchange": "upbit",
            "mode": self.live_mode,
            "confirm_live_trading": self.confirm_live_trading,
            "symbol": symbol,
            "market": market,
            "side": side,
            "requested_price": price,
            "normalized_price": normalized["normalized_price"],
            "tick_size": normalized["tick_size"],
            "volume": volume,
            "notional": notional,
            "min_order_notional": rules["min_order_notional"],
            "account_summary": account_summary,
            "asset_summary": asset_summary,
            "would_submit_live": self.live_mode == "live" and self.confirm_live_trading and allowed,
            "allowed": allowed,
            "dry_run_only": self.live_mode != "live" or not self.confirm_live_trading,
        }
        self.run_history_service.record(kind="live_order_preview", payload=payload)
        return payload

    def submit_order(self, symbol: str, side: str, price: float, volume: float) -> dict:
        preview = self.preview_order(symbol=symbol, side=side, price=price, volume=volume)
        if self.live_mode != "live":
            return {**preview, "status": "blocked", "reason": "live_mode_disabled"}
        if not self.confirm_live_trading:
            return {**preview, "status": "blocked", "reason": "live_trading_not_confirmed"}
        if not preview["allowed"]:
            return {**preview, "status": "blocked", "reason": "order_below_exchange_rules_or_balance"}

        order_payload = {
            "market": preview["market"],
            "side": self._to_upbit_side(side),
            "volume": self._format_decimal(volume),
            "price": self._format_decimal(preview["normalized_price"]),
            "ord_type": "limit",
        }
        response = self.upbit_client.create_limit_order(**order_payload)
        result = {
            **preview,
            "status": "submitted",
            "order": response,
            "submitted_payload": order_payload,
        }
        self.run_history_service.record(kind="live_order_submit", payload={
            "symbol": symbol,
            "market": preview["market"],
            "side": side,
            "price": preview["normalized_price"],
            "volume": volume,
            "status": "submitted",
        })
        return result

    def _format_decimal(self, value: float) -> str:
        rendered = f"{value:.16f}".rstrip("0").rstrip(".")
        return rendered or "0"

    def _to_upbit_side(self, side: str) -> str:
        if side == "buy":
            return "bid"
        if side == "sell":
            return "ask"
        return side
