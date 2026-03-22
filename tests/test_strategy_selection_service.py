from investment_bot.services.strategy_selection_service import StrategySelectionService


svc = StrategySelectionService()


def test_btc_uptrend_allows_trend_following():
    assert svc._allowed_strategies("BTC/KRW", "uptrend") == ["trend_following"]


def test_btc_downtrend_allows_trend_following():
    assert svc._allowed_strategies("BTC/KRW", "downtrend") == ["trend_following"]


def test_btc_ranging_allows_dca():
    assert svc._allowed_strategies("BTC/KRW", "ranging") == ["dca"]


def test_btc_mixed_allows_dca():
    assert svc._allowed_strategies("BTC/KRW", "mixed") == ["dca"]


def test_btc_unknown_regime_returns_empty():
    assert svc._allowed_strategies("BTC/KRW", "unknown") == []


def test_eth_uptrend():
    assert svc._allowed_strategies("ETH/KRW", "uptrend") == ["trend_following"]


def test_eth_ranging():
    assert "mean_reversion" in svc._allowed_strategies("ETH/KRW", "ranging")


def test_sol_ranging():
    allowed = svc._allowed_strategies("SOL/KRW", "ranging")
    assert "mean_reversion" in allowed
    assert "dca" in allowed


def test_choose_picks_highest_score():
    candidates = [
        {"strategy_name": "dca", "score": 30.0},
        {"strategy_name": "trend_following", "score": 50.0},
    ]
    result = svc.choose("BTC/KRW", "uptrend", candidates)
    assert result["strategy_name"] == "trend_following"


def test_choose_filters_by_regime():
    candidates = [
        {"strategy_name": "trend_following", "score": 80.0},
        {"strategy_name": "dca", "score": 40.0},
    ]
    result = svc.choose("BTC/KRW", "ranging", candidates)
    assert result["strategy_name"] == "dca"


def test_choose_returns_none_when_no_match():
    candidates = [
        {"strategy_name": "mean_reversion", "score": 50.0},
    ]
    result = svc.choose("BTC/KRW", "uptrend", candidates)
    assert result is None
