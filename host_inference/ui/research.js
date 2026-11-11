let graphView;
let selectedConcept;
let selectedNode;
let canEdit = false;
let fullData;
let showingAll = false;

const HUB_LABEL_DEGREE = 9;

const elements = {
  query: document.getElementById('query'),
  status: document.getElementById('graph-status'),
  counts: document.getElementById('graph-counts'),
  title: document.getElementById('detail-heading'),
  summary: document.getElementById('detail-summary'),
  source: document.getElementById('detail-source'),
  kind: document.getElementById('detail-kind'),
  degree: document.getElementById('detail-degree'),
  sourceCount: document.getElementById('detail-source-count'),
  expand: document.getElementById('expand-node'),
  list: document.getElementById('concept-list'),
  form: document.getElementById('annotation-form'),
  editorHeading: document.getElementById('editor-heading'),
  editorSummary: document.getElementById('annotation-summary'),
  editorSource: document.getElementById('annotation-source'),
  editorStatus: document.getElementById('annotation-status')
};

function setStatus(message) { elements.status.textContent = message; }

function renderAnnotation(annotation, node) {
  elements.summary.textContent = annotation?.summary || node.summary || 'No description is available for this concept yet.';
  const url = annotation?.source_url;
  const validUrl = typeof url === 'string' && url.startsWith('https://');
  elements.source.hidden = !validUrl;
  if (validUrl) elements.source.href = url;
  if (canEdit) {
    elements.form.hidden = false;
    elements.editorHeading.textContent = annotation ? 'Update curated details' : 'Add curated details';
    elements.editorSummary.value = annotation?.summary || '';
    elements.editorSource.value = annotation?.source_url || '';
    elements.editorStatus.textContent = '';
  }
}

async function showNode(node) {
  selectedNode = node;
  selectedConcept = node.id;
  elements.title.textContent = node.name || node.id;
  elements.summary.textContent = node.summary || 'Loading curated details…';
  elements.kind.textContent = node.kind || 'concept';
  elements.degree.textContent = graphView?.getElementById(node.id).connectedEdges().length ?? '—';
  elements.sourceCount.textContent = node.source_count ?? '—';
  elements.expand.disabled = false;
  elements.source.hidden = true;
  elements.form.hidden = true;
  if (node.source_url && ['paper', 'institutional_page'].includes(node.kind)) {
    elements.summary.textContent = node.summary || 'This record has no abstract or extract.';
    elements.source.href = node.source_url;
    elements.source.hidden = false;
    elements.expand.disabled = true;
    return;
  }
  if (['topic', 'provider'].includes(node.kind) || String(node.id).startsWith('concept:')) {
    elements.expand.disabled = true;
    return;
  }
  if (showingAll && graphView) {
    const center = graphView.getElementById(node.id);
    const neighborhood = center.closedNeighborhood();
    graphView.elements().removeClass('dimmed highlighted');
    graphView.elements().not(neighborhood).addClass('dimmed');
    center.connectedEdges().addClass('highlighted');
  }
  try {
    const response = await fetch('/api/research/graph/annotation?' + new URLSearchParams({ concept_id: node.id }), { cache: 'no-store' });
    const data = await response.json();
    if (selectedConcept !== node.id) return;
    if (!response.ok) throw new Error(data.error || 'Details unavailable');
    renderAnnotation(data.annotation, node);
  } catch (error) {
    if (selectedConcept !== node.id) return;
    renderAnnotation(null, node);
    elements.editorStatus.textContent = 'Saved details could not be loaded. Try again later.';
  }
}

