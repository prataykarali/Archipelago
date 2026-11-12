"use strict";

const s5 = id => document.getElementById(id);
let activeRunId = null;

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
  for (const paper of run.papers) {
    const article = document.createElement('article');
    article.className = 'research-card';
    const title = document.createElement('h3');
    title.textContent = `${paper.rank}. ${paper.title}`;
    const facts = document.createElement('p');
    facts.textContent = [paper.year, paper.authors.map(author => author.name).join(', '), paper.venue, paper.citation_count == null ? null : `${paper.citation_count} citations (${paper.citation_provider})`, paper.evidence_status].filter(Boolean).join(' · ');
    const reason = document.createElement('p');
    reason.textContent = `Relevance ${paper.relevance_score}: ${paper.ranking_reasons.join('; ')}`;
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
    label.textContent = `${monitor.options.topic} · ${monitor.enabled ? 'active' : 'disabled'} · last run ${monitor.last_run || 'never'}`;
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
    list.append(row);
  }
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  await loadHistory();
  try {
    const me = await s5Json('/api/auth/me');
    if (['faculty', 'librarian', 'administrator'].includes(me.role)) {
      s5('monitor-section').hidden = false;
      await loadMonitors();
    }
  } catch (_) { /* Monitoring remains unavailable without a verified role. */ }
  s5('monitor-save').addEventListener('click', async () => {
    const topic = s5('topic-input').value.trim();
    if (topic.length < 3) { s5('monitor-status').textContent = 'Enter a topic first.'; return; }
    try {
      await s5Json('/api/research/intelligence/monitors', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic })
      });
      s5('monitor-status').textContent = 'Topic saved disabled. Activate it when ready.';
      await loadMonitors();
    } catch (error) { s5('monitor-status').textContent = error.message; }
  });
  s5('intelligence-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form));
    payload.top_k = Number(payload.top_k);
    for (const field of ['year_from', 'year_to']) payload[field] = payload[field] ? Number(payload[field]) : null;
    payload.open_access = payload.open_access === '' ? null : payload.open_access === 'true';
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
