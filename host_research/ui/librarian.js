const section = location.pathname.split('/')[2] || 'overview';
const sections = {
  overview: ['Librarian Space', 'Library operations, in one place.'],
  catalog: ['Catalogue notes', 'Record verified book IDs, shelf locations, copy counts and status.'],
  circulation: ['Circulation', 'Track staff issue counts and status notes without borrower information.'],
  orders: ['Orders', 'Keep a staff record of requested and ordered titles.'],
  fines: ['Fine notes', 'Track internal fine adjustment notes; Koha remains the official balance.'],
};
const title = document.getElementById('section-title');
const form = document.getElementById('record-form');
const fields = Object.fromEntries(['key','title','status','quantity','amount','shelf','source','note'].map(key => [key, document.getElementById(`record-${key}`)]));
const status = document.getElementById('workspace-status');
const formStatus = document.getElementById('form-status');
let records = [];

function showRecords() {
  const body = document.getElementById('record-rows');
  body.replaceChildren();
  document.getElementById('record-count').textContent = `${records.length} records`;
  for (const record of records) {
    const tr = document.createElement('tr');
    const values = [record.title || record.record_key, record.status, record.quantity ?? '—', record.amount == null ? '—' : `₹${record.amount}`, record.shelf, new Date(record.updated_at).toLocaleDateString()];
    values.forEach((value, index) => {
      const td = document.createElement('td');
      td.textContent = String(value || '—');
      if (index === 0 && record.title) { const small = document.createElement('small'); small.textContent = record.record_key; td.append(small); }
      tr.append(td);
    });
    const action = document.createElement('td');
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = 'Edit';
    button.addEventListener('click', () => {
      for (const [key, field] of Object.entries(fields)) field.value = record[key === 'key' ? 'record_key' : key === 'source' ? 'source_url' : key] ?? '';
      fields.key.focus(); form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    action.append(button); tr.append(action); body.append(tr);
  }
}

async function loadRecords() {
  status.textContent = 'Loading staff records…';
  const response = await fetch(`/api/librarian/${section}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not load records (${response.status}).`);
  records = (await response.json()).records;
  showRecords();
  status.textContent = 'These are Archipelago staff records; official values remain in Koha.';
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  formStatus.textContent = 'Saving…';
  const data = { record_key: fields.key.value.trim(), title: fields.title.value.trim(), status: fields.status.value.trim(), shelf: fields.shelf.value.trim(), note: fields.note.value.trim(), source_url: fields.source.value.trim(), quantity: fields.quantity.value === '' ? null : Number(fields.quantity.value), amount: fields.amount.value === '' ? null : Number(fields.amount.value) };
  try {
    const response = await fetch(`/api/librarian/${section}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Save failed (${response.status}).`);
    formStatus.textContent = 'Saved to Archipelago. Koha was not changed.';
    await loadRecords();
  } catch (error) { formStatus.textContent = error.message; }
});

document.getElementById('lookup-opac').addEventListener('click', async () => {
  const key = fields.key.value.trim();
  if (!/^\d{1,9}$/.test(key)) { formStatus.textContent = 'Enter an exact numeric Koha book ID.'; return; }
  formStatus.textContent = 'Checking the public OPAC record…';
  try {
    const response = await fetch(`/api/library/opac/live?biblionumber=${encodeURIComponent(key)}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`OPAC lookup returned ${response.status}.`);
    const record = await response.json();
    fields.title.value = record.title || '';
    fields.source.value = record.source_url || '';
    if (record.source_kind === 'dated_koha_export') {
      const saved = record.snapshot_record || {};
      fields.quantity.value = saved['No. of copies'] || '';
      fields.status.value = `${saved['Available Copies'] || 'unknown'} copies available in dated export`;
      fields.shelf.value = saved.rack_number || saved.call_number || '';
      formStatus.textContent = `Live OPAC unavailable. Loaded a ${record.stale ? 'stale' : 'dated'} Koha export from ${record.source_updated_at || 'unknown date'}; verify before saving.`;
      return;
    }
    const holdings = Array.isArray(record.holdings) ? record.holdings : [];
    fields.quantity.value = holdings.length;
    fields.status.value = [...new Set(holdings.map(copy => copy.status).filter(Boolean))].join(', ');
    fields.shelf.value = [...new Set(holdings.map(copy => copy.call_number).filter(Boolean))].join(', ');
    formStatus.textContent = `Checked ${new Date(record.fetched_at).toLocaleString()}. Review each value before saving.`;
  } catch (error) { formStatus.textContent = error.message; }
});

window.addEventListener('load', async () => {
  const principal = await window.archipelagoAuthorizePage(['faculty','librarian','administrator']);
  if (!principal) return;
  document.querySelector(`[data-section="${section}"]`)?.setAttribute('aria-current','page');
  title.textContent = sections[section][0];
  document.getElementById('section-description').textContent = sections[section][1];
  if (section !== 'overview') {
    document.getElementById('overview').hidden = true;
    const trafficPanel = document.getElementById('people-traffic-panel');
    if (trafficPanel) trafficPanel.hidden = true;
    document.getElementById('records-panel').hidden = false;
    document.getElementById('records-title').textContent = sections[section][0];
    if (!['librarian','administrator'].includes(principal.role)) {
      form.hidden = true;
      status.textContent = 'Read-only access for faculty.';
    }
    loadRecords().catch(error => { status.textContent = error.message; });
  } else {
    loadPeopleTraffic();
    try {
      const response = await fetch('/api/library/koha', { cache: 'no-store' });
      if (!response.ok) throw new Error('No authorized export available.');
      const exportData = await response.json();
      const box = document.getElementById('export-status');
      box.hidden = false;
      box.textContent = `Koha export: ${exportData.source_updated_at || 'date unknown'} · ${exportData.stale ? 'stale; verify in OPAC' : 'current'} · ${exportData.holdings?.length || 0} keyword-filtered holdings (not the full inventory).`;
    } catch (error) { status.textContent = error.message; }
  }
});

let trafficTimer = null;
function renderTrafficChart(series) {
  const svg = document.getElementById('traffic-chart');
  if (!svg) return;
  const NS = 'http://www.w3.org/2000/svg';
  svg.replaceChildren();
  if (!Array.isArray(series) || series.length === 0) {
    const txt = document.createElementNS(NS, 'text');
    txt.setAttribute('x', '320'); txt.setAttribute('y', '84'); txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('fill', '#575249'); txt.setAttribute('font-size', '13');
    txt.textContent = 'No live gate, QR check-in, or occupancy events recorded yet.';
    svg.append(txt);
    return;
  }
  const maxVal = Math.max(1, ...series.map(d => Number(d.count ?? d.entries ?? 0)));
  const w = 640, h = 130, pad = 20;
  const step = (w - pad * 2) / series.length;
  series.forEach((d, idx) => {
    const val = Number(d.count ?? d.entries ?? 0);
    const barH = Math.round((val / maxVal) * (h - 24));
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', String(pad + idx * step + 2));
    rect.setAttribute('y', String(h - barH));
    rect.setAttribute('width', String(Math.max(4, step - 4)));
    rect.setAttribute('height', String(Math.max(2, barH)));
    rect.setAttribute('rx', '2');
    rect.setAttribute('fill', val > 0 ? '#1d4ed8' : '#e5dfd2');
    const tip = document.createElementNS(NS, 'title');
    tip.textContent = `${d.hour || d.date}: ${val} events`;
    rect.append(tip);
    svg.append(rect);
    if (idx % Math.max(1, Math.floor(series.length / 6)) === 0) {
      const lbl = document.createElementNS(NS, 'text');
      lbl.setAttribute('x', String(pad + idx * step + step / 2));
      lbl.setAttribute('y', '150'); lbl.setAttribute('text-anchor', 'middle');
      lbl.setAttribute('fill', '#575249'); lbl.setAttribute('font-size', '10');
      lbl.textContent = String(d.hour || d.date || '').slice(0, 5);
      svg.append(lbl);
    }
  });
}

async function loadPeopleTraffic() {
  const tStatus = document.getElementById('traffic-status');
  try {
    const resp = await fetch('/api/analytics/summary', { cache: 'no-store' });
    if (!resp.ok) throw new Error(`Analytics summary unavailable (${resp.status}).`);
    const data = await resp.json();
    const foot = data.physical_footfall || {};
    const occ = data.occupancy || {};
    document.getElementById('kpi-entries').textContent = foot.total_entries ?? '—';
    document.getElementById('kpi-exits').textContent = foot.total_exits ?? '—';
    document.getElementById('kpi-checkins').textContent = foot.total_qr_checkins ?? '—';
    document.getElementById('kpi-occupancy').textContent = occ.current_occupancy ?? '—';
    const series = (foot.hourly_activity && foot.hourly_activity.length) ? foot.hourly_activity : (foot.daily_entries || []);
    renderTrafficChart(series);
    tStatus.textContent = foot.status === 'connected'
      ? `Peak: ${foot.peak_period || 'recorded'} · Updated ${new Date().toLocaleTimeString()}`
      : 'Not connected — no live gate or QR check-in events recorded yet.';
  } catch (err) {
    renderTrafficChart([]);
    if (tStatus) tStatus.textContent = err.message;
  }
}

document.getElementById('traffic-refresh')?.addEventListener('click', () => loadPeopleTraffic());
document.getElementById('traffic-autorefresh')?.addEventListener('change', e => {
  clearInterval(trafficTimer);
  trafficTimer = e.target.checked ? setInterval(loadPeopleTraffic, 15000) : null;
});
