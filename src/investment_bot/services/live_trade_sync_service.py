from dataclasses import dataclass
from datetime import datetime, timezone

from investment_bot.models.trade_log import TradeLogSchema
from investment_bot.services.ledger_store import LedgerStore
from investment_bot.services.live_execution_service import LiveExecutionService
from investment_bot.services.run_history_service import RunHistoryService


@dataclass
class LiveTradeSyncService:
    run_history_service: RunHistoryService
    live_execution_service: LiveExecutionService
    ledger_store: LedgerStore

    def sync_order(self, uuid_value: str) -> dict:
        order = self.live_execution_service.get_order(uuid_value)
        if order.get('state') not in {'done', 'cancel'}:
            return {'status': 'pending', 'order': order}

        side = 'buy' if order.get('side') == 'bid' else 'sell'
        trades = order.get('trades') or []
        executed_volume = float(order.get('executed_volume', 0.0) or 0.0)
        if executed_volume <= 0:
            return {'status': 'no_fill', 'order': order}

        if trades:
            executed_price = sum(float(t.get('price', 0.0) or 0.0) * float(t.get('volume', 0.0) or 0.0) for t in trades) / max(executed_volume, 1e-9)
        else:
            executed_price = float(order.get('price', 0.0) or 0.0)

        symbol = (order.get('market') or '').replace('KRW-', '') + '/KRW'

        if side == 'buy':
            entry = TradeLogSchema(
                trade_id=uuid_value,
                strategy_version=None,
                symbol=symbol,
                side='buy',
                entry_time=datetime.now(timezone.utc),
                entry_price=executed_price,
                quantity=executed_volume,
                entry_reason='live_order_sync',
            )
            existing = self.ledger_store.load() or {}
            trade_logs = existing.get('trade_logs', [])
            if not any(log.get('trade_id') == uuid_value for log in trade_logs):
                self.ledger_store.append_trade_log_entry(entry)
            return {'status': 'synced_buy', 'order_uuid': uuid_value, 'executed_price': executed_price, 'executed_volume': executed_volume}

        updated = self.ledger_store.update_latest_open_trade_log(
            symbol=symbol,
            side='buy',
            updates={
                'exit_time': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'exit_price': executed_price,
                'exit_reason': 'live_order_sync',
            },
        )
        return {'status': 'synced_sell', 'updated': updated, 'order_uuid': uuid_value}

    def sync_latest_submitted_order(self) -> dict:
        runs = self.run_history_service.list_recent(limit=50)
        submits = [run for run in reversed(runs) if run.get('kind') == 'live_order_submit']
        if not submits:
            return {'status': 'no_submitted_order'}
        latest = submits[0]
        payload = latest.get('payload', {})
        uuid_value = payload.get('order_uuid')
        if not uuid_value:
            return {'status': 'missing_order_uuid', 'run_id': latest.get('id')}

        return self.sync_order(uuid_value)
