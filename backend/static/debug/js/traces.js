/** Debug Console — Traces tab */
async function loadTraces(el, mode) {
  const filterParams = mode !== 'errors' ? `
    <div class="filters">
      <select id="f-outcome" onchange="filterTraces()"><option value="">All outcomes</option><option value="success">success</option><option value="validation_error">validation</option><option value="auth_error">auth</option><option value="service_error">service</option><option value="storage_error">storage</option></select>
      <select id="f-method" onchange="filterTraces()"><option value="">All methods</option><option value="POST">POST</option><option value="PUT">PUT</option><option value="DELETE">DELETE</option><option value="GET">GET</option></select>
      <input id="f-action" placeholder="Filter by action..." oninput="filterTraces()"/>
      <div class="auto-refresh"><input type="checkbox" id="auto-ref" onchange="toggleAutoRefresh(this.checked)"/> <label for="auto-ref">Auto-refresh (10s)</label></div>
    </div>` : '';
  const url = mode === 'errors' ? '/traces?errors_only=true&limit=100' : '/traces?limit=100';
  const data = await apiFetch(url);
  if (!data) { el.innerHTML = '<div class="empty">Failed to load traces</div>'; return; }
  window._traces = data.traces || [];
  el.innerHTML = filterParams + '<div id="traces-table"></div>';
  renderTracesTable(window._traces);
}

function filterTraces() {
  let traces = window._traces || [];
  const outcome = document.getElementById('f-outcome')?.value;
  const method = document.getElementById('f-method')?.value;
  const action = document.getElementById('f-action')?.value?.toLowerCase();
  if (outcome) traces = traces.filter(t => t.outcome === outcome);
  if (method) traces = traces.filter(t => t.method === method);
  if (action) traces = traces.filter(t => (t.action||'').toLowerCase().includes(action) || (t.endpoint||'').toLowerCase().includes(action));
  renderTracesTable(traces);
}

function renderTracesTable(traces) {
  const el = document.getElementById('traces-table');
  if (!traces.length) { el.innerHTML = '<div class="empty">No traces found</div>'; return; }
  el.innerHTML = `<table><thead><tr><th>Time</th><th>Method</th><th>Endpoint</th><th>Action</th><th>User</th><th>Entity</th><th>Outcome</th><th>Duration</th><th>RID</th><th></th></tr></thead><tbody>${
    traces.map((t,i) => {
      const cls = t.outcome !== 'success' ? ' class="error"' : '';
      const badge = t.outcome === 'success' ? 'badge-success' : t.outcome.includes('auth') ? 'badge-warn' : 'badge-error';
      const time = t.created_at ? new Date(t.created_at).toLocaleTimeString() : '?';
      const ent = t.entity_type ? `${t.entity_type}/${(t.entity_id||'').substring(0,15)}` : '-';
      return `<tr${cls}><td>${time}</td><td>${t.method}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${t.endpoint}</td><td>${t.action||'-'}</td><td>${t.user_id ? t.user_id.substring(0,15) : '-'}</td><td style="font-size:11px">${ent}</td><td><span class="badge ${badge}">${t.outcome}</span></td><td>${t.duration_ms}ms</td><td style="font-size:10px;color:var(--text-dim)">${t.request_id}</td><td><span class="expand" onclick="toggleDetail(${i})">+</span></td></tr><tr id="detail-${i}" style="display:none"><td colspan="10"><div class="detail">${JSON.stringify({request_summary:t.request_summary,response_summary:t.response_summary,service_chain:t.service_chain,db_mutations:t.db_mutations,side_effects:t.side_effects,related_entities:t.related_entities,error_code:t.error_code,error_message:t.error_message},null,2)}</div></td></tr>`;
    }).join('')
  }</tbody></table>`;
}

function toggleDetail(i) { const el = document.getElementById('detail-'+i); el.style.display = el.style.display === 'none' ? '' : 'none'; }

let autoRefresh = false, refreshTimer = null;
function toggleAutoRefresh(on) {
  autoRefresh = on;
  if (refreshTimer) clearInterval(refreshTimer);
  if (on) refreshTimer = setInterval(() => loadTab(), 10000);
}
