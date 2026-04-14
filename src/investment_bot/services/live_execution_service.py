from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from investment_bot.services.account_service import AccountService
from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.upbit_client import UpbitClient


def _format_decimal(value: float, max_decimals: int = 8) -> str:
    """Format a float to a clean decimal string without floating-point artifacts."""
    d = Decimal(str(value)).quantize(Decimal(10) ** -max_decimals, rounding=ROUND_DOWN)
    # Normalize removes trailing zeros; ensure no scientific notation
    return format(d.normalize(), 'f')


def _price_str(price: float, tick_size: float) -> str:
    """Format price aligned to tick size, no trailing artifacts."""
    if tick_size >= 1:
        return str(int(price))
    decimals = max(0, -Decimal(str(tick_size)).as_tuple().exponent)
    d = Decimal(str(price)).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)
    return format(d, 'f')


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
        account_summary = self.account_service.summarize_upbit_balances() if self.account_service else None
        asset_summary = self.account_service.get_asset_balance(symbol) if self.account_service else None
        krw_cash = account_summary["krw_cash"] if account_summary else None
        asset_balance = asset_summary["balance"] if asset_summary else None

        adjusted_volume = volume
        normalized_price = normalized["normalized_price"]
        if side == "buy" and normalized_price > 0:
            requested_notional = normalized_price * volume
            min_notional = max(rules["min_order_notional"], requested_notional)
            if krw_cash is not None:
                min_notional = min(min_notional, krw_cash)
            adjusted_volume = min_notional / normalized_price

        notional = round(normalized_price * adjusted_volume, 8)
        allowed = notional >= rules["min_order_notional"]
        if side == "buy" and krw_cash is not None and notional > krw_cash:
            allowed = False
        if side == "sell" and asset_balance is not None and adjusted_volume > asset_balance:
            allowed = False
        # Explicit check: sell must also meet minimum notional requirement
        if side == "sell" and notional < rules["min_order_notional"]:
            allowed = False
        payload = {
            "exchange": "upbit",
            "mode": self.live_mode,
            "confirm_live_trading": self.confirm_live_trading,
            "symbol": symbol,
            "market": market,
            "side": side,
            "requested_price": price,
            "normalized_price": normalized_price,
            "tick_size": normalized["tick_size"],
            "volume": adjusted_volume,
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

    def submit_order(self, symbol: str, side: str, price: float, volume: float, force_live: bool = False) -> dict:
        preview = self.preview_order(symbol=symbol, side=side, price=price, volume=volume)
        if self.live_mode != "live":
            return {**preview, "status": "blocked", "reason": "live_mode_disabled"}
        if not self.confirm_live_trading:
            return {**preview, "status": "blocked", "reason": "live_trading_not_confirmed"}
        if not preview["allowed"]:
            return {**preview, "status": "blocked", "reason": "order_below_exchange_rules_or_balance"}

        
        # 매도 시에도 최소 주문 금액 체크 (포지션 금액 기준)
        if side == "sell":
            position_value = preview["notional"]
            if position_value < preview["min_order_notional"]:
                return {**preview, "status": "blocked", "reason": "position_value_below_min_order_notional"}

        order_payload = {
            "market": preview["market"],
            "side": self._to_upbit_side(side),
            "volume": _format_decimal(preview["volume"]),
            "price": _price_str(preview["normalized_price"], preview["tick_size"]),
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
            "order_uuid": response.get("uuid"),
            "order": response,
        })
        return result

    def get_order(self, uuid_value: str) -> dict:
        return self.upbit_client.get_order(uuid_value)

    def _to_upbit_side(self, side: str) -> str:
        if side == "buy":
            return "bid"
        if side == "sell":
            return "ask"
        return side
