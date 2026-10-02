// Auto-split from ui/chat/index.html — 04-module-4.js
// Feature module 5 of 6.
import { state } from './00-state.js';
import { BooksModule } from './01-books-module.js';
import { escapeHtml } from './00-escape-html.js';

// ══════════════════════════════════════════════════════════════
// 5. LIBRARIAN MODULE (STAFF INGESTION & MANUAL EDITS)
// ══════════════════════════════════════════════════════════════
(function(){
  const INFER_HOST = window.location.origin;

  const panel = document.getElementById('librarian-panel');
  const graphW = document.getElementById('graph-wrap');
  const booksW = document.getElementById('books-view');
  const chipBar = document.getElementById('chip-bar');
  const statsBar = document.getElementById('stats-bar');
  const zoomCtrls = document.getElementById('zoom-ctrls');
  const flashC = document.getElementById('flashcard');
  const actionsGrid = document.getElementById('lib-actions-grid');
  const authStatus = document.getElementById('lib-auth-status');
  const tokenInput = document.getElementById('lib-token-input');

  function getLibrarianToken(){ return 'verified-session'; }
  function setLibrarianToken(){ }
  function librarianHeaders(extra){ return Object.assign({}, extra || {}); }
  function refreshAuthUI(){
    if (actionsGrid) {
      actionsGrid.style.opacity = '1';
      actionsGrid.style.pointerEvents = 'auto';
    }
    if (authStatus) {
      authStatus.textContent = 'Staff access is verified by your Supabase session; the server enforces librarian/admin permissions.';
      authStatus.className = 'lib-status ok';
    }
    if (tokenInput) tokenInput.closest('.lib-auth')?.remove();
  }

  document.getElementById('lib-token-save')?.addEventListener('click', () => {
    setLibrarianToken(tokenInput?.value || '');
    refreshAuthUI();
  });
  document.getElementById('lib-token-clear')?.addEventListener('click', () => {
    setLibrarianToken('');
    if (tokenInput) tokenInput.value = '';
    refreshAuthUI();
  });
  refreshAuthUI();

  function openLibrarian(){
    panel.classList.add('open');
    if (graphW) graphW.style.display = 'none';
    if (booksW) booksW.classList.remove('active');
    if (chipBar) chipBar.classList.add('hidden');
    if (statsBar) statsBar.style.display = 'none';
    if (zoomCtrls) zoomCtrls.style.display = 'none';
    if (flashC) flashC.classList.remove('open');
    document.getElementById('srch').parentElement.style.display = 'none';
    document.getElementById('back-btn').style.display = 'none';
    document.getElementById('book-label').style.display = 'none';
    populateConceptDatalist();
    refreshAuthUI();
  }

  function closeLibrarian(){
    panel.classList.remove('open');
    if (statsBar) statsBar.style.display = 'flex';
    document.getElementById('srch').parentElement.style.display = '';
    if (state.currentView === 'books') {
      BooksModule.render();
    } else {
      if (graphW) graphW.style.display = 'block';
      if (chipBar) chipBar.classList.remove('hidden');
      if (zoomCtrls) zoomCtrls.style.display = 'flex';
    }
  }

  document.getElementById('tab-librarian').onclick = () => {
    document.querySelectorAll('#nav-tabs .nav-tab').forEach(t => t.classList.toggle('active', t === document.getElementById('tab-librarian')));
    openLibrarian();
  };

  ['tab-books', 'tab-concepts', 'tab-crossbook'].forEach(id => {
    document.getElementById(id).addEventListener('click', closeLibrarian);
  });
  document.getElementById('home-btn').addEventListener('click', closeLibrarian);

  function populateConceptDatalist(){
    const dl = document.getElementById('lib-concept-datalist');
    if (dl) dl.innerHTML = state.allNodes.map(n => `<option value="${escapeHtml(n.label || n.id)}"></option>`).join('');
  }

  // ── PDF UPLOAD ──
  let pdfFile = null;
  let pollTimer = null;
  const dropZone = document.getElementById('lib-drop-zone');
  const pdfInput = document.getElementById('lib-pdf-input');
  const dropLabel = document.getElementById('lib-drop-label');
  const uploadBtn = document.getElementById('lib-upload-btn');
  const cancelBtn = document.getElementById('lib-cancel-btn');
  const uploadStatus = document.getElementById('lib-upload-status');
  const stagesEl = document.getElementById('lib-stages');
  const elapsedEl = document.getElementById('lib-elapsed');

  function setUploadStatus(msg, type){
    uploadStatus.textContent = msg;
    uploadStatus.className = `lib-status ${type || 'info'}`;
  }
  function resetStages(){
    stagesEl.style.display = 'none';
    stagesEl.querySelectorAll('.lib-stage').forEach(s => s.removeAttribute('data-state'));
    elapsedEl.style.display = 'none';
    elapsedEl.textContent = '';
  }
  function setStage(name, state){
    stagesEl.style.display = 'block';
    const all = [...stagesEl.querySelectorAll('.lib-stage')];
    const idx = all.findIndex(s => s.dataset.stage === name);
    all.forEach((s, i) => {
      if (i < idx) s.dataset.state = 'done';
      else if (i === idx) s.dataset.state = state;
      else s.removeAttribute('data-state');
    });
  }

  dropZone.addEventListener('click', () => pdfInput.click());
  pdfInput.addEventListener('change', () => {
    const f = pdfInput.files[0];
    if (f && isAllowedUpload(f)) { pdfFile = f; dropLabel.textContent = f.name; uploadBtn.disabled = false; }
    else if (f) { setUploadStatus('Supported: PDF, Markdown (.md), plain text (.txt).', 'err'); }
  });
  ['dragenter', 'dragover'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('drag-over'); }));
  ['dragleave', 'drop'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('drag-over'); }));

  function isAllowedUpload(f){
    if (!f) return false;
    const n = (f.name || '').toLowerCase();
    return n.endsWith('.pdf') || n.endsWith('.md') || n.endsWith('.markdown') || n.endsWith('.txt')
      || f.type === 'application/pdf' || f.type === 'text/markdown' || f.type === 'text/plain';
  }

  dropZone.addEventListener('drop', e => {
    const f = [...e.dataTransfer.files].find(isAllowedUpload);
    if (!f) { setUploadStatus('Supported: PDF, Markdown (.md), plain text (.txt).', 'err'); return; }
    pdfFile = f; dropLabel.textContent = f.name; uploadBtn.disabled = false;
    const dt = new DataTransfer(); dt.items.add(f); pdfInput.files = dt.files;
  });

  let jobStarted = null;
  function tickElapsed(){
    if (!jobStarted) return;
    const s = Math.floor((Date.now() - jobStarted) / 1000);
    elapsedEl.textContent = `Elapsed: ${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    elapsedEl.style.display = 'block';
  }

  async function pollJob(jobId){
    try {
      const r = await fetch(`${INFER_HOST}/api/ingest/${encodeURIComponent(jobId)}`, {
        headers: librarianHeaders({ Accept: 'application/json' })
      });
      if (!r.ok) throw new Error(`Poll failed (${r.status})`);
      const j = await r.json();
      const status = (j.status || '').toLowerCase();
      if (status === 'complete' || status === 'completed') {
        setStage('complete', 'done');
        setUploadStatus('✓ Ingestion complete! Reload the graph to see new concepts.', 'ok');
        cancelBtn.style.display = 'none';
        uploadBtn.disabled = false;
        clearInterval(pollTimer);
        return;
      }
      if (status === 'error' || status === 'failed') {
        setUploadStatus(`Ingestion failed: ${j.error || j.message || 'unknown error'}`, 'err');
        cancelBtn.style.display = 'none';
        uploadBtn.disabled = false;
        clearInterval(pollTimer);
        return;
      }
      const stageMap = { queued: 'queued', parsing: 'parsing', extracting: 'extracting', canonicalizing: 'canonicalizing', validating: 'validating' };
      const s = stageMap[status] || 'queued';
      setStage(s, 'active');
      setUploadStatus(`In progress — ${status}…`, 'info');
    } catch (err) {
      setUploadStatus(`Poll error: ${err.message}`, 'err');
    }
    tickElapsed();
  }

  uploadBtn.addEventListener('click', async () => {
    if (!pdfFile) return;
    if (!getLibrarianToken()) {
      setUploadStatus('Save a librarian token first (top of this panel). Students cannot upload.', 'err');
      return;
    }
    uploadBtn.disabled = true;
    cancelBtn.style.display = 'block';
    resetStages();
    jobStarted = Date.now();
    setStage('queued', 'active');
    setUploadStatus('Submitting to ingestion service…', 'info');
    try {
      const fd = new FormData(); fd.append('file', pdfFile);
      const r = await fetch(`${INFER_HOST}/api/ingest`, {
        method: 'POST',
        headers: librarianHeaders(),
        body: fd
      });
      if (r.status === 401) throw new Error('Unauthorized — check librarian token');
      if (!r.ok) throw new Error(`Upload rejected (${r.status})`);
      const j = await r.json();
      const jobId = j.job_id || j.id;
      if (!jobId) throw new Error('No job ID returned by ingestion service.');
      setUploadStatus(`Job started (${jobId.slice(0, 8)}…) — polling for progress…`, 'info');
      pollTimer = setInterval(() => pollJob(jobId), 2200);
    } catch (err) {
      setUploadStatus(`Error: ${err.message}`, 'err');
      cancelBtn.style.display = 'none';
      uploadBtn.disabled = false;
      resetStages();
    }
  });

  cancelBtn.addEventListener('click', () => {
    clearInterval(pollTimer);
    cancelBtn.style.display = 'none';
    uploadBtn.disabled = false;
    setUploadStatus('Cancelled.', 'err');
    resetStages();
  });

  // ── DOCUMENT LIST + DELETE / UNMERGE ──
  const docsListEl = document.getElementById('lib-docs-list');
  const deleteStatus = document.getElementById('lib-delete-status');

  async function refreshDocList(){
    if (!docsListEl) return;
    docsListEl.textContent = 'Loading…';
    try {
      const r = await fetch(`${INFER_HOST}/api/documents`, { headers: librarianHeaders({ Accept: 'application/json' }) });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const docs = j.documents || [];
      if (!docs.length) { docsListEl.textContent = 'No documents in graph.'; return; }
      docsListEl.innerHTML = docs.map(d => {
        const id = escapeHtml(d.id || '');
        const title = escapeHtml(d.title || d.id || '');
        const n = d.chunk_count != null ? d.chunk_count : '?';
        return `
          <div style="margin:4px 0;padding:6px 8px;border:1px solid rgba(15,23,42,0.08);border-radius:8px;cursor:pointer;background:#fff" data-doc-id="${id}">
            <div style="font-weight:700;font-size:12px;color:var(--tx)">${title}</div>
            <div style="font-size:11px;color:var(--mu)">${id} · ${n} chunks</div>
          </div>
        `;
      }).join('');
      docsListEl.querySelectorAll('[data-doc-id]').forEach(el => {
        el.addEventListener('click', () => {
          const inp = document.getElementById('lib-delete-id');
          if (inp) inp.value = el.getAttribute('data-doc-id') || '';
        });
      });
    } catch (err) {
      docsListEl.textContent = `Failed to list documents: ${err.message}`;
    }
  }

  document.getElementById('lib-docs-refresh')?.addEventListener('click', () => {
    if (!getLibrarianToken()) {
      if (docsListEl) docsListEl.textContent = 'Save a librarian token first.';
      return;
    }
    refreshDocList();
  });

  document.getElementById('lib-delete-btn')?.addEventListener('click', async () => {
    const docId = (document.getElementById('lib-delete-id')?.value || '').trim();
    if (!docId) {
      if (deleteStatus) { deleteStatus.textContent = 'Enter a document id.'; deleteStatus.className = 'lib-status err'; }
      return;
    }
    if (!getLibrarianToken()) {
      if (deleteStatus) { deleteStatus.textContent = 'Save a librarian token first.'; deleteStatus.className = 'lib-status err'; }
      return;
    }
    if (!confirm(`Delete and unmerge "${docId}" from the live graph?`)) return;
    if (deleteStatus) { deleteStatus.textContent = 'Deleting…'; deleteStatus.className = 'lib-status info'; }
    try {
      const rmPdf = document.getElementById('lib-delete-pdf')?.checked ? '1' : '0';
      const url = `${INFER_HOST}/api/documents/${encodeURIComponent(docId)}?remove_pdf=${rmPdf}`;
      const r = await fetch(url, { method: 'DELETE', headers: librarianHeaders({ Accept: 'application/json' }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
      if (deleteStatus) {
        deleteStatus.textContent = `✓ Deleted ${j.doc_id || docId}: chunks=${j.chunks_deleted || 0}, edges=${j.edges_deleted || 0}, concepts_removed=${j.concepts_deleted || 0}`;
        deleteStatus.className = 'lib-status ok';
      }
      refreshDocList();
    } catch (err) {
      if (deleteStatus) { deleteStatus.textContent = `Error: ${err.message}`; deleteStatus.className = 'lib-status err'; }
    }
  });

  // ── MANUAL CONCEPT CREATION ──
  document.getElementById('lib-concept-btn').addEventListener('click', async () => {
    const name = document.getElementById('lib-concept-name').value.trim();
    const type = document.getElementById('lib-concept-type').value;
    const diff = document.getElementById('lib-concept-diff').value;
    const summary = document.getElementById('lib-concept-summary').value.trim();
    const tags = document.getElementById('lib-concept-tags').value.split(',').map(t => t.trim()).filter(Boolean);
    const statusEl = document.getElementById('lib-concept-status');
    if (!name || !type || !diff) {
      statusEl.textContent = 'Name, type and difficulty are required.'; statusEl.className = 'lib-status err'; return;
    }
    if (!getLibrarianToken()) {
      statusEl.textContent = 'Save a librarian token first.'; statusEl.className = 'lib-status err'; return;
    }
    statusEl.textContent = 'Adding concept…'; statusEl.className = 'lib-status info';
    try {
      const r = await fetch(`${INFER_HOST}/api/manual/concept`, {
        method: 'POST',
        headers: librarianHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ name, concept_type: type, difficulty: diff, summary, tags })
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
      statusEl.textContent = `✓ Concept "${name}" added (ID: ${j.id || j.concept_id || '—'}).`;
      statusEl.className = 'lib-status ok';
      document.getElementById('lib-concept-name').value = '';
      document.getElementById('lib-concept-summary').value = '';
      document.getElementById('lib-concept-tags').value = '';
    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`; statusEl.className = 'lib-status err';
    }
  });

  // ── MANUAL EDGE CREATION ──
  document.getElementById('lib-edge-btn').addEventListener('click', async () => {
    const from = document.getElementById('lib-edge-from').value.trim();
    const to = document.getElementById('lib-edge-to').value.trim();
    const rel = document.getElementById('lib-edge-relation').value;
    const statusEl = document.getElementById('lib-edge-status');
    if (!from || !to || !rel) {
      statusEl.textContent = 'All three fields are required.'; statusEl.className = 'lib-status err'; return;
    }
    if (!getLibrarianToken()) {
      statusEl.textContent = 'Save a librarian token first.'; statusEl.className = 'lib-status err'; return;
    }
    statusEl.textContent = 'Adding edge…'; statusEl.className = 'lib-status info';
    try {
      const r = await fetch(`${INFER_HOST}/api/manual/edge`, {
        method: 'POST',
        headers: librarianHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ from_concept: from, to_concept: to, relation: rel })
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
      statusEl.textContent = `✓ Edge "${from}" → [${rel}] → "${to}" added.`;
      statusEl.className = 'lib-status ok';
      document.getElementById('lib-edge-from').value = '';
      document.getElementById('lib-edge-to').value = '';
    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`; statusEl.className = 'lib-status err';
    }
  });
})();
