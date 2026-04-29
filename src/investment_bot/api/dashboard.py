from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from investment_bot.services.container import (
    get_ledger_store,
    get_visualization_service,
    get_run_history_service,
)

router = APIRouter()


@router.get("/dashboard/summary", response_class=HTMLResponse)
def dashboard_summary():
    ledger_store = get_ledger_store()
    visualization_service = get_visualization_service()
    run_history_service = get_run_history_service()

    ledger = ledger_store.load() or {}
    trade_logs = ledger.get("trade_logs", [])
    stats = visualization_service.summarize_profit_structure()
    history = run_history_service.list_recent()

    html = f"""
    <html>
    <head><title>Investment Bot Dashboard</title></head>
    <body>
      <h1>Investment Bot Dashboard</h1>
      <h2>Ledger (Recent Trades)</h2>
      <pre>{trade_logs[-10:]}</pre>
      <h2>Stats Summary</h2>
      <pre>{stats}</pre>
      <h2>Recent Run History</h2>
      <pre>{history[:5]}</pre>
    </body>
    </html>
    """
    return html
