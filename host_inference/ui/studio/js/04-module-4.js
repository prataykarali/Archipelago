// Staff console for the hosted graph studio. Server routes enforce every role check.
import { state } from './00-state.js';
import { BooksModule } from './01-books-module.js';

const JOB_POLL_INTERVAL_MS = 1500;
const SETTLED_JOB_STATES = new Set(['complete', 'failed', 'cancelled']);
const STAFF_EDIT_ROLES = new Set(['librarian', 'administrator']);

const panel = document.getElementById('librarian-panel');
const graphWrap = document.getElementById('graph-wrap');
const booksView = document.getElementById('books-view');
const chipBar = document.getElementById('chip-bar');
const statsBar = document.getElementById('stats-bar');
const zoomControls = document.getElementById('zoom-ctrls');
const flashcard = document.getElementById('flashcard');
const search = document.getElementById('srch');
const backButton = document.getElementById('back-btn');
const bookLabel = document.getElementById('book-label');
const uploadForm = document.getElementById('studio-upload-form');
const uploadButton = document.getElementById('studio-upload-button');
const uploadStatus = document.getElementById('studio-ingest-status');
let canUpload = false;
let pollTimer = null;

function openStudio() {
  document.querySelectorAll('#nav-tabs .nav-tab').forEach(tab => {
    tab.classList.toggle('active', tab.id === 'tab-librarian');
  });
  panel.classList.add('open');
  graphWrap.style.display = 'none';
  booksView.classList.remove('active');
  chipBar.classList.add('hidden');
  statsBar.style.display = 'none';
  zoomControls.style.display = 'none';
  flashcard.classList.remove('open');
  search.parentElement.style.display = 'none';
  backButton.style.display = 'none';
  bookLabel.style.display = 'none';
}

function closeStudio() {
  panel.classList.remove('open');
  statsBar.style.display = 'flex';
  search.parentElement.style.display = '';
  if (state.currentView === 'books') {
    BooksModule.render();
  } else {
    graphWrap.style.display = 'block';
    chipBar.classList.remove('hidden');
    zoomControls.style.display = 'flex';
  }
}

document.getElementById('tab-librarian').addEventListener('click', openStudio);
for (const id of ['tab-books', 'tab-concepts', 'tab-crossbook', 'home-btn']) {
  document.getElementById(id).addEventListener('click', closeStudio);
}

async function configureIngestion() {
  await window.archipelagoAuthReady;
  const identityResponse = await fetch('/api/auth/me', { cache: 'no-store' });
  if (!identityResponse.ok) return;
  const principal = await identityResponse.json();
  if (!STAFF_EDIT_ROLES.has(principal.role)) {
    document.getElementById('studio-faculty-card').hidden = false;
    return;
  }
  document.getElementById('studio-ingest-card').hidden = false;
  try {
    const response = await fetch('/api/ingest/capabilities', { cache: 'no-store' });
    if (!response.ok) throw new Error('Capability check failed');
    const capability = await response.json();
    canUpload = capability.upload_api_enabled === true;
    uploadButton.disabled = !canUpload;
    uploadStatus.textContent = canUpload
      ? 'Worker available. Uploads are queued and must finish before the graph changes.'
      : 'The hosted ingestion worker is unavailable. No upload will be accepted here.';
  } catch (_error) {
    uploadStatus.textContent = 'Could not verify ingestion availability. Upload is disabled.';
  }
}

async function pollJob(jobId) {
  const response = await fetch(`/api/ingest/${encodeURIComponent(jobId)}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Job status unavailable (${response.status})`);
  const job = await response.json();
  uploadStatus.textContent = `Job ${job.job_id}: ${job.status}${job.error ? ` — ${job.error}` : ''}`;
  if (SETTLED_JOB_STATES.has(job.status)) {
    clearInterval(pollTimer);
    pollTimer = null;
    uploadButton.disabled = !canUpload;
    if (job.status === 'complete') uploadStatus.textContent += ' · Refresh to see the updated projection.';
  }
}

uploadForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!canUpload) return;
  const file = document.getElementById('studio-file').files[0];
  if (!file) return;
  uploadButton.disabled = true;
  uploadStatus.textContent = 'Submitting document…';
  try {
    const form = new FormData();
    form.append('file', file);
    const response = await fetch('/api/ingest', { method: 'POST', body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || `Upload failed (${response.status})`);
    uploadStatus.textContent = `Queued job ${payload.job_id}.`;
    pollTimer = setInterval(() => {
      pollJob(payload.job_id).catch(error => {
        clearInterval(pollTimer);
        pollTimer = null;
        uploadButton.disabled = !canUpload;
        uploadStatus.textContent = error.message;
      });
    }, JOB_POLL_INTERVAL_MS);
    await pollJob(payload.job_id);
  } catch (error) {
    uploadButton.disabled = !canUpload;
    uploadStatus.textContent = error.message;
  }
});

configureIngestion().catch(() => {
  uploadStatus.textContent = 'Could not verify staff ingestion access.';
});

if (new URLSearchParams(window.location.search).get('tab') === 'staff') {
  openStudio();
}
