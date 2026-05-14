from dataclasses import dataclass
import math

from investment_bot.core.settings import get_settings
from investment_bot.models.account_summary import SellBlockReason
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class AccountService:
    upbit_client: UpbitClient

    def summarize_upbit_balances(self) -> dict:
        snapshot = self.summarize_upbit_balances_internal()
        assets = [
            {
                "currency": asset["currency"],
                "balance": asset["balance"],
                "market_value": asset["market_value"],
                "liquidation_value": asset["liquidation_value"],
                "sellable_now": asset["sellable_now"],
                "sell_block_reason": asset["sell_block_reason"],
            }
            for asset in snapshot["assets"]
        ]
        return {
            "exchange": snapshot["exchange"],
            "asset_count": snapshot["asset_count"],
            "krw_cash": snapshot["krw_cash"],
            "assets": assets,
        }

    def summarize_upbit_balances_internal(self) -> dict:
        balances = self.upbit_client.get_balances()
        assets = []
        total_krw_cash = 0.0
        market_map = {}
        market_currencies = []
        active_markets = self._get_active_market_set()

        for item in balances:
            currency = item.get("currency")
            unit_currency = item.get("unit_currency") or 'KRW'
            if currency and currency != "KRW":
                market = f"{unit_currency}-{currency}"
                market_map[currency] = market
                if not active_markets or market in active_markets:
                    market_currencies.append(market)

        ticker_map = {}
        if market_currencies:
            try:
                tickers = self.upbit_client.get_ticker(market_currencies)
                ticker_map = {row.get('market', ''): float(row.get('trade_price', 0) or 0) for row in tickers}
            except Exception:
                ticker_map = {}

        for item in balances:
            currency = item.get("currency")
            balance = float(item.get("balance", 0) or 0)
            locked = float(item.get("locked", 0) or 0)
            avg_buy_price = float(item.get("avg_buy_price", 0) or 0)
            unit_currency = item.get("unit_currency") or "KRW"

            if currency == "KRW":
                total_krw_cash += balance
            else:
                market = market_map.get(currency, "")
                total_balance = balance + locked
                market_active = bool(market and (not active_markets or market in active_markets))
                current_price = ticker_map.get(market)
                market_value = round(total_balance * current_price, 4) if current_price is not None else None
                liquidation_value = self._estimate_liquidation_value(balance=balance, current_price=current_price)
                sellable_now = False
                sell_block_reason = None
                if balance <= 0:
                    sell_block_reason = SellBlockReason.INSUFFICIENT_BALANCE.value
                elif not market_active:
                    sell_block_reason = SellBlockReason.INACTIVE_MARKET.value
                elif current_price is None:
                    sell_block_reason = SellBlockReason.NO_TICKER.value
                elif liquidation_value is None:
                    sell_block_reason = SellBlockReason.INSUFFICIENT_BALANCE.value
                elif liquidation_value < self._min_order_notional(unit_currency):
                    sell_block_reason = SellBlockReason.BELOW_MIN_ORDER_NOTIONAL.value
                else:
                    sellable_now = True
                assets.append(
                    {
                        "currency": currency,
                        "balance": balance,
                        "locked": locked,
                        "total_balance": round(total_balance, 8),
                        "avg_buy_price": avg_buy_price,
                        "current_price": current_price,
                        "unit_currency": unit_currency,
                        "market": market,
                        "market_active": market_active,
                        "estimated_cost_basis": round(total_balance * avg_buy_price, 4),
                        "estimated_market_value": market_value,
                        "market_value": market_value,
                        "liquidation_value": liquidation_value,
                        "sellable_now": sellable_now,
                        "sell_block_reason": sell_block_reason,
                    }
                )

        assets.sort(key=lambda x: self._sort_value(x), reverse=True)
        return {
            "exchange": "upbit",
            "asset_count": len(assets),
            "krw_cash": round(total_krw_cash, 4),
            "assets": assets,
        }

    def _get_active_market_set(self) -> set[str]:
        try:
            markets = self.upbit_client.get_markets()
        except Exception:
            return set()
        return {
            str(item.get("market", ""))
            for item in markets
            if item.get("market")
        }

    def get_asset_balance(self, symbol: str) -> dict:
        account = self.summarize_upbit_balances_internal()
        asset = symbol.split("/")[0].split("-")[-1].upper()
        for item in account["assets"]:
            if item["currency"].upper() == asset:
                return item
        return {
            "currency": asset,
            "balance": 0.0,
            "locked": 0.0,
            "total_balance": 0.0,
            "avg_buy_price": 0.0,
            "unit_currency": account.get("exchange_base", "KRW"),
            "estimated_cost_basis": 0.0,
            "estimated_market_value": None,
            "market_value": None,
            "liquidation_value": None,
            "sellable_now": False,
            "sell_block_reason": SellBlockReason.INSUFFICIENT_BALANCE.value,
        }

    def _estimate_liquidation_value(self, balance: float, current_price: float | None) -> float | None:
        if balance <= 0 or current_price is None:
            return None
        settings = get_settings()
        execution_price = current_price * max(1 - (settings.slippage_pct / 100), 0.0)
        adjusted_volume = self._floor_volume(balance)
        if adjusted_volume <= 0:
            return None
        return round(execution_price * adjusted_volume, 4)

    def _min_order_notional(self, unit_currency: str) -> float:
        return 5000.0 if (unit_currency or "KRW").upper() == "KRW" else 0.0

    def _floor_volume(self, value: float, decimals: int = 8) -> float:
        factor = 10 ** decimals
        return math.floor(value * factor) / factor

    def _sort_value(self, asset: dict) -> float:
        for key in ("market_value", "liquidation_value", "estimated_cost_basis"):
            value = asset.get(key)
            if value is not None:
                return float(value)
        return 0.0
