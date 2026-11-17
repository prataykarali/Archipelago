"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;
const S5_STATE_KEY = 'archipelago_research_state_v2';
const S5_PENDING_KEY = 'archipelago_research_pending_v2';
const SEARCH_RECOVERY_INTERVAL_MS = 8000;
const SEARCH_RECOVERY_WINDOW_MS = 360000;
const SEARCH_PROGRESS_TICK_MS = 1000;
const SEARCH_SLOW_NOTICE_MS = 30000;
const SEARCH_LONG_NOTICE_MS = 90000;
let progressTimer = null;

function pendingSearch() {
  try { return JSON.parse(sessionStorage.getItem(S5_PENDING_KEY) || 'null'); }
  catch (_) { return null; }
}

function clearPendingSearch() {
  sessionStorage.removeItem(S5_PENDING_KEY);
  renderSearchProgress();
}

function renderSearchProgress() {
  const panel = s5('research-progress');
  if (!panel) return;
  const pending = pendingSearch();
  panel.hidden = !pending;
  if (!pending) {
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = null;
    return;
  }
  const elapsedSeconds = Math.floor(Math.max(0, Date.now() - pending.started_at) / SEARCH_PROGRESS_TICK_MS);
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = String(elapsedSeconds % 60).padStart(2, '0');
  s5('research-elapsed').textContent = minutes ? `${minutes}m ${seconds}s elapsed` : `${elapsedSeconds}s elapsed`;
  const age = Date.now() - pending.started_at;
  s5('research-progress-message').textContent = age >= SEARCH_LONG_NOTICE_MS
    ? 'Still waiting for a saved result. Provider requests can be slow; you may leave this page and return.'
    : age >= SEARCH_SLOW_NOTICE_MS
      ? 'The request is taking longer than usual. Waiting for the research service to respond.'
      : 'Request sent. Waiting for the research service to respond.';
}

function startSearchProgress() {
  renderSearchProgress();
  if (!progressTimer) progressTimer = setInterval(renderSearchProgress, SEARCH_PROGRESS_TICK_MS);
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
  startSearchProgress();
  if (status) status.textContent = `Researching "${pending.topic}". You can visit other pages and return here.`;
  try {
    const job = await s5Json(`/api/research/intelligence/search-status/${pending.request_id}`);
    if (job.status === 'completed') {
      const run = await s5Json(`/api/research/intelligence/runs/${job.run_id}`);
      activeRunId = job.run_id;
      saveResearchState();
      clearPendingSearch();
      await showRun(run);
      if (submit) submit.disabled = false;
      if (status) status.textContent = `Done — loaded ${s5('paper-results').children.length} source-linked papers for "${pending.topic}".`;
      return;
    }
  } catch (error) {
    if (!pendingSearch()) {
      if (status) status.textContent = `Papers were saved but could not be displayed (${error.message}). Reload this page to retry.`;
      if (submit) submit.disabled = false;
      return;
    }
    if (status) status.textContent = `Checking search progress: ${error.message}`;
  }
  setTimeout(recoverPendingSearch, SEARCH_RECOVERY_INTERVAL_MS);
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
        if (!['topic', 'year_from', 'year_to'].includes(k)) continue;
        const el = form.elements.namedItem(k);
        if (el && v != null && String(v) !== '') el.value = String(v);
      }
    }
    const query = new URLSearchParams(location.search);
    const urlTopic = query.get('topic');
    if (form && urlTopic && urlTopic.length >= 3) form.elements.namedItem('topic').value = urlTopic;
    const urlRun = query.get('run');
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
  let data;
  try { data = await response.json(); }
  catch (_) { data = { error: `HTTP ${response.status}` }; }
  if (!response.ok) {
    const error = new Error(data.message || data.error || 'Research service unavailable');
    error.httpStatus = response.status;
    throw error;
  }
  return data;
}

