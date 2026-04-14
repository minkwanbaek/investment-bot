#!/usr/bin/env python3
"""
Investment Bot Executor

5 분마다 모든 심볼에 대해 트레이딩 사이클을 실행합니다.
- 진입 신호 (buy) 와 청산 신호 (sell) 모두 처리
- 로그 출력: logs/executor.log

Log Improvements (2026-04-14):
- [BUY_OK]/[SELL_OK]: Executed trades with key details
- [BUY_SKIP]/[SELL_SKIP]: Skipped/rejected orders with structured reason codes
- [ORDER_FAIL]: Exchange/API failures
- Summary lines for quick human scanning
- Trace ID for order flow correlation
"""

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
import uuid

# 프로젝트 루트를 Python path 에 추가
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from investment_bot.services.container import (
    get_market_data_service,
    get_trading_cycle_service,
    get_paper_broker,
    get_run_history_service,
)
from investment_bot.core.settings import get_settings
from investment_bot.services.ledger_store import LedgerStore

# 설정 로드
settings = get_settings()

# 로그 설정
log_dir = project_root / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "executor.log"

# Log format: timestamp [LEVEL] [trace_id] message
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Reason Code Registry - Centralized skip/reject reasons for human readability
# =============================================================================

REASON_CODES = {
    # Order size / notional blockers
    "below_min_order_notional": "주문 금액이 최소 주문 금액 (5,000 KRW) 미만",
    "position_value_below_min_order_notional": "포지션 가치가 최소 주문 금액 미만",
    
    # Position limits
    "max_consecutive_buys_reached": "연속 매수 횟수 제한 도달",
    "max_symbol_exposure_reached": "심볼별 노출 한도 도달",
    "insufficient_cash": "현금 부족",
    "insufficient_asset_balance": "자산 잔고 부족",
    
    # Position state
    "no_position_to_sell": "매도할 포지션 없음",
    "below_min_managed_position_notional": "관리 대상 포지션 금액 미만",
    "dust_position_sell_noise": "소량 포지션 (노이즈)",
    "sell_volume_zero_after_sizing": "주문 사이징 후 수량 0",
    
    # Policy / route blocks
    "uncertain_regime_blocked": "불확실 시장 레짐 차단",
    "trend_strategy_route_blocked": "추적 전략 레짐 불일치",
    "range_strategy_route_blocked": "평균회귀 전략 레짐 불일치",
    "sideway_filter_blocked": "횡보장 필터 차단",
    "market_regime_sideways_hold": "횡보장 Hold",
    "blocked_time_window": "블랙아웃 시간대",
    "higher_tf_bias_mismatch": "상위 시간대 바이어스 불일치",
    
    # Execution / preview
    "preview_blocked": "주문 프리뷰 차단",
    "live_mode_disabled": "라이브 모드 비활성화",
    "live_trading_not_confirmed": "라이브 트레이딩 미확인",
    "order_below_exchange_rules_or_balance": "거래소 규칙/잔고 위반",
    
    # Cooldown / allocation
    "cooldown_active": "쿨다운 기간 중",
    "insufficient_krw_balance": "KRW 잔고 부족",
    "below_meaningful_order_notional_or_total_exposure_limit": "의미 있는 주문 금액 미만 또는 총 노출 한도",
    "total_exposure_limit": "총 노출 한도 도달",
    "meaningful_order_notional": "의미 있는 주문 금액 미만",
    
    # Signal quality
    "non_actionable_signal": "실행 가능한 신호 없음",
    
    # Errors
    "exchange_reject": "거래소 거절",
    "exchange_timeout": "거래소 타임아웃",
    "api_error": "API 오류",
}


def _format_reason_human(reason: str) -> str:
    """Convert reason code to human-readable Korean explanation."""
    return REASON_CODES.get(reason, reason)


