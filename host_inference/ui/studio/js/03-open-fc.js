// Auto-split from ui/chat/index.html — 03-open-fc.js
// Feature module 4 of 6.
import { state } from './00-state.js';
import { EC, TC, escapeHtml, rid } from './00-escape-html.js';
import { showConcepts } from './01-books-module.js';

// ══════════════════════════════════════════════════════════════
// 3. FLASHCARD MODULE: ALL OKF CATEGORIES & INFERENCE
// ══════════════════════════════════════════════════════════════
function openFC(d){
  state.flashcardOpen = true;
  d3.select('#graph-svg').on('.zoom', null);

  const panel = document.getElementById('flashcard');
  const gc = TC[d.concept_type] || '#8b5cf6';
  document.getElementById('fc-hero').style.background = `linear-gradient(180deg,${gc}10 0%,transparent 100%)`;
  panel.style.borderColor = `${gc}30`;

  document.getElementById('fc-badges').innerHTML = `
    <div class="badge bd-${escapeHtml(d.difficulty||'intermediate')}">${escapeHtml(d.difficulty||'?')}</div>
    <div class="badge bd-type" style="background:${gc}12;color:${gc};border:1px solid ${gc}25">${escapeHtml(d.concept_type||'?')}</div>
  `;
  document.getElementById('fc-title').textContent = d.label || d.id;
  document.getElementById('fc-summary').textContent = d.summary || 'No summary extracted by the model.';
  document.getElementById('fc-degree').textContent = (d._d || d.degree || 0) + ' edges';
  document.getElementById('fc-sources').textContent = (d.source_count || d.sources?.length || 0) + ' passages';

  const gE = window._gEdges || state.allEdges;
  const gNM = window._gNM || state.nodeMap;

  // ── DYNAMIC INFERENCE FOR PREREQUISITES & UNLOCKS ──
  let prereqs = (d.prerequisites && Array.isArray(d.prerequisites) && d.prerequisites.length) ? [...d.prerequisites] : [];
  let unlocks = (d.unlocks && Array.isArray(d.unlocks) && d.unlocks.length) ? [...d.unlocks] : [];

  if (!prereqs.length) {
    const inferred = new Set();
    gE.forEach(l => {
      const s = rid(l.source), t = rid(l.target), r = (l.relation || '').toLowerCase();
      if (t === d.id && (r === 'requires' || r === 'prerequisite')) {
        const sn = gNM[s];
        if (sn) inferred.add(sn.label || sn.id);
      } else if (s === d.id && (r === 'required_by' || r === 'prerequisite_of')) {
        const tn = gNM[t];
        if (tn) inferred.add(tn.label || tn.id);
      }
    });
    prereqs = Array.from(inferred);
  }

  if (!unlocks.length) {
    const inferred = new Set();
    gE.forEach(l => {
      const s = rid(l.source), t = rid(l.target), r = (l.relation || '').toLowerCase();
      if (s === d.id && (r === 'enables' || r === 'unlocks')) {
        const tn = gNM[t];
        if (tn) inferred.add(tn.label || tn.id);
      } else if (t === d.id && (r === 'enabled_by' || r === 'unlocked_by')) {
        const sn = gNM[s];
        if (sn) inferred.add(sn.label || sn.id);
      }
    });
    unlocks = Array.from(inferred);
  }

  document.getElementById('fc-prereqs').innerHTML = prereqs.length
    ? prereqs.map(p => `<span class="okf-pill prereq" data-name="${escapeHtml(p)}">${escapeHtml(p)}</span>`).join('')
    : '<span class="okf-empty">None identified</span>';

  document.getElementById('fc-unlocks').innerHTML = unlocks.length
    ? unlocks.map(u => `<span class="okf-pill unlock" data-name="${escapeHtml(u)}">${escapeHtml(u)}</span>`).join('')
    : '<span class="okf-empty">None identified</span>';

  document.querySelectorAll('.okf-pill').forEach(p => {
    p.onclick = () => {
      const nm2 = window._gNM || state.nodeMap;
      const name = p.dataset.name.toLowerCase();
      const f = Object.values(nm2).find(n => (n.label || n.id).toLowerCase().includes(name));
      if (f) openFC(f);
    };
  });

  // Tags
  const tags = d.tags || [];
  if (tags.length) {
    document.getElementById('fc-tags').innerHTML = tags.map(t => `<span class="fc-tag">${escapeHtml(t)}</span>`).join('');
    document.getElementById('fc-tags-sec').style.display = '';
  } else {
    document.getElementById('fc-tags-sec').style.display = 'none';
  }

  // ── ALL OKF RELATION CATEGORIES WITH DIRECTIONAL FLOW ──
  const cats = {
    requires: [],
    enables: [],
    uses: [],
    extends: [],
    part_of: [],
    contrasts_with: [],
    evaluated_by: [],
    variant_of: []
  };

  gE.forEach(l => {
    let r = (l.relation || '').toLowerCase();
    if (r === 'prerequisite') r = 'requires';
    if (r === 'unlocks') r = 'enables';
    if (!cats[r]) return;
    const s = rid(l.source), t = rid(l.target);
    if (s === d.id) {
      const n = gNM[t];
      if (n) cats[r].push({ node: n, dir: 'out', rel: r });
    }
    if (t === d.id) {
      const n = gNM[s];
      if (n) cats[r].push({ node: n, dir: 'in', rel: r });
    }
  });

  Object.keys(cats).forEach(rel => {
    const items = cats[rel];
    const sec = document.getElementById('sec-' + rel);
    const list = document.getElementById('list-' + rel);
    const cnt = document.getElementById('cnt-' + rel);
    if (!sec || !list || !cnt) return;

    cnt.textContent = items.length;
    list.innerHTML = '';
    if (!items.length) {
      sec.style.display = 'none';
      return;
    }

    items.slice(0, 16).forEach(({node, dir, rel: r}) => {
      if (!node) return;
      const li = document.createElement('li');
      li.className = 'edge-item';
      li.innerHTML = `
        <span class="edge-name">${escapeHtml(node.label || node.id)}</span>
        <span class="edge-rel" style="color:${EC[r]||'#8b5cf6'}">${escapeHtml(r.replace(/_/g, ' '))}</span>
      `;
      li.onclick = ev => { ev.stopPropagation(); openFC(node); };
      list.appendChild(li);
    });
    sec.style.display = '';
  });

  // ── GROUNDED PASSAGES WITH CHUNKS & PAGES ──
  const srcs = d.sources || [];
  if (srcs.length) {
    document.getElementById('fc-src').innerHTML = srcs.map(s => {
      const p = (s.text_passage || '').trim();
      const docName = escapeHtml((s.doc_id || '').split('/').pop().replace(/\.pdf$/i,'').replace(/\.md$/i,''));
      const chunkBadge = s.chunk_id ? `<span class="src-chunk-badge">${escapeHtml(s.chunk_id)}</span>` : '';
      const pageBadge = s.page_number != null ? `<span class="src-page-badge">Page ${escapeHtml(s.page_number)}</span>` : '';
      const section = s.section_title ? `<div class="src-section-title">${escapeHtml(s.section_title)}</div>` : '';
      const h = p ? `<div class="src-highlight">${escapeHtml(p)}</div>` : '';
      return `
        <div class="src-box">
          <div class="src-header">
            <img src="/ui/assets/pdf_btn.png" class="btn-icon-sm" alt="Doc">
            <span class="doc">${docName}</span>
            ${chunkBadge}
            ${pageBadge}
          </div>
          ${section}
          ${h}
        </div>
      `;
    }).join('');
    document.getElementById('fc-src-sec').style.display = '';
  } else {
    document.getElementById('fc-src-sec').style.display = 'none';
  }

  panel.classList.add('open');
  if (window._hlNode) window._hlNode(d.id);
}

