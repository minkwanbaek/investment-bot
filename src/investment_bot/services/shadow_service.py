from dataclasses import dataclass

from investment_bot.services.account_service import AccountService
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService
from investment_bot.services.semi_live_service import SemiLiveService
from investment_bot.services.upbit_client import UpbitClient


@dataclass
class ShadowService:
    semi_live_service: SemiLiveService
    run_history_service: RunHistoryService
    upbit_client: UpbitClient
    account_service: AccountService | None = None
    live_execution_service: LiveExecutionService | None = None
    live_mode: str = "shadow"
    confirm_live_trading: bool = False

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5) -> dict:
        balances = self.upbit_client.get_balances()
        account_summary = self.account_service.summarize_upbit_balances() if self.account_service else None
        if self.account_service:
            asset = self.account_service.get_asset_balance(symbol)
            self.semi_live_service.trading_cycle_service.paper_broker.sync_exchange_position(
                symbol=symbol,
                quantity=float(asset.get("balance", 0.0)),
                average_price=float(asset.get("avg_buy_price", 0.0)),
                cash_balance=float(account_summary.get("krw_cash", 0.0)) if account_summary else None,
            )
        semi_live_result = self.semi_live_service.run_once(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        account_summary = self.account_service.summarize_upbit_balances() if self.account_service else None
        
        # live 모드에서 실제 주문 제출 여부 확인
        live_order_submitted = False
        if self.live_mode == "live" and self.confirm_live_trading and self.live_execution_service and semi_live_result:
            # live_execution_service 를 통해 실제 주문 제출
            signal = semi_live_result.get("signal", {})
            if signal.get("action") in ("buy", "sell") and signal.get("approved_size", 0) > 0:
                preview = self.live_execution_service.preview_order(
                    symbol=signal.get("symbol", symbol),
                    side=signal.get("action"),
                    price=semi_live_result.get("latest_price", 0),
                    volume=signal.get("approved_size", 0),
                )
                if preview.get("would_submit_live"):
                    result = self.live_execution_service.submit_order(
                        symbol=signal.get("symbol", symbol),
                        side=signal.get("action"),
                        price=semi_live_result.get("latest_price", 0),
                        volume=signal.get("approved_size", 0),
                    )
                    live_order_submitted = result.get("status") == "submitted"
        payload = {
            "mode": self.live_mode,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "exchange": "upbit",
            "exchange_balance_count": len(balances),
            "exchange_balances": balances,
            "exchange_account_summary": account_summary,
            "decision": semi_live_result,
            "live_order_submitted": live_order_submitted,
        }
        self.run_history_service.record(kind="shadow_cycle", payload={
            "mode": self.live_mode,
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit,
            "exchange_balance_count": len(balances),
            "exchange_account_summary": account_summary,
            "decision": semi_live_result,
            "live_order_submitted": live_order_submitted,
        })
        return payload
