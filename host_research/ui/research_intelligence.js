"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;
const S5_STATE_KEY = 'archipelago_research_state_v1';
const S5_PENDING_KEY = 'archipelago_research_pending_v1';
const SEARCH_RECOVERY_INTERVAL_MS = 8000;
const SEARCH_RECOVERY_WINDOW_MS = 360000;

function pendingSearch() {
  try { return JSON.parse(sessionStorage.getItem(S5_PENDING_KEY) || 'null'); }
  catch (_) { return null; }
}

function clearPendingSearch() {
  sessionStorage.removeItem(S5_PENDING_KEY);
}

async function recoverPendingSearch() {
  const pending = pendingSearch();
  if (!pending?.request_id) return;
  const status = s5('intelligence-status');
  const submit = s5('intelligence-form')?.querySelector('button[type="submit"]');
  if (Date.now() - pending.started_at > SEARCH_RECOVERY_WINDOW_MS) {
    clearPendingSearch();
    if (status) status.textContent = 'The search did not finish. Please retry.';
    return;
  }
  if (submit) submit.disabled = true;
  if (status) status.textContent = `Researching "${pending.topic}". You can visit other pages and return here.`;
  try {
    const job = await s5Json(`/api/research/intelligence/search-status/${pending.request_id}`);
    if (job.status === 'completed') {
      const run = await s5Json(`/api/research/intelligence/runs/${job.run_id}`);
      activeRunId = job.run_id;
      showRun(run);
      saveResearchState();
      clearPendingSearch();
      if (submit) submit.disabled = false;
      if (status) status.textContent = `Done — loaded ${run.papers?.length || 0} papers for "${pending.topic}".`;
      await loadHistory();
      return;
    }
  } catch (error) {
    if (status) status.textContent = `Checking search progress: ${error.message}`;
  }
  setTimeout(recoverPendingSearch, SEARCH_RECOVERY_INTERVAL_MS);
}

function formatShortDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function saveResearchState() {
  try {
    const form = s5('intelligence-form');
    const data = form ? Object.fromEntries(new FormData(form)) : {};
    sessionStorage.setItem(S5_STATE_KEY, JSON.stringify({ run_id: activeRunId, form: data }));
    if (activeRunId) {
      const sp = new URLSearchParams(location.search);
      sp.set('run', activeRunId);
      history.replaceState(null, '', `${location.pathname}?${sp.toString()}`);
    }
  } catch (_) {}
}

function restoreResearchForm() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(S5_STATE_KEY) || '{}') || {};
    const form = s5('intelligence-form');
    if (form && saved.form) {
      for (const [k, v] of Object.entries(saved.form)) {
        const el = form.elements.namedItem(k);
        if (el && v != null && String(v) !== '') el.value = String(v);
      }
    }
    const urlRun = new URLSearchParams(location.search).get('run');
    return urlRun || saved.run_id || null;
  } catch (_) {
    return null;
  }
}

function currentSearchOptions() {
  const payload = Object.fromEntries(new FormData(s5('intelligence-form')));
  payload.top_k = Number(payload.top_k);
  for (const field of ['year_from', 'year_to']) payload[field] = payload[field] ? Number(payload[field]) : null;
  payload.open_access = payload.open_access === 'true' ? true : payload.open_access === 'false' ? false : null;
  return payload;
}