function closeFlashcard(){
  state.flashcardOpen = false;
  document.getElementById('flashcard').classList.remove('open');
  if (state.svgZoom) {
    const svg = d3.select('#graph-svg');
    svg.call(state.svgZoom);
  }
}

document.getElementById('fc-close').onclick = () => { closeFlashcard(); if (window._clearHL) window._clearHL(); };

document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeFlashcard(); if (window._clearHL) window._clearHL(); } });

// ══════════════════════════════════════════════════════════════
// 4. SEARCH MODULE
// ══════════════════════════════════════════════════════════════
const srchI = document.getElementById('srch'), srchR = document.getElementById('search-results');

srchI.addEventListener('input', function(){
  const q = this.value.trim().toLowerCase();
  if (!q || q.length < 2) { srchR.classList.remove('show'); return; }
  const matches = state.allNodes.filter(n => (n.label || n.id).toLowerCase().includes(q) || (n.summary || '').toLowerCase().includes(q)).slice(0, 8);
  if (!matches.length) { srchR.classList.remove('show'); return; }

  srchR.innerHTML = matches.map(n => {
    const c = TC[n.concept_type] || '#8b5cf6';
    return `
      <div class="sr-item" data-id="${escapeHtml(n.id)}">
        <div class="sr-dot" style="background:${c};box-shadow:0 0 6px ${c}50"></div>
        <div class="sr-name">${escapeHtml(n.label || n.id)}</div>
        <div class="sr-meta">${escapeHtml(n.concept_type || 'concept')} · ${escapeHtml(n._d)} edges</div>
      </div>
    `;
  }).join('');

  const rect = document.getElementById('sw').getBoundingClientRect();
  srchR.style.top = (rect.bottom + 4) + 'px';
  srchR.style.left = rect.left + 'px';
  srchR.style.width = rect.width + 'px';
  srchR.classList.add('show');

  srchR.querySelectorAll('.sr-item').forEach(item => {
    item.onclick = () => {
      const node = state.nodeMap[item.dataset.id];
      if (!node) return;
      srchR.classList.remove('show');
      srchI.value = '';
      const bookId = [...node._books][0];
      showConcepts(bookId);
      setTimeout(() => {
        const gn = window._gNM && window._gNM[node.id];
        if (gn) openFC(gn);
      }, 500);
    };
  });
});

srchI.addEventListener('blur', () => { setTimeout(() => srchR.classList.remove('show'), 200); });

export { closeFlashcard, openFC, srchI, srchR };
