const researchPage = document.body.dataset.researchPage;
const byId = id => document.getElementById(id);
let recentRecords = [];
let activeJobId = null;
let jobPollTimer = null;
let inspectedJobId = null;
let fullSessionData = null;
const JOB_POLL_MS = 5000;
const RECORD_REFRESH_MS = 60000;

function coverageText(okfs) {
  const counts = { observed: 0, inferred: 0, derived: 0, unknown: 0, not_reported: 0, not_applicable: 0 };
  okfs.forEach(okf => Object.values(okf?.parameters || {}).forEach(group =>
    Object.values(group).forEach(field => { if (field?.status in counts) counts[field.status]++; })));
  return `${counts.observed} source values · ${counts.inferred} quote-checked facts · ${counts.derived} calculated values · ${counts.unknown} unknown · ${counts.not_reported} not reported. These are field counts, not a quality score.`;
}

function confirmGpuRequest(topic) {
  let dialog = byId('gpu-request-popup');
  if (!dialog) {
    dialog = document.createElement('dialog');
    dialog.id = 'gpu-request-popup';
    dialog.className = 'gpu-request-popup';
    const title = document.createElement('h2');
    title.textContent = 'Use the local GPU for research?';
    const message = document.createElement('p');
    message.id = 'gpu-request-message';
    const actions = document.createElement('div');
    actions.className = 'gpu-request-actions';
    const no = document.createElement('button');
    no.type = 'button';
    no.value = 'no';
    no.textContent = 'No, cancel';
    const yes = document.createElement('button');
    yes.type = 'button';
    yes.value = 'yes';
    yes.textContent = 'Yes, ingest papers';
    actions.append(no, yes);
    dialog.append(title, message, actions);
    document.body.append(dialog);
  }
  byId('gpu-request-message').textContent = `Discover and ingest 25 paper metadata and abstracts for “${topic}” on the local GPU? If it is offline, this will wait in the queue. No paper PDFs will be downloaded.`;
  return new Promise(resolve => {
    const finish = approved => { dialog.close(); resolve(approved); };
    dialog.querySelector('[value="yes"]').onclick = () => finish(true);
    dialog.querySelector('[value="no"]').onclick = () => finish(false);
    dialog.oncancel = event => { event.preventDefault(); finish(false); };
    dialog.showModal();
  });
}

function jobTarget() { return byId(researchPage === 'papers' ? 'paper-status' : 'reply-result'); }

function renderWorkerState(worker) {
  const target = byId('worker-status');
  if (!target) return;
  target.textContent = worker?.online
    ? 'Local GPU system online · queued questions process automatically.'
    : 'Local GPU system offline · new questions remain queued until this workstation returns.';
}

function jobMessage(job, worker) {
  const count = `${job.processed_count || 0}/${job.paper_limit || 25}`;
  const offline = !worker?.online ? ' Local GPU system offline; your request remains queued.' : '';
  if (job.status === 'failed') return `Research job failed: ${job.error || 'source processing unavailable'}.`;
  if (job.status === 'completed' || job.status === 'partial')
    return `Research ${job.status}: ${count} paper records ingested from metadata and abstracts.${job.result_summary?.abstract_facts_extracted ? ` ${job.result_summary.abstract_facts_extracted} quote-checked abstract facts.` : ''}${job.result_summary?.gpu?.peak_allocated_mib ? ` GPU peak: ${job.result_summary.gpu.peak_allocated_mib} MiB.` : ''}`;
  return `Research ${job.status}: ${job.stage || 'QUEUED'} · ${count} papers ingested.${offline}`;
}