function applyFilter(filter) {
  if (!graphView) return;
  graphView.edges().forEach(edge => {
    const relation = String(edge.data('rel_label') || '').toLowerCase();
    const matches = filter === 'all' || relation.includes(filter) ||
      (filter === 'enables' && relation.includes('unlocks'));
    edge.style('display', matches ? 'element' : 'none');
  });
  document.querySelectorAll('.filter').forEach(button => {
    const active = button.dataset.filter === filter;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

function renderConceptList(nodes) {
  elements.list.replaceChildren();
  nodes.sort((a, b) => a.data.name.localeCompare(b.data.name)).forEach(item => {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = item.data.name || item.data.id;
    button.addEventListener('click', () => {
      graphView.getElementById(item.data.id).select();
      showNode(item.data);
    });
    li.append(button);
    elements.list.append(li);
  });
}

function drawGraph(data) {
  showingAll = Boolean(data.counts) && data.graph_label !== 'research';
  graphView?.destroy();
  graphView = cytoscape({
    container: document.getElementById('graph'),
    elements: [
      ...data.nodes.map(item => ({
        ...item,
        data: {
          ...item.data,
          display_name: showingAll && (item.data.degree || 0) < HUB_LABEL_DEGREE ? '' : item.data.name
        },
        classes: item.data.id === data.target_id ? 'anchor' : ''
      })),
      ...data.edges
    ],
    layout: data.graph_label === 'research'
      ? { name: 'grid', fit: true, padding: 45, avoidOverlap: true }
      : showingAll
        ? { name: 'cose', animate: false, fit: true, padding: 45, nodeRepulsion: 9000, idealEdgeLength: 90, numIter: 250 }
        : { name: 'cose', animate: false, fit: true, padding: 50, nodeRepulsion: 6300, idealEdgeLength: 125 },
    minZoom: .12,
    maxZoom: 2.5,
    style: [
      { selector: 'node', style: { 'background-color': '#a44eea', 'border-width': 2, 'border-color': '#eac7f8', 'label': 'data(display_name)', 'color': '#f4eaff', 'text-outline-color': '#140a21', 'text-outline-width': 2, 'font-family': 'DM Sans', 'font-size': 10, 'font-weight': 700, 'text-wrap': 'wrap', 'text-max-width': 100, 'text-valign': 'bottom', 'text-margin-y': 9, 'width': showingAll ? 18 : 26, 'height': showingAll ? 18 : 26 } },
      { selector: 'node.anchor', style: { 'background-color': '#13cfc4', 'border-color': '#b6f5ee', 'width': 42, 'height': 42, 'font-size': 12 } },
      { selector: 'edge', style: { 'width': showingAll ? 1 : 2.2, 'line-color': '#e6a2ee', 'target-arrow-color': '#e6a2ee', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'opacity': showingAll ? .2 : .75 } },
      { selector: 'edge[rel_label = "REQUIRES"]', style: { 'line-color': '#d73aa4', 'target-arrow-color': '#d73aa4' } },
      { selector: 'edge[rel_label = "UNLOCKS"]', style: { 'line-color': '#ebb23d', 'target-arrow-color': '#ebb23d' } },
      { selector: '.dimmed', style: { 'opacity': .08 } },
      { selector: 'edge.highlighted', style: { 'opacity': .95, 'width': 3 } },
      { selector: ':selected', style: { 'border-color': '#ffffff', 'border-width': 5 } }
    ]
  });
  graphView.on('tap', 'node', event => showNode(event.target.data()));
  if (data.graph_label !== 'research') graphView.on('dbltap', 'node', event => loadGraph({ target_id: event.target.id() }));
  graphView.on('tap', event => {
    if (event.target === graphView) graphView.elements().removeClass('dimmed highlighted');
  });
  const anchor = data.nodes.find(item => item.data.id === data.target_id);
  if (anchor) showNode(anchor.data);
  renderConceptList(data.nodes);
  const total = data.graph_label === 'research' ? data.nodes.length : (fullData?.counts?.concepts || data.nodes.length);
  const label = data.graph_label === 'research' ? 'research nodes' : 'concepts';
  elements.counts.textContent = `${data.nodes.length} of ${total} ${label} · ${data.edges.length} relationships`;
  setStatus(data.graph_label === 'research' ? 'Live research sources grouped by topic. Select a paper or college page to inspect it.' : showingAll ? 'Full institutional graph loaded. Select a concept to inspect it.' : 'Focused view. Choose All concepts to return to the complete graph.');
  applyFilter(document.querySelector('.filter.active')?.dataset.filter || 'all');
}

function showGraphView() {
  document.getElementById('sources-view').hidden = true;
  document.getElementById('graph-grid').hidden = false;
  document.getElementById('show-all').classList.remove('active');
  document.getElementById('show-sources').classList.remove('active');
  document.getElementById('show-intake-map').classList.remove('active');
}

window.archipelagoDrawIntake = records => {
  const nodes = [];
  const edges = [];
  const topics = new Set();
  records.forEach(record => {
    const topic = record.topic || (record.kind === 'institutional_page' ? 'College sites' : 'Research papers');
    const topicId = `topic:${topic}`;
    if (!topics.has(topicId)) {
      topics.add(topicId);
      nodes.push({ data: { id: topicId, name: topic, summary: 'Ingested source cluster', kind: 'topic', degree: 0 } });
    }
    const id = `record:${record.record_key}`;
    nodes.push({ data: { id, name: record.title, summary: record.content, kind: record.kind, source_url: record.source_url, degree: 1, source_count: 1 } });
    edges.push({ data: { id: `${topicId}:${id}`, source: topicId, target: id, rel_label: 'SOURCE' } });
  });
  showGraphView();
  document.getElementById('show-all').classList.remove('active');
  document.getElementById('show-intake-map').classList.add('active');
  if (nodes.length) drawGraph({ nodes, edges, graph_label: 'research' });
  else setStatus('No research records ingested yet. Fetch a topic or college page below.');
  document.getElementById('graph').scrollIntoView({ behavior: 'smooth', block: 'center' });
};

function renderSourceList(query = '') {
  const target = document.getElementById('source-list');
  target.replaceChildren();
  const matching = (fullData?.documents || []).filter(doc =>
    (doc.title + ' ' + doc.id).toLowerCase().includes(query.toLowerCase())
  );
  matching.forEach(doc => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'source-card';
    const title = document.createElement('strong');
    title.textContent = doc.title;
    const detail = document.createElement('span');
    detail.textContent = `${doc.concepts} concepts · ${doc.id}`;
    button.append(title, detail);
    button.addEventListener('click', () => {
      const ids = new Set(doc.concept_ids);
      const nodes = fullData.nodes.filter(node => ids.has(node.data.id));
      const edges = fullData.edges.filter(edge => ids.has(edge.data.source) && ids.has(edge.data.target));
      showGraphView();
      drawGraph({ nodes, edges, target_id: nodes[0]?.data.id });
    });
    target.append(button);
  });
}

async function fetchFullData() {
  if (!fullData) {
    const response = await fetch('/api/research/graph/full', { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Full graph unavailable.');
    fullData = data;
  }
  return fullData;
}

async function loadFullGraph() {
  showGraphView();
  setStatus('Loading the full institutional graph…');
  try {
    await fetchFullData();
    drawGraph(fullData);
    document.getElementById('show-all').classList.add('active');
    renderSourceList();
  } catch (error) { setStatus(error.message || 'Full graph unavailable.'); }
}

async function loadGraph(params) {
  showGraphView();
  setStatus('Loading graph…');
  try {
    const response = await fetch('/api/research/graph/subgraph?' + new URLSearchParams({ ...params, max_nodes: '48' }), { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'Graph request failed.');
    if (typeof cytoscape !== 'function') throw new Error('Graph renderer could not load. Refresh the page.');
    drawGraph(data);
  } catch (error) { setStatus(error.message || 'Graph request failed.'); }
}

document.getElementById('search-form').addEventListener('submit', event => {
  event.preventDefault();
  const q = elements.query.value.trim();
  if (!q) return;
  const match = fullData?.nodes.find(node =>
    node.data.name.toLowerCase().includes(q.toLowerCase()) || node.data.id.includes(q.toLowerCase())
  );
  if (match && showingAll && graphView) {
    const node = graphView.getElementById(match.data.id);
    graphView.animate({ center: { eles: node }, zoom: .95 }, { duration: 350 });
    node.select();
    showNode(match.data);
  } else {
    loadGraph({ q });
  }
});
document.getElementById('show-all').addEventListener('click', loadFullGraph);
document.getElementById('download-research-graph').addEventListener('click', async () => {
  setStatus('Preparing saved research graph JSON…');
  try {
    const response = await fetch('/api/research/graph/export', { cache: 'no-store' });
    if (!response.ok) throw new Error('Research graph export unavailable.');
    const content = await response.blob();
    const url = URL.createObjectURL(content);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'archipelago-research-graph.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setStatus('Research graph JSON downloaded.');
  } catch (error) { setStatus(error.message || 'Research graph export unavailable.'); }
});
document.getElementById('show-intake-map').addEventListener('click', async () => {
  setStatus('Loading the saved research graph…');
  try {
    const response = await fetch('/api/research/graph/ingested', { cache: 'no-store' });
    if (!response.ok) throw new Error('Saved research graph unavailable.');
    const graph = await response.json();
    showGraphView();
    document.getElementById('show-intake-map').classList.add('active');
    drawGraph({ ...graph, graph_label: 'research' });
  } catch (error) { setStatus(error.message || 'Saved research graph unavailable.'); }
});
document.getElementById('show-sources').addEventListener('click', () => {
  document.getElementById('graph-grid').hidden = true;
  document.getElementById('sources-view').hidden = false;
  document.getElementById('show-all').classList.remove('active');
  document.getElementById('show-sources').classList.add('active');
  renderSourceList(document.getElementById('source-filter').value);
});
document.getElementById('source-filter').addEventListener('input', event => renderSourceList(event.target.value));
document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => applyFilter(button.dataset.filter)));
elements.expand.addEventListener('click', () => { if (selectedConcept) loadGraph({ target_id: selectedConcept }); });
document.getElementById('zoom-in').addEventListener('click', () => graphView?.zoom(Math.min(graphView.maxZoom(), graphView.zoom() * 1.25)));
document.getElementById('zoom-out').addEventListener('click', () => graphView?.zoom(Math.max(graphView.minZoom(), graphView.zoom() / 1.25)));
document.getElementById('zoom-fit').addEventListener('click', () => graphView?.fit(undefined, 40));

window.archipelagoFocusConcept = conceptId => {
  loadGraph({ target_id: conceptId });
};

elements.form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!canEdit || !selectedConcept) return;
  elements.editorStatus.textContent = 'Saving…';
  try {
    const response = await fetch('/api/research/graph/annotation', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concept_id: selectedConcept, summary: elements.editorSummary.value.trim(), source_url: elements.editorSource.value.trim() })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Could not save details.');
    renderAnnotation(data.annotation, selectedNode);
    elements.editorStatus.textContent = 'Details saved.';
  } catch (error) { elements.editorStatus.textContent = error.message || 'Could not save details.'; }
});

window.addEventListener('load', async () => {
  const principal = await window.archipelagoResearchReady;
  if (!principal) return;
  canEdit = ['librarian', 'administrator'].includes(principal.role);
  const query = new URLSearchParams(location.search).get('q') || 'attention';
  elements.query.value = query;
  try {
    await fetchFullData();
    const concept = new URLSearchParams(location.search).get('concept');
    if (concept) await loadGraph({ target_id: concept });
    else await loadFullGraph();
  } catch (error) {
    setStatus(error.message || 'Concept index unavailable.');
  }
});