async function s5Json(url, options = {}) {
  const response = await fetch(url, { cache: 'no-store', ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Research service unavailable');
  return data;
}

function showRun(run) {
  s5('intelligence-results').hidden = false;
  s5('retrieved-at').textContent = `Retrieved ${run.retrieved_at} · ${run.candidate_count} provider candidates · ${run.filtered_count} after filters`;
  s5('provider-status').textContent = run.sources.map(source => `${source.source}: ${source.status} (${source.record_count})`).join(' · ');
  const excelLink = s5('excel-link');
  excelLink.href = `/api/research/intelligence/runs/${activeRunId}/xlsx?mode=standard`;
  excelLink.onclick = async event => {
    event.preventDefault();
    const runId = activeRunId;
    if (!runId) return;
    const mode = 'standard';
    try {
      const resp = await fetch(`/api/research/intelligence/runs/${runId}/xlsx?mode=${mode}`, { cache: 'no-store', credentials: 'include' });
      if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `archipelago-research-${runId.slice(0, 8)}-${mode}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      s5('provider-status').textContent = err.message || 'Could not download workbook.';
    }
  };
  const list = s5('paper-results');
  list.replaceChildren();
  for (const paper of run.papers) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    title.textContent = paper.title;
    const facts = document.createElement('p');
    facts.textContent = [paper.authors?.map(author => author.name).join(', '), paper.venue].filter(Boolean).join(' · ');
    const metrics = document.createElement('dl');
    metrics.className = 'paper-metrics';
    const number = (value, digits = 0) => Number.isFinite(value) ? value.toFixed(digits) : 'N/A';
    const listValue = value => Array.isArray(value) && value.length ? value.map(item => typeof item === 'string' ? item : item?.name || item?.label || JSON.stringify(item)).join(', ') : 'N/A';
    const metricRows = [
      ['Citations', number(paper.citation_count)],
      ['Citations per year', number(paper.citations_per_year, 2)],
      ['FWCI', number(paper.fwci, 2)],
      ['Citation percentile', Number.isFinite(paper.citation_normalized_percentile?.value) ? `${(paper.citation_normalized_percentile.value * 100).toFixed(1)}%` : 'N/A'],
      ['Topic relevance score', Number.isFinite(paper.relevance_classification?.confidence) ? paper.relevance_classification.confidence.toFixed(2) : 'N/A'],
      ['Publication year', Number.isFinite(paper.year) ? String(paper.year) : 'N/A'],
      ['Benchmark performance', listValue(paper.evaluation_metrics)],
      ['Methodological evidence', listValue(paper.methods)],
      ['Reproducibility', [paper.code_repo_urls?.length ? 'Code linked' : null, paper.dataset_repo_urls?.length ? 'Data linked' : null].filter(Boolean).join(', ') || 'N/A'],
      ['Reference count', Array.isArray(paper.references) && paper.references.length ? String(paper.references.length) : 'N/A'],
      ['Influential citations', number(paper.influential_citations)],
      ['Open access', paper.is_open_access === true ? 'Yes' : paper.is_open_access === false ? 'No' : 'N/A'],
    ];
    for (const [label, value] of metricRows) {
      const item = document.createElement('div');
      const term = document.createElement('dt');
      const description = document.createElement('dd');
      term.textContent = label;
      description.textContent = value;
      item.append(term, description);
      metrics.append(item);
    }
    article.append(title, facts, metrics);
    if (paper.url && paper.url.startsWith('https://')) {
      const link = document.createElement('a');
      link.href = paper.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = 'Open provider record ↗';
      article.append(link);
    }
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Abstract, references and identifiers';
    const body = document.createElement('p');
    body.textContent = paper.abstract || 'Abstract unavailable from selected providers.';
    const references = document.createElement('p');
    references.textContent = `${paper.references.length} provider reference IDs · DOI: ${paper.doi || 'unavailable'}`;
    details.append(summary, body, references);
    article.append(details);
    list.append(article);
  }
  if (!run.papers.length) list.textContent = 'No papers matched the filters in the returned provider results.';
}

async function loadHistory() {
  const history = s5('run-history');
  const statusEl = s5('intelligence-status');
  if (statusEl) statusEl.textContent = 'Loading previous research searches…';
  try {
    const data = await s5Json('/api/research/intelligence/runs');
    history.replaceChildren();
    if (!data.runs.length) {
      history.textContent = 'No previous searches yet.';
    }
    for (const run of data.runs) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${run.topic} · ${formatShortDate(run.created_at)}`;
      button.addEventListener('click', async () => {
        activeRunId = run.run_id;
        if (statusEl) statusEl.textContent = `Loading saved search "${run.topic}"…`;
        try {
          const loaded = await s5Json(`/api/research/intelligence/runs/${activeRunId}`);
          showRun(loaded);
          saveResearchState();
          if (statusEl) statusEl.textContent = `Loaded ${loaded.papers?.length || 0} papers for "${run.topic}".`;
          s5('intelligence-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (err) {
          if (statusEl) statusEl.textContent = err.message;
        }
      });
      history.append(button);
    }
    if (statusEl && statusEl.textContent === 'Loading previous research searches…') {
      statusEl.textContent = 'Ready to search.';
    }
  } catch (error) {
    history.textContent = error.message;
    if (statusEl) statusEl.textContent = error.message;
  }
}

async function loadMonitors() {
  const data = await s5Json('/api/research/intelligence/monitors');
  const list = s5('monitor-list');
  list.replaceChildren();
  for (const monitor of data.monitors) {
    const row = document.createElement('p');
    const label = document.createElement('span');
    label.textContent = `${monitor.options.topic} · ${monitor.enabled ? 'active' : 'disabled'} · last successful check ${monitor.last_success_at || 'never'} · next check ${monitor.next_run_at || 'not scheduled'}${monitor.last_error ? ` · error ${monitor.last_error} (retry ${monitor.consecutive_failures || 0})` : ''}`;
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.textContent = monitor.enabled ? 'Disable' : 'Activate';
    toggle.addEventListener('click', async () => {
      try {
        await s5Json(`/api/research/intelligence/monitors/${monitor.id}`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: !monitor.enabled })
        });
        s5('monitor-status').textContent = monitor.enabled ? 'Monitoring disabled.' : 'Monitoring activated. A configured worker will refresh this topic.';
        await loadMonitors();
      } catch (error) { s5('monitor-status').textContent = error.message; }
    });
    row.append(label, toggle);
    const cadenceLabel = document.createElement('label');
    cadenceLabel.textContent = 'Check every ';
    const cadence = document.createElement('select');
    cadence.setAttribute('aria-label', `Refresh frequency for ${monitor.options.topic}`);
    for (const [hours, caption] of [['6', '6 hours'], ['24', '24 hours'], ['168', '7 days']]) {
      const option = new Option(caption, hours);
      cadence.append(option);
    }
    cadence.value = String(monitor.cadence_hours || 24);
    cadence.addEventListener('change', async () => {
      try {
        await s5Json(`/api/research/intelligence/monitors/${monitor.id}`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cadence_hours: Number(cadence.value) })
        });
        s5('monitor-status').textContent = 'Monitoring frequency updated.';
        await loadMonitors();
      } catch (error) { s5('monitor-status').textContent = error.message; }
    });
    cadenceLabel.append(cadence);
    row.append(cadenceLabel);
    if (monitor.enabled) {
      const refresh = document.createElement('button');
      refresh.type = 'button';
      refresh.textContent = 'Refresh now';
      refresh.addEventListener('click', async () => {
        refresh.disabled = true;
        s5('monitor-status').textContent = 'Refreshing metadata…';
        try {
          const result = await s5Json(`/api/research/intelligence/monitors/${monitor.id}/run`, { method: 'POST' });
          s5('monitor-status').textContent = `Refresh ${result.status}.`;
          await loadMonitors();
          await loadUpdates();
        } catch (error) { s5('monitor-status').textContent = error.message; }
        finally { refresh.disabled = false; }
      });
      row.append(refresh);
    }
    const history = document.createElement('details');
    const historySummary = document.createElement('summary');
    historySummary.textContent = 'Execution history';
    history.append(historySummary);
    history.addEventListener('toggle', async () => {
      if (!history.open) return;
      try {
        const data = await s5Json(`/api/research/intelligence/monitors/${monitor.id}/history`);
        history.replaceChildren(historySummary);
        for (const item of data.history) {
          const entry = document.createElement('p');
          entry.textContent = `${item.finished_at || item.created_at} · ${item.status}${item.error ? ` · ${item.error}` : ''}`;
          history.append(entry);
        }
      } catch (error) { history.append(document.createTextNode(error.message)); }
    });
    row.append(history);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove monitor';
    remove.setAttribute('aria-label', `Remove monitor for ${monitor.options.topic}`);
    remove.addEventListener('click', async () => {
      if (!confirm(`Remove monitoring for ${monitor.options.topic} and its update history?`)) return;
      try {
        await s5Json(`/api/research/intelligence/monitors/${monitor.id}`, { method: 'DELETE' });
        s5('monitor-status').textContent = 'Monitor removed.';
        await loadMonitors();
        await loadUpdates();
      } catch (error) { s5('monitor-status').textContent = error.message; }
    });
    row.append(remove);
    list.append(row);
  }
}

