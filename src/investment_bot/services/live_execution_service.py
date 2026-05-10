from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from investment_bot.core.settings import get_settings
from investment_bot.services.account_service import AccountService
from investment_bot.services.exchange_rules_service import ExchangeRulesService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.upbit_client import UpbitClient


def _format_decimal(value: float, max_decimals: int = 8) -> str:
    """Format a float to a clean decimal string without floating-point artifacts."""
    d = Decimal(str(value)).quantize(Decimal(10) ** -max_decimals, rounding=ROUND_DOWN)
    # Normalize removes trailing zeros; ensure no scientific notation
    return format(d.normalize(), 'f')


def _floor_decimal_float(value: float, max_decimals: int = 8) -> float:
    d = Decimal(str(value)).quantize(Decimal(10) ** -max_decimals, rounding=ROUND_DOWN)
    return float(d)


def _price_str(price: float, tick_size: float) -> str:
    """Format price aligned to tick size, no trailing artifacts."""
    if tick_size >= 1:
        return str(int(price))
    decimals = max(0, -Decimal(str(tick_size)).as_tuple().exponent)
    d = Decimal(str(price)).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)
    return format(d, 'f')


def _market_order_payload(preview: dict) -> dict:
    side = preview["side"]
    payload = {
        "market": preview["market"],
        "side": "bid" if side == "buy" else "ask",
    }
    if side == "buy":
        max_decimals = 0 if str(preview["market"]).startswith("KRW-") else 8
        payload["price"] = _format_decimal(preview["notional"], max_decimals=max_decimals)
        payload["ord_type"] = "price"
        return payload
    payload["volume"] = _format_decimal(preview["volume"])
    payload["ord_type"] = "market"
    return payload


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
            requested_notional = max(price * volume, 0.0)
            min_notional = max(rules["min_order_notional"], requested_notional)
            if krw_cash is not None:
                fee_multiplier = 1 + (get_settings().trading_fee_pct / 100)
                max_affordable_notional = krw_cash / fee_multiplier
                min_notional = min(min_notional, max_affordable_notional)
            buy_execution_price = normalized_price * (1 + (get_settings().slippage_pct / 100))
            adjusted_volume = min_notional / buy_execution_price if buy_execution_price > 0 else 0.0

        execution_price = normalized_price
        if side == "sell":
            execution_price = normalized_price * max(1 - (get_settings().slippage_pct / 100), 0.0)
        notional = round(min_notional, 8) if side == "buy" and normalized_price > 0 else round(execution_price * adjusted_volume, 8)
        fee_paid = round(notional * (get_settings().trading_fee_pct / 100), 8) if side == "buy" else 0.0
        total_cost = round(notional + fee_paid, 8) if side == "buy" else notional
        allowed = notional >= rules["min_order_notional"]
        block_reason = None if allowed else "below_min_order_notional"
        if side == "buy" and krw_cash is not None and total_cost > krw_cash:
            allowed = False
            block_reason = "insufficient_cash_after_fee"
        if side == "sell" and asset_balance is not None and adjusted_volume > asset_balance:
            adjusted_volume = asset_balance
            adjusted_volume = _floor_decimal_float(adjusted_volume)
            notional = round(execution_price * adjusted_volume, 8)
            total_cost = notional
            allowed = notional >= rules["min_order_notional"]
            block_reason = None if allowed else "insufficient_asset_balance_for_min_order"
        elif side == "sell":
            adjusted_volume = _floor_decimal_float(adjusted_volume)
            notional = round(execution_price * adjusted_volume, 8)
            total_cost = notional
            allowed = notional >= rules["min_order_notional"]
            block_reason = None if allowed else "below_min_order_notional"
        # Explicit check: sell must also meet minimum notional requirement
        if side == "sell" and notional < rules["min_order_notional"]:
            allowed = False
            block_reason = block_reason or "below_min_order_notional"
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
            "fee_paid": fee_paid,
            "total_cost": total_cost,
            "min_order_notional": rules["min_order_notional"],
            "account_summary": account_summary,
            "asset_summary": asset_summary,
            "would_submit_live": self.live_mode == "live" and self.confirm_live_trading and allowed,
            "allowed": allowed,
            "reason": block_reason,
            "dry_run_only": self.live_mode != "live" or not self.confirm_live_trading,
        }
        self.run_history_service.record(kind="live_order_preview", payload=payload)
        return payload

    def submit_order(self, symbol: str, side: str, price: float, volume: float, force_live: bool = False, preview: dict | None = None) -> dict:
        preview = preview or self.preview_order(symbol=symbol, side=side, price=price, volume=volume)
        if not preview["allowed"]:
            return {**preview, "status": "blocked", "reason": preview.get("reason") or "order_below_exchange_rules_or_balance"}
        if self.live_mode == "paper":
            result = {
                **preview,
                "status": "submitted",
                "order": {
                    "uuid": None,
                    "dry_run_only": True,
                    "mode": self.live_mode,
                },
                "submitted_payload": {
                    **_market_order_payload(preview),
                    "dry_run_only": True,
                },
            }
            self.run_history_service.record(kind="live_order_submit", payload={
                "symbol": symbol,
                "market": preview["market"],
                "side": side,
                "price": preview["normalized_price"],
                "volume": preview["volume"],
                "status": "submitted",
                "dry_run_only": True,
                "order_uuid": None,
            })
            return result
        if self.live_mode != "live":
            return {**preview, "status": "blocked", "reason": "live_mode_disabled"}
        if not self.confirm_live_trading:
            return {**preview, "status": "blocked", "reason": "live_trading_not_confirmed"}

        
        # 매도 시에도 최소 주문 금액 체크 (포지션 금액 기준)
        if side == "sell":
            position_value = preview["notional"]
            if position_value < preview["min_order_notional"]:
                return {**preview, "status": "blocked", "reason": "position_value_below_min_order_notional"}

        order_payload = _market_order_payload(preview)
        response = self.upbit_client.create_order(**order_payload)
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
            "volume": preview["volume"],
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
