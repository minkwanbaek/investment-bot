#!/usr/bin/env python3
"""
Investment Bot Executor

5 분마다 모든 심볼에 대해 트레이딩 사이클을 실행합니다.
- 진입 신호 (buy) 와 청산 신호 (sell) 모두 처리
- 로그 출력: logs/executor.log
"""

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_executor_cycle():
    """
    모든 심볼에 대해 트레이딩 사이클을 실행합니다.
    """
    logger.info("=" * 60)
    logger.info(f"Executor cycle started at {datetime.now(timezone.utc).isoformat()}")
    
    try:
        market_data = get_market_data_service()
        trading_cycle = get_trading_cycle_service()
        broker = get_paper_broker()
        run_history = get_run_history_service()
        
        # 현재 포지션 확인
        portfolio = broker.portfolio_snapshot()
        position_count = len([p for p in portfolio.get("positions", {}).values() if p.get("quantity", 0) > 0])
        logger.info(f"Current positions: {position_count}")
        logger.info(f"Cash balance: {portfolio.get('cash_balance', 0):,.0f} KRW")
        logger.info(f"Total equity: {portfolio.get('total_equity', 0):,.0f} KRW")
        
        results = []
        
        # 각 심볼에 대해 트레이딩 사이클 실행
        for symbol in settings.symbols:
            try:
                # 최근 캔들 가져오기 (5m timeframe)
                candles = market_data.get_recent_candles("live", symbol, "5m", limit=10)
                
                if len(candles) < 8:
                    logger.warning(f"[{symbol}] Insufficient candles ({len(candles)}), skipping")
                    continue
                
                current_price = candles[-1].close
                logger.info(f"[{symbol}] Current price: {current_price:,.0f}")
                
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
                            logger.info(
                                f"[{symbol}] {strategy_name}: SELL signal generated but no broker_result - "
                                f"reason={reason[:80]}"
                            )
                        
                        if broker_result:
                            status = broker_result.get("status")
                            if status == "recorded":
                                order = broker_result.get("order", {})
                                logger.info(
                                    f"[{symbol}] {strategy_name}: {action.upper()} executed - "
                                    f"size={order.get('approved_size', 0):.4f}, "
                                    f"price={order.get('execution_price', 0):,.0f}, "
                                    f"reason={order.get('reason', '')[:50]}"
                                )
                            elif status == "rejected":
                                logger.warning(
                                    f"[{symbol}] {strategy_name}: {action.upper()} rejected - "
                                    f"reason={broker_result.get('reason', '')}"
                                )
                        
                        results.append({
                            "symbol": symbol,
                            "strategy": strategy_name,
                            "signal": signal,
                            "broker_result": broker_result,
                        })
                        
                    except Exception as e:
                        logger.error(f"[{symbol}] Strategy {strategy_name} error: {e}")
                        
            except Exception as e:
                logger.error(f"[{symbol}] Market data error: {e}")
        
        # 실행 기록 저장
        run_history.record("executor_cycle", {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbols_processed": len(settings.symbols),
            "results_count": len(results),
            "results": results,
            "portfolio_after": broker.portfolio_snapshot(),
        })
        
        # 최종 포트폴리오 요약
        final_portfolio = broker.portfolio_snapshot()
        logger.info("-" * 60)
        logger.info("Cycle completed")
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
        
        return {"status": "success", "results": results}
        
    except Exception as e:
        logger.error(f"Executor cycle failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    result = run_executor_cycle()
    sys.exit(0 if result.get("status") == "success" else 1)
