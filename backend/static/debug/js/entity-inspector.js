/** Debug Console — Entity Inspector tab */
function loadEntityForm(el) {
  el.innerHTML = `
    <div class="inspector-input">
      <select id="ent-type"><option value="document">document</option><option value="quote">quote</option><option value="invoice">invoice</option><option value="vault_document">vault_document</option><option value="client">client</option><option value="change_request">change_request</option><option value="decision">decision</option><option value="user">user</option></select>
      <input id="ent-id" placeholder="Entity ID (e.g. doc_xxx)" style="flex:1"/>
      <button onclick="inspectEntity()">Inspect</button>
    </div>
    <div id="entity-result"></div>`;
}

async function inspectEntity() {
  const type = document.getElementById('ent-type').value;
  const id = document.getElementById('ent-id').value.trim();
  if (!id) return;
  const el = document.getElementById('entity-result');
  el.innerHTML = '<div class="empty">Loading...</div>';
  const data = await apiFetch('/entity/'+type+'/'+id);
  if (!data) { el.innerHTML = '<div class="empty">Failed to inspect entity</div>'; return; }
  el.innerHTML = `
    <div class="entity-state"><h3>Current State (${data.exists ? 'exists' : 'NOT FOUND'})</h3><pre>${data.current_state ? JSON.stringify(data.current_state, null, 2) : 'Entity not found in database'}</pre></div>
    ${data.state_transitions?.length ? `<div class="entity-state"><h3>State Transitions (${data.state_transitions.length})</h3><pre>${JSON.stringify(data.state_transitions, null, 2)}</pre></div>` : ''}
    ${data.change_requests?.length ? `<div class="entity-state"><h3>Change Requests (${data.change_requests.length})</h3><pre>${JSON.stringify(data.change_requests, null, 2)}</pre></div>` : ''}
    ${data.notifications?.length ? `<div class="entity-state"><h3>Notifications (${data.notifications.length})</h3><pre>${JSON.stringify(data.notifications, null, 2)}</pre></div>` : ''}
    <div class="entity-state"><h3>Related Traces (${data.traces?.length || 0})</h3>${
      data.traces?.length ? `<table><thead><tr><th>Time</th><th>Action</th><th>Outcome</th><th>User</th><th>DB Mutations</th><th>RID</th></tr></thead><tbody>${
        data.traces.map(t => `<tr><td>${new Date(t.created_at).toLocaleString()}</td><td>${t.action||t.method+' '+t.endpoint}</td><td><span class="badge badge-${t.outcome==='success'?'success':'error'}">${t.outcome}</span></td><td>${t.user_id||'-'}</td><td style="font-size:10px">${(t.db_mutations||[]).map(m=>m.collection+'.'+m.operation).join(', ')||'-'}</td><td style="font-size:10px">${t.request_id}</td></tr>`).join('')
      }</tbody></table>` : '<div class="empty">No traces for this entity</div>'
    }</div>`;
}
