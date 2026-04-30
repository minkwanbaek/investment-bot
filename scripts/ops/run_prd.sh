#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export INVESTMENT_BOT_CONFIG_PATH="config/prd.yml"
exec uvicorn investment_bot.main:app
