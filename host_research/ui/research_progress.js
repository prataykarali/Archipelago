const progressEl = id => document.getElementById(id);
const PROGRESS_POLL_MS = 4000;
async function progressJson(url) {
  const response = await fetch(url, { cache: 'no-store' });
  if (response.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`/login?timeout=1&next=${next}`);
    throw new Error('Sign in again to follow this job. Local ingestion continues.');
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Research job unavailable');
  return data;
}

async function pollProgress(jobId) {
  try {
    const data = await progressJson(`/api/research/jobs/${encodeURIComponent(jobId)}`);
    const job = data.job;
    const done = Number(job.processed_count || 0);
    const total = Number(job.paper_limit || 25);
    progressEl('progress-topic').textContent = job.topic;
    const topicLink = progressEl('progress-topic-link');
    topicLink.href = `/research/topic?name=${encodeURIComponent(job.topic)}`;
    topicLink.hidden = !['completed', 'partial'].includes(job.status);
    topicLink.style.display = topicLink.hidden ? 'none' : '';
    progressEl('progress-fill').style.width = `${Math.min(100, 100 * done / total)}%`;
    const track = document.querySelector('.research-progress-track');
    track.setAttribute('aria-valuemax', String(total));
    track.setAttribute('aria-valuenow', String(done));
    const state = job.stage === 'AWAITING_LOCAL_APPROVAL' ? 'Waiting for workstation approval' : job.stage || job.status;
    progressEl('progress-status').textContent = `${state} · ${done}/${total} papers ingested${job.error ? ` · ${job.error}` : ''}`;
    progressEl('progress-worker').textContent = data.worker?.online ? 'Local workstation online.' : 'Local workstation offline. This job remains queued until it reconnects.';
    const summary = job.result_summary || {};
    if (['completed', 'partial'].includes(job.status)) {
      const hf = summary.hf_dataset?.status || 'not reported';
      progressEl('progress-summary').textContent = `${summary.abstract_facts_extracted || 0} quote-checked abstract facts · ${summary.fulltext_extracted || 0} papers with page-linked Indra facts · Hugging Face: ${hf}. The dashboard shows fields supported by sources.`;
    } else {
      progressEl('progress-summary').textContent = `Current stage: ${state}. Source access and OCR results will appear here when complete.`;
    }
    if (['completed', 'partial', 'failed'].includes(job.status)) return;
    window.archipelagoTouchSession?.();
  } catch (error) {
    progressEl('progress-status').textContent = error.message === 'unauthorized'
      ? 'Sign in again to follow this job. Local ingestion continues.'
      : error.message;
  }
  window.setTimeout(() => pollProgress(jobId), PROGRESS_POLL_MS);
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  const jobId = new URLSearchParams(window.location.search).get('job');
  if (!jobId || !/^[0-9a-f-]{36}$/i.test(jobId)) {
    progressEl('progress-status').textContent = 'No research job selected. Start from the research graph.';
    return;
  }
  pollProgress(jobId);
});
