"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;

function currentSearchOptions() {
  const payload = Object.fromEntries(new FormData(s5('intelligence-form')));
  payload.top_k = Number(payload.top_k);
  for (const field of ['year_from', 'year_to']) payload[field] = payload[field] ? Number(payload[field]) : null;
  payload.open_access = payload.open_access === '' ? null : payload.open_access === 'true';
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
  s5('excel-link').href = `/api/research/intelligence/runs/${activeRunId}/xlsx`;
  const list = s5('paper-results');
  list.replaceChildren();
  const authorsById = new Map((run.author_observations || []).map(author => [author.id, author]));
  for (const paper of run.papers) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    title.textContent = `${paper.collection_order}. ${paper.title}`;
    const facts = document.createElement('p');
    facts.textContent = [paper.year, paper.authors.map(author => author.name).join(', '), paper.venue, paper.citation_count == null ? null : `${paper.citation_count} citations (${paper.citation_provider})`, paper.evidence_status].filter(Boolean).join(' · ');
    const reason = document.createElement('p');
    reason.textContent = `Collection order ${paper.collection_order} (${run.ordering}); topic terms found in provider metadata. Not a quality ranking.`;
    article.append(title, facts, reason);
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
    const identities = document.createElement('details');
    const identityHeading = document.createElement('summary');
    identityHeading.textContent = 'Author and venue intelligence';
    identities.append(identityHeading);
    const providerIds = paper.source_metadata?.author_openalex_ids || [];
    paper.authors.forEach((author, index) => {
      const id = (providerIds[index] || '').split('/').pop();
      const observation = authorsById.get(id);
      const line = document.createElement('p');
      const metrics = observation?.metrics;
      line.textContent = `${author.name} · ${observation?.identity_status || 'unresolved identity'} · ${id || author.orcid || 'no provider ID'} · ${metrics ? `${metrics.publication_count ?? 'N/A'} indexed works, ${metrics.citation_count ?? 'N/A'} citations, h-index ${metrics.h_index ?? 'N/A'}, i10-index ${metrics.i10_index ?? 'N/A'} (${observation.provider}, ${observation.retrieved_at})` : 'metrics N/A'}`;
      identities.append(line);
    });
    const venue = document.createElement('p');
    const venueDetails = paper.venue_details;
    venue.textContent = venueDetails ? `${venueDetails.name} · ${venueDetails.id || 'unresolved ID'} · ${venueDetails.publisher || 'publisher N/A'} · impact factor/CiteScore/SJR/CORE N/A · ${venueDetails.provider || 'provider N/A'}` : 'Venue metadata unavailable.';
    identities.append(venue);
    article.append(identities);
    list.append(article);
  }
  if (!run.papers.length) list.textContent = 'No papers matched the filters in the returned provider results.';
}

async function loadHistory() {
  const history = s5('run-history');
  try {
    const data = await s5Json('/api/research/intelligence/runs');
    history.replaceChildren();
    for (const run of data.runs) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${run.topic} · ${run.created_at}`;
      button.addEventListener('click', async () => {
        activeRunId = run.run_id;
        showRun(await s5Json(`/api/research/intelligence/runs/${activeRunId}`));
      });
      history.append(button);
    }
  } catch (error) { history.textContent = error.message; }
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
  await loadHistory();
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
  s5('intelligence-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = currentSearchOptions();
    s5('intelligence-status').textContent = 'Searching scholarly providers…';
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const run = await s5Json('/api/research/intelligence/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      activeRunId = run.run_id;
      showRun(run);
      s5('intelligence-status').textContent = `${run.papers.length} papers selected.`;
      await loadHistory();
    } catch (error) { s5('intelligence-status').textContent = error.message; }
    finally { form.querySelector('button[type="submit"]').disabled = false; }
  });
  s5('graph-button').addEventListener('click', async () => {
    if (!activeRunId) return;
    const graph = await s5Json(`/api/research/intelligence/runs/${activeRunId}/graph`);
    const summary = s5('graph-summary');
    summary.hidden = false;
    summary.textContent = `${graph.nodes.length} nodes · ${graph.edges.length} sourced relationships\n` + graph.edges.filter(edge => edge.type === 'CITES').map(edge => `${edge.source} cites ${edge.target} via ${edge.provider}`).join('\n');
  });
});
