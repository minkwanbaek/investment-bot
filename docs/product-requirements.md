# Product Requirements

## Functional requirements
1. Ingest market data from exchange APIs with websocket-first design where possible
2. Support strategy plugins that can be enabled/disabled independently
3. Run a risk engine that gates all orders
4. Support backtest, paper trading, and later limited live trading
5. Record orders, fills, balances, and metrics
6. Provide monitoring, alerts, and an operator-facing dashboard/API

## Non-functional requirements
- modular architecture
- recoverable failure handling
- secure secret management
- low API cost
- reproducible execution
- auditability

## Out of scope for MVP
- multi-exchange arbitrage
- market-neutral hedge execution
- autonomous ML trading in production
- mobile app
- live trading with leverage
