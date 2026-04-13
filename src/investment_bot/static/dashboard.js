const refreshMs = 3000;

function timeAgo(isoString) {
  if (!isoString) return '-';
  const diff = Date.now() - new Date(isoString).getTime();
  const sec = Math.max(0, Math.floor(diff / 1000));
  if (sec < 60) return `${sec}초 전`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  return `${hr}시간 전`;
}

function won(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(Number(value));
}

function qty(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return new Intl.NumberFormat('ko-KR', { minimumFractionDigits: 0, maximumFractionDigits: 4 }).format(Number(value));
}

function assetCode(symbol) {
  if (!symbol) return '';
  return String(symbol).split('/')[0] || '';
}

function renderCards(data) {
  const c = data.summary_cards || {};
  const cards = [
    {
      label: '총 손익',
      value: won(c.total_net_pnl),
      hint: '누적 순손익',
      accent: Number(c.total_net_pnl || 0) >= 0,
    },
    {
      label: '승률',
      value: c.win_rate !== undefined && c.win_rate !== null ? `${Number(c.win_rate).toFixed(2)}%` : '-',
      hint: '전체 trade 기준',
    },
    {
      label: 'Profit Factor',
      value: c.profit_factor ?? '-',
      hint: '총 이익 / 총 손실',
    },
    {
      label: 'MDD',
      value: won(c.max_drawdown),
      hint: '누적 손익 기준',
    },
  ];

  document.getElementById('summary-cards').innerHTML = cards.map((card) => `
    <div class="card ${card.accent ? 'is-accent' : ''}">
      <div class="label">${card.label}</div>
      <div class="value">${card.value}</div>
      <div class="hint">${card.hint}</div>
    </div>
  `).join('');
}

function renderFeed(data) {
  const rows = data.recent_trades || [];
  document.getElementById('feed-count').textContent = `${rows.length}건`;
  const container = document.getElementById('activity-feed');
  if (!rows.length) {
    container.className = 'feed empty';
    container.textContent = '최근 매수/매도 기록이 없습니다.';
    return;
  }
  container.className = 'feed';
  container.innerHTML = rows.map((row) => `
    <div class="feed-item">
      <div class="feed-item-top">
        <span class="badge ${row.side || ''}">${row.side || '-'}</span>
        <span class="badge">${row.symbol || '-'}</span>
      </div>
      <div class="meta-line">
        <span>진입가 ${won(row.entry_price)}</span>
        <span>수량 ${qty(row.quantity)} ${assetCode(row.symbol)}</span>
        <span>${timeAgo(row.entry_time || row.created_at)}</span>
      </div>
      <div class="reason-line">진입 근거: ${row.entry_reason || row.reason || '-'}</div>
    </div>
  `).join('');
}

function renderBucketList(containerId, mapping, formatter) {
  const el = document.getElementById(containerId);
  const entries = Object.entries(mapping || {});
  if (!entries.length) {
    el.className = 'feed empty';
    el.textContent = '데이터 없음';
    return;
  }
  el.className = 'feed';
  el.innerHTML = entries.map(([key, value]) => formatter(key, value)).join('');
}

function renderChecklist(data) {
  const el = document.getElementById('deploy-checklist');
  const items = data.items || [];
  if (!items.length) {
    el.className = 'feed empty';
    el.textContent = '체크리스트 없음';
    return;
  }
  el.className = 'feed';
  el.innerHTML = items.map((item) => `
    <div class="feed-item">
      <div class="feed-item-top">
        <span class="badge ${item.completed ? 'buy' : 'sell'}">${item.completed ? '완료' : '미완료'}</span>
        <span class="badge">${item.name}</span>
      </div>
    </div>
  `).join('');
}

