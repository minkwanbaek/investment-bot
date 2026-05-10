#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export INVESTMENT_BOT_CONFIG_PATH="config/prd.yml"
export INVESTMENT_BOT_HOST="${INVESTMENT_BOT_HOST:-127.0.0.1}"
export INVESTMENT_BOT_PORT="${INVESTMENT_BOT_PORT:-8000}"
exec .venv/bin/python -m uvicorn investment_bot.main:app --host "$INVESTMENT_BOT_HOST" --port "$INVESTMENT_BOT_PORT"
