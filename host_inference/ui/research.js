let graphView;
let selectedConcept;
let selectedNode;
let canEdit = false;
let fullData;
let showingAll = false;
let currentGraphLabel = '';

const HUB_LABEL_DEGREE = 9;
const SCHOLARLY_KINDS = new Set([
  'paper', 'institutional_page', 'author', 'venue', 'topic', 'institution', 'dataset', 'provider'
]);
const NON_ACADEMIC_PREFIXES = ['record:', 'paper:', 'author:', 'venue:', 'topic:', 'institution:', 'dataset:', 'provider:', 'concept:'];

const elements = {
  query: document.getElementById('query'),
  status: document.getElementById('graph-status'),
  counts: document.getElementById('graph-counts'),
  title: document.getElementById('detail-heading'),
  summary: document.getElementById('detail-summary'),
  source: document.getElementById('detail-source'),
  secondaryLink: document.getElementById('detail-secondary-link'),
  kind: document.getElementById('detail-kind'),
  degree: document.getElementById('detail-degree'),
  sourceCount: document.getElementById('detail-source-count'),
  metaList: document.getElementById('node-meta-list'),
  edgeInspector: document.getElementById('edge-inspector'),
  edgeInspectorList: document.getElementById('edge-inspector-list'),
  expand: document.getElementById('expand-node'),
  list: document.getElementById('concept-list'),
  form: document.getElementById('annotation-form'),
  editorHeading: document.getElementById('editor-heading'),
  editorSummary: document.getElementById('annotation-summary'),
  editorSource: document.getElementById('annotation-source'),
  editorStatus: document.getElementById('annotation-status')
};

function prefersReducedMotion() {
  return Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

function setStatus(message) {
  elements.status.textContent = message;
}

function isScholarlyNode(node) {
  const kind = String(node.kind || '').toLowerCase();
  const id = String(node.id || '');
  return SCHOLARLY_KINDS.has(kind) || NON_ACADEMIC_PREFIXES.some(prefix => id.startsWith(prefix));
}

function isPaperNode(node) {
  const kind = String(node.kind || '').toLowerCase();
  const id = String(node.id || '');
  return kind === 'paper' || id.startsWith('paper:') || (id.startsWith('record:') && kind !== 'institutional_page');
}

function clearMetaList() {
  if (!elements.metaList) return;
  elements.metaList.replaceChildren();
  elements.metaList.hidden = true;
}

function appendMetaRow(label, valueNodeOrText) {
  if (!elements.metaList) return;
  const wrapper = document.createElement('div');
  const dt = document.createElement('dt');
  dt.textContent = label;
  const dd = document.createElement('dd');
  if (valueNodeOrText instanceof Node) dd.append(valueNodeOrText);
  else dd.textContent = String(valueNodeOrText);
  wrapper.append(dt, dd);
  elements.metaList.append(wrapper);
  elements.metaList.hidden = false;
}

function createLink(href, label) {
  const link = document.createElement('a');
  link.href = href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = label;
  return link;
}

function buildLinkedPapersList(paperNodes) {
  if (!paperNodes.length) return 'No linked papers in current view.';
  const container = document.createElement('div');
  container.className = 'node-linked-papers';
  paperNodes.forEach(paperData => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'node-paper-link';
    btn.textContent = paperData.name || paperData.title || paperData.id;
    btn.addEventListener('click', () => {
      if (!graphView) return;
      const cyNode = graphView.getElementById(paperData.id);
      if (cyNode && cyNode.length) {
        graphView.elements().unselect();
        cyNode.select();
        highlightNeighborhood(cyNode);
      }
      showNode(paperData);
    });
    container.append(btn);
  });
  return container;
}

