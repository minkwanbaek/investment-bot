# Symbol Validation Report
Date: 2026-04-11 14:24 UTC

## Summary
- Total symbols tested: 50
- Passed: 50
- Failed: 0
- Removed: 0

## Validation Method
Each symbol was tested against Upbit API:
- Endpoint: GET https://api.upbit.com/v1/candles/minutes/5?market=KRW-{SYMBOL}&count=20
- Pass criteria: HTTP 200 OK
- Fail criteria: HTTP 404, 400, or any error

## Special Checks
- MATIC/KRW: Returns 404 (confirmed) - NOT in current symbol list ✓
- LTC/KRW: No duplicates found ✓
- USDT/BUSD/USDC: No stablecoins found ✓

## Result
All 50 symbols in config/app.yml are valid KRW markets on Upbit.
No changes required to config/app.yml.

## Passed Symbols (50)
BTC, FF, ETH, XRP, LPT, ONG, ONT, ID, TAO, COMP, RED, BLAST, SOL, DOGE, CFG, MON, CKB, RAY, KITE, WLFI, XPL, MMT, F, EDGE, BARD, ADA, NEO, ANIME, AVNT, MET2, BLUR, ONDO, WAL, WLD, ZBT, ORDER, XLM, TRUMP, DRIFT, ZK, SUI, SAFE, IP, ARB, ENA, VIRTUAL, MIRA, PEPE, AZTEC, MINA