def _log_skip(action: str, symbol: str, strategy: str, reason: str, extra: dict = None):
    """
    Log a skipped/rejected order with structured format.
    
    Format: [{action}_SKIP] symbol | strategy | reason_code | human_reason | extra_metrics
    """
    human_reason = _format_reason_human(reason)
    trace_id = extra.get("trace_id", "N/A") if extra else "N/A"
    
    # Key metrics extraction
    metrics = []
    if extra:
        if "notional" in extra:
            metrics.append(f"notional={extra['notional']:,.0f}KRW")
        if "min_order_notional" in extra:
            metrics.append(f"min={extra['min_order_notional']:,.0f}KRW")
        if "consecutive_buys" in extra:
            metrics.append(f"consecutive={extra['consecutive_buys']}")
        if "max_consecutive_buys" in extra:
            metrics.append(f"max={extra['max_consecutive_buys']}")
        if "cash_balance" in extra:
            metrics.append(f"cash={extra['cash_balance']:,.0f}KRW")
        if "position_value" in extra:
            metrics.append(f"pos_value={extra['position_value']:,.0f}KRW")
        if "managed_notional" in extra:
            metrics.append(f"managed={extra['managed_notional']:,.0f}KRW")
        if "min_managed_position_notional" in extra:
            metrics.append(f"min_managed={extra['min_managed_position_notional']:,.0f}KRW")
    
    metrics_str = " | ".join(metrics) if metrics else ""
    logger.warning(
        f"[{action.upper()}_SKIP] {symbol} | {strategy} | {reason} | {human_reason}"
        + (f" | {metrics_str}" if metrics_str else "")
        + (f" | trace={trace_id}" if trace_id != "N/A" else "")
    )


def _log_execute(action: str, symbol: str, strategy: str, order: dict, trace_id: str = None):
    """
    Log an executed order with structured format.
    
    Format: [{action}_OK] symbol | strategy | size | price | notional | reason
    """
    size = order.get("approved_size", 0)
    price = order.get("execution_price", 0)
    notional = order.get("notional_value", size * price)
    reason = order.get("reason", "")[:60]
    
    logger.info(
        f"[{action.upper()}_OK] {symbol} | {strategy} | size={size:.8f} | price={price:,.0f} | "
        f"notional={notional:,.0f}KRW | reason={reason}"
        + (f" | trace={trace_id}" if trace_id else "")
    )


def _log_fail(symbol: str, strategy: str, error_type: str, error_msg: str, trace_id: str = None):
    """
    Log an execution/API failure.
    
    Format: [ORDER_FAIL] symbol | strategy | error_type | error_msg
    """
    logger.error(
        f"[ORDER_FAIL] {symbol} | {strategy} | {error_type} | {error_msg}"
        + (f" | trace={trace_id}" if trace_id else "")
    )


