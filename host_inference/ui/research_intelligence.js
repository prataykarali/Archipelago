"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;
let activeRunData = null;
const S5_STATE_KEY = 'archipelago_research_state_v1';

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

function makeBadge(text, cls = '') {
  const span = document.createElement('span');
  span.className = `s5-badge ${cls}`.trim();
  span.textContent = text;
  return span;
}

function makeExtLink(href, text) {
  const a = document.createElement('a');
  a.href = href;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.textContent = text;
  return a;
}

function filterAndSortPapers(papers, opts) {
  const yf = opts.year_from ? Number(opts.year_from) : null;
  const yt = opts.year_to ? Number(opts.year_to) : null;
  const auth = (opts.author || '').trim().toLowerCase();
  const inst = (opts.institution || '').trim().toLowerCase();
  const ven = (opts.venue || '').trim().toLowerCase();
  const pub = (opts.publisher || '').trim().toLowerCase();
  const ptype = (opts.paper_type || '').trim().toLowerCase();
  const prov = (opts.provider || '').trim().toLowerCase();
  const gr = (opts.google_research || '').trim().toLowerCase();
  const ev = (opts.evidence_field || '').trim();
  const oa = opts.open_access;

  const filtered = papers.filter(p => {
    if (yf && (p.year == null || p.year < yf)) return false;
    if (yt && (p.year == null || p.year > yt)) return false;
    if (oa !== null && oa !== undefined && p.is_open_access !== oa) return false;
    if (ptype && !(p.publication_type || '').toLowerCase().includes(ptype)) return false;
    if (ven && !(p.venue || '').toLowerCase().includes(ven)) return false;
    if (pub && !(p.publisher || p.source_metadata?.publisher || '').toLowerCase().includes(pub)) return false;
    if (auth && !(p.authors || []).some(a => (a.name || '').toLowerCase().includes(auth))) return false;
    if (inst && !(p.authors || []).some(a => (a.institutions || []).some(i => i.toLowerCase().includes(inst)))) return false;
    if (prov) {
      const pProvs = new Set((p.provenance || []).map(x => (x.source_type || '').toLowerCase()));
      if (p.source) pProvs.add(p.source.toLowerCase());
      if (!pProvs.has(prov)) return false;
    }
    if (gr === 'official' && !p.google_research?.official_listing) return false;
    if (gr === 'affiliated' && !p.google_research?.google_author_affiliation) return false;
    if (ev && !(Array.isArray(p[ev]) ? p[ev].length > 0 : Boolean(p[ev]))) return false;
    return true;
  });

  const sort = opts.sort || 'newest';
  const copy = [...filtered];
  if (sort === 'newest') {
    copy.sort((a, b) => (b.publication_date || '').localeCompare(a.publication_date || ''));
  } else if (sort === 'citations') {
    copy.sort((a, b) => (b.citation_count ?? -1) - (a.citation_count ?? -1));
  } else if (sort === 'citations_per_year') {
    copy.sort((a, b) => (b.citations_per_year ?? -1) - (a.citations_per_year ?? -1));
  } else if (sort === 'fwci') {
    copy.sort((a, b) => (b.fwci ?? -1) - (a.fwci ?? -1));
  } else if (sort === 'open_access') {
    copy.sort((a, b) => Number(b.is_open_access === true) - Number(a.is_open_access === true));
  } else if (sort === 'evidence_completeness') {
    const score = p => ['abstract', 'doi', 'methods', 'datasets', 'evaluation_metrics', 'grants', 'references'].filter(k => Array.isArray(p[k]) ? p[k].length > 0 : Boolean(p[k])).length;
    copy.sort((a, b) => score(b) - score(a));
  }
  return copy;
}