function getNeighborNodes(nodeId, filterFn = null) {
  if (!graphView) return [];
  const center = graphView.getElementById(nodeId);
  if (!center || !center.length) return [];
  const results = [];
  const seen = new Set();
  center.connectedEdges().forEach(edge => {
    const src = edge.source();
    const tgt = edge.target();
    const other = src.id() === nodeId ? tgt : src;
    const otherData = other.data();
    if (!otherData || seen.has(otherData.id)) return;
    if (filterFn && !filterFn(edge.data(), otherData, src.id() === nodeId)) return;
    seen.add(otherData.id);
    results.push(otherData);
  });
  return results;
}

function highlightNeighborhood(target) {
  if (!graphView || !target || !target.length) return;
  graphView.elements().removeClass('dimmed highlighted');
  if (target.isEdge()) {
    const endpoints = target.connectedNodes();
    const keep = target.union(endpoints);
    graphView.elements().not(keep).addClass('dimmed');
    target.addClass('highlighted');
    endpoints.addClass('highlighted');
    return;
  }
  const neighborhood = target.closedNeighborhood();
  graphView.elements().not(neighborhood).addClass('dimmed');
  target.connectedEdges().addClass('highlighted');
}

function clearHighlight() {
  if (!graphView) return;
  graphView.elements().removeClass('dimmed highlighted');
}

function showEdge(edgeEl) {
  if (!elements.edgeInspector || !elements.edgeInspectorList) return;
  const edge = edgeEl.data();
  const srcData = edgeEl.source().data();
  const tgtData = edgeEl.target().data();
  const srcName = srcData?.name || srcData?.title || edge.source;
  const tgtName = tgtData?.name || tgtData?.title || edge.target;
  const rawRel = String(edge.rel_label || edge.relation || edge.type || 'RELATED').toUpperCase();
  const rel = (currentGraphLabel === 'research' && (rawRel === 'REQUIRES' || rawRel === 'UNLOCKS'))
    ? 'RELATED_TO'
    : rawRel;
  const isCitation = rel === 'CITES';
  const provenance = edge.source_ref || edge.provenance || edge.provider || '';

  elements.edgeInspectorList.replaceChildren();
  const rows = [
    [isCitation ? 'Citing work (source)' : 'Source node', srcName],
    [isCitation ? 'Cited work (target)' : 'Target node', tgtName],
    ['Relation type', rel],
    ['Direction', isCitation ? `${srcName} → ${tgtName} (cites)` : `${srcName} → ${tgtName}`],
    ['Stored provenance', provenance || 'No edge-level provenance stored']
  ];
  rows.forEach(([label, val]) => {
    const wrapper = document.createElement('div');
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = val;
    wrapper.append(dt, dd);
    elements.edgeInspectorList.append(wrapper);
  });
  elements.edgeInspector.hidden = false;
  setStatus(`${isCitation ? 'Citation' : rel} edge: ${srcName} → ${tgtName}`);
}

function renderAnnotation(annotation, node) {
  elements.summary.textContent = annotation?.summary || node.summary || 'No description is available for this concept yet.';
  const url = annotation?.source_url;
  const validUrl = typeof url === 'string' && url.startsWith('https://');
  elements.source.hidden = !validUrl;
  if (validUrl) {
    elements.source.href = url;
    elements.source.textContent = 'Open source ↗';
  }
  if (canEdit) {
    elements.form.hidden = false;
    elements.editorHeading.textContent = annotation ? 'Update curated details' : 'Add curated details';
    elements.editorSummary.value = annotation?.summary || '';
    elements.editorSource.value = annotation?.source_url || '';
    elements.editorStatus.textContent = '';
  }
}