async function renderJobPapers(jobId) {
  const target = byId('job-papers');
  if (!target) return;
  const response = await fetch(`/api/research/jobs/${encodeURIComponent(jobId)}/papers`, { cache: 'no-store' });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Could not load paper results.');
  target.replaceChildren();
  byId('intake-count').textContent = `${(data.papers || []).length} papers in last session`;
  (data.papers || []).forEach(paper => {
    const card = document.createElement('article');
    card.className = 'intake-record';
    const title = document.createElement('strong');
    title.textContent = paper.title;
    const meta = document.createElement('small');
    meta.textContent = `${paper.source_name || 'scholarly source'} · ${paper.access_state}`;
    const metrics = document.createElement('p');
    metrics.className = 'paper-metrics';
    metrics.textContent = [
      paper.doi && `DOI ${paper.doi}`,
      paper.citations !== null && paper.citations !== undefined && `Citations ${paper.citations}`,
      paper.references !== null && paper.references !== undefined && `References ${paper.references}`,
      paper.first_author_h_index !== null && paper.first_author_h_index !== undefined && `First-author h-index ${paper.first_author_h_index}`,
      paper.method && `Method ${paper.method}`
    ].filter(Boolean).join(' · ') || 'Source supplied no additional numeric metrics.';
    const link = document.createElement('a');
    link.href = paper.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Open source ↗';
    const abstract = document.createElement('p');
    abstract.textContent = paper.abstract || paper.content || 'Abstract not supplied by this source.';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Inspect OKF JSON';
    button.addEventListener('click', async () => {
      const result = await fetch(`/api/research/jobs/${encodeURIComponent(jobId)}/papers/${encodeURIComponent(paper.paper_id)}/okf`);
      const okf = await result.json();
      if (!result.ok) { button.textContent = okf.error || 'OKF unavailable'; return; }
      byId('json-heading').textContent = `OKF JSON · ${paper.title}`;
      byId('paper-coverage').textContent = coverageText([okf]);
      byId('paper-json').textContent = JSON.stringify(okf, null, 2);
      byId('paper-json-panel').hidden = false;
      byId('download-paper-json').onclick = () => downloadJson(`okf-${paper.paper_id}.json`, okf);
    });
    card.append(title, meta, metrics, abstract, link, button);
    target.append(card);
  });
  if (data.papers?.length && inspectedJobId !== jobId) {
    inspectedJobId = jobId;
    target.querySelector('button')?.click();
  }
}

