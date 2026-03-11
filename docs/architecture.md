# Architecture

## Layers
1. API layer
   - operator endpoints
   - health/status/config inspection
2. Orchestration layer
   - trading cycle scheduler
   - mode switching: backtest / paper / live
3. Domain layer
   - strategies
   - risk controller
   - signal models
4. Infrastructure layer
   - exchange adapters
   - persistence
   - alerting

## Core design rules
- strategies propose signals
- risk controller approves, scales, or rejects
- executor is downstream of risk, never bypassing it
- paper mode is the default runtime mode until explicit graduation
- all runs emit structured records for later analysis
