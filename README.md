# Investment Bot

AI-assisted crypto investment bot built iteratively.

## Current phase
Phase 0 / Iteration 1:
- Documentation-first project framing
- MVP architecture scaffold
- FastAPI health/config surface
- Strategy/risk domain skeletons

## Principles
- Build small, validate fast
- Start with paper trading before live execution
- Prefer deterministic strategy/risk logic over LLM-driven order decisions
- Optimize for low external API cost

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
- `POST /runs/reset` - clear run history
- `GET /market-data/adapters` - available market-data adapters (`mock`, `replay`, `live`)
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