async function showFullSession() {
  byId('full-session-view').hidden = false;
  byId('paper-wise-view').hidden = true;
  byId('show-full-session').setAttribute('aria-pressed', 'true');
  byId('show-paper-wise').setAttribute('aria-pressed', 'false');
  if (!activeJobId) {
    byId('full-session-summary').textContent = 'No ingestion session is available yet.';
    return;
  }
  byId('full-session-summary').textContent = 'Loading the complete ingestion bundle…';
  try {
    const response = await fetch(`/api/research/jobs/${encodeURIComponent(activeJobId)}/export`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Complete session unavailable.');
    fullSessionData = data;
    byId('full-session-summary').textContent = `${data.paper_count} papers · ${data.job.topic} · ${data.job.status}. Every paper includes its full OKF JSON and source link.`;
    byId('full-session-coverage').textContent = coverageText((data.papers || []).map(paper => paper.okf));
    byId('full-session-json').textContent = JSON.stringify(data, null, 2);
    byId('download-session-json').hidden = false;
  } catch (error) {
    byId('full-session-summary').textContent = error.message || 'Complete session unavailable.';
  }
}

function showPaperWise() {
  byId('full-session-view').hidden = true;
  byId('paper-wise-view').hidden = false;
  byId('show-full-session').setAttribute('aria-pressed', 'false');
  byId('show-paper-wise').setAttribute('aria-pressed', 'true');
}

function renderJobReply(job) {
  if (researchPage !== 'evidence' || !job.result_summary?.answer) return;
  const target = byId('reply-result');
  target.replaceChildren();
  const intro = document.createElement('p');
  intro.textContent = job.result_summary.answer;
  target.append(intro);
  (job.result_summary.sources || []).forEach(source => {
    const link = document.createElement('a');
    link.href = source.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = source.title;
    target.append(link);
  });
}

async function pollJob(jobId) {
  if (jobId !== activeJobId) return;
  try {
    const response = await fetch(`/api/research/jobs/${encodeURIComponent(jobId)}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Research status unavailable.');
    renderWorkerState(data.worker);
    jobTarget().textContent = jobMessage(data.job, data.worker);
    if (researchPage === 'papers') {
      byId('job-results-heading').textContent = `Last session results · ${data.job.topic}`;
      if (data.job.processed_count) await renderJobPapers(jobId);
    }
    if (['completed', 'partial', 'failed'].includes(data.job.status)) {
      renderJobReply(data.job);
      return;
    }
  } catch (error) { jobTarget().textContent = error.message || 'Research status unavailable.'; }
  jobPollTimer = setTimeout(() => pollJob(jobId), JOB_POLL_MS);
}

async function queueResearch(topic) {
  const target = jobTarget();
  if (!await confirmGpuRequest(topic)) {
    target.textContent = 'Research request cancelled. No ingestion was queued.';
    return;
  }
  target.textContent = 'Adding research request to queue…';
  const response = await fetch('/api/research/jobs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, paper_limit: 25 })
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Research queue unavailable.');
  clearTimeout(jobPollTimer);
  activeJobId = data.job.job_id;
  inspectedJobId = null;
  fullSessionData = null;
  if (researchPage === 'papers') {
    byId('job-papers').replaceChildren();
    byId('paper-json-panel').hidden = true;
    byId('full-session-json').textContent = '';
    byId('download-session-json').hidden = true;
    showPaperWise();
    byId('intake-count').textContent = '0 papers in last session';
  }
  renderWorkerState(data.worker);
  target.textContent = jobMessage(data.job, data.worker);
  await pollJob(activeJobId);
}

async function resumeLatestJob() {
  try {
    const requestedJob = new URLSearchParams(window.location.search).get('job');
    const validJob = requestedJob && /^[0-9a-f-]{36}$/i.test(requestedJob);
    const path = validJob ? `/api/research/jobs/${encodeURIComponent(requestedJob)}` : '/api/research/jobs/latest';
    const response = await fetch(path, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Research queue unavailable.');
    renderWorkerState(data.worker);
    if (!data.job) {
      jobTarget().textContent = data.worker?.online ? 'GPU worker online. Ready to research.' : 'Local GPU system offline. Requests will wait in the queue.';
      if (researchPage === 'papers') byId('intake-count').textContent = 'No papers in last session';
      return;
    }
    activeJobId = data.job.job_id;
    await pollJob(activeJobId);
  } catch (error) { jobTarget().textContent = error.message || 'Research queue unavailable.'; }
}

function renderRecords() {
  const target = byId('intake-records');
  if (!target) return;
  target.replaceChildren();
  const kind = researchPage === 'papers' ? 'paper' : 'institutional_page';
  const visible = recentRecords.filter(record => record.kind === kind);
  byId('intake-count').textContent = `${visible.length} recent ${kind === 'paper' ? 'papers' : 'college pages'}`;
  if (!visible.length) {
    const empty = document.createElement('p');
    empty.className = 'intake-empty';
    empty.textContent = 'No saved sources in this view yet.';
    target.append(empty);
    return;
  }
  visible.forEach(record => {
    const card = document.createElement('article');
    card.className = 'intake-record';
    const title = document.createElement('strong');
    title.textContent = record.title;
    const meta = document.createElement('small');
    meta.textContent = `${record.source_name}${record.topic ? ` · ${record.topic}` : ''}`;
    const content = document.createElement('p');
    content.textContent = record.content || 'No abstract provided by this source.';
    const link = document.createElement('a');
    link.href = record.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Open original source ↗';
    card.append(title, meta, content, link);
    if (kind === 'paper') {
      const okfButton = document.createElement('button');
      okfButton.type = 'button';
      okfButton.textContent = 'Inspect complete OKF JSON';
      okfButton.addEventListener('click', async () => {
        okfButton.disabled = true;
        try {
          const response = await fetch(`/api/research/intake/paper-okf/${encodeURIComponent(record.record_key)}`);
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || 'OKF unavailable');
          byId('paper-json').textContent = JSON.stringify(data, null, 2);
          byId('paper-json-panel').hidden = false;
          byId('download-paper-json').onclick = () => downloadJson(`okf-${record.record_key}.json`, data);
          byId('paper-json-panel').scrollIntoView({ behavior: 'smooth' });
        } catch (error) { okfButton.textContent = error.message || 'OKF unavailable'; }
        finally { okfButton.disabled = false; }
      });
      card.append(okfButton);
    }
    target.append(card);
  });
}

async function refreshRecords() {
  const kind = researchPage === 'papers' ? 'paper' : 'institutional_page';
  const topic = researchPage === 'papers' ? new URLSearchParams(window.location.search).get('topic') : null;
  try {
    const suffix = topic ? `&topic=${encodeURIComponent(topic)}` : '';
    const response = await fetch(`/api/research/intake/records?kind=${kind}${suffix}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not load saved sources.');
    recentRecords = data.records || [];
    renderRecords();
  } catch (error) {
    byId('intake-count').textContent = 'Sources unavailable';
    byId('intake-records').textContent = error.message || 'Could not load saved sources.';
  }
}

function downloadJson(name, value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function submitIntake(form, path, payload, statusId) {
  const button = form.querySelector('button[type="submit"]');
  const status = byId(statusId);
  button.disabled = true;
  status.textContent = 'Fetching and saving the college page…';
  try {
    const response = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Intake failed.');
    status.textContent = `Saved “${data.record.title}”.`;
    await refreshRecords();
  } catch (error) { status.textContent = error.message || 'Intake failed.'; }
  finally { button.disabled = false; }
}

byId('paper-form')?.addEventListener('submit', async event => {
  event.preventDefault();
  const topic = byId('paper-topic').value.trim();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  if (!topic) return;
  button.disabled = true;
  try { await queueResearch(topic); }
  catch (error) { jobTarget().textContent = error.message || 'Research queue unavailable.'; }
  finally { button.disabled = false; }
});
byId('show-full-session')?.addEventListener('click', showFullSession);
byId('show-paper-wise')?.addEventListener('click', showPaperWise);
byId('download-session-json')?.addEventListener('click', () => {
  if (fullSessionData) downloadJson(`research-session-${activeJobId}.json`, fullSessionData);
});
byId('college-form')?.addEventListener('submit', event => {
  event.preventDefault();
  const url = byId('college-url').value.trim();
  if (url) submitIntake(event.currentTarget, '/api/research/intake/college', { url }, 'college-status');
});
byId('reply-form')?.addEventListener('submit', async event => {
  event.preventDefault();
  const query = byId('reply-query').value.trim();
  const target = byId('reply-result');
  const button = event.currentTarget.querySelector('button[type="submit"]');
  if (!query) return;
  button.disabled = true;
  target.textContent = 'Queueing paper discovery…';
  try {
    await queueResearch(query);
  } catch (error) { target.textContent = error.message || 'Research reply unavailable.'; }
  finally { button.disabled = false; }
});
document.querySelectorAll('.college-presets button').forEach(button => button.addEventListener('click', () => {
  byId('college-url').value = button.dataset.url;
}));

window.addEventListener('load', async () => {
  const principal = await window.archipelagoResearchReady;
  if (!principal) return;
  if (researchPage === 'college') {
    const manager = ['librarian', 'administrator'].includes(principal.role);
    byId('college-form').hidden = !manager;
    if (!manager) byId('college-readonly').hidden = false;
  }
  if (researchPage === 'college') await refreshRecords();
  if (researchPage === 'papers') {
    const topic = new URLSearchParams(window.location.search).get('topic');
    if (topic) byId('paper-topic').value = topic;
  }
  if (researchPage === 'papers' || researchPage === 'evidence') await resumeLatestJob();
  if (researchPage === 'college') setInterval(refreshRecords, RECORD_REFRESH_MS);
});
