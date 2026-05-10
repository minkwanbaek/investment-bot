from dataclasses import dataclass

from investment_bot.core.settings import get_settings
from investment_bot.core.trading_policy import build_trading_policy


@dataclass
class StrategySelectionService:
    def choose(self, symbol: str, regime: str, candidates: list[dict], min_order_notional: float | None = None) -> dict | None:
        filtered = [
            c for c in candidates
            if (c["strategy_name"] in self._allowed_strategies(symbol=symbol, regime=self._candidate_regime(c, fallback=regime)) or c.get("action") == "sell")
            and not self._is_trend_down_spot_buy(c, regime=self._candidate_regime(c, fallback=regime))
            and not self._is_unmanaged_sell(c)
            and not self._is_below_min_order_buy(c, min_order_notional=min_order_notional)
            and c.get("action") != "hold"
        ]
        if not filtered:
            return None
        filtered.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        return filtered[0]

    def _candidate_regime(self, candidate: dict, fallback: str) -> str:
        regime = candidate.get("regime")
        if isinstance(regime, dict):
            return str(regime.get("regime") or fallback)
        return str(regime or fallback)

    def _is_unmanaged_sell(self, candidate: dict) -> bool:
        if candidate.get("action") != "sell":
            return False
        asset = candidate.get("asset") or {}
        return asset.get("managed") is False

    def _is_below_min_order_buy(self, candidate: dict, min_order_notional: float | None = None) -> bool:
        if candidate.get("action") != "buy":
            return False
        review = candidate.get("review") or {}
        if "target_notional" not in review and "target_notional" not in candidate:
            return False
        target_notional = float(review.get("target_notional", candidate.get("target_notional", 0.0)) or 0.0)
        minimum = float(get_settings().min_order_notional if min_order_notional is None else min_order_notional or 0.0)
        return target_notional < minimum

    def _is_trend_down_spot_buy(self, candidate: dict, regime: str) -> bool:
        normalized_regime = build_trading_policy(get_settings()).normalize_regime(regime)
        return (
            normalized_regime == "trend_down"
            and candidate.get("strategy_name") == "trend_following"
            and candidate.get("action") == "buy"
        )

    def _allowed_strategies(self, symbol: str, regime: str) -> list[str]:
        symbol = symbol.upper()
        normalized_regime = build_trading_policy(get_settings()).normalize_regime(regime)
        if symbol == "BTC/KRW":
            if normalized_regime in {"trend_up", "trend_down", "sideways"}:
                if normalized_regime == "sideways":
                    return ["trend_following", "mean_reversion", "dca"]
                if normalized_regime == "trend_down":
                    return ["trend_following", "mean_reversion", "dca"]
                return ["trend_following"]
            if normalized_regime in {"sideways", "uncertain"}:
                return ["mean_reversion", "dca"]
            return []
        if symbol == "ETH/KRW":
            if normalized_regime in {"trend_up", "trend_down"}:
                return ["trend_following", "mean_reversion", "dca"] if normalized_regime == "trend_down" else ["trend_following"]
            if normalized_regime == "uncertain":
                return ["mean_reversion", "dca"]
            if normalized_regime == "sideways":
                return ["trend_following", "mean_reversion", "dca"]
            return []
        if symbol == "SOL/KRW":
            if normalized_regime == "trend_up":
                return ["trend_following"]
            if normalized_regime == "sideways":
                return ["trend_following", "mean_reversion", "dca"]
            if normalized_regime in {"trend_down", "uncertain"}:
                return ["mean_reversion", "dca"]
            return []
        if normalized_regime == "sideways":
            return ["trend_following", "mean_reversion", "dca"]
        if normalized_regime == "uncertain":
            return ["mean_reversion", "dca"]
        if normalized_regime == "trend_up":
            return ["trend_following"]
        if normalized_regime == "trend_down":
            return ["trend_following", "mean_reversion", "dca"]
        return []
