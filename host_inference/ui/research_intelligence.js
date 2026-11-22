"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;
const S5_STATE_KEY = 'archipelago_research_state_v2';
const S5_PENDING_KEY = 'archipelago_research_pending_v2';
const SEARCH_RECOVERY_INTERVAL_MS = 3000;
const SEARCH_RECOVERY_WINDOW_MS = 360000;
const SEARCH_PROGRESS_TICK_MS = 1000;
const SEARCH_SLOW_NOTICE_MS = 25000;
const SEARCH_LONG_NOTICE_MS = 75000;
const RECENT_TOPIC_LIMIT = 10;

const SEARCH_STATUS_STAGES = [
  "Connecting to OpenAlex, Crossref, Semantic Scholar and arXiv APIs…",
  "Querying academic providers for matching peer-reviewed literature…",
  "Collecting candidate records and deduplicating by DOI/arXiv IDs…",
  "Normalizing titles, abstracts and publication venue metadata…",
  "Computing query relevance scores and filtering candidates…",
  "Enriching author metrics, ORCID citations and affiliations…",
  "Assembling discovery fit rankings and source corroboration…",
  "Structuring 4-section Excel export (Paper, Author, Publication, Resource)…",
  "Saving complete research run to durable library database…",
  "Finalizing paper dossier and rendering results…"
];

// Route safety only: a missing identifier must not become a "run=undefined" URL.
function validRunId(value) {
  return typeof value === 'string' && Boolean(value.trim()) &&
    !/^(?:undefined|null|nan)$/i.test(value.trim());
}

let progressTimer = null;
let recoveryTimer = null;
let isUnloading = false;
let recentRunsInFlight = null;
let lastRecentRunsAt = 0;
let restoreInFlight = null;

function stopResearchPolling(event) {
  if (!event?.persisted) isUnloading = true;
  if (progressTimer) {
    clearInterval(progressTimer);
    progressTimer = null;
  }
  if (recoveryTimer) {
    clearTimeout(recoveryTimer);
    recoveryTimer = null;
  }
}

window.addEventListener('pagehide', stopResearchPolling);
window.addEventListener('beforeunload', stopResearchPolling);

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
  const stageIdx = Math.min(Math.floor(elapsedSeconds / 7), SEARCH_STATUS_STAGES.length - 1);
  s5('research-progress-message').textContent = SEARCH_STATUS_STAGES[stageIdx];
}

function startSearchProgress() {
  renderSearchProgress();
  if (!progressTimer) progressTimer = setInterval(renderSearchProgress, SEARCH_PROGRESS_TICK_MS);
}

