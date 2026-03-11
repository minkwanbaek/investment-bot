from dataclasses import dataclass

from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class ShadowService:
    semi_live_service: SemiLiveService
    run_history_service: RunHistoryService
    upbit_client: UpbitClient

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5) -> dict:
        balances = self.upbit_client.get_balances()
        semi_live_result = self.semi_live_service.run_once(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        payload = {
            "mode": "shadow",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "exchange": "upbit",
            "exchange_balance_count": len(balances),
            "exchange_balances": balances,
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
            "decision": semi_live_result,
            "live_order_submitted": False,
        })
        return payload