async function loadUpdates() {
  const list = s5('research-updates');
  try {
    const data = await s5Json('/api/research/intelligence/updates');
    list.replaceChildren();
    if (!data.updates.length) list.textContent = 'No updates yet.';
    for (const update of data.updates) {
      const entry = document.createElement('p');
      entry.textContent = `${update.created_at} · ${update.kind.replaceAll('_', ' ')} · ${update.payload.title || update.subject_id}`;
      list.append(entry);
    }
  } catch (error) { list.textContent = error.message; }
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  const savedRunId = restoreResearchForm();
  await loadHistory();
  if (savedRunId) {
    try {
      s5('intelligence-status').textContent = 'Restoring your previous research view…';
      activeRunId = savedRunId;
      const run = await s5Json(`/api/research/intelligence/runs/${savedRunId}`);
      showRun(run);
      s5('intelligence-status').textContent = `Restored ${run.papers?.length || 0} papers.`;
    } catch (_) {
      activeRunId = null;
      s5('intelligence-status').textContent = 'Ready to search.';
    }
  }
  if (pendingSearch()) void recoverPendingSearch();
  s5('intelligence-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = currentSearchOptions();
    const requestId = crypto.randomUUID();
    payload.client_request_id = requestId;
    sessionStorage.setItem(S5_PENDING_KEY, JSON.stringify({ request_id: requestId, topic: payload.topic, started_at: Date.now() }));
    saveResearchState();
    s5('intelligence-status').textContent = `Fetching papers from OpenAlex, Crossref, Semantic Scholar & arXiv for "${payload.topic}"…`;
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const run = await s5Json('/api/research/intelligence/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), keepalive: true });
      clearPendingSearch();
      activeRunId = run.run_id;
      showRun(run);
      saveResearchState();
      const liveCount = (run.sources || []).filter(s => s.status === 'live').length;
      s5('intelligence-status').textContent = `Done — loaded ${run.papers.length} papers from ${liveCount} live provider(s).`;
      await loadHistory();
    } catch (error) {
      s5('intelligence-status').textContent = `Search request interrupted (${error.message}); checking for the completed search…`;
      if (pendingSearch()) void recoverPendingSearch();
    }
    finally { if (!pendingSearch()) form.querySelector('button[type="submit"]').disabled = false; }
  });
});
