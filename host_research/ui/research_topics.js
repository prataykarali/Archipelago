const atlas = id => document.getElementById(id);
let atlasGraph = null;
let atlasData = null;
let selectedTopic = null;
const MAX_PAPERS_PER_TOPIC = 30;

function markFocus(node) {
  atlasGraph.elements().removeClass('atlas-muted atlas-focused atlas-related');
  atlasGraph.elements().addClass('atlas-muted');
  node.closedNeighborhood().removeClass('atlas-muted').addClass('atlas-related');
  node.addClass('atlas-focused');
}

function directoryButton(label, action, secondary) {
  const button = document.createElement('button');
  button.className = 'atlas-directory-item';
  button.type = 'button';
  const name = document.createElement('strong');
  name.textContent = label;
  const detail = document.createElement('small');
  detail.textContent = secondary;
  button.append(name, detail);
  button.addEventListener('click', action);
  return button;
}

function showDirectory(topic) {
  const list = atlas('atlas-directory-items');
  list.replaceChildren();
  if (!topic) {
    const topics = atlasData.nodes.filter(item => item.data.kind === 'topic');
    atlas('atlas-directory-title').textContent = 'Explore topics';
    atlas('atlas-directory-summary').textContent = `${topics.length} verified topics · select one to see its papers`;
    topics.sort((a, b) => a.data.name.localeCompare(b.data.name)).forEach(item => {
      const count = atlasData.edges.filter(edge => edge.data.source === item.data.id && edge.data.rel_label === 'IN_TOPIC').length;
      list.append(directoryButton(item.data.name, () => drawAtlas(item.data.id), `${count} papers`));
    });
    return;
  }
  const papers = atlasData.edges.filter(edge => edge.data.source === topic && edge.data.rel_label === 'IN_TOPIC')
    .map(edge => atlasData.nodes.find(node => node.data.id === edge.data.target)).filter(Boolean).slice(0, MAX_PAPERS_PER_TOPIC);
  const name = atlasData.nodes.find(node => node.data.id === topic)?.data.name || 'Topic';
  atlas('atlas-directory-title').textContent = name;
  atlas('atlas-directory-summary').textContent = `${papers.length} saved papers · select a circle to inspect its links and open its OKF`;
  const overview = directoryButton('Open complete topic dossier →', () => {
    window.location.assign(`/research/topic?name=${encodeURIComponent(name)}`);
  }, 'All papers, source coverage, and reported facts');
  overview.classList.add('atlas-dossier-action');
  list.append(overview);
  const hint = document.createElement('p');
  hint.className = 'atlas-paper-hint';
  hint.textContent = 'Select a paper circle to highlight its citations. The complete topic dossier groups every paper and its source-backed fields.';
  list.append(hint);
  const browser = document.createElement('details');
  browser.className = 'atlas-paper-browser';
  const toggle = document.createElement('summary');
  toggle.textContent = `Browse all ${papers.length} papers`;
  const browseList = document.createElement('div');
  browseList.className = 'atlas-paper-browser-list';
  papers.forEach(item => {
    const state = item.data.access_state;
    const label = state === 'FULLTEXT_EXTRACTED' ? 'Indra OCR · quote checked'
      : state === 'FULLTEXT_NO_VERIFIED_FIELDS' ? 'Indra read · no verified detail'
        : 'Metadata and abstract';
    browseList.append(directoryButton(item.data.name, () => openPaper(item.data.record_key), `${label} · ${item.data.provider || 'source linked'}`));
  });
  browser.append(toggle, browseList);
  list.append(browser);
}

function openPaper(key) {
  if (key) window.location.assign(`/research/paper?key=${encodeURIComponent(key)}`);
}

function shortNodeLabel(name, topicName = '') {
  const distinct = topicName && name.toLowerCase().startsWith(topicName.toLowerCase())
    ? name.slice(topicName.length).replace(/^[:\s–-]+/, '') : name;
  const label = distinct || name;
  return label.length > 40 ? label.slice(0, 38) + '…' : label;
}

