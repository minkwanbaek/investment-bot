#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from investment_bot.core.settings import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Ralph loop context files from the current investment-bot config")
    parser.add_argument("--config", default="config/dev.yml", help="Config path to load before summarizing")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    ralph_dir = project_root / "ops" / "ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)

    os.environ["INVESTMENT_BOT_CONFIG_PATH"] = args.config
    get_settings.cache_clear()
    settings = get_settings()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    current_strategy = textwrap.dedent(f"""\
    [CURRENT_STRATEGY]
    strategy_name: {settings.auto_trade_strategy_name}
    version: {settings.auto_trade_strategy_version}
    last_updated: {now}

    objective: 절대 수익률 극대화
    market_scope: upbit-auth-all
    primary_timeframes: 5m,15m
    holding_profile: intraday to several hours
    strategy_family: breakout + momentum

    universe_selection:
    - symbols: {', '.join(settings.symbols)}
    - dynamic_symbol_selection: {settings.dynamic_symbol_selection}
    - dynamic_symbol_top_n: {settings.dynamic_symbol_top_n}

    entry_logic:
    - strategy_name: {settings.auto_trade_strategy_name}
    - timeframe: {settings.auto_trade_timeframe}
    - limit: {settings.auto_trade_limit}

    exit_logic:
    - stop_loss_pct: {settings.auto_trade_stop_loss_pct}
    - partial_take_profit_pct: {settings.auto_trade_partial_take_profit_pct}
    - trailing_stop_pct: {settings.auto_trade_trailing_stop_pct}
    - max_holding_minutes: {settings.max_holding_minutes}

    position_sizing:
    - base_entry_notional: {settings.auto_trade_base_entry_notional}
    - target_allocation_pct: {settings.auto_trade_target_allocation_pct}
    - max_total_exposure_pct: {settings.auto_trade_max_total_exposure_pct}
    - min_managed_position_notional: {settings.auto_trade_min_managed_position_notional}

    risk_controls:
    - max_risk_per_trade_pct: {settings.max_risk_per_trade_pct}
    - max_daily_loss_pct: {settings.max_daily_loss_pct}
    - max_drawdown_pct: {settings.max_drawdown_pct}
    - higher_tf_bias_filter_enabled: {settings.higher_tf_bias_filter_enabled}
    - high_volatility_defense_enabled: {settings.high_volatility_defense_enabled}

    execution_constraints:
    - fee applied
    - slippage applied
    - liquidity required
    - minimum order size required
    - live_mode: {settings.live_mode}
    - confirm_live_trading: {settings.confirm_live_trading}

    known_strengths:
    - update after observed promising runs

    known_weaknesses:
    - update after observed reject runs

    current_hypothesis:
    - prioritize the next single modification with the highest expected impact on absolute profit

    [/CURRENT_STRATEGY]
    """)
    (ralph_dir / 'CURRENT_STRATEGY.md').write_text(current_strategy, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
