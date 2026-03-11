# Agile Roadmap

## Phase 0 - Foundations
- convert source material into project docs
- define MVP boundaries
- scaffold repository

## Phase 1 - Deterministic MVP
- market data adapter interface
- strategy interface and 3 baseline strategies
- risk controller
- paper trading engine
- API endpoints for status and dry-run cycle execution
- runtime config loading for symbols, strategy toggles, starting cash, and risk parameters

## Phase 2 - Validation
- backtest harness
- result persistence
- metrics and reporting
- parameter tuning workflow

## Phase 3 - Controlled Operations
- alerts
- operator dashboard
- exchange account read-only integration
- paper/live separation hardening
- shadow mode against real exchange balances
- guarded live-order preview flow

## Phase 4 - Selective Expansion
- multi-asset support
- multi-exchange support
- ML research module behind feature flag