const metricNumber = (value, digits = 0) => Number.isFinite(value) ? Number(value).toFixed(digits) : '—';
const metricList = value => {
  if (!Array.isArray(value)) return '—';
  const names = value.map(item => typeof item === 'string' ? item : item?.name || item?.label || item?.normalized_value)
    .filter(item => typeof item === 'string' && item.trim());
  return names.length ? names.join(', ') : '—';
};
const openAlexAuthorId = value => typeof value === 'string' && value ? value.split('/').filter(Boolean).at(-1) : null;
const paperAuthorIds = paper => Array.isArray(paper.source_metadata?.author_openalex_ids) ? paper.source_metadata.author_openalex_ids.map(openAlexAuthorId) : [];

function metricGrid(rows) {
  const grid = document.createElement('dl');
  grid.className = 'paper-metrics';
  for (const [label, value] of rows) {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    const description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value == null || value === '' ? '—' : String(value);
    item.append(term, description);
    grid.append(item);
  }
  return grid;
}

async function showRun(run) {
  const dossier = await s5Json(`/api/research/intelligence/runs/${encodeURIComponent(activeRunId)}/dossier`);
  const paperRows = (dossier.papers || []).map(detail => ({
    detail,
    paper: run.papers.find(paper => paper.title === detail.title && String(paper.doi || '') === detail.doi)
  })).filter(row => row.paper);
  s5('intelligence-results').hidden = false;
  s5('topic-dossier-link').href = `/research/topic?run=${encodeURIComponent(activeRunId)}`;
  s5('paper-list-link').textContent = `Browse ${paperRows.length} paper pages ↓`;
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
  const authorsById = new Map((run.author_observations || []).map(author => [author.id, author]));
  const visiblePapers = paperRows.map(row => row.paper);
  for (const { detail, paper } of paperRows) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    title.textContent = paper.title;
    const facts = document.createElement('p');
    facts.textContent = [paper.authors?.map(author => author.name).join(', '), paper.venue].filter(Boolean).join(' · ');
    const metricRows = [
      [`Citation count${paper.citation_provider ? ` (${paper.citation_provider})` : ''}`, metricNumber(paper.citation_count)],
      ['Citations per year', metricNumber(paper.citations_per_year, 2)],
      ['FWCI (OpenAlex)', metricNumber(paper.fwci, 2)],
      ['Citation percentile (OpenAlex)', Number.isFinite(paper.citation_normalized_percentile?.value) ? `${(paper.citation_normalized_percentile.value * 100).toFixed(1)}%` : '—'],
      ['Topic relevance score (0–1)', metricNumber(paper.relevance_classification?.confidence, 2)],
      ['Publication year', Number.isFinite(paper.year) ? String(paper.year) : '—'],
      ['Benchmark performance', metricList(paper.benchmark_performance)],
      ['Methodological evidence', metricList(paper.methods)],
      ['Reproducibility indicators', [paper.code_repo_urls?.length ? 'Code' : null, paper.dataset_repo_urls?.length ? 'Data' : null, paper.checkpoint_urls?.length ? 'Checkpoints' : null, paper.experimental_details_url ? 'Experimental details' : null].filter(Boolean).join(', ') || '—'],
      ['Reference count', metricNumber(paper.reference_count ?? (paper.references?.length || null))],
      ['Influential citation count (Semantic Scholar)', metricNumber(paper.influential_citations)],
      ['Open-access status', paper.is_open_access === true ? 'Yes' : paper.is_open_access === false ? 'No' : '—'],
    ];
    const additionalHeaders = [
      'Paper Age (Years)', 'Title Query Match (%)', 'Verified Source Count',
      'Author Count', 'Metadata Completeness (%)', 'Method Reported',
      'Benchmark Reported', 'Code Link Reported', 'Data Link Reported',
      'Venue Papers in This Search', 'Venue Author Bylines in This Search',
      'Venue Newest Paper Year in This Search', 'Venue Median Paper Year in This Search',
      'Venue Mean Title Match in This Search (%)',
      'Venue Public Full-Text Links in This Search',
      'Venue h-index', 'Venue i10-index', 'Indexed Publication Count',
      'Mean Citedness', 'Indexing Status'
    ];
    for (const header of additionalHeaders) {
      const index = dossier.paper_headers.indexOf(header);
      const value = index >= 0 ? detail.rankable_values[index] : null;
      metricRows.push([header, value == null || value === '' ? '—' : String(value)]);
    }
    const coverage = document.createElement('p');
    coverage.textContent = `${metricRows.filter(([, value]) => value !== '—').length} of ${metricRows.length} paper and venue parameters filled · search counts cover these retrieved papers only · 0 for an evidence flag means the retrieved record did not report it. Provider metrics remain blank when unreported.`;
    article.append(title, facts, coverage, metricGrid(metricRows));
    const paperDetail = document.createElement('a');
    paperDetail.href = `/research/paper?run=${encodeURIComponent(activeRunId)}&paper=${detail.index}`;
    paperDetail.textContent = 'Open paper page ↗';
    article.append(paperDetail);
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
    references.textContent = `${paper.references?.length || 0} provider reference IDs · DOI: ${paper.doi || 'unavailable'}`;
    details.append(summary, body, references);
    article.append(details);
    const authorDetails = document.createElement('details');
    const authorSummary = document.createElement('summary');
    authorSummary.textContent = 'Author parameters';
    authorDetails.append(authorSummary);
    const authorCoverage = document.createElement('p');
    authorCoverage.textContent = 'Byline measures cover this search only. Provider citation metrics appear when verified.';
    authorDetails.append(authorCoverage);
    const providerIds = paperAuthorIds(paper);
    paper.authors?.forEach((author, index) => {
      const id = providerIds[index];
      const observation = authorsById.get(id);
      const values = observation?.metrics || {};
      const recent = Array.isArray(values.counts_by_year) && values.counts_by_year.length ? values.counts_by_year.filter(row => Number.isInteger(row.year) && row.year >= new Date().getFullYear() - 4 && Number.isInteger(row.cited_by_count)).reduce((sum, row) => sum + row.cited_by_count, 0) : null;
      const bylinePapers = visiblePapers.filter(record => id
        ? paperAuthorIds(record).includes(id)
        : record.authors?.some(person => person.name?.trim().toLocaleLowerCase() === author.name?.trim().toLocaleLowerCase()));
      const isAuthorAt = (record, position) => id
        ? paperAuthorIds(record)[position] === id
        : record.authors?.[position]?.name?.trim().toLocaleLowerCase() === author.name?.trim().toLocaleLowerCase();
      const bylineYears = bylinePapers.map(record => record.year).filter(Number.isInteger).sort((a, b) => a - b);
      const allQueryWords = new Set((run.options?.topic || '').toLocaleLowerCase().match(/\w+/g) || []);
      const queryWords = new Set([...allQueryWords].filter(word => !new Set(['a', 'an', 'and', 'for', 'in', 'of', 'on', 'the', 'to', 'with']).has(word)));
      if (!queryWords.size) allQueryWords.forEach(word => queryWords.add(word));
      const matches = bylinePapers.map(record => {
        const titleWords = new Set((record.title || '').toLocaleLowerCase().match(/\w+/g) || []);
        return queryWords.size ? 100 * [...queryWords].filter(word => titleWords.has(word)).length / queryWords.size : 0;
      });
      const bylineCoauthors = new Set(bylinePapers.flatMap(record => (record.authors || []).map(person => person.name?.trim().toLocaleLowerCase()).filter(name => name && name !== author.name?.trim().toLocaleLowerCase())));
      const heading = document.createElement('h4');
      heading.textContent = author.name;
      authorDetails.append(heading, metricGrid([
        ['h-index', metricNumber(values.h_index)],
        ['i10-index', metricNumber(values.i10_index)],
        ['m-quotient', Number.isFinite(values.h_index) && Number.isInteger(values.earliest_year) && values.earliest_year <= new Date().getFullYear() ? metricNumber(values.h_index / (new Date().getFullYear() - values.earliest_year + 1), 2) : '—'],
        ['Total citations', metricNumber(values.citation_count)],
        ['Total publications', metricNumber(values.publication_count)],
        ['Average citations per paper', values.publication_count > 0 && Number.isFinite(values.citation_count) ? metricNumber(values.citation_count / values.publication_count, 2) : '—'],
        ['Recent citations (5 years)', metricNumber(recent)],
        ['Papers in this search', String(bylinePapers.length)],
        ['Mean title match in this search (%)', matches.length ? metricNumber(matches.reduce((sum, value) => sum + value, 0) / matches.length, 1) : '0'],
        ['Newest paper year in this search', bylineYears.length ? String(bylineYears.at(-1)) : '—'],
        ['Median paper year in this search', bylineYears.length ? String((bylineYears[Math.floor((bylineYears.length - 1) / 2)] + bylineYears[Math.ceil((bylineYears.length - 1) / 2)]) / 2) : '—'],
        ['Distinct coauthor bylines in this search', String(bylineCoauthors.size)],
        ['First-author publications (this search)', String(bylinePapers.filter(record => isAuthorAt(record, 0)).length)],
        ['Last-author publications (this search)', String(bylinePapers.filter(record => isAuthorAt(record, (record.authors?.length || 1) - 1)).length)],
      ]));
      if (observation?.source_url?.startsWith('https://')) {
        const authorSource = document.createElement('a');
        authorSource.href = observation.source_url;
        authorSource.target = '_blank';
        authorSource.rel = 'noopener noreferrer';
        authorSource.textContent = `Author source: ${observation.provider} ↗`;
        authorDetails.append(authorSource);
      }
    });
    article.append(authorDetails);
    list.append(article);
  }
  if (!paperRows.length) list.textContent = 'No source-linked papers with enough verified identity metadata matched this topic.';
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
  if (savedRunId && !pendingSearch()) {
    try {
      activeRunId = savedRunId;
      const run = await s5Json(`/api/research/intelligence/runs/${encodeURIComponent(savedRunId)}`);
      await showRun(run);
      s5('intelligence-status').textContent = `Restored ${s5('paper-results').children.length} source-linked papers.`;
    } catch (error) {
      activeRunId = null;
      sessionStorage.removeItem(S5_STATE_KEY);
      s5('intelligence-status').textContent = error.message || 'Ready to search.';
      const query = new URLSearchParams(location.search);
      query.delete('run');
      history.replaceState(null, '', `${location.pathname}?${query.toString()}`);
    }
  }
  if (pendingSearch()) void recoverPendingSearch();
  s5('intelligence-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = currentSearchOptions();
    activeRunId = null;
    s5('intelligence-results').hidden = true;
    const searchUrl = new URLSearchParams(location.search);
    searchUrl.delete('run');
    history.replaceState(null, '', `${location.pathname}?${searchUrl.toString()}`);
    const requestId = crypto.randomUUID();
    payload.client_request_id = requestId;
    sessionStorage.setItem(S5_PENDING_KEY, JSON.stringify({ request_id: requestId, topic: payload.topic, started_at: Date.now() }));
    startSearchProgress();
    saveResearchState();
    s5('intelligence-status').textContent = `Search request sent for "${payload.topic}". Waiting for a result…`;
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const run = await s5Json('/api/research/intelligence/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), keepalive: true });
      clearPendingSearch();
      activeRunId = run.run_id;
      saveResearchState();
      await showRun(run);
      const liveCount = (run.sources || []).filter(s => s.status === 'live').length;
      s5('intelligence-status').textContent = `Done — loaded ${s5('paper-results').children.length} source-linked papers from ${liveCount} live provider(s).`;
    } catch (error) {
      if (error.httpStatus) {
        clearPendingSearch();
        s5('intelligence-status').textContent = `Search failed: ${error.message}. Please retry.`;
      } else if (pendingSearch()) {
        s5('intelligence-status').textContent = `Search request interrupted (${error.message}); checking for the completed search…`;
        void recoverPendingSearch();
      } else {
        s5('intelligence-status').textContent = `Papers were saved but could not be displayed (${error.message}). Reload this page to retry.`;
      }
    }
    finally { if (!pendingSearch()) form.querySelector('button[type="submit"]').disabled = false; }
  });
});
