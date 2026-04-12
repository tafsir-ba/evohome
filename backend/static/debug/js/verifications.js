/** Debug Console — Verification Checklist tab */
async function loadVerifications(el) {
  const data = await apiFetch('/verifications');
  if (!data) { el.innerHTML = '<div class="empty">Failed to load verifications</div>'; return; }
  const items = data.items || [];
  const stats = {
    passed: items.filter(i => i.status === 'passed').length,
    failed: items.filter(i => i.status === 'failed').length,
    untested: items.filter(i => i.status === 'untested').length,
  };
  el.innerHTML = `
    <div style="margin-bottom:16px;display:flex;gap:16px;align-items:center">
      <span class="badge badge-passed">${stats.passed} passed</span>
      <span class="badge badge-failed">${stats.failed} failed</span>
      <span class="badge badge-untested">${stats.untested} untested</span>
      <span style="color:var(--text-dim);font-size:12px">${items.length} total items</span>
    </div>
    <div id="checklist">${items.map(item => `
      <div class="checklist-item">
        <span class="id">${item.item_id}</span>
        <span class="cat">${item.category}</span>
        <span class="name">${item.name}<br><span style="color:var(--text-dim);font-size:11px">${item.description}</span></span>
        <select onchange="updateVerification('${item.item_id}', this.value)" style="width:90px">
          <option value="untested" ${item.status === 'untested' ? 'selected' : ''}>untested</option>
          <option value="passed" ${item.status === 'passed' ? 'selected' : ''}>passed</option>
          <option value="failed" ${item.status === 'failed' ? 'selected' : ''}>failed</option>
        </select>
        <input class="notes-input" placeholder="Notes..." value="${item.notes || ''}" onchange="updateVerificationNotes('${item.item_id}', this.value)"/>
        ${item.last_verified ? `<span style="font-size:10px;color:var(--text-dim)">${new Date(item.last_verified).toLocaleDateString()}</span>` : ''}
      </div>`).join('')}</div>`;
}

async function updateVerification(id, status) {
  await apiFetch('/verifications/' + id, {method: 'PUT', body: JSON.stringify({status, verified_by: 'debug_console'})});
}

async function updateVerificationNotes(id, notes) {
  await apiFetch('/verifications/' + id, {method: 'PUT', body: JSON.stringify({notes})});
}
