from dataclasses import dataclass


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
        # Regime names unified: sideways (not ranging), trend_up/trend_down (not uptrend/downtrend), uncertain (not mixed/unknown)
        if symbol == "BTC/KRW":
            if regime in {"trend_up", "trend_down", "sideways"}:
                return ["trend_following"]
            if regime in {"sideways", "uncertain"}:
                return ["dca"]
            return []
        if symbol == "ETH/KRW":
            if regime in {"trend_up", "sideways"}:
                return ["trend_following"]
            if regime in {"trend_down", "sideways", "uncertain"}:
                return ["mean_reversion"]
            return []
        if symbol == "SOL/KRW":
            if regime in {"trend_up", "sideways"}:
                return ["trend_following"]
            if regime in {"trend_down", "sideways", "uncertain"}:
                return ["mean_reversion", "dca"]
            return []
        return ["trend_following"] if regime in {"trend_up", "trend_down", "sideways"} else []
