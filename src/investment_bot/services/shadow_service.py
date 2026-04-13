from dataclasses import dataclass
import time

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
    _balances_cache: list | None = None
    _account_cache: dict | None = None

    def _get_cached_balances(self) -> list:
        if self._balances_cache is None:
            self._balances_cache = self.upbit_client.get_balances()
        return self._balances_cache

    def _get_cached_account_summary(self) -> dict | None:
        if self._account_cache is None and self.account_service:
            self._account_cache = self.account_service.summarize_upbit_balances()
        return self._account_cache

    def invalidate_cache(self) -> None:
        self._balances_cache = None
        self._account_cache = None

    def run_once(self, strategy_name: str, symbol: str, timeframe: str, limit: int = 5, candles: list | None = None, skip_position_sync: bool = False) -> dict:
        import logging
        logger = logging.getLogger(__name__)
        
        t0 = time.time()
        balances = self._get_cached_balances()
        t1 = time.time()
        account_summary = self._get_cached_account_summary()
        t2 = time.time()
        
        # Only sync position if explicitly requested (caller may have already synced)
        if self.account_service and not skip_position_sync:
            asset = self.account_service.get_asset_balance(symbol)
            self.semi_live_service.trading_cycle_service.paper_broker.sync_exchange_position(
                symbol=symbol,
                quantity=float(asset.get("balance", 0.0)),
                average_price=float(asset.get("avg_buy_price", 0.0)),
                cash_balance=float(account_summary.get("krw_cash", 0.0)) if account_summary else None,
            )
        t3 = time.time()
        
        semi_live_result = self.semi_live_service.run_once(
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            candles=candles,
        )
        t4 = time.time()
        
        logger.debug(
            "shadow_service.run_once | symbol=%s strategy=%s cache_bal=%.3fs cache_acct=%.3fs sync_pos=%.3fs semi_live=%.3fs total=%.3fs",
            symbol, strategy_name, t1-t0, t2-t1, t3-t2, t4-t3, t4-t0,
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
