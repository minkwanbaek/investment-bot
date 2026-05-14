from pathlib import Path

from investment_bot.core.settings import get_settings


def _load_with_config(monkeypatch, config_path: str):
    monkeypatch.setenv("INVESTMENT_BOT_CONFIG_PATH", config_path)
    get_settings.cache_clear()
    return get_settings()


def test_dev_config_is_paper_and_unconfirmed(monkeypatch):
    settings = _load_with_config(monkeypatch, "config/dev.yml")
    assert settings.environment == "dev"
    assert settings.live_mode == "paper"
    assert settings.confirm_live_trading is False
    assert settings.auto_trade_enabled is False


def test_prd_config_is_live_and_confirmed(monkeypatch):
    settings = _load_with_config(monkeypatch, "config/prd.yml")
    assert settings.environment == "prd"
    assert settings.live_mode == "live"
    assert settings.confirm_live_trading is True
    assert settings.auto_trade_enabled is True


def test_ralph_context_files_exist():
    base = Path("ops/ralph")
    assert (base / "RUN_CONTEXT.md").exists()
    assert (base / "CURRENT_STRATEGY.md").exists()
    assert (base / "BACKTEST_SUMMARY.md").exists()
    assert (base / "RALPH_LOG.md").exists()