def run_executor_cycle():
    """
    모든 심볼에 대해 트레이딩 사이클을 실행합니다.
    """
    cycle_trace_id = str(uuid.uuid4())[:8]
    logger.info("=" * 60)
    logger.info(f"Executor cycle started at {datetime.now(timezone.utc).isoformat()} | trace={cycle_trace_id}")
    
    try:
        market_data = get_market_data_service()
        trading_cycle = get_trading_cycle_service()
        broker = get_paper_broker()
        run_history = get_run_history_service()
        
        # 현재 포지션 확인
        portfolio = broker.portfolio_snapshot()
        position_count = len([p for p in portfolio.get("positions", {}).values() if p.get("quantity", 0) > 0])
        cash_balance = portfolio.get('cash_balance', 0)
        total_equity = portfolio.get('total_equity', 0)
        
        logger.info(f"Current positions: {position_count}")
        logger.info(f"Cash balance: {cash_balance:,.0f} KRW")
        logger.info(f"Total equity: {total_equity:,.0f} KRW")
        
        results = []
        skip_counts = {}  # Aggregate skip reasons for summary
        execute_counts = {"buy": 0, "sell": 0}
        
        # 각 심볼에 대해 트레이딩 사이클 실행
        for symbol in settings.symbols:
            symbol_trace_id = str(uuid.uuid4())[:8]
            try:
                # 최근 캔들 가져오기 (5m timeframe)
                candles = market_data.get_recent_candles("live", symbol, "5m", limit=10)
                
                if len(candles) < 8:
                    logger.warning(f"[{symbol}] Insufficient candles ({len(candles)}), skipping")
                    continue
                
                current_price = candles[-1].close
                logger.debug(f"[{symbol}] Current price: {current_price:,.0f} | trace={symbol_trace_id}")
                
                # 각 전략 실행
                for strategy_name in settings.enabled_strategies:
                    try:
                        result = trading_cycle.run(strategy_name, candles)
                        
                        signal = result.get("signal", {})
                        action = signal.get("action", "hold")
                        broker_result = result.get("broker_result")
                        reason = signal.get("reason", "")
                        
                        # 청산 신호 로깅
                        if action == "sell" and broker_result is None:
                            logger.debug(
                                f"[{symbol}] {strategy_name}: SELL signal generated but no broker_result - "
                                f"reason={reason[:80]}"
                            )
                        
                        if broker_result:
                            status = broker_result.get("status")
                            trace_id = broker_result.get("trace_id", symbol_trace_id)
                            
                            if status == "recorded":
                                order = broker_result.get("order", {})
                                _log_execute(action, symbol, strategy_name, order, trace_id)
                                execute_counts[action] = execute_counts.get(action, 0) + 1
                                
                            elif status == "rejected":
                                reject_reason = broker_result.get("reason", "unknown")
                                
                                # Aggregate skip counts
                                skip_counts[reject_reason] = skip_counts.get(reject_reason, 0) + 1
                                
                                # Extract extra metrics for structured logging
                                extra = {
                                    "trace_id": trace_id,
                                    "min_order_notional": broker_result.get("min_order_notional"),
                                    "consecutive_buys": broker_result.get("max_consecutive_buys"),
                                    "max_consecutive_buys": broker_result.get("max_consecutive_buys"),
                                    "cash_balance": broker_result.get("cash_balance"),
                                    "position_value": broker_result.get("position_value"),
                                    "managed_notional": broker_result.get("managed_notional"),
                                    "min_managed_position_notional": broker_result.get("min_managed_position_notional"),
                                }
                                # Clean None values
                                extra = {k: v for k, v in extra.items() if v is not None}
                                
                                _log_skip(action, symbol, strategy_name, reject_reason, extra)
                        
                        results.append({
                            "symbol": symbol,
                            "strategy": strategy_name,
                            "signal": signal,
                            "broker_result": broker_result,
                        })
                        
                    except Exception as e:
                        _log_fail(symbol, strategy_name, "strategy_error", str(e), symbol_trace_id)
                        logger.error(f"[{symbol}] Strategy {strategy_name} error: {e}")
                        
            except Exception as e:
                _log_fail(symbol, "N/A", "market_data_error", str(e), symbol_trace_id)
                logger.error(f"[{symbol}] Market data error: {e}")
        
        # 실행 기록 저장
        run_history.record("executor_cycle", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": cycle_trace_id,
            "symbols_processed": len(settings.symbols),
            "results_count": len(results),
            "execute_counts": execute_counts,
            "skip_counts": skip_counts,
            "results": results,
            "portfolio_after": broker.portfolio_snapshot(),
        })
        
        # 최종 포트폴리오 요약
        final_portfolio = broker.portfolio_snapshot()
        logger.info("-" * 60)
        logger.info(f"Cycle completed | trace={cycle_trace_id}")
        logger.info(f"Executed: BUY={execute_counts.get('buy', 0)} SELL={execute_counts.get('sell', 0)}")
        
        # Skip summary
        if skip_counts:
            logger.info("Skip reasons summary:")
            for reason, count in sorted(skip_counts.items(), key=lambda x: -x[1])[:10]:
                human = _format_reason_human(reason)
                logger.info(f"  {reason}: {count} ({human})")
        
        logger.info(f"Final cash: {final_portfolio.get('cash_balance', 0):,.0f} KRW")
        logger.info(f"Final equity: {final_portfolio.get('total_equity', 0):,.0f} KRW")
        logger.info(f"Total realized PnL: {final_portfolio.get('total_realized_pnl', 0):,.0f} KRW")
        
        # 포지션 상세 출력
        positions = final_portfolio.get("positions", {})
        for sym, pos in positions.items():
            qty = pos.get("quantity", 0)
            if qty > 0:
                avg_price = pos.get("average_price", 0)
                market_price = pos.get("market_price", 0)
                pnl = pos.get("unrealized_pnl", 0)
                logger.info(f"  [{sym}] Qty: {qty:.4f}, Avg: {avg_price:,.0f}, Current: {market_price:,.0f}, PnL: {pnl:,.0f}")
        
        logger.info("=" * 60)
        
        return {"status": "success", "results": results, "trace_id": cycle_trace_id}
        
    except Exception as e:
        logger.error(f"Executor cycle failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    result = run_executor_cycle()
    sys.exit(0 if result.get("status") == "success" else 1)