function renderPaperInspector(node) {
  const title = node.name || node.title || node.id;
  const abstractText = node.abstract || node.summary || 'No abstract available in stored record.';
  elements.title.textContent = title;
  elements.summary.textContent = abstractText;
  elements.kind.textContent = 'paper';
  elements.expand.disabled = true;

  const connectedAuthors = getNeighborNodes(node.id, (edgeData, otherData) => {
    const rel = String(edgeData.rel_label || '').toUpperCase();
    return rel === 'AUTHORED_BY' || String(otherData.kind || '').toLowerCase() === 'author';
  }).map(a => a.name || a.id);

  let authorsText = 'Not reported in stored metadata';
  if (Array.isArray(node.authors) && node.authors.length) {
    authorsText = node.authors.map(a => (typeof a === 'string' ? a : a?.name)).filter(Boolean).join(', ') || authorsText;
  } else if (typeof node.authors === 'string' && node.authors.trim()) {
    authorsText = node.authors.trim();
  } else if (connectedAuthors.length) {
    authorsText = connectedAuthors.join(', ');
  }

  const year = node.year || node.publication_year || (node.published_at ? String(node.published_at).slice(0, 4) : '');
  const doi = node.doi ? String(node.doi).replace(/^https?:\/\/doi\.org\//i, '') : '';
  const provider = node.provider || node.source_name || node.source || 'Not reported';

  const outgoingCitations = getNeighborNodes(node.id, (edgeData, _other, isOutgoing) =>
    String(edgeData.rel_label || '').toUpperCase() === 'CITES' && isOutgoing
  );
  const incomingCitations = getNeighborNodes(node.id, (edgeData, _other, isOutgoing) =>
    String(edgeData.rel_label || '').toUpperCase() === 'CITES' && !isOutgoing
  );

  appendMetaRow('Title', title);
  appendMetaRow('Authors', authorsText);
  appendMetaRow('Year', year || 'Not reported');
  if (doi) {
    appendMetaRow('DOI', createLink(`https://doi.org/${doi}`, doi));
  } else {
    appendMetaRow('DOI', 'Not reported');
  }
  appendMetaRow('Source provider', provider);
  appendMetaRow(
    'Cites (outgoing)',
    outgoingCitations.length ? buildLinkedPapersList(outgoingCitations) : 'No outgoing citation edges in current view'
  );
  appendMetaRow(
    'Cited by (incoming)',
    incomingCitations.length ? buildLinkedPapersList(incomingCitations) : 'No incoming citation edges in current view'
  );

  const sourceUrl = node.source_url || node.url || (doi ? `https://doi.org/${doi}` : '');
  if (sourceUrl && /^https?:\/\//i.test(sourceUrl)) {
    elements.source.href = sourceUrl;
    elements.source.textContent = 'Open scholarly source ↗';
    elements.source.hidden = false;
  }
  if (elements.secondaryLink && node.record_key) {
    elements.secondaryLink.href = `/research/paper?record_key=${encodeURIComponent(node.record_key)}`;
    elements.secondaryLink.textContent = 'View saved paper OKF ↗';
    elements.secondaryLink.hidden = false;
  }
}

function renderAuthorInspector(node) {
  elements.title.textContent = node.name || node.id;
  elements.summary.textContent = node.summary || 'Verified author identity from stored scholarly records.';
  elements.kind.textContent = 'author';
  elements.expand.disabled = true;

  const linkedPapers = getNeighborNodes(node.id, (_edgeData, otherData) => isPaperNode(otherData));
  appendMetaRow('Verified identity', node.name || node.id);
  if (node.orcid) appendMetaRow('ORCID', String(node.orcid));
  if (node.openalex_id) appendMetaRow('OpenAlex ID', String(node.openalex_id));
  if (node.affiliation || node.institution) appendMetaRow('Affiliation', String(node.affiliation || node.institution));

  const bibliometrics = [];
  if (node.works_count != null) bibliometrics.push(`Works: ${node.works_count}`);
  if (node.cited_by_count != null) bibliometrics.push(`Cited by: ${node.cited_by_count}`);
  if (node.h_index != null) bibliometrics.push(`h-index: ${node.h_index}`);
  if (node.paper_count != null) bibliometrics.push(`Stored papers: ${node.paper_count}`);
  appendMetaRow(
    'Bibliometric observations (stored)',
    bibliometrics.length
      ? bibliometrics.join(' · ')
      : `${linkedPapers.length} linked paper(s) in current graph (no additional bibliometric metrics stored)`
  );
  appendMetaRow('Linked papers', buildLinkedPapersList(linkedPapers));
}

function renderGroupingNodeInspector(node) {
  const kind = String(node.kind || 'topic').toLowerCase();
  elements.title.textContent = node.name || node.id;
  elements.summary.textContent = node.summary || `Verified ${kind} node in the scholarly graph.`;
  elements.kind.textContent = kind;
  elements.expand.disabled = true;

  const linkedPapers = getNeighborNodes(node.id, (_edgeData, otherData) => isPaperNode(otherData));
  if (node.provider) appendMetaRow('Provider', String(node.provider));
  if (node.url && /^https?:\/\//i.test(node.url)) {
    appendMetaRow('Source URL', createLink(node.url, node.url));
  }
  appendMetaRow(`Linked papers (${linkedPapers.length})`, buildLinkedPapersList(linkedPapers));
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
  if (elements.secondaryLink) elements.secondaryLink.hidden = true;
  elements.form.hidden = true;
  clearMetaList();
  if (elements.edgeInspector) elements.edgeInspector.hidden = true;

  if (isPaperNode(node)) {
    renderPaperInspector(node);
    return;
  }
  const kind = String(node.kind || '').toLowerCase();
  if (kind === 'author' || String(node.id).startsWith('author:')) {
    renderAuthorInspector(node);
    return;
  }
  if (['topic', 'venue', 'institution', 'dataset', 'provider'].includes(kind)) {
    renderGroupingNodeInspector(node);
    return;
  }
  if (node.source_url && kind === 'institutional_page') {
    elements.summary.textContent = node.summary || 'This record has no abstract or extract.';
    elements.source.href = node.source_url;
    elements.source.textContent = 'Open source ↗';
    elements.source.hidden = false;
    elements.expand.disabled = true;
    return;
  }
  if (isScholarlyNode(node)) {
    elements.summary.textContent = node.summary || 'Linked scholarly concept.';
    elements.expand.disabled = true;
    return;
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

function updateFilterButtonsForMode(isResearch) {
  document.querySelectorAll('.filter').forEach(button => {
    const filter = button.dataset.filter;
    if (filter === 'requires' || filter === 'enables') {
      button.hidden = isResearch;
    } else if (button.classList.contains('scholarly-filter')) {
      button.hidden = !isResearch;
    }
  });
  const activeBtn = document.querySelector('.filter.active');
  if (activeBtn && activeBtn.hidden) {
    applyFilter('all');
  }
}

function renderConceptList(nodes) {
  elements.list.replaceChildren();
  nodes.slice().sort((a, b) => String(a.data.name || '').localeCompare(String(b.data.name || ''))).forEach(item => {
    const li = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = item.data.name || item.data.id;
    button.addEventListener('click', () => {
      const cyNode = graphView.getElementById(item.data.id);
      if (cyNode && cyNode.length) {
        graphView.elements().unselect();
        cyNode.select();
        highlightNeighborhood(cyNode);
      }
      showNode(item.data);
    });
    li.append(button);
    elements.list.append(li);
  });
}

function drawGraph(data) {
  currentGraphLabel = data.graph_label || '';
  const isResearch = currentGraphLabel === 'research';
  showingAll = Boolean(data.counts) && !isResearch;
  updateFilterButtonsForMode(isResearch);

  const sanitizedEdges = (data.edges || []).map(edge => {
    const rawRel = String(edge.data?.rel_label || edge.data?.relation || '').toUpperCase();
    const safeRel = (isResearch && (rawRel === 'REQUIRES' || rawRel === 'UNLOCKS')) ? 'RELATED_TO' : rawRel;
    return {
      ...edge,
      data: {
        ...edge.data,
        rel_label: safeRel || (isResearch ? 'RELATED_TO' : edge.data?.rel_label)
      }
    };
  });

  graphView?.destroy();
  graphView = cytoscape({
    container: document.getElementById('graph'),
    elements: [
      ...data.nodes.map(item => ({
        ...item,
        data: {
          ...item.data,
          display_name: showingAll && (item.data.degree || 0) < HUB_LABEL_DEGREE
            ? ''
            : (item.data.name || item.data.title || item.data.id)
        },
        classes: item.data.id === data.target_id ? 'anchor' : ''
      })),
      ...sanitizedEdges
    ],
    layout: isResearch
      ? { name: 'cose', animate: false, fit: true, padding: 45, nodeRepulsion: 7200, idealEdgeLength: 110, numIter: 220 }
      : showingAll
        ? { name: 'cose', animate: false, fit: true, padding: 45, nodeRepulsion: 9000, idealEdgeLength: 90, numIter: 250 }
        : { name: 'cose', animate: false, fit: true, padding: 50, nodeRepulsion: 6300, idealEdgeLength: 125 },
    minZoom: .12,
    maxZoom: 2.5,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#a44eea',
          'border-width': 2,
          'border-color': '#eac7f8',
          'label': 'data(display_name)',
          'color': '#f4eaff',
          'text-outline-color': '#140a21',
          'text-outline-width': 2,
          'font-family': 'DM Sans',
          'font-size': 10,
          'font-weight': 700,
          'text-wrap': 'wrap',
          'text-max-width': 110,
          'text-valign': 'bottom',
          'text-margin-y': 9,
          'width': showingAll ? 18 : 26,
          'height': showingAll ? 18 : 26
        }
      },
      { selector: 'node[kind = "paper"]', style: { 'background-color': '#2a1859', 'border-color': '#8673fa', shape: 'round-rectangle', width: 30, height: 24 } },
      { selector: 'node[kind = "author"]', style: { 'background-color': '#8c2d9c', 'border-color': '#f3b8ff' } },
      { selector: 'node[kind = "venue"]', style: { 'background-color': '#9c6316', 'border-color': '#fde68a' } },
      { selector: 'node[kind = "topic"]', style: { 'background-color': '#67108b', 'border-color': '#e382ff', width: 32, height: 32 } },
      { selector: 'node[kind = "institution"]', style: { 'background-color': '#1e40af', 'border-color': '#93c5fd' } },
      { selector: 'node[kind = "dataset"]', style: { 'background-color': '#065f46', 'border-color': '#6ee7b7' } },
      { selector: 'node.anchor', style: { 'background-color': '#13cfc4', 'border-color': '#b6f5ee', 'width': 42, 'height': 42, 'font-size': 12 } },
      {
        selector: 'edge',
        style: {
          'width': showingAll ? 1 : 2.2,
          'line-color': '#e6a2ee',
          'target-arrow-color': '#e6a2ee',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 1.1,
          'curve-style': 'bezier',
          'control-point-step-size': 40,
          'opacity': showingAll ? .2 : .75
        }
      },
      { selector: 'edge[rel_label = "REQUIRES"]', style: { 'line-color': '#d73aa4', 'target-arrow-color': '#d73aa4' } },
      { selector: 'edge[rel_label = "UNLOCKS"]', style: { 'line-color': '#ebb23d', 'target-arrow-color': '#ebb23d' } },
      { selector: 'edge[rel_label = "CITES"]', style: { 'line-color': '#28d9d0', 'target-arrow-color': '#75fff5', width: 2.5 } },
      { selector: 'edge[rel_label = "AUTHORED_BY"]', style: { 'line-color': '#c084fc', 'target-arrow-color': '#c084fc' } },
      { selector: 'edge[rel_label = "PUBLISHED_IN"]', style: { 'line-color': '#fbbf24', 'target-arrow-color': '#fbbf24' } },
      { selector: 'edge[rel_label = "IN_TOPIC"]', style: { 'line-color': '#e879f9', 'target-arrow-color': '#e879f9' } },
      { selector: '.dimmed', style: { 'opacity': .1 } },
      { selector: 'edge.highlighted', style: { 'opacity': .98, 'width': 3.2 } },
      { selector: 'node.highlighted', style: { 'opacity': 1 } },
      { selector: ':selected', style: { 'border-color': '#ffffff', 'border-width': 4 } }
    ]
  });

  const container = graphView.container();
  if (container) container.style.cursor = 'grab';

  graphView.on('mouseover', 'node, edge', event => {
    if (container) container.style.cursor = 'pointer';
    if (graphView.$(':selected').length === 0) {
      highlightNeighborhood(event.target);
    }
  });
  graphView.on('mouseout', 'node, edge', () => {
    if (container) container.style.cursor = 'grab';
    if (graphView.$(':selected').length === 0) {
      clearHighlight();
    }
  });

  graphView.on('tap', 'node', event => {
    highlightNeighborhood(event.target);
    showNode(event.target.data());
  });
  graphView.on('tap', 'edge', event => {
    highlightNeighborhood(event.target);
    showEdge(event.target);
  });
  if (!isResearch) graphView.on('dbltap', 'node', event => loadGraph({ target_id: event.target.id() }));
  graphView.on('tap', event => {
    if (event.target === graphView) {
      clearHighlight();
      if (elements.edgeInspector) elements.edgeInspector.hidden = true;
    }
  });

  const anchor = data.nodes.find(item => item.data.id === data.target_id);
  if (anchor) {
    const cyAnchor = graphView.getElementById(anchor.data.id);
    if (cyAnchor && cyAnchor.length) highlightNeighborhood(cyAnchor);
    showNode(anchor.data);
  } else {
    clearMetaList();
    if (elements.edgeInspector) elements.edgeInspector.hidden = true;
  }
  renderConceptList(data.nodes);
  const total = isResearch ? data.nodes.length : (fullData?.counts?.concepts || data.nodes.length);
  const label = isResearch ? 'research nodes' : 'concepts';
  elements.counts.textContent = `${data.nodes.length} of ${total} ${label} · ${sanitizedEdges.length} relationships`;
  setStatus(isResearch
    ? 'Live scholarly research graph. Select any paper, author, topic, venue, or citation edge to inspect.'
    : showingAll
      ? 'Full institutional graph loaded. Select a concept or edge to inspect it.'
      : 'Focused view. Choose All concepts to return to the complete graph.');
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
    nodes.push({ data: { id, name: record.title, summary: record.content, kind: record.kind || 'paper', record_key: record.record_key, source_url: record.source_url, provider: record.source_name, degree: 1, source_count: 1 } });
    edges.push({ data: { id: `${id}:${topicId}`, source: id, target: topicId, rel_label: 'IN_TOPIC' } });
  });
  showGraphView();
  document.getElementById('show-all').classList.remove('active');
  document.getElementById('show-intake-map').classList.add('active');
  if (nodes.length) drawGraph({ nodes, edges, graph_label: 'research' });
  else setStatus('No research records ingested yet. Fetch a topic or college page below.');
  document.getElementById('graph').scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'center' });
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
    if (prefersReducedMotion()) {
      graphView.center(node);
      graphView.zoom(.95);
    } else {
      graphView.animate({ center: { eles: node }, zoom: .95 }, { duration: 350 });
    }
    node.select();
    highlightNeighborhood(node);
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
document.getElementById('zoom-reset')?.addEventListener('click', () => {
  if (!graphView) return;
  graphView.elements().unselect();
  clearHighlight();
  applyFilter('all');
  if (elements.edgeInspector) elements.edgeInspector.hidden = true;
  graphView.fit(undefined, 40);
});

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
