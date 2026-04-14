from fastapi import APIRouter
from investment_bot.services.container import (
    get_account_service,
    get_ledger_store,
    get_visualization_service,
    get_run_history_service,
)

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    account_service = get_account_service()
    ledger_store = get_ledger_store()
    visualization_service = get_visualization_service()
    run_history_service = get_run_history_service()

    account = account_service.get_summary()
    ledger = ledger_store.get_all()
    stats = visualization_service.generate_summary()
    history = run_history_service.get_recent()

    html = f"""
    <html>
    <head><title>Investment Bot Dashboard</title></head>
    <body>
      <h1>Investment Bot Dashboard</h1>
      <h2>Account Overview</h2>
      <pre>{account}</pre>
      <h2>Ledger (Recent Trades)</h2>
      <pre>{ledger[-10:]}</pre>
      <h2>Stats Summary</h2>
      <pre>{stats}</pre>
      <h2>Recent Run History</h2>
      <pre>{history[:5]}</pre>
    </body>
    </html>
    """
    return html