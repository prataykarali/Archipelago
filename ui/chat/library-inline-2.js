  (function() {
    async function showStaffIngestionPanel() {
      try {
        const response = await fetch('/api/auth/me', { cache: 'no-store' });
        if (!response.ok) return;
        const principal = await response.json();
        if (principal.authenticated && ['librarian', 'administrator'].includes(principal.role)) {
          document.getElementById('librarian-panel').style.display = 'block';
        }
      } catch (_) {}
    }
    showStaffIngestionPanel();

    function getAuthHeaders() { return {}; }

    // Upload form
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) uploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById('upload-file');
      if (!fileInput.files.length) return;
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);
      document.getElementById('upload-status').textContent = 'Uploading...';
      try {
        const resp = await fetch('/api/ingest', { method: 'POST', body: fd, headers: getAuthHeaders() });
        const data = await resp.json();
        document.getElementById('upload-status').textContent = data.error ? `Error: ${data.error}` : `Job ${data.job_id} created (${data.status})`;
      } catch (err) {
        document.getElementById('upload-status').textContent = 'Upload failed: ' + err.message;
      }
    });

    // Index submit
    const indexBtn = document.getElementById('submit-index');
    if (indexBtn) indexBtn.addEventListener('click', async () => {
      const bookId = document.getElementById('index-book-id').value.trim();
      const title = document.getElementById('index-title').value.trim();
      const chaptersRaw = document.getElementById('index-chapters').value.trim();
      if (!bookId) { document.getElementById('index-status').textContent = 'Book ID required'; return; }
      const chapters = chaptersRaw.split('\n').map(l => l.trim()).filter(Boolean);
      document.getElementById('index-status').textContent = 'Submitting...';
      try {
        const resp = await fetch('/api/ingest/index', {
          method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({ doc_id: bookId, title: title || bookId, chapters })
        });
        const data = await resp.json();
        document.getElementById('index-status').textContent = data.error ? `Error: ${data.error}` : `Job ${data.job_id}: ${data.status}`;
      } catch (err) {
        document.getElementById('index-status').textContent = 'Submit failed: ' + err.message;
      }
    });

    // Refresh jobs
    async function loadJobs() {
      try {
        const resp = await fetch('/api/ingest', { headers: getAuthHeaders() });
        const data = await resp.json();
        const jobs = data.jobs || [];
        if (!jobs.length) {
          document.getElementById('jobs-list').textContent = 'No active jobs.';
          return;
        }
        document.getElementById('jobs-list').innerHTML = jobs.slice(0, 10).map(j =>
          `<div style="padding: 0.3rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <span style="color: #a78bfa;">${j.job_id?.slice(0,8) || '?'}</span> —
            <span>${j.source_filename || '?'}</span> —
            <span style="color: ${j.status === 'complete' ? '#10b981' : j.status === 'failed' ? '#ef4444' : '#f59e0b'};">${j.status || '?'}</span>
          </div>`
        ).join('');
      } catch (err) {
        document.getElementById('jobs-list').textContent = 'Failed to load jobs.';
      }
    }
    const refreshBtn = document.getElementById('refresh-jobs');
    if (refreshBtn) refreshBtn.addEventListener('click', loadJobs);
    if (role === 'librarian' || role === 'administrator') loadJobs();
  })();