function drawAtlas(topic = null) {
  selectedTopic = topic;
  showDirectory(topic);
  const topics = atlasData.nodes.filter(item => item.data.kind === 'topic');
  const paperEdges = topic ? atlasData.edges.filter(item => item.data.source === topic && item.data.rel_label === 'IN_TOPIC').slice(0, MAX_PAPERS_PER_TOPIC) : [];
  const paperIds = new Set(paperEdges.map(item => item.data.target));
  const visibleNodes = topic ? atlasData.nodes.filter(item => item.data.id === topic || paperIds.has(item.data.id)) : topics;
  const center = topic || 'research:center';
  const nodes = topic ? visibleNodes : [{ data: { id: center, name: 'Research', kind: 'center' } }, ...visibleNodes];
  const citationEdges = topic ? atlasData.edges.filter(item => item.data.rel_label === 'CITES' && paperIds.has(item.data.source) && paperIds.has(item.data.target)) : [];
  const edges = topic ? [...paperEdges, ...citationEdges] : topics.map(item => ({ data: { id: `root:${item.data.id}`, source: center, target: item.data.id, rel_label: 'TOPIC' } }));
  const width = 1200;
  const height = 780;
  const orbit = nodes.filter(item => item.data.id !== center);
  const positions = new Map([[center, { x: width / 2, y: height / 2 }]]);
  orbit.forEach((item, index) => {
    const ringSize = topic ? Math.ceil(orbit.length / 2) : 10;
    const ring = Math.floor(index / ringSize);
    const ringCount = Math.min(ringSize, orbit.length - ring * ringSize);
    const angle = (2 * Math.PI * (index % ringSize) / ringCount) - Math.PI / 2 + ring * .12;
    const radius = 240 + ring * 135;
    positions.set(item.data.id, { x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius });
  });
  atlasGraph?.destroy();
  atlasGraph = cytoscape({
    container: atlas('atlas-canvas'),
    elements: [...nodes.map(item => ({ ...item, data: { ...item.data, display_name: shortNodeLabel(item.data.name, topic ? atlasData.nodes.find(node => node.data.id === topic)?.data.name : '') }, position: positions.get(item.data.id) })), ...edges],
    layout: { name: 'preset', fit: true, padding: 90 }, minZoom: .2, maxZoom: 2.5,
    style: [
      { selector: 'node', style: { shape: 'ellipse', label: 'data(display_name)', color: '#fff', 'font-family': 'Space Grotesk', 'font-weight': 700, 'font-size': 12, 'text-wrap': 'wrap', 'text-max-width': 86, 'text-valign': 'center', 'text-halign': 'center', width: 108, height: 108, 'background-color': '#3d1182', 'border-width': 2, 'border-color': '#ac7bff', 'underlay-color': '#8237ff', 'underlay-opacity': .28, 'underlay-padding': 12, 'underlay-shape': 'ellipse' } },
      { selector: 'node[kind="center"]', style: { width: 164, height: 164, 'font-size': 19, 'background-color': '#8b10d2', 'border-color': '#efa9ff', 'underlay-color': '#d500f9', 'underlay-padding': 18 } },
      { selector: 'node[kind="topic"]', style: { width: 120, height: 120, 'font-size': 12, 'background-color': '#9c0ab0', 'border-color': '#fa8dff', 'underlay-color': '#ea0df9' } },
      { selector: 'node[kind="paper"]', style: { 'background-color': '#04485a', 'border-color': '#62f8f2', 'underlay-color': '#00e9e7', 'text-max-width': 82 } },
      { selector: 'edge', style: { width: 2, 'line-color': '#9a60df', 'curve-style': 'bezier', 'opacity': .85 } },
      { selector: 'edge[rel_label="CITES"]', style: { width: 2.3, 'line-color': '#28d9d0', 'target-arrow-color': '#75fff5', 'target-arrow-shape': 'triangle' } },
      { selector: '.atlas-muted', style: { opacity: .12, 'text-opacity': .08 } },
      { selector: 'node.atlas-related', style: { 'border-width': 3, 'underlay-opacity': .5 } },
      { selector: 'edge.atlas-related', style: { width: 3.2, opacity: 1 } },
      { selector: '.atlas-focused', style: { 'border-width': 4, 'border-color': '#fff', 'underlay-opacity': .65, 'underlay-padding': 18 } }
    ]
  });
  atlasGraph.on('tap', 'node', event => {
    const node = event.target;
    markFocus(node);
    const data = node.data();
    const list = atlas('atlas-directory-items');
    list.querySelector('.atlas-focus-action')?.remove();
    if (data.kind === 'topic' && !topic) {
      const action = directoryButton(`Explore ${data.name}`, () => drawAtlas(data.id), 'Open paper network ↗');
      action.classList.add('atlas-focus-action');
      list.prepend(action);
    }
    if (data.kind === 'paper') {
      const action = directoryButton(`Open OKF · ${data.name}`, () => openPaper(data.record_key), 'View all verified fields ↗');
      action.classList.add('atlas-focus-action');
      list.insertBefore(action, list.querySelector('.atlas-paper-browser'));
    }
    if (data.kind === 'center' && topic) drawAtlas();
  });
  atlas('atlas-status').textContent = topic ? `${orbit.length} papers · ${citationEdges.length} linked citations` : `${topics.length} topics from verified local ingestion`;
  const url = new URL(location.href);
  if (topic) url.searchParams.set('topic', topic);
  else url.searchParams.delete('topic');
  history.replaceState(null, '', url);
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  try {
    const response = await fetch('/api/research/graph/papers', { cache: 'no-store' });
    if (!response.ok) throw new Error('Research graph is unavailable');
    atlasData = await response.json();
    if (!window.cytoscape) throw new Error('Graph renderer is unavailable');
    const topic = new URLSearchParams(location.search).get('topic');
    drawAtlas(atlasData.nodes.some(node => node.data.id === topic) ? topic : null);
  } catch (error) { atlas('atlas-status').textContent = error.message; }
  atlas('atlas-reset').addEventListener('click', () => atlasData && drawAtlas());
  atlas('atlas-plus').addEventListener('click', () => atlasGraph?.zoom(Math.min(atlasGraph.maxZoom(), atlasGraph.zoom() * 1.2)));
  atlas('atlas-minus').addEventListener('click', () => atlasGraph?.zoom(Math.max(atlasGraph.minZoom(), atlasGraph.zoom() / 1.2)));
  atlas('atlas-fit').addEventListener('click', () => atlasGraph?.fit(undefined, 80));
});
