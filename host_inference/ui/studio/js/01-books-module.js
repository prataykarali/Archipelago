// Auto-split from ui/chat/index.html — 01-books-module.js
// Feature module 2 of 6.
import { state } from './00-state.js';
import { bk, destroyGraph, escapeHtml, setTab } from './00-escape-html.js';
import { closeFlashcard } from './03-open-fc.js';
import { buildConceptGraph } from './02-build-concept-graph.js';

// ══════════════════════════════════════════════════════════════
// 1. BOOKS MODULE: MODERN RESPONSIVE GRID VIEW
// ══════════════════════════════════════════════════════════════
const BooksModule = {
  render(){
    setTab('books');
    state.currentBook = null;
    closeFlashcard();
    destroyGraph();

    // Toggle UI views
    document.getElementById('books-view').classList.add('active');
    document.getElementById('graph-wrap').style.display = 'none';
    document.getElementById('chip-bar').classList.add('hidden');
    document.getElementById('zoom-ctrls').style.display = 'none';
    document.getElementById('back-btn').style.display = 'none';
    document.getElementById('book-label').style.display = 'none';

    // Aggregate book statistics
    const bs = {};
    state.allNodes.forEach(n => {
      n._books.forEach(b => {
        if (b !== '_other_') {
          bs[b] = bs[b] || { nodes: 0, edges: 0 };
          bs[b].nodes++;
        }
      });
    });

    state.allEdges.forEach(e => {
      const sn = state.nodeMap[e.source], tn = state.nodeMap[e.target];
      if (sn && tn) {
        sn._books.forEach(b => {
          if (b !== '_other_' && tn._books.has(b)) {
            bs[b] = bs[b] || { nodes: 0, edges: 0 };
            bs[b].edges++;
          }
        });
      }
    });

    const bookKeys = Object.keys(bs);
    document.getElementById('books-total-count').textContent = `${bookKeys.length} books in catalog`;

    // Group books by domain/shelf
    const domainGroups = {};
    bookKeys.forEach(bookId => {
      const info = bk(bookId);
      const domain = info.domain || info.shelf || 'General Knowledge';
      if (!domainGroups[domain]) domainGroups[domain] = [];
      domainGroups[domain].push({ bookId, info });
    });

    const grid = document.getElementById('books-grid');
    grid.style.display = 'flex';
    grid.style.flexDirection = 'column';
    grid.style.gap = '24px';
    grid.style.maxWidth = '840px';
    grid.style.margin = '0 auto';

    grid.innerHTML = Object.keys(domainGroups).map(domainName => {
      const items = domainGroups[domainName];
      const cardsHtml = items.map(({ bookId, info }) => {
        const nodeCount = bs[bookId] ? bs[bookId].nodes : 0;
        const edgeCount = bs[bookId] ? bs[bookId].edges : 0;
        const accent = info.color || '#8b5cf6';
        const yearStr = info.year ? ` · ${info.year}` : '';

        return `
          <div class="book-card" style="--card-accent:${accent}; margin-bottom: 12px;">
            <div class="book-card-top">
              <div class="book-card-icon-wrap" style="border-color:${accent}30;background:${accent}12">
                <img src="/ui/assets/book_btn.png" class="book-card-icon" alt="Book">
              </div>
              <div class="book-card-headings">
                <div class="book-card-title">${escapeHtml(info.name)}</div>
                <span class="book-shelf-badge" style="background:${accent}12;color:${accent};border-color:${accent}25">
                  ${escapeHtml(info.shelf || 'Archive')}
                </span>
              </div>
            </div>
            <div class="book-card-full">${escapeHtml(info.full)}</div>
            <div class="book-card-meta">
              <span class="book-card-author">${escapeHtml(info.author)}</span>
              <span class="book-card-year">${escapeHtml(yearStr)}</span>
            </div>
            <div class="book-stats-row">
              <div class="book-stat-pill">
                <img src="/ui/assets/brain_btn.png" class="btn-icon-sm" alt="Concepts">
                <span><strong>${nodeCount}</strong> concepts</span>
              </div>
              <div class="book-stat-pill">
                <img src="/ui/assets/network_btn.png" class="btn-icon-sm" alt="Connections">
                <span><strong>${edgeCount}</strong> edges</span>
              </div>
            </div>
            <button class="book-explore-btn" onclick="showConcepts('${escapeHtml(bookId)}')">
              <img src="/ui/assets/graph_btn.png" class="btn-icon-sm" alt="Explore"> Explore Knowledge Graph &rarr;
            </button>
          </div>
        `;
      }).join('');

      return `
        <div class="domain-group-wrapper">
          <div style="font-size: 11px; font-family: monospace; letter-spacing: 0.15em; text-transform: uppercase; color: rgba(255,255,255,0.5); padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 12px; display: flex; items-center: center; gap: 8px;">
            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#3b82f6;"></span>
            <span>DOMAIN: ${escapeHtml(domainName)}</span>
          </div>
          <div class="domain-stack" style="display:flex; flex-direction:column; gap:12px;">
            ${cardsHtml}
          </div>
        </div>
      `;
    }).join('');

    document.getElementById('st-n').textContent = state.allNodes.length;
    document.getElementById('st-e').textContent = state.allEdges.length;
    document.getElementById('st-view').textContent = 'Books Catalog';
  }
};

