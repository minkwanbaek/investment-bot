from dataclasses import dataclass

from investment_bot.services.account_service import AccountService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class ShadowService:
    semi_live_service: SemiLiveService
    run_history_service: RunHistoryService
    upbit_client: UpbitClient
    account_service: AccountService | None = None

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5) -> dict:
        balances = self.upbit_client.get_balances()
        semi_live_result = self.semi_live_service.run_once(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        account_summary = self.account_service.summarize_upbit_balances() if self.account_service else None
        payload = {
            "mode": "shadow",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "exchange": "upbit",
            "exchange_balance_count": len(balances),
            "exchange_balances": balances,
            "exchange_account_summary": account_summary,
            "decision": semi_live_result,
            "live_order_submitted": False,
        }
        self.run_history_service.record(kind="shadow_cycle", payload={
            "mode": "shadow",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "exchange_balance_count": len(balances),
            "exchange_account_summary": account_summary,
            "decision": semi_live_result,
            "live_order_submitted": False,
        })
        return payload
