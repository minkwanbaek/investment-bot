# Investment Bot

AI-assisted crypto investment bot built iteratively.

## Current phase
Phase 3 / Controlled Operations:
- Deterministic paper-trading prototype is operational
- Replay/backtest, semi-live, shadow, and read-only exchange flows are available
- Live execution remains safety-blocked behind explicit mode + confirmation controls

## Principles
- Build small, validate fast
- Start with paper trading before live execution
- Prefer deterministic strategy/risk logic over LLM-driven order decisions
- Optimize for low external API cost
- Keep live trading disabled by default until read-only, shadow, and rule-validation paths are all verified

## Run
```bash
cd projects/investment-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
uvicorn investment_bot.main:app --reload
```

## Test
```bash
cd projects/investment-bot
source .venv/bin/activate
pytest -q
```

## Configuration
- Default runtime config lives in `config/app.yml`
- Override config file path with `INVESTMENT_BOT_CONFIG_PATH`
- Environment variables can still override individual settings
- Paper ledger persistence path defaults to `data/paper_ledger.json` and can be overridden with `INVESTMENT_BOT_LEDGER_PATH`
- Candle store path defaults to `data/candles.json` and can be overridden with `INVESTMENT_BOT_CANDLE_STORE_PATH`
- Run history path defaults to `data/run_history.json`
- Upbit read-only keys are loaded from `.env` via `UPBIT_ACCESS_KEY` / `UPBIT_SECRET_KEY`
- Live mode controls: `INVESTMENT_BOT_LIVE_MODE` (`paper|shadow|live`), `INVESTMENT_BOT_CONFIRM_LIVE_TRADING` (`true|false`)
- Execution cost defaults: `INVESTMENT_BOT_TRADING_FEE_PCT=0.05`, `INVESTMENT_BOT_SLIPPAGE_PCT=0.05`
- Safety limits: `min_order_notional=0` by default, `max_consecutive_buys=3`, `max_symbol_exposure_pct=25` (configurable via `config/app.yml`)

## API
- `GET /health` - service health plus active symbols/base currency
- `GET /config` - resolved runtime settings
- `GET /config/validate` - validate resolved runtime settings and report issues/warnings
- `GET /strategies` - registered and enabled strategies
- `GET /paper/portfolio` - paper portfolio snapshot plus threshold-based alerts
- `GET /paper/export` - export current paper broker state
- `POST /paper/reset` - reset paper broker state to clean starting cash
- `GET /runs?limit=...` - list recent live tests / dry runs / backtests
- `GET /runs/summary?limit=...` - operator dashboard summary for recent runs, stop reasons, and latest portfolio snapshot
- `GET /visualizations/profit-structure?limit=...` - chart-ready equity curve / PnL waterfall / stop-reason aggregates for dashboarding
- `POST /runs/reset` - clear run history
- `GET /market-data/adapters` - available market-data adapters (`mock`, `replay`, `live`)
- `GET /exchange/upbit/status` - verify whether Upbit credentials are configured
- `GET /exchange/upbit/markets` - fetch Upbit market list (public)
- `GET /exchange/upbit/balances` - fetch Upbit account balances (private, read-only)
- `GET /exchange/upbit/rules?symbol=...` - inspect Upbit market rules and minimum notional assumptions for a symbol
- `GET /exchange/upbit/normalize-price?symbol=...&price=...` - normalize a requested price to the current Upbit tick-size ladder
- `POST /cycle/shadow` - run one shadow-mode cycle using live market data + real account read-only balances, without submitting a live order
- `POST /exchange/upbit/orders/preview` - preview a live order against Upbit tick/min-notional rules without sending it
- `POST /exchange/upbit/orders/submit` - currently blocked unless live mode + confirmation are explicitly enabled; returns the next order payload shape for the future live adapter

## Practical status
- **Working now:** paper trading, replay backtests, semi-live paper cycles, shadow cycles against real Upbit balances, run history, dashboard summary, rule/tick-size inspection, guarded live order previews
- **Intentionally blocked now:** real live order submission
- **Next unlock step:** implement the actual Upbit order adapter behind the existing guarded submit flow
- `GET /market-data/live/test?symbol=...&timeframe=...&limit=...` - probe live public market data and store a run-history entry
- `GET /market-data/stored?symbol=...&timeframe=...&limit=...` - read stored candles from the local candle store
- `GET /market-data/stored/export` - export all stored candle series metadata and payload
- `POST /market-data/stored/reset` - clear stored candle series
- `POST /market-data/mock/seed` - seed mock candles for a symbol/timeframe
- `POST /market-data/replay/load` - load replay candles for a symbol/timeframe
- `POST /market-data/replay/advance` - advance replay cursor
- `POST /cycle/dry-run` - run one strategy cycle against submitted candles and record approved paper order at the latest candle price
- `POST /cycle/from-adapter` - run one strategy cycle from a configured market-data adapter
- `POST /backtest/replay` - run a replay-based multi-step backtest and return step-by-step results plus summary metrics
- `POST /cycle/semi-live` - fetch live public candles once and execute one semi-live paper cycle
- `POST /cycle/semi-live/batch` - run a small semi-live batch loop for a requested number of iterations with fail-safe stopping
