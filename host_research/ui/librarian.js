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
    document.getElementById('records-panel').hidden = false;
    document.getElementById('records-title').textContent = sections[section][0];
    if (!['librarian','administrator'].includes(principal.role)) {
      form.hidden = true;
      status.textContent = 'Read-only access for faculty.';
    }
    loadRecords().catch(error => { status.textContent = error.message; });
  } else {
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