function showRun(run) {
  activeRunData = run;
  s5('intelligence-results').hidden = false;
  s5('retrieved-at').textContent = `Retrieved ${run.retrieved_at} · ${run.candidate_count} provider candidates · ${run.filtered_count} after server filters`;
  const provEl = s5('provider-status');
  provEl.replaceChildren();
  for (const source of run.sources || []) {
    const cls = source.status === 'live' ? 's5-badge--live' : (source.rate_limited || source.status === 'automated_access_restricted' || source.status === 'blocked_bot_challenge' ? 's5-badge--warn' : '');
    const httpTxt = source.http_status ? ` · HTTP ${source.http_status}` : '';
    provEl.append(makeBadge(`${source.source}: ${source.status} (${source.record_count || 0})${httpTxt}`, cls));
  }
  const sortEl = s5('sort-definition');
  if (sortEl) {
    const sm = run.sort_metadata;
    sortEl.textContent = sm
      ? `Ordering: ${sm.label} — ${sm.definition} (Source: ${sm.source}; collected ${formatShortDate(sm.collected_at)})`
      : `Ordering: ${run.ordering || 'newest'} (missing values sorted last, never zero).`;
  }
  const extLinks = s5('external-verification-links');
  if (extLinks) {
    extLinks.replaceChildren();
    if (run.google_research_url) extLinks.append(makeExtLink(run.google_research_url, 'Google Research publications ↗'));
    if (run.google_scholar_url) extLinks.append(makeExtLink(run.google_scholar_url, 'Google Scholar verification ↗'));
    for (const a of extLinks.querySelectorAll('a')) a.className = 's5-badge s5-badge--link';
  }
  const excelLink = s5('excel-link');
  excelLink.href = `/api/research/intelligence/runs/${activeRunId}/xlsx`;
  excelLink.onclick = async event => {
    event.preventDefault();
    const runId = activeRunId;
    if (!runId) return;
    try {
      const resp = await fetch(`/api/research/intelligence/runs/${runId}/xlsx`, { cache: 'no-store', credentials: 'include' });
      if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `archipelago-research-${runId.slice(0, 8)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      s5('intelligence-status').textContent = err.message || 'Could not download workbook.';
    }
  };
  const list = s5('paper-results');
  list.replaceChildren();
  const authorsById = new Map((run.author_observations || []).map(author => [author.id, author]));
  const visiblePapers = filterAndSortPapers(run.papers || [], currentSearchOptions());
  for (const paper of visiblePapers) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    title.textContent = `${paper.collection_order}. ${paper.title}`;
    const badges = document.createElement('div');
    badges.className = 's5-badges';
    const provNames = [...new Set((paper.provenance || []).map(p => p.source_type).filter(Boolean))];
    for (const pn of provNames) badges.append(makeBadge(pn, 's5-badge--live'));
    if (paper.published_vs_preprint) badges.append(makeBadge(paper.published_vs_preprint));
    if (paper.is_open_access === true) badges.append(makeBadge('Open Access', 's5-badge--live'));
    if (paper.google_research?.official_listing) badges.append(makeBadge('GOOGLE_RESEARCH_OFFICIAL_LISTING', 's5-badge--live'));
    else if (paper.google_research?.google_author_affiliation) badges.append(makeBadge('GOOGLE_AUTHOR_AFFILIATION', 's5-badge--warn'));

    const facts = document.createElement('p');
    facts.textContent = [
      paper.year,
      (paper.authors || []).map(author => author.name).join(', '),
      paper.venue,
      paper.citation_count == null ? null : `${paper.citation_count} citations (${paper.citation_provider})`,
      paper.citations_per_year == null ? null : `${paper.citations_per_year}/yr`,
      paper.fwci == null ? null : `FWCI ${paper.fwci}`,
      paper.evidence_status,
    ].filter(Boolean).join(' · ');

    const actions = document.createElement('div');
    actions.className = 's5-actions';
    if (paper.url && paper.url.startsWith('https://')) actions.append(makeExtLink(paper.url, 'Open provider record ↗'));
    if (paper.doi) actions.append(makeExtLink(`https://doi.org/${paper.doi}`, `DOI: ${paper.doi} ↗`));
    if (paper.google_scholar_url) actions.append(makeExtLink(paper.google_scholar_url, 'Google Scholar ↗'));
    if (paper.google_research?.official_search_url) actions.append(makeExtLink(paper.google_research.official_search_url, 'Google Research ↗'));

    article.append(title, badges, facts, actions);

    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Abstract, scientific evidence, references & identifiers';
    const body = document.createElement('p');
    body.textContent = paper.abstract || 'Abstract unavailable from selected providers.';
    const sci = document.createElement('p');
    const mList = (paper.methods || []).map(m => m.name || m).join(', ') || 'NOT_FOUND';
    const dList = (paper.datasets || []).map(d => d.name || d).join(', ') || 'NOT_FOUND';
    const eList = (paper.evaluation_metrics || []).map(e => e.name || e).join(', ') || 'NOT_FOUND';
    sci.textContent = `Methods: ${mList} · Datasets: ${dList} · Metrics: ${eList}`;
    const references = document.createElement('p');
    references.textContent = `${(paper.references || []).length} provider reference IDs · DOI: ${paper.doi || 'unavailable'} · Retrieved: ${paper.retrieved_at || run.retrieved_at}`;
    details.append(summary, body, sci, references);
    article.append(details);

    const identities = document.createElement('details');
    const identityHeading = document.createElement('summary');
    identityHeading.textContent = 'Author → Institution → Venue intelligence';
    identities.append(identityHeading);
    const providerIds = paper.source_metadata?.author_openalex_ids || [];
    const s2Ids = paper.source_metadata?.author_s2_ids || [];
    (paper.authors || []).forEach((author, index) => {
      const id = (providerIds[index] || '').split('/').pop();
      const s2id = s2Ids[index];
      const observation = authorsById.get(id) || (s2id ? authorsById.get(`s2:${s2id}`) : null);
      const line = document.createElement('p');
      const metrics = observation?.metrics;
      const insts = (author.institutions || []).join(', ') || 'affiliation unavailable';
      line.textContent = `${author.name} (${insts}) · ${observation?.identity_review_status || observation?.identity_status || 'unresolved identity'} · ${id || author.orcid || (s2id ? `S2:${s2id}` : 'no provider ID')} · ${metrics ? `${metrics.publication_count ?? 'N/A'} works, ${metrics.citation_count ?? 'N/A'} citations, h-index ${metrics.h_index ?? 'N/A'}, i10-index ${metrics.i10_index ?? 'N/A'} (${observation.provider})` : 'metrics N/A'} · `;
      const gsAuthor = makeExtLink(`https://scholar.google.com/scholar?q=${encodeURIComponent(`author:"${author.name}"`)}`, 'Scholar author ↗');
      line.append(gsAuthor);
      identities.append(line);
    });
    const venue = document.createElement('p');
    const vd = paper.venue_details;
    venue.textContent = vd
      ? `Venue: ${vd.name} [${vd.venue_category || vd.type || 'unknown'}] · ${vd.publisher || 'publisher N/A'} · JIF/CiteScore/SJR: LICENSE_RESTRICTED · ${vd.provider || 'provider N/A'}`
      : 'Venue metadata unavailable.';
    identities.append(venue);
    article.append(identities);
    list.append(article);
  }
  if (!visiblePapers.length) list.textContent = 'No papers matched the current filters in the returned provider results.';
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
  try {
    const me = await s5Json('/api/auth/me');
    if (['faculty', 'librarian', 'administrator'].includes(me.role)) {
      s5('monitor-section').hidden = false;
      await loadMonitors();
      await loadUpdates();
    }
  } catch (_) { /* Monitoring remains unavailable without a verified role. */ }
  s5('monitor-save').addEventListener('click', async () => {
    const options = currentSearchOptions();
    const topic = options.topic.trim();
    if (topic.length < 3) { s5('monitor-status').textContent = 'Enter a topic first.'; return; }
    try {
      await s5Json('/api/research/intelligence/monitors', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...options, cadence_hours: Number(s5('monitor-cadence').value) })
      });
      s5('monitor-status').textContent = 'Topic saved disabled. Activate it when ready.';
      await loadMonitors();
    } catch (error) { s5('monitor-status').textContent = error.message; }
  });
  s5('intelligence-form').addEventListener('change', event => {
    if (activeRunData && event.target?.name && event.target.name !== 'topic' && event.target.name !== 'top_k') {
      showRun(activeRunData);
    }
  });
  s5('intelligence-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = currentSearchOptions();
    s5('intelligence-status').textContent = `Fetching papers across OpenAlex, Crossref, Semantic Scholar, arXiv, Europe PMC, OpenAIRE & DBLP for "${payload.topic}"…`;
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const run = await s5Json('/api/research/intelligence/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      activeRunId = run.run_id;
      showRun(run);
      saveResearchState();
      const liveCount = (run.sources || []).filter(s => s.status === 'live').length;
      s5('intelligence-status').textContent = `Done — loaded ${run.papers.length} papers from ${liveCount} live provider(s).`;
      await loadHistory();
    } catch (error) { s5('intelligence-status').textContent = error.message; }
    finally { form.querySelector('button[type="submit"]').disabled = false; }
  });
  s5('graph-button').addEventListener('click', async () => {
    if (!activeRunId) return;
    s5('intelligence-status').textContent = 'Building paper & citation graph…';
    try {
      const graph = await s5Json(`/api/research/intelligence/runs/${activeRunId}/graph`);
      const summary = s5('graph-summary');
      summary.hidden = false;
      summary.textContent = `${graph.nodes.length} nodes · ${graph.edges.length} sourced relationships\n` + graph.edges.filter(edge => edge.type === 'CITES').map(edge => `${edge.source} cites ${edge.target} via ${edge.provider}`).join('\n');
      s5('intelligence-status').textContent = `Graph ready: ${graph.nodes.length} nodes · ${graph.edges.length} relationships.`;
    } catch (error) { s5('intelligence-status').textContent = error.message; }
  });
});
