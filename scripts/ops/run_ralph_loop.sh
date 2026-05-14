#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

MAX_ITERATIONS="${1:-10}"
MODEL_FLAG="${RALPH_CODEX_MODEL:-}"
ITERATION_TIMEOUT_SECONDS="${RALPH_ITERATION_TIMEOUT_SECONDS:-420}"
PROMPT_FILE="$ROOT/ops/ralph/PROMPT.md"
STATE_DIR="$ROOT/ops/ralph/state"
LOG_FILE="$STATE_DIR/loop.log"
ITER_LOG="$STATE_DIR/iteration-log.md"
VENV_PY="$ROOT/.venv/bin/python"
CODEx_BIN="${CODEX_BIN:-codex}"

mkdir -p "$STATE_DIR"
export INVESTMENT_BOT_CONFIG_PATH="config/dev.yml"

if [ ! -x "$VENV_PY" ]; then
  echo "Missing virtualenv python at $VENV_PY" >&2
  exit 1
fi

if ! command -v "$CODEx_BIN" >/dev/null 2>&1; then
  echo "codex CLI not found" >&2
  exit 1
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "timeout command not found" >&2
  exit 1
fi

run_refresh() {
  "$VENV_PY" scripts/ops/refresh_ralph_context.py --config config/dev.yml
}

build_iteration_prompt() {
  local iter="$1"
  cat "$PROMPT_FILE"
  printf '\n\n[LOOP_META]\niteration: %s\nmax_iterations: %s\nconfig_path: config/dev.yml\n[/LOOP_META]\n' "$iter" "$MAX_ITERATIONS"
}

run_refresh

: > "$LOG_FILE"
echo "# Ralph loop iteration log" > "$ITER_LOG"

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "## iteration $i - $TS" | tee -a "$ITER_LOG" "$LOG_FILE"
  CMD=("$CODEx_BIN" exec --full-auto -)
  if [ -n "$MODEL_FLAG" ]; then
    CMD+=(--model "$MODEL_FLAG")
  fi
  PROMPT_TMP="$(mktemp)"
  build_iteration_prompt "$i" > "$PROMPT_TMP"
  timeout "$ITERATION_TIMEOUT_SECONDS" "${CMD[@]}" < "$PROMPT_TMP" 2>&1 | tee "$STATE_DIR/codex-iteration-$i.log" || true
  rm -f "$PROMPT_TMP"
  run_refresh
  printf '\n' | tee -a "$ITER_LOG" "$LOG_FILE" >/dev/null
  sleep 1
done
