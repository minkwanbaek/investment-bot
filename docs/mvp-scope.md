# MVP Scope

## Objective
Deliver a safe first slice that proves the operating model.

## MVP includes
- Single exchange integration target: Upbit-compatible abstraction
- Single symbol focus: BTC/KRW
- Deterministic strategies only:
  - trend following
  - mean reversion
  - DCA scheduler
- Risk controls:
  - max risk per trade
  - daily loss guard
  - max drawdown halt
- Paper trading ledger
- FastAPI service with health/config/strategy endpoints
- Structured config files
- Basic test coverage for signal/risk rules

## MVP excludes
- live order execution
- multi-exchange portfolio routing
- machine learning prediction services
- advanced dashboards
