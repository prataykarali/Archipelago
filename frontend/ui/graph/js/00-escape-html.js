// Auto-split from ui/chat/index.html — 00-escape-html.js
// Feature module 1 of 6.
import { state } from './00-state.js';

// Escape data-derived strings for innerHTML
function escapeHtml(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

// ── BOOKS METADATA & SHELVES ──
const BOOKS = {
  'papers/Devlin2018_BERT.pdf': {
    name: 'BERT',
    full: 'Pre-training of Deep Bidirectional Transformers for Language Understanding',
    author: 'Devlin et al.',
    year: 2018,
    color: '#8b5cf6',
    shelf: 'Language Models',
    domain: 'NLP & Transformers'
  },
  'papers/Edge2024_GraphRAG.pdf': {
    name: 'GraphRAG',
    full: 'From Local to Global: A Graph RAG Approach to Query-Focused Summarization',
    author: 'Edge et al.',
    year: 2024,
    color: '#10b981',
    shelf: 'Knowledge Graphs',
    domain: 'RAG & Graphs'
  },
  'papers/Hu2021_LoRA.pdf': {
    name: 'LoRA',
    full: 'Low-Rank Adaptation of Large Language Models',
    author: 'Hu et al.',
    year: 2021,
    color: '#f97316',
    shelf: 'Parameter-Efficient Fine-Tuning',
    domain: 'Model Adaptation'
  },
  'papers/Lewis2020_RAG.pdf': {
    name: 'RAG',
    full: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
    author: 'Lewis et al.',
    year: 2020,
    color: '#0284c7',
    shelf: 'Information Retrieval',
    domain: 'RAG Architecture'
  },
  'papers/Vaswani2017_Attention_Is_All_You_Need.pdf': {
    name: 'Attention',
    full: 'Attention Is All You Need',
    author: 'Vaswani et al.',
    year: 2017,
    color: '#ec4899',
    shelf: 'Transformer Architecture',
    domain: 'Foundation Models'
  },
  'papers/Velickovic2017_GAT.pdf': {
    name: 'GAT',
    full: 'Graph Attention Networks',
    author: 'Veličković et al.',
    year: 2017,
    color: '#06b6d4',
    shelf: 'Graph Learning',
    domain: 'Graph Neural Networks'
  },
  'papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf': {
    name: 'Network Security GNN',
    full: 'Real-time Network Security: Integrating ANN and Dynamic Graph-Based Detection',
    author: 'Dubin et al.',
    year: 2024,
    color: '#ef4444',
    shelf: 'Cybersecurity',
    domain: 'GNN & Intrusion Detection'
  },
  'probable.pdf': {
    name: 'Probable',
    full: 'Probabilistic Methods & Soft-Target Fine-Tuning',
    author: 'Research Paper',
    year: 2024,
    color: '#f59e0b',
    shelf: 'Probabilistic ML',
    domain: 'Statistical Learning'
  },
  'web_syllabi/AI_ML_Archipelago_Corpus_Seed.md': {
    name: 'AI/ML Syllabi',
    full: 'AI/ML Archipelago Corpus Seed & Curated Taxonomy',
    author: 'Curated Faculty',
    year: 2024,
    color: '#06b6d4',
    shelf: 'Curriculum',
    domain: 'Academic Seed'
  },
  'textbooks/Deisenroth_Math_For_ML.pdf': {
    name: 'Math for ML',
    full: 'Mathematics for Machine Learning',
    author: 'Deisenroth et al.',
    year: 2020,
    color: '#10b981',
    shelf: 'Foundations',
    domain: 'Linear Algebra & Calculus'
  }
};

function bk(id){
  if(BOOKS[id]) return BOOKS[id];
  const clean = (id||'').split('/').pop().replace(/\.pdf$/i,'').replace(/\.md$/i,'').replace(/\.txt$/i,'');
  let shelf = 'Academic Paper';
  if((id||'').startsWith('papers/')) shelf = 'Research Paper';
  else if((id||'').startsWith('textbooks/')) shelf = 'Textbook';
  else if((id||'').includes('syllabi')) shelf = 'Curriculum';

  return {
    name: clean.length > 28 ? clean.slice(0, 26) + '…' : clean,
    full: clean || 'Document',
    author: 'Archipelago Scholar',
    year: '',
    color: '#8b5cf6',
    shelf: shelf,
    domain: shelf
  };
}

// ── VIBRANT COLOR PALETTES ──
const TC = {
  definition:   '#0284c7', // vivid sky blue
  method:       '#8b5cf6', // vivid purple
  technique:    '#06b6d4', // electric cyan
  theory:       '#d97706', // rich amber gold
  metric:       '#059669', // vivid emerald green
  dataset:      '#db2777', // vivid pink/crimson
  result:       '#dc2626', // vivid red
  tool:         '#10b981', // bright mint
  architecture: '#7c3aed', // deep violet
  framework:    '#0284c7', // cyan blue
  model:        '#a855f7', // electric purple
  principle:    '#f59e0b', // bright amber
  concept:      '#0284c7'
};

const EC = {
  requires:       '#8b5cf6',
  enables:        '#10b981',
  uses:           '#0284c7',
  extends:        '#f97316',
  part_of:        '#ec4899',
  contrasts_with: '#ef4444',
  evaluated_by:   '#d97706',
  variant_of:     '#06b6d4',
  co_mention:     '#64748b'
};

const EW = {
  requires:       2.4,
  enables:        2.4,
  uses:           2.0,
  extends:        2.0,
  part_of:        1.8,
  contrasts_with: 1.8,
  evaluated_by:   1.8,
  variant_of:     1.8,
  co_mention:     1.2
};

const EO = {
  requires:       0.85,
  enables:        0.85,
  uses:           0.80,
  extends:        0.85,
  part_of:        0.80,
  contrasts_with: 0.85,
  evaluated_by:   0.85,
  variant_of:     0.80,
  co_mention:     0.45
};

const EI = {
  requires: 'requires', enables: 'enables', uses: 'uses', extends: 'extends',
  part_of: 'part_of', contrasts_with: 'contrasts_with', evaluated_by: 'evaluated_by', variant_of: 'variant_of'
};

const rid = x => (typeof x === 'object' ? x.id : x);

function nR(d){ const g = d._d || 0; return g >= 30 ? 22 : g >= 15 ? 15 : g >= 8 ? 10 : g >= 4 ? 7 : g >= 1 ? 5 : 4; }

function nC(d){ return TC[d.concept_type] || '#0284c7'; }

// Parse URL parameter highlighting at startup
const urlParams = new URLSearchParams(window.location.search);

const highlightParam = urlParams.get('highlight');

if (highlightParam) {
  window._highlightIds = highlightParam.split(',').map(id => id.trim()).filter(Boolean);
}

// ── STAFF RBAC VERIFICATION ──
async function checkGraphStaffAccess() {
  const gate = document.getElementById('staff-auth-gate');
  let principal = null;
  let config = { required: true };

  try {
    config = await fetch('/api/auth/config', { cache: 'no-store' }).then(r => r.json());
    if (!config.required) {
      if (gate) gate.style.display = 'none';
      return true;
    }
    const loginLink = gate?.querySelector('a');
    if (loginLink && config.chatUrl) {
      const graphTarget = config.graphUrl || window.location.href;
      loginLink.href = `${config.chatUrl}/login?next=${encodeURIComponent(graphTarget)}`;
    }
    const response = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' });
    if (response.ok) principal = await response.json();
  } catch (_) {}

  const allowedRoles = ['administrator', 'librarian'];
  const userRole = (principal?.role || '').toLowerCase();
  const isAuth = principal?.authenticated === true;
  if (!isAuth || !allowedRoles.includes(userRole)) {
    if (gate) gate.style.display = 'flex';
    return false;
  } else {
    if (gate) gate.style.display = 'none';
    const hdr = document.getElementById('hdr');
    if (hdr && !document.getElementById('staff-pill')) {
      const pill = document.createElement('div');
      pill.id = 'staff-pill';
      pill.style.cssText = 'margin-left:auto;display:flex;align-items:center;gap:8px;padding:4px 12px;border-radius:999px;background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);font-size:11px;font-weight:700;color:#7c3aed;';
      const roleLabel = document.createElement('span');
      roleLabel.textContent = `${principal.role.toUpperCase()}: ${principal.username || ''}`;
      const chatLink = document.createElement('a');
      chatLink.href = `${config.chatUrl || ''}/chat`;
      chatLink.textContent = 'Chat →';
      chatLink.style.cssText = 'color:#7c3aed;text-decoration:none;margin-left:6px;font-size:10px;padding:2px 6px;border-radius:4px;background:rgba(139,92,246,0.1);';
      pill.append(roleLabel, chatLink);
      hdr.appendChild(pill);
    }
    return true;
  }
}

// ── STARFIELD BACKGROUND ──
(()=>{
  const c = document.getElementById('stars'), ctx = c.getContext('2d');
  let st = [], raf;
  const rsz = () => {
    c.width = innerWidth; c.height = innerHeight;
    st = Array.from({length: 50}, () => ({
      x: Math.random() * c.width, y: Math.random() * c.height,
      r: Math.random() * 1 + .15, a: Math.random() * .3 + .04,
      da: (Math.random() - .5) * .001
    }));
  };
  const draw = () => {
    if (document.hidden) { raf = requestAnimationFrame(draw); return; }
    ctx.clearRect(0, 0, c.width, c.height);
    for (const s of st) {
      s.a += s.da;
      if (s.a < .04 || s.a > .3) s.da *= -1;
      ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(139,92,246,${s.a})`; ctx.fill();
    }
    raf = requestAnimationFrame(draw);
  };
  rsz(); addEventListener('resize', rsz); raf = requestAnimationFrame(draw);
})();

// ── DATA INGESTION & PROCESSING ──
function processData(data){
  if (data.visualization && data.edges) {
    const nodes = data.visualization.nodes;
    const edges = data.edges.map((e, i) => ({
      id: e.id || `e${i}`,
      source: e.from_id,
      target: e.to_id,
      relation: e.relation,
      edge_type: e.edge_type,
      source_ref: e.source || ""
    }));
    data = { nodes, edges };
  }

  state.allNodes = data.nodes || [];
  state.allEdges = data.edges || [];
  const deg = {};
  state.allEdges.forEach(e => {
    deg[e.source] = (deg[e.source] || 0) + 1;
    deg[e.target] = (deg[e.target] || 0) + 1;
  });
  state.allNodes.forEach(n => {
    n._d = deg[n.id] || 0;
    n._book = (n.sources && n.sources.length) ? n.sources[0].doc_id : '_other_';
    n._books = new Set((n.sources || []).map(s => s.doc_id).filter(Boolean));
    if (!n._books.size) n._books.add('_other_');
  });
  state.nodeMap = {};
  state.allNodes.forEach(n => state.nodeMap[n.id] = n);
}

function destroyGraph(){
  if (state.simulation) { state.simulation.stop(); state.simulation = null; }
  const svg = d3.select('#graph-svg');
  svg.on('.zoom', null);
  svg.selectAll('g.root').remove();
  state.nSel = null; state.eSel = null;
}

function setTab(view){
  state.currentView = view;
  document.querySelectorAll('#nav-tabs .nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
}

export { BOOKS, EC, EI, EO, EW, TC, bk, checkGraphStaffAccess, destroyGraph, escapeHtml, highlightParam, nC, nR, processData, rid, setTab, urlParams };