function showBooks(){
  BooksModule.render();
}

// ══════════════════════════════════════════════════════════════
// 2. CONCEPTS & CROSS-BOOK MODULE: D3 FORCE SIMULATION
// ══════════════════════════════════════════════════════════════
function showConcepts(bookId){
  setTab('concepts');
  state.currentBook = bookId;
  closeFlashcard();
  destroyGraph();

  // Switch view containers
  document.getElementById('books-view').classList.remove('active');
  document.getElementById('graph-wrap').style.display = 'block';
  document.getElementById('chip-bar').classList.remove('hidden');
  document.getElementById('zoom-ctrls').style.display = 'flex';

  if (bookId) {
    const info = bk(bookId);
    const backBtn = document.getElementById('back-btn');
    backBtn.style.display = 'inline-flex';
    backBtn.innerHTML = `<img src="/ui/assets/book_btn.png" class="btn-icon" alt="Back"> ← Books`;

    const label = document.getElementById('book-label');
    label.style.display = 'inline-flex';
    label.innerHTML = `<img src="/ui/assets/book_btn.png" class="btn-icon" alt="Book"> <span>${escapeHtml(info.name)} — ${escapeHtml(info.author)} ${escapeHtml(info.year||'')}</span>`;
    label.style.color = info.color;
  } else {
    document.getElementById('back-btn').style.display = 'none';
    const label = document.getElementById('book-label');
    label.style.display = 'inline-flex';
    label.innerHTML = `<img src="/ui/assets/graph_btn.png" class="btn-icon" alt="All"> <span>All Concepts</span>`;
    label.style.color = 'var(--tx2)';
  }

  let fN, fE;
  if (bookId) {
    const bids = new Set();
    const prim = state.allNodes.filter(n => {
      if (n._books.has(bookId)) { bids.add(n.id); return true; }
      return false;
    });
    const intE = state.allEdges.filter(e => bids.has(e.source) && bids.has(e.target));
    const xE = state.allEdges.filter(e => {
      const s = bids.has(e.source), t = bids.has(e.target);
      return (s && !t) || (t && !s);
    });
    const gids = new Set();
    xE.forEach(e => {
      if (!bids.has(e.source)) gids.add(e.source);
      if (!bids.has(e.target)) gids.add(e.target);
    });
    const ghosts = state.allNodes.filter(n => gids.has(n.id)).map(n => ({...n, _ghost: true}));
    fN = [...prim, ...ghosts];
    fE = [...intE, ...xE.map(e => ({...e, _external: true}))];
  } else {
    fN = [...state.allNodes];
    fE = [...state.allEdges];
  }

  const nodes = fN.map(n => ({...n}));
  const edges = fE.map(e => ({...e}));
  const nm = {};
  nodes.forEach(n => nm[n.id] = n);
  buildConceptGraph(nodes, edges, nm, bookId);
}

function showCrossBook(){
  setTab('crossbook');
  state.currentBook = null;
  closeFlashcard();
  destroyGraph();

  document.getElementById('books-view').classList.remove('active');
  document.getElementById('graph-wrap').style.display = 'block';
  document.getElementById('chip-bar').classList.remove('hidden');
  document.getElementById('zoom-ctrls').style.display = 'flex';
  document.getElementById('back-btn').style.display = 'none';

  const label = document.getElementById('book-label');
  label.style.display = 'inline-flex';
  label.innerHTML = `<img src="/ui/assets/network_btn.png" class="btn-icon" alt="Cross-Book"> <span>Cross-Book Connections</span>`;
  label.style.color = 'var(--cyan)';

  const crossEdges = state.allEdges.filter(e => {
    const sn = state.nodeMap[e.source], tn = state.nodeMap[e.target];
    if (!sn || !tn) return false;
    return sn._book !== tn._book;
  });
  const crossIds = new Set();
  crossEdges.forEach(e => { crossIds.add(e.source); crossIds.add(e.target); });
  const crossNodes = state.allNodes.filter(n => crossIds.has(n.id));

  const nodes = crossNodes.map(n => ({...n}));
  const edges = crossEdges.map(e => ({...e}));
  const nm = {};
  nodes.forEach(n => nm[n.id] = n);
  buildConceptGraph(nodes, edges, nm, null);

  document.getElementById('st-n').textContent = nodes.length;
  document.getElementById('st-e').textContent = edges.length;
  document.getElementById('st-view').textContent = 'Cross-Book';
}

export { BooksModule, showBooks, showConcepts, showCrossBook };
