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

## API
- `GET /health` - service health plus active symbols/base currency
- `GET /config` - resolved runtime settings
- `GET /strategies` - registered and enabled strategies
- `GET /paper/portfolio` - in-memory paper portfolio snapshot
- `POST /cycle/dry-run` - run one strategy cycle against submitted candles and record approved paper order
