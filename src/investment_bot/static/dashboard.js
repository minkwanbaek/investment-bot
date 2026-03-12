const refreshMs = 3000;

function won(value) {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(Number(value));
}

function pct(value) {
  if (value === null || value === undefined) return '-';
  return `${Number(value).toFixed(2)}%`;
}

function timeAgo(isoString) {
  if (!isoString) return '-';
  const diff = Date.now() - new Date(isoString).getTime();
  const sec = Math.max(0, Math.floor(diff / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

function latestRunSignal(run) {
  return run?.payload?.signal?.action || run?.payload?.decision?.signal?.action || 'n/a';
}

function brokerStatus(run) {
  return run?.payload?.broker_result?.status || run?.payload?.decision?.broker_result?.status || '-';
}

function renderCards(data) {
  const summary = data.summary || {};
  const portfolio = data.paper_portfolio?.portfolio || {};
  const latestRun = data.latest_run;
  const cards = [
    { label: 'Mode', value: data.health?.mode || '-', hint: `${data.health?.app || 'trading-bot'} · ${data.health?.environment || '-'}` },
    { label: 'Latest Equity', value: `₩${won(summary.latest_portfolio?.total_equity ?? portfolio.total_equity)}`, hint: 'paper portfolio 기준' },
    { label: 'Realized PnL', value: `₩${won(summary.latest_portfolio?.total_realized_pnl ?? portfolio.total_realized_pnl ?? 0)}`, hint: '누적 실현 손익' },
    { label: 'Unrealized PnL', value: `₩${won(summary.latest_portfolio?.total_unrealized_pnl ?? portfolio.total_unrealized_pnl ?? 0)}`, hint: '평가 손익' },
    { label: 'Latest Run', value: latestRun?.kind || '-', hint: latestRun ? timeAgo(latestRun.created_at) : '기록 없음' },
    { label: 'Signal', value: latestRunSignal(latestRun), hint: `broker: ${brokerStatus(latestRun)}` },
  ];

  document.getElementById('summary-cards').innerHTML = cards.map(card => `
    <div class="card">
      <div class="label">${card.label}</div>
      <div class="value">${card.value}</div>
      <div class="hint">${card.hint}</div>
    </div>
  `).join('');
}

function renderFeed(data) {
  const runs = data.recent_runs || [];
  document.getElementById('feed-count').textContent = `${runs.length} runs`;
  const container = document.getElementById('activity-feed');
  if (!runs.length) {
    container.className = 'feed empty';
    container.textContent = '아직 활동 기록이 없습니다.';
    return;
  }
  container.className = 'feed';
  container.innerHTML = runs.slice().reverse().map(run => {
    const signal = latestRunSignal(run);
    const kind = run.kind;
    const stopReason = run.payload?.fail_safe?.stop_reason;
    const badgeClass = signal === 'buy' || signal === 'sell' || signal === 'hold' ? signal : '';
    return `
      <div class="feed-item">
        <div class="feed-item-top">
          <span class="badge">${kind}</span>
          <span class="badge ${badgeClass}">${signal}</span>
        </div>
        <div class="meta-line">
          <span>broker: ${brokerStatus(run)}</span>
          <span>updated: ${timeAgo(run.created_at)}</span>
          ${stopReason ? `<span>stop: ${stopReason}</span>` : ''}
        </div>
      </div>
    `;
  }).join('');
}

function renderOperatorStatus(data) {
  const drift = data.drift_report || {};
  const summary = data.summary || {};
  const items = [
    { title: 'Recent run counts', body: Object.entries(summary.kind_counts || {}).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'No runs yet' },
    { title: 'Stop reasons', body: Object.entries(summary.stop_reasons || {}).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'None' },
    { title: 'Cash drift', body: drift.cash_drift ? `paper ₩${won(drift.cash_drift.paper_cash)} / shadow ₩${won(drift.cash_drift.shadow_cash)} / diff ₩${won(drift.cash_drift.difference)}` : 'shadow 기준 없음' },
    { title: 'Recommendations', body: (drift.recommendations || []).join(' · ') || 'None' },
  ];
  document.getElementById('operator-status').innerHTML = items.map(item => `
    <div class="stack-item">
      <div class="label">${item.title}</div>
      <div>${item.body}</div>
    </div>
  `).join('');
}

function renderEquityChart(data) {
  const points = data.profit_structure?.equity_curve || [];
  const container = document.getElementById('equity-chart');
  if (!points.length) {
    container.innerHTML = '<div class="empty">equity 데이터가 아직 없습니다.</div>';
    return;
  }
  const max = Math.max(...points.map(p => Number(p.total_equity || 0)), 1);
  container.innerHTML = points.slice(-12).map((point, index) => {
    const height = Math.max(8, Math.round((Number(point.total_equity || 0) / max) * 220));
    return `<div class="bar" style="height:${height}px"><span class="bar-label">${index + 1}</span></div>`;
  }).join('');
}

function renderDistribution(data) {
  const profit = data.profit_structure || {};
  const wrap = document.getElementById('distribution-chart');
  const waterfall = (profit.pnl_waterfall || []).slice(-5).map(item => {
    const total = Number(item.realized_pnl || 0) + Number(item.unrealized_pnl || 0);
    return `<div class="stack-item"><div class="label">${item.label}</div><div class="${total >= 0 ? 'pos' : 'neg'}">₩${won(total)}</div></div>`;
  }).join('');
  const kinds = Object.entries(profit.kind_counts || {}).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'No run mix yet';
  wrap.innerHTML = `
    <div class="stack-item">
      <div class="label">Recent PnL</div>
      <div class="stack">${waterfall || '<div class="muted">No pnl events yet</div>'}</div>
    </div>
    <div class="stack-item">
      <div class="label">Run mix</div>
      <div>${kinds}</div>
    </div>
  `;
}

async function loadDashboard() {
  const response = await fetch('/operator/live-dashboard?limit=20', { cache: 'no-store' });
  const data = await response.json();
  renderCards(data);
  renderFeed(data);
  renderOperatorStatus(data);
  renderEquityChart(data);
  renderDistribution(data);
  document.getElementById('last-updated').textContent = new Date().toLocaleTimeString('ko-KR');
}

async function boot() {
  document.getElementById('refresh-interval').textContent = `${refreshMs / 1000}s`;
  try {
    await loadDashboard();
  } catch (error) {
    document.getElementById('activity-feed').textContent = `대시보드 로딩 실패: ${error}`;
  }
  setInterval(async () => {
    try {
      await loadDashboard();
    } catch (error) {
      console.error(error);
    }
  }, refreshMs);
}

boot();