async function recoverPendingSearch() {
  if (isUnloading) return;
  if (typeof document !== 'undefined' && document.hidden) {
    recoveryTimer = setTimeout(recoverPendingSearch, SEARCH_RECOVERY_INTERVAL_MS);
    return;
  }
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
    const job = await s5Json(`/api/research/intelligence/search-status/${pending.request_id}`, {
      headers: { 'X-Background-Poll': '1' },
    });
    if (job.status === 'completed') {
      if (!validRunId(job.run_id)) {
        clearPendingSearch();
        if (status) status.textContent = 'Search completed without a valid run ID. Please retry.';
        if (submit) submit.disabled = false;
        return;
      }
      await s5Json(`/api/research/intelligence/runs/${job.run_id}`);
      activeRunId = job.run_id;
      saveResearchState();
      clearPendingSearch();
      location.assign(`/research/papers?run=${encodeURIComponent(job.run_id)}`);
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
  if (!isUnloading) {
    recoveryTimer = setTimeout(recoverPendingSearch, SEARCH_RECOVERY_INTERVAL_MS);
  }
}

function saveResearchState() {
  try {
    const form = s5('intelligence-form');
    const data = form ? Object.fromEntries(new FormData(form)) : {};
    sessionStorage.setItem(S5_STATE_KEY, JSON.stringify({ run_id: validRunId(activeRunId) ? activeRunId : null, form: data }));
    if (validRunId(activeRunId)) {
      const sp = new URLSearchParams(location.search);
      sp.set('run', activeRunId);
      history.replaceState(null, '', `${location.pathname}?${sp.toString()}${location.hash}`);
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
    return validRunId(urlRun) ? urlRun : validRunId(saved.run_id) ? saved.run_id : null;
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

function renderRun(run, dossier = null, dossierError = null, prepareExport = false) {
  const normalizedTitle = value => String(value || '').trim().toLocaleLowerCase().replace(/\s+/g, ' ');
  const details = dossier?.papers || [];
  const paperRows = (run.papers || []).map((paper, originalIndex) => ({
    paper,
    originalIndex,
    detail: details.find(detail =>
      detail.doi && paper.doi && String(paper.doi).toLocaleLowerCase() === String(detail.doi).toLocaleLowerCase()
    ) || details.find(detail => normalizedTitle(paper.title) === normalizedTitle(detail.title)) || null
  })).filter(row => !dossier || row.detail).sort((a, b) => {
    const scoreColumn = dossier?.paper_headers?.indexOf('Discovery Fit Score (%)') ?? -1;
    const aScore = scoreColumn >= 0 ? a.detail?.rankable_values?.[scoreColumn] : null;
    const bScore = scoreColumn >= 0 ? b.detail?.rankable_values?.[scoreColumn] : null;
    return typeof aScore === 'number' && typeof bScore === 'number' ? bScore - aScore : a.originalIndex - b.originalIndex;
  });
  s5('intelligence-results').hidden = false;
  const effectiveRunId = validRunId(activeRunId) ? activeRunId : (validRunId(run?.run_id) ? run.run_id : '');
  const browsingMode = document.body.classList.contains('research-browse-mode');
  if (browsingMode) {
    s5('results-heading').textContent = `${paperRows.length} papers · ${run.options?.topic || 'Saved research'}`;
  }
  if (effectiveRunId) {
    activeRunId = effectiveRunId;
    s5('topic-dossier-link').href = `/research/topic?run=${encodeURIComponent(effectiveRunId)}`;
    s5('paper-list-link').textContent = browsingMode ? '← Find papers' : `Browse ${paperRows.length} papers ↗`;
    s5('paper-list-link').href = browsingMode ? '/research#topic-form' : `/research/papers?run=${encodeURIComponent(effectiveRunId)}`;
  } else {
    s5('paper-list-link').textContent = '← Find papers';
    s5('paper-list-link').href = '/research#topic-form';
  }
  s5('retrieved-at').textContent = `Retrieved ${run.retrieved_at} · ${paperRows.length} source-linked papers · Discovery rank compares query match, recency and source corroboration within this search; it is not scientific quality.`;
  s5('provider-status').textContent = (run.sources || []).map(source => `${source.source}: ${source.status} (${source.record_count})`).join(' · ') + (dossierError ? ' · Detailed rankings are temporarily unavailable; saved paper records are shown.' : '');
  const excelLink = s5('excel-link');
  if (prepareExport) void prepareResearchExcelLink(
    excelLink,
    `/api/research/intelligence/runs/${encodeURIComponent(activeRunId)}/xlsx?mode=standard`,
    `archipelago-research-${activeRunId.slice(0, 8)}-complete-ranking.xlsx`,
    s5('provider-status')
  );
  const list = s5('paper-results');
  list.replaceChildren();
  const authorsById = new Map((run.author_observations || []).map(author => [author.id, author]));
  const visiblePapers = paperRows.map(row => row.paper);
  for (const { detail, paper, originalIndex } of paperRows) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    const rankColumn = dossier?.paper_headers?.indexOf('Discovery Rank') ?? -1;
    const rank = rankColumn >= 0 ? detail?.rankable_values?.[rankColumn] : null;
    title.textContent = `${rank ? `#${rank} · ` : `#${originalIndex + 1} · `}${paper.title}`;
    const facts = document.createElement('p');
    facts.textContent = [paper.authors?.map(author => author.name).join(', '), paper.venue].filter(Boolean).join(' · ');
    const metricRows = ['Discovery Fit Score (%)', 'Title Query Match (%)', 'Abstract Query Match (%)', 'Recency Within Search (%)', 'Source Corroboration Within Search (%)', 'Verified Source Count', 'Author Count', 'Abstract Reported', 'Metadata Completeness (%)', 'Paper Age at Retrieval (Years)', 'DOI Reported', 'Public Full-Text Link Reported', 'Venue Reported', 'Venue Papers in This Search']
      .map(header => {
        const index = (dossier?.paper_headers || []).indexOf(header);
        return [header, index >= 0 ? detail?.rankable_values?.[index] : null];
      }).filter(([, value]) => value !== null && value !== undefined);
    const coverage = document.createElement('p');
    coverage.textContent = detail ? `${metricRows.length} complete comparable values · fit = 50% title + 25% abstract + 15% recency + 10% source corroboration` : 'Loading comparable ranking values…';
    article.append(title, facts, coverage);
    if (metricRows.length) article.append(metricGrid(metricRows));
    const paperDetail = document.createElement('a');
    if (detail) {
      paperDetail.href = `/research/paper?run=${encodeURIComponent(activeRunId)}&paper=${detail.index}`;
      paperDetail.textContent = 'Open paper page ↗';
      article.append(paperDetail);
    }
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
    authorCoverage.textContent = 'Comparable byline counts cover this saved search only.';
    authorDetails.append(authorCoverage);
    const providerIds = paperAuthorIds(paper);
    paper.authors?.forEach((author, index) => {
      const id = providerIds[index];
      const observation = authorsById.get(id);
      const rankedAuthor = dossier?.authors?.find(item => item.key === detail?.author_keys?.[index]);
      if (rankedAuthor) {
        const heading = document.createElement('h4');
        heading.textContent = author.name;
        authorDetails.append(heading, metricGrid(dossier.author_headers.slice(1).map((label, offset) => [label, rankedAuthor.values[offset + 1]])));
        if (observation?.source_url?.startsWith('https://')) {
          const source = document.createElement('a');
          source.href = observation.source_url;
          source.target = '_blank';
          source.rel = 'noopener noreferrer';
          source.textContent = `Author source: ${observation.provider} ↗`;
          authorDetails.append(source);
        }
        return;
      }
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

function showRun(run) {
  const runId = activeRunId;
  renderRun(run, null, null, true);
  void s5Json(`/api/research/intelligence/runs/${encodeURIComponent(runId)}/dossier`)
    .then(dossier => {
      if (activeRunId !== runId) return;
      renderRun(run, dossier);
      s5('intelligence-status').textContent = `Loaded ${s5('paper-results').children.length} verified paper pages.`;
    })
    .catch(error => {
      if (activeRunId !== runId) return;
      s5('provider-status').textContent += ` · Detailed rankings unavailable (${error.message}); saved paper records remain visible.`;
    });
}

async function loadRecentRuns(force = false) {
  const status = s5('recent-research-status');
  const list = s5('recent-research-list');
  if (!status || !list) return;
  if (recentRunsInFlight) return recentRunsInFlight;
  if (!force && Date.now() - lastRecentRunsAt < 15000) return;
  recentRunsInFlight = (async () => {
    try {
      const data = await s5Json('/api/research/intelligence/runs');
      lastRecentRunsAt = Date.now();
      list.replaceChildren();
      const runs = Array.isArray(data.runs) ? data.runs : [];
      const seen = new Set();
      const recent = runs.filter(run => {
        const key = String(run.topic || '').trim().toLocaleLowerCase();
        if (!run.run_id || !key || seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, RECENT_TOPIC_LIMIT);
      status.textContent = recent.length ? `Showing ${recent.length} latest topics — select one to reopen its papers.` : 'No saved topics yet.';
      for (const run of recent) {
        if (!run.run_id) continue;
        const link = document.createElement('a');
        link.href = `/research/topic?run=${encodeURIComponent(run.run_id)}`;
        link.textContent = `${run.topic || 'Untitled topic'} · ${String(run.created_at || '').slice(0, 10)}`;
        list.append(link);
      }
    } catch (error) { status.textContent = `Could not load saved topics: ${error.message}`; }
    finally { recentRunsInFlight = null; }
  })();
  return recentRunsInFlight;
}

async function restoreRun(runId) {
  if (!validRunId(runId)) return;
  if (restoreInFlight) return restoreInFlight;
  const status = s5('intelligence-status');
  status.textContent = 'Loading saved papers…';
  restoreInFlight = (async () => {
    try {
      const run = await s5Json(`/api/research/intelligence/runs/${encodeURIComponent(runId)}`);
      activeRunId = runId;
      if (run.options?.topic && s5('topic-input')) s5('topic-input').value = run.options.topic;
      await showRun(run);
      status.textContent = `Restored ${s5('paper-results').children.length} source-linked papers.`;
    } catch (error) {
      if (error?.name === 'AbortError') {
        status.textContent = 'Paper loading was paused while switching pages. Returning to view will retry…';
        return;
      }
      status.textContent = error.httpStatus === 410
        ? 'This older search cannot use the current paper format. Search the topic again to create updated paper pages.'
        : `Could not restore this saved search: ${error.message}. Choose another saved topic or retry.`;
    } finally {
      restoreInFlight = null;
    }
  })();
  return restoreInFlight;
}

window.addEventListener('load', async () => {
  const browsing = location.pathname.replace(/\/$/, '') === '/research/papers';
  const linkedRun = new URLSearchParams(location.search).get('run');
  if (browsing && !validRunId(linkedRun)) { location.replace('/research'); return; }
  if (!browsing && validRunId(linkedRun)) { location.replace(`/research/papers?run=${encodeURIComponent(linkedRun)}`); return; }
  if (browsing) document.body.classList.add('research-browse-mode');
  if (!await window.archipelagoResearchReady) return;
  const savedRunId = restoreResearchForm();
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
      if (!validRunId(run?.run_id)) {
        clearPendingSearch();
        s5('intelligence-status').textContent = 'Search returned no valid run ID. Please retry.';
        return;
      }
      clearPendingSearch();
      activeRunId = run.run_id;
      saveResearchState();
      location.assign(`/research/papers?run=${encodeURIComponent(run.run_id)}`);
      return;
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
  void loadRecentRuns();
  if (pendingSearch()) void recoverPendingSearch();
  else if (savedRunId && browsing) void restoreRun(savedRunId);
});

function resumePapersIfNeeded() {
  isUnloading = false;
  const browsing = location.pathname.replace(/\/$/, '') === '/research/papers';
  const linkedRun = new URLSearchParams(location.search).get('run');
  if (browsing && validRunId(linkedRun) && s5('intelligence-results')?.hidden && !restoreInFlight) {
    void restoreRun(linkedRun);
  }
}

window.addEventListener('pageshow', event => {
  resumePapersIfNeeded();
  if (event.persisted) void loadRecentRuns();
});
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    resumePapersIfNeeded();
    void loadRecentRuns();
  }
});
