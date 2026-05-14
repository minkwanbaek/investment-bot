[CURRENT_STRATEGY]
strategy_name: trend_following
version: v1.0-dev
last_updated: 2026-04-30T11:28:19Z

objective: 절대 수익률 극대화
market_scope: upbit-auth-all
primary_timeframes: 5m,15m
holding_profile: intraday to several hours
strategy_family: breakout + momentum

universe_selection:
- symbols: BTC/KRW, ETH/KRW, SOL/KRW
- dynamic_symbol_selection: True
- dynamic_symbol_top_n: 10

entry_logic:
- strategy_name: trend_following
- timeframe: 5m
- limit: 100

exit_logic:
- stop_loss_pct: 1.5
- partial_take_profit_pct: 2.0
- trailing_stop_pct: 1.0
- max_holding_minutes: 60

position_sizing:
- base_entry_notional: 10000.0
- target_allocation_pct: 20.0
- max_total_exposure_pct: 60.0
- min_managed_position_notional: 5000.0

risk_controls:
- max_risk_per_trade_pct: 5.0
- max_daily_loss_pct: 3.0
- max_drawdown_pct: 10.0
- higher_tf_bias_filter_enabled: False
- high_volatility_defense_enabled: True

execution_constraints:
- fee applied
- slippage applied
- liquidity required
- minimum order size required
- live_mode: paper
- confirm_live_trading: False

known_strengths:
- update after observed promising runs

known_weaknesses:
- update after observed reject runs

current_hypothesis:
- prioritize the next single modification with the highest expected impact on absolute profit

[/CURRENT_STRATEGY]
