from dataclasses import dataclass

from investment_bot.core.settings import get_settings
from investment_bot.core.trading_policy import build_trading_policy


@dataclass
class StrategySelectionService:
    def choose(self, symbol: str, regime: str, candidates: list[dict]) -> dict | None:
        allowed = self._allowed_strategies(symbol=symbol, regime=regime)
        filtered = [c for c in candidates if c["strategy_name"] in allowed]
        if not filtered:
            return None
        filtered.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        return filtered[0]

    def _allowed_strategies(self, symbol: str, regime: str) -> list[str]:
        symbol = symbol.upper()
        normalized_regime = build_trading_policy(get_settings()).normalize_regime(regime)
        if symbol == "BTC/KRW":
            if normalized_regime in {"trend_up", "trend_down", "sideways"}:
                return ["trend_following"]
            if normalized_regime in {"sideways", "uncertain"}:
                return ["dca"]
            return []
        if symbol == "ETH/KRW":
            if normalized_regime in {"trend_up", "trend_down"}:
                return ["trend_following"]
            if normalized_regime in {"trend_down", "uncertain"}:
                return ["mean_reversion"]
            if normalized_regime == "sideways":
                return ["trend_following", "mean_reversion"]
            return []
        if symbol == "SOL/KRW":
            if normalized_regime == "trend_up":
                return ["trend_following"]
            if normalized_regime == "sideways":
                return ["trend_following", "mean_reversion", "dca"]
            if normalized_regime in {"trend_down", "uncertain"}:
                return ["mean_reversion", "dca"]
            return []
        return ["trend_following"] if normalized_regime in {"trend_up", "trend_down", "sideways"} else []
