from investment_bot.services.strategy_selection_service import StrategySelectionService


svc = StrategySelectionService()


def test_btc_uptrend_allows_trend_following():
    assert svc._allowed_strategies("BTC/KRW", "trend_up") == ["trend_following"]


def test_btc_downtrend_allows_trend_following():
    assert svc._allowed_strategies("BTC/KRW", "trend_down") == ["trend_following"]


def test_btc_sideways_allows_trend_following_due_to_symbol_policy():
    assert svc._allowed_strategies("BTC/KRW", "sideways") == ["trend_following"]


def test_btc_uncertain_allows_dca():
    assert svc._allowed_strategies("BTC/KRW", "uncertain") == ["dca"]


def test_btc_legacy_unknown_alias_maps_to_uncertain_and_allows_dca():
    assert svc._allowed_strategies("BTC/KRW", "unknown") == ["dca"]


def test_eth_trend_up():
    assert svc._allowed_strategies("ETH/KRW", "trend_up") == ["trend_following"]


def test_eth_sideways():
    assert "mean_reversion" in svc._allowed_strategies("ETH/KRW", "sideways")


def test_sol_sideways():
    allowed = svc._allowed_strategies("SOL/KRW", "sideways")
    assert "mean_reversion" in allowed
    assert "dca" in allowed


def test_choose_picks_highest_score():
    candidates = [
        {"strategy_name": "dca", "score": 30.0},
        {"strategy_name": "trend_following", "score": 50.0},
    ]
    result = svc.choose("BTC/KRW", "trend_up", candidates)
    assert result["strategy_name"] == "trend_following"


def test_choose_filters_by_regime():
    candidates = [
        {"strategy_name": "trend_following", "score": 80.0},
        {"strategy_name": "dca", "score": 40.0},
    ]
    result = svc.choose("BTC/KRW", "uncertain", candidates)
    assert result["strategy_name"] == "dca"


def test_choose_returns_none_when_no_match():
    candidates = [
        {"strategy_name": "mean_reversion", "score": 50.0},
    ]
    result = svc.choose("BTC/KRW", "trend_up", candidates)
    assert result is None
