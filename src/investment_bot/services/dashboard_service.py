from dataclasses import dataclass
import re
from typing import Any


@dataclass
class DashboardService:
    def reason_to_korean(self, reason: str) -> str:
        """기술적 파라미터를 사람이 읽기 쉬운 한국어로 변환"""
        if not reason:
            return ""
        
        # short_ma, long_ma, trend_gap_pct, momentum_pct 파싱
        short_ma = None
        long_ma = None
        trend_gap_pct = None
        momentum_pct = None
        deviation = None
        
        # short_ma=xxx, long_ma=xxx 패턴
        short_match = re.search(r'short_ma=([\d.]+)', reason)
        long_match = re.search(r'long_ma=([\d.]+)', reason)
        trend_match = re.search(r'trend_gap_pct=(-?[\d.]+)', reason)
        momentum_match = re.search(r'momentum_pct=(-?[\d.]+)', reason)
        deviation_match = re.search(r'deviation=(-?[\d.]+)', reason)
        
        if short_match:
            short_ma = float(short_match.group(1))
        if long_match:
            long_ma = float(long_match.group(1))
        if trend_match:
            trend_gap_pct = float(trend_match.group(1))
        if momentum_match:
            momentum_pct = float(momentum_match.group(1))
        if deviation_match:
            deviation = float(deviation_match.group(1))
        
        # 평균 기간 추정 (short=3 일, long=5 일로 가정)
        short_period = 3
        long_period = 5
        
        # mean_reversion 케이스
        if deviation is not None and trend_gap_pct is None:
            deviation_pct = abs(deviation) * 100
            if deviation < 0:
                return f"평균가 대비 {deviation_pct:.2f}% 하락, 회귀 신호"
            else:
                return f"평균가 대비 {deviation_pct:.2f}% 상승, 회귀 신호"
        
        # trend + momentum 케이스
        if trend_gap_pct is not None:
            trend_pct = abs(trend_gap_pct) * 100
            
            if trend_gap_pct > 0 and momentum_pct is not None and momentum_pct > 0:
                return f"{short_period}일 평균가가 {long_period}일 평균가보다 {trend_pct:.2f}% 높음, 상승 모멘텀 감지"
            elif trend_gap_pct > 0:
                return f"{short_period}일 평균가가 {long_period}일 평균가보다 {trend_pct:.2f}% 높음"
            elif trend_gap_pct < 0 and momentum_pct is not None and momentum_pct < 0:
                return f"{short_period}일 평균가가 {long_period}일 평균가보다 {trend_pct:.2f}% 낮음, 하락 모멘텀 감지"
            elif trend_gap_pct < 0:
                return f"{short_period}일 평균가가 {long_period}일 평균가보다 {trend_pct:.2f}% 낮음"
        
        # fallback: 원본 반환
        return reason

    def extract_policy_observations(self, trade_logs: list[dict]) -> list[dict]:
        """Extract latest policy observations from trade logs for observability.
        
        Returns list of policy observations with:
        - policy_name: which policy was evaluated
        - policy_value: the policy threshold/limit
        - current_state: the actual state value
        - block_reason: if blocked, why (None if passed)
        """
        observations = []
        
        # Extract from most recent trades (last 10)
        recent_logs = list(trade_logs)[-10:] if trade_logs else []
        
        for log in recent_logs:
            review = log.get("review", {})
            meta = log.get("meta", {})
            
            # Route policy observations
            if meta.get("block_reason"):
                block_reasons = str(meta.get("block_reason", "")).split(",")
                for reason in block_reasons:
                    reason = reason.strip()
                    if reason:
                        observations.append({
                            "policy_name": "route_filter",
                            "policy_value": "regime-based routing rules",
                            "current_state": meta.get("market_regime", "unknown"),
                            "block_reason": reason,
                            "timestamp": log.get("entry_time"),
                            "symbol": log.get("symbol"),
                        })
            
            # Risk controller observations
            if review.get("risk_mode"):
                observations.append({
                    "policy_name": "risk_mode",
                    "policy_value": review.get("risk_mode", "normal"),
                    "current_state": {
                        "losing_streak": review.get("losing_streak", 0),
                        "volatility_state": review.get("volatility_state", "normal"),
                    },
                    "block_reason": None if review.get("approved") else "risk_mode_size_reduction",
                    "timestamp": log.get("entry_time"),
                    "symbol": log.get("symbol"),
                })
            
            # Exposure observations (if available in broker_result)
            broker_result = log.get("broker_result", {})
            if broker_result.get("block_reason"):
                observations.append({
                    "policy_name": "exposure_limit",
                    "policy_value": broker_result.get("policy_limit"),
                    "current_state": broker_result.get("current_exposure"),
                    "block_reason": broker_result.get("block_reason"),
                    "timestamp": log.get("entry_time"),
                    "symbol": log.get("symbol"),
                })
        
        # Deduplicate by (policy_name, block_reason, timestamp)
        seen = set()
        unique = []
        for obs in observations:
            key = (obs["policy_name"], obs.get("block_reason"), obs.get("timestamp"))
            if key not in seen:
                seen.add(key)
                unique.append(obs)
        
        return unique[-5:]  # Return last 5 unique observations
    def build_trade_log_dashboard(self, summary: dict, trade_logs: list[dict], limit: int = 20, policy_snapshot: dict | None = None) -> dict:
        recent = list(trade_logs)[-limit:]
        recent.reverse()

        # 프론트엔드 호환: price, volume, created_at, reason 별칭 추가
        recent_trades = []
        for trade in recent:
            trade_copy = dict(trade)
            trade_copy["price"] = trade.get("entry_price")
            trade_copy["volume"] = trade.get("quantity")
            trade_copy["created_at"] = trade.get("entry_time")
            trade_copy["reason"] = trade.get("entry_reason")
            trade_copy["reason_kr"] = self.reason_to_korean(trade.get("entry_reason", ""))
            recent_trades.append(trade_copy)

        # Extract policy observations for observability
        policy_observations = self.extract_policy_observations(trade_logs)

        return {
            "summary_cards": {
                "max_drawdown": summary.get("overall", {}).get("all", {}).get("max_drawdown"),
                "win_rate": summary.get("overall", {}).get("all", {}).get("win_rate"),
                "profit_factor": summary.get("overall", {}).get("all", {}).get("profit_factor"),
                "total_net_pnl": summary.get("overall", {}).get("all", {}).get("total_net_pnl"),
            },
            "equity_curve": self._build_equity_curve(recent),
            "recent_trades": recent_trades,
            "by_strategy_version": summary.get("by_strategy_version", {}),
            "by_market_regime": summary.get("by_market_regime", {}),
            "policy_snapshot": policy_snapshot,
            "policy_observations": policy_observations,
        }

    def _build_equity_curve(self, trade_logs: list[dict]) -> list[dict]:
        equity = 0.0
        points = []
        ordered = sorted(trade_logs, key=lambda item: item.get('entry_time') or '')
        for idx, item in enumerate(ordered, start=1):
            equity += float(item.get('net_pnl', 0.0) or 0.0)
            points.append({
                'index': idx,
                'trade_id': item.get('trade_id'),
                'entry_time': item.get('entry_time'),
                'equity': round(equity, 4),
            })
        return points
