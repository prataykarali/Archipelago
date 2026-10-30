const homeEl = id => document.getElementById(id);
const HOME_REFRESH_MS = 60000;
const MAX_VISIBLE_RESEARCH_PAPERS = 10;
let currentTopic = '';
let graphPayload = null;
let graphView = null;
let savedPapers = [];
let activeTopicId = null;
let activePaper = null;
let paperRequestId = 0;

async function homeJson(url, options = {}) {
  const response = await fetch(url, { cache: 'no-store', ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.error || 'Research service unavailable');
  return data;
}

function makePaperItem(paper, showAbstract = false) {
  const article = document.createElement('article');
  article.className = 'research-paper-item';
  const title = document.createElement('strong');
  title.textContent = paper.title || 'Untitled paper';
  const meta = document.createElement('small');
  const detail = paper.metadata || {};
  const authors = (Array.isArray(detail.authors) ? detail.authors : []).slice(0, 3).map(author => author.name).filter(Boolean);
  const extracted = (Array.isArray(detail.verified_extractions) ? detail.verified_extractions : []).filter(item =>
    item.verification_status === 'abstract_quote_matched' && item.value
  ).slice(0, 3).map(item => `${item.field}: ${item.value}`);
  const tags = [
    paper.source_name,
    detail.publication_year || paper.published_at?.slice(0, 4),
    detail.citation_count != null && `${detail.citation_count} citations`,
    ...authors, ...(Array.isArray(detail.keywords) ? detail.keywords : []).slice(0, 2), ...extracted
  ].filter(Boolean);
  meta.textContent = `[${tags.join(' · ')}]`;
  article.append(title, meta);
  if (showAbstract && paper.abstract) {
    const abstract = document.createElement('p');
    abstract.textContent = paper.abstract;
    article.append(abstract);
  }
  if (paper.source_url) {
    const link = document.createElement('a');
    link.href = paper.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'Original paper ↗';
    article.append(link);
  }
  if (paper.record_key) {
    const inspect = document.createElement('button');
    inspect.type = 'button';
    inspect.textContent = 'View OKF';
    inspect.addEventListener('click', () => {
      showPaperOkf(paper.record_key, paper.title);
      homeEl('graph-title').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    article.append(inspect);
  }
  return article;
}

async function showPaperOkf(recordKey, title) {
  activePaper = { recordKey, title };
  const requestId = ++paperRequestId;
  const panel = homeEl('research-graph-detail');
  panel.textContent = 'Loading OKF…';
  try {
    const okf = await homeJson(`/api/research/intake/paper-okf/${encodeURIComponent(recordKey)}`);
    if (requestId !== paperRequestId) return;
    const back = document.createElement('button');
    back.type = 'button';
    back.textContent = '← Back to papers';
    back.onclick = () => drawResearchGraph(activeTopicId);
    panel.replaceChildren(back, decorateOkf(okf, title));
  } catch (error) {
    if (requestId === paperRequestId) panel.textContent = error.message;
  }
}

function showGraphDirectory(topicId) {
  const detail = homeEl('research-graph-detail');
  detail.replaceChildren();
  const heading = document.createElement('h3');
  heading.textContent = topicId ? graphPayload.nodes.find(node => node.data.id === topicId)?.data.name || 'Research topic' : 'Research topics';
  detail.append(heading);
  if (topicId) {
    const back = document.createElement('button');
    back.type = 'button';
    back.textContent = '← All topics';
    back.onclick = () => drawResearchGraph();
    detail.append(back);
  }
  const nodes = topicId ? graphPayload.edges
    .filter(edge => edge.data.source === topicId && edge.data.rel_label === 'IN_TOPIC')
    .map(edge => graphPayload.nodes.find(node => node.data.id === edge.data.target))
    .filter(Boolean) : graphPayload.nodes.filter(node => node.data.kind === 'topic');
  const description = document.createElement('p');
  description.textContent = topicId
    ? `${nodes.length} saved papers. Select a graph card to inspect its source-backed OKF.`
    : 'Choose a topic card to reveal its paper network.';
  detail.append(description);
  const addButton = (node, container) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = node.data.name;
    button.className = 'research-node-button';
    button.onclick = () => topicId ? showPaperOkf(node.data.record_key, node.data.name) : drawResearchGraph(node.data.id);
    container.append(button);
  };
  if (!topicId) nodes.slice(0, 4).forEach(node => addButton(node, detail));
  if (topicId || nodes.length > 4) {
    const drawer = document.createElement('details');
    drawer.className = 'research-graph-directory';
    const summary = document.createElement('summary');
    summary.textContent = topicId ? `Browse all ${nodes.length} paper titles` : `Browse all ${nodes.length} topics`;
    drawer.append(summary);
    (topicId ? nodes : nodes.slice(4)).forEach(node => addButton(node, drawer));
    detail.append(drawer);
  }
  if (!nodes.length) {
    const empty = document.createElement('p');
    empty.textContent = topicId ? 'No papers are saved for this topic.' : 'No research topics have been ingested yet.';
    detail.append(empty);
  }
}

function graphElements(topicId) {
  const topics = graphPayload.nodes.filter(node => node.data.kind === 'topic');
  if (!topicId) return topics;
  const papers = graphPayload.edges.filter(edge => edge.data.source === topicId && edge.data.rel_label === 'IN_TOPIC');
  const visible = papers.slice(0, MAX_VISIBLE_RESEARCH_PAPERS);
  const paperIds = new Set(visible.map(edge => edge.data.target));
  return [graphPayload.nodes.find(node => node.data.id === topicId), ...graphPayload.nodes.filter(node => paperIds.has(node.data.id)), ...visible].filter(Boolean);
}

function drawResearchGraph(topicId = null) {
  if (!graphPayload) return;
  activePaper = null;
  paperRequestId += 1;
  activeTopicId = topicId;
  showGraphDirectory(topicId);
  const totalPapers = topicId ? graphPayload.edges.filter(edge => edge.data.source === topicId && edge.data.rel_label === 'IN_TOPIC').length : 0;
  homeEl('graph-count').textContent = topicId ? `${totalPapers} papers` : `${graphElements().length} topics`;
  if (!window.cytoscape) {
    homeEl('graph-status').textContent = 'Graph renderer unavailable. Browse the topics and papers in the side panel.';
    return;
  }
  graphView?.destroy();
  const graphItems = graphElements(topicId).map(item => item.group === 'edges' || item.data.source
    ? item
    : { ...item, data: { ...item.data, display_name: String(item.data.name || '').slice(0, 54) } });
  const paperNodes = graphItems.filter(item => item.data.kind === 'paper');
  const topicNodes = graphItems.filter(item => item.data.kind === 'topic');
  const positions = new Map();
  if (topicId) {
    positions.set(topicId, { x: 500, y: 380 });
    paperNodes.forEach((item, index) => positions.set(item.data.id, {
      x: index % 2 ? 840 : 160,
      y: 95 + Math.floor(index / 2) * 140
    }));
  } else {
    topicNodes.forEach((item, index) => positions.set(item.data.id, {
      x: 160 + (index % 3) * 340,
      y: 100 + Math.floor(index / 3) * 155
    }));
  }
  graphView = cytoscape({
    container: homeEl('research-graph'), elements: graphItems.map(item => positions.has(item.data.id) ? { ...item, position: positions.get(item.data.id) } : item),
    style: [
      { selector: 'node', style: { shape: 'round-rectangle', 'background-color': '#241050', label: 'data(display_name)', color: '#fff7ff', 'font-size': 11, 'font-weight': 600, 'text-wrap': 'wrap', 'text-max-width': 126, 'text-valign': 'center', 'text-halign': 'center', width: 164, height: 61, 'border-width': 1.7, 'border-color': '#8673fa', 'shadow-blur': 19, 'shadow-color': '#7143e4', 'shadow-opacity': .4 } },
      { selector: 'node[kind="topic"]', style: { 'background-color': '#67108b', 'border-color': '#e382ff', width: 184, height: 70, 'font-size': 12, 'font-weight': 700, 'shadow-color': '#c734f2', 'shadow-opacity': .65 } },
      { selector: 'edge', style: { width: 2, 'line-color': '#a263e2', 'target-arrow-color': '#d2a1ff', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'label': 'PAPER', 'font-size': 8, 'color': '#d8c6ee', 'text-rotation': 'autorotate', 'text-background-color': '#130723', 'text-background-opacity': .95, 'text-background-padding': 3 } },
      { selector: ':selected', style: { 'border-color': '#fff', 'border-width': 3 } }
    ],
    layout: { name: 'preset', fit: true, padding: 42 },
    minZoom: .3,
    maxZoom: 2.5
  });
  graphView.on('tap', 'node', event => {
    const data = event.target.data();
    if (data.kind === 'topic') {
      drawResearchGraph(data.id);
    } else if (data.kind === 'paper' && data.record_key) {
      showPaperOkf(data.record_key, data.name);
    }
  });
}

async function loadResearchGraph() {
  try {
    graphPayload = await homeJson('/api/research/graph/papers');
    if (!activePaper) {
      const topicId = graphPayload.nodes.some(node => node.data.id === activeTopicId) ? activeTopicId : null;
      drawResearchGraph(topicId);
    }
    if (window.cytoscape) homeEl('graph-status').textContent = graphPayload.truncated ? 'Showing the latest 2,000 saved records.' : 'Research graph updates as local ingestion saves papers.';
  } catch (error) { homeEl('graph-status').textContent = error.message; }
}

async function loadSavedPapers() {
  try {
    const data = await homeJson('/api/research/intake/records?kind=paper');
    savedPapers = data.records || [];
    homeEl('paper-list-count').textContent = `${savedPapers.length} recent papers`;
    const list = homeEl('saved-paper-list');
    list.replaceChildren(...savedPapers.map(makePaperItem));
    if (!savedPapers.length) list.textContent = 'No papers ingested yet.';
    const latest = homeEl('latest-okf');
    if (!savedPapers.length) { latest.textContent = 'The first extracted OKF will appear after local ingestion.'; return; }
    const paper = savedPapers[0];
    const okf = await homeJson(`/api/research/intake/paper-okf/${encodeURIComponent(paper.record_key)}`);
    latest.replaceChildren(decorateOkf(okf, paper.title));
  } catch (error) { homeEl('latest-okf').textContent = error.message; }
}

async function discoverTopic(event) {
  event.preventDefault();
  const topic = homeEl('topic-input').value.trim();
  if (topic.length < 3) return;
  currentTopic = topic;
  const status = homeEl('discovery-status');
  const submit = homeEl('topic-form').querySelector('button');
  submit.disabled = true;
  status.textContent = 'Searching OpenAlex, Crossref, arXiv and other available indexes…';
  homeEl('discovery-panel').hidden = true;
  try {
    const data = await homeJson('/api/research/discover', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic }) });
    const papers = data.papers || [];
    const list = homeEl('discovery-list');
    list.replaceChildren(...papers.map(paper => makePaperItem(paper, true)));
    homeEl('discovery-count').textContent = `${papers.length} source previews`;
    homeEl('discovery-panel').hidden = false;
    homeEl('ingest-local').disabled = !papers.length;
    status.textContent = papers.length ? `${papers.length} source-linked previews found. Local ingestion is available below.` : 'No relevant papers found from available sources.';
    await loadWorkerReadiness();
  } catch (error) { status.textContent = `Discovery failed: ${error.message}`; }
  finally { submit.disabled = false; }
}