function renderPolicyState(data) {
  const policyState = data.policy_snapshot;
  if (!policyState) {
    const el = document.getElementById('policy-snapshot');
    if (el) {
      el.className = 'feed empty';
      el.textContent = '정책 스냅샷 데이터 없음';
    }
    return;
  }

  const policy = policyState.policy || {};
  const state = policyState.state || {};
  const observations = data.policy_observations || [];

  // Render policy snapshot
  const policyEl = document.getElementById('policy-snapshot');
  if (policyEl) {
    const policyItems = [
      { label: 'max_consecutive_buys', value: policy.max_consecutive_buys },
      { label: 'sideway_filter_enabled', value: policy.sideway_filter_enabled ? '활성' : '비활성' },
      { label: 'uncertain_block_enabled', value: policy.uncertain_block_enabled ? '활성' : '비활성' },
      { label: 'high_volatility_defense', value: policy.high_volatility_defense_enabled ? '활성' : '비활성' },
      { label: 'max_symbol_exposure', value: `${policy.max_symbol_exposure_pct}%` },
      { label: 'max_total_exposure', value: `${policy.max_total_exposure_pct}%` },
      { label: 'meaningful_order_notional', value: won(policy.meaningful_order_notional) },
    ];

    policyEl.className = 'feed';
    policyEl.innerHTML = `
      <div class="feed-item">
        <div class="feed-item-top"><span class="badge">POLICY</span></div>
        <div class="meta-line" style="display:block;">
          ${policyItems.map((item) => `
            <div style="display:flex;justify-content:space-between;padding:2px 0;">
              <span style="font-size:0.85em;color:#666;">${item.label}</span>
              <span style="font-size:0.85em;font-weight:600;">${item.value}</span>
            </div>
          `).join('')}
        </div>
      </div>
      <div class="feed-item">
        <div class="feed-item-top"><span class="badge">STATE</span></div>
        <div class="meta-line" style="display:block;">
          <div style="display:flex;justify-content:space-between;padding:2px 0;">
            <span style="font-size:0.85em;color:#666;">consecutive_buys</span>
            <span style="font-size:0.85em;font-weight:600;">${state.consecutive_buys || 0}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:2px 0;">
            <span style="font-size:0.85em;color:#666;">losing_streak</span>
            <span style="font-size:0.85em;font-weight:600;">${state.losing_streak || 0}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:2px 0;">
            <span style="font-size:0.85em;color:#666;">cash_balance</span>
            <span style="font-size:0.85em;font-weight:600;">${won(state.cash_balance)}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:2px 0;">
            <span style="font-size:0.85em;color:#666;">positions</span>
            <span style="font-size:0.85em;font-weight:600;">${state.positions_count || 0}</span>
          </div>
        </div>
      </div>
    `;
  }

  // Render latest observations
  const obsEl = document.getElementById('policy-observations');
  if (obsEl) {
    if (!observations.length) {
      obsEl.className = 'feed empty';
      obsEl.textContent = '최근 관측 기록 없음';
      return;
    }
    obsEl.className = 'feed';
    obsEl.innerHTML = observations.map((obs) => `
      <div class="feed-item">
        <div class="feed-item-top">
          <span class="badge ${obs.block_reason ? 'sell' : 'buy'}">${obs.block_reason ? 'BLOCK' : 'PASS'}</span>
          <span class="badge">${obs.policy_name}</span>
        </div>
        <div class="meta-line">
          <span>${obs.symbol || '-'}</span>
          <span style="font-size:0.8em;">${obs.block_reason || 'policy_check_passed'}</span>
        </div>
      </div>
    `).join('');
  }
}

async function loadDashboard() {
  const [dashboardRes, checklistRes] = await Promise.all([
    fetch('/operator/live-dashboard?limit=20', { cache: 'no-store' }),
    fetch('/operator/deploy-checklist', { cache: 'no-store' }),
  ]);
  const data = await dashboardRes.json();
  const checklist = await checklistRes.json();
  renderCards(data);
  renderFeed(data);
  renderBucketList('strategy-version-list', data.by_strategy_version, (key, value) => `
    <div class="feed-item">
      <div class="feed-item-top"><span class="badge">${key}</span></div>
      <div class="meta-line"><span>손익 ${won(value.total_net_pnl)}</span><span>승률 ${value.win_rate}%</span></div>
    </div>
  `);
  renderBucketList('market-regime-list', data.by_market_regime, (key, value) => `
    <div class="feed-item">
      <div class="feed-item-top"><span class="badge">${key}</span></div>
      <div class="meta-line"><span>손익 ${won(value.total_net_pnl)}</span><span>승률 ${value.win_rate}%</span></div>
    </div>
  `);
  renderChecklist(checklist);
  renderPolicyState(data);
  document.getElementById('last-updated').textContent = new Date().toLocaleTimeString('ko-KR');
}

async function boot() {
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
