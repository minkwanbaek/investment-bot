from dataclasses import dataclass

from investment_bot.services.upbit_client import UpbitClient


@dataclass
class AccountService:
    upbit_client: UpbitClient

    def summarize_upbit_balances(self) -> dict:
        balances = self.upbit_client.get_balances()
        assets = []
        total_krw_cash = 0.0

        for item in balances:
            currency = item.get("currency")
            balance = float(item.get("balance", 0) or 0)
            locked = float(item.get("locked", 0) or 0)
            avg_buy_price = float(item.get("avg_buy_price", 0) or 0)
            unit_currency = item.get("unit_currency")

            if currency == "KRW":
                total_krw_cash += balance
            else:
                assets.append(
                    {
                        "currency": currency,
                        "balance": balance,
                        "locked": locked,
                        "total_balance": round(balance + locked, 8),
                        "avg_buy_price": avg_buy_price,
                        "unit_currency": unit_currency,
                        "estimated_cost_basis": round((balance + locked) * avg_buy_price, 4),
                    }
                )

        assets.sort(key=lambda x: x["estimated_cost_basis"], reverse=True)
        return {
            "exchange": "upbit",
            "asset_count": len(assets),
            "krw_cash": round(total_krw_cash, 4),
            "assets": assets,
        }

    def get_asset_balance(self, symbol: str) -> dict:
        account = self.summarize_upbit_balances()
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
        }