async function loadWorkerReadiness() {
  const workerItem = homeEl('check-worker');
  const modelItem = homeEl('check-model');
  const ocrItem = homeEl('check-ocr');
  try {
    const worker = await homeJson('/api/research/jobs/worker');
    workerItem.className = worker.online ? 'ready' : 'blocked';
    workerItem.textContent = worker.online ? '✓ Local workstation connected' : '✕ Local workstation offline; the job will wait in the queue';
    const modelReady = worker.online && !String(worker.model_status || '').startsWith('model_unavailable');
    modelItem.className = modelReady ? 'ready' : 'blocked';
    modelItem.textContent = modelReady ? '✓ Local SLM reported ready' : '✕ Local SLM has not reported ready';
    const ocrReady = worker.online && String(worker.model_status || '').includes('ocr_ready');
    ocrItem.className = ocrReady ? 'ready' : 'blocked';
    ocrItem.textContent = ocrReady ? '✓ Indra OCR available on workstation' : '✕ Indra OCR has not reported ready; full-text jobs need it';
  } catch (_) {
    workerItem.textContent = '○ Workstation status unavailable';
    modelItem.textContent = '○ SLM status unavailable';
    ocrItem.textContent = '○ OCR status unavailable';
  }
}

async function ingestLocal() {
  const button = homeEl('ingest-local');
  button.disabled = true;
  try {
    const data = await homeJson('/api/research/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic: currentTopic }) });
    window.location.assign(`/research/progress?job=${encodeURIComponent(data.job.job_id)}`);
  } catch (error) {
    homeEl('discovery-status').textContent = `Could not queue ingestion: ${error.message}`;
    button.disabled = false;
  }
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  homeEl('topic-form').addEventListener('submit', discoverTopic);
  homeEl('ingest-local').addEventListener('click', ingestLocal);
  homeEl('topic-form').querySelector('button').disabled = false;
});
