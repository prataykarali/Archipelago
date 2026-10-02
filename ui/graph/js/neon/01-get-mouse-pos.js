// Auto-split from ui/chat/index.html — 01-get-mouse-pos.js
// Feature module 2 of 2.
import { state } from './00-state.js';
import { TCLRS, canvas, transform } from './00-canvas.js';

// Zoom triggers
document.getElementById('zi').onclick = () => {
  const prevK = transform.k;
  transform.k = Math.min(9, transform.k * 1.35);
  transform.x = state.width/2 - (state.width/2 - transform.x) * (transform.k / prevK);
  transform.y = state.height/2 - (state.height/2 - transform.y) * (transform.k / prevK);
};

document.getElementById('zo').onclick = () => {
  const prevK = transform.k;
  transform.k = Math.max(0.02, transform.k / 1.35);
  transform.x = state.width/2 - (state.width/2 - transform.x) * (transform.k / prevK);
  transform.y = state.height/2 - (state.height/2 - transform.y) * (transform.k / prevK);
};

document.getElementById('zr').onclick = () => {
  transform.x = state.width / 2;
  transform.y = state.height / 2;
  transform.k = 0.38;
};

// Utilities for mouse coordinates
function getMousePos(ev) {
  const rect = canvas.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;
  // Convert screen coordinates to simulation space coords based on transform k, x, y
  return {
    x: (mx - transform.x) / transform.k,
    y: (my - transform.y) / transform.k
  };
}

function findNodeAt(x, y) {
  return state.nodesG.find(n => {
    if (n.x === undefined) return false;
    const deg = n._d || 0;
    const baseR = deg >= 30 ? 24 : deg >= 15 ? 18 : deg >= 8 ? 13 : 9;
    const distSq = (n.x - x) * (n.x - x) + (n.y - y) * (n.y - y);
    return distSq < (baseR + 8) * (baseR + 8);
  });
}

/* ── SEARCH ──────────────────────────────────────── */
document.getElementById('srch').addEventListener('input', function() {
  const q = this.value.trim().toLowerCase();
  if (!q) { state.activeNode = null; return; }
  const matched = state.nodesG.find(n => (n.label||n.id).toLowerCase().includes(q));
  if (matched) {
    state.activeNode = matched;
    openPanel(matched);
    // Smooth camera pan to matching node
    transform.x = state.width/2 - matched.x * transform.k;
    transform.y = state.height/2 - matched.y * transform.k;
  }
});

/* ── OVERLAY FLASHCARD ────────────────────────────── */
const panel = document.getElementById('rpanel');

function mkList(listId, secId, cntId, items, clr, icon) {
  const sec = document.getElementById(secId);
  const ul = document.getElementById(listId);
  if (cntId) document.getElementById(cntId).textContent = items.length;
  ul.innerHTML = '';
  if (!items.length) { sec.style.display = 'none'; return; }
  items.slice(0, 8).forEach(({node, dir, rel}) => {
    if (!node) return;
    const li = document.createElement('li');
    li.className = 'ei';
    li.innerHTML = `<span class="earr" style="color:${clr}">${icon}</span>` +
      `<span class="ename">${node.label || node.id}</span>` +
      `<span class="erel" style="color:${clr}">${dir === 'out' ? '→' : '←'}${rel}</span>`;
    li.onclick = ev => {
      ev.stopPropagation();
      openPanel(node);
      // center camera
      transform.x = state.width/2 - node.x * transform.k;
      transform.y = state.height/2 - node.y * transform.k;
    };
    ul.appendChild(li);
  });
  sec.style.display = '';
}

function openPanel(d) {
  state.activeNode = d;
  const glowColor = TCLRS[d.concept_type] || '#a78bfa';

  panel.style.borderColor = `${glowColor}40`;
  panel.style.boxShadow = `0 30px 70px rgba(0, 0, 0, 0.7), 0 0 35px ${glowColor}25`;

  const ind = document.getElementById('card-indicator');
  ind.style.backgroundColor = glowColor;
  ind.style.boxShadow = `0 0 8px ${glowColor}`;

  const br = document.getElementById('ptype-row');
  br.innerHTML = `<div class="badge bd-${d.difficulty || 'intermediate'}">${d.difficulty || '?'}</div>` +
    `<div class="badge bd-type" style="background:${glowColor}15;color:${glowColor};border:1px solid ${glowColor}30">${d.concept_type || '?'}</div>`;

  document.getElementById('pname').textContent = d.label || d.id;
  document.getElementById('psumm').textContent = d.summary || 'No summary extracted by pipeline.';
  document.getElementById('ptype').textContent = d.concept_type || '—';
  document.getElementById('pdiff').textContent = d.difficulty || '—';
  document.getElementById('pdeg').textContent = (d._d || d.degree || 0) + ' edges';
  document.getElementById('psrcc').textContent = (d.source_count || d.sources?.length || 0) + ' papers';

  // Prerequisites & Unlocks
  const prereqs = d.prerequisites || [];
  const unlocks = d.unlocks || [];
  const prereqEl = document.getElementById('prereq-pills');
  const unlockEl = document.getElementById('unlock-pills');
  prereqEl.innerHTML = prereqs.length
    ? prereqs.map(p => `<span class="okf-pill prereq" data-name="${p}">↑ ${p}</span>`).join('')
    : '<span class="okf-empty">none</span>';
  unlockEl.innerHTML = unlocks.length
    ? unlocks.map(u => `<span class="okf-pill unlock" data-name="${u}">↓ ${u}</span>`).join('')
    : '<span class="okf-empty">none</span>';

  document.querySelectorAll('.okf-pill').forEach(pill => {
    pill.onclick = () => {
      const name = pill.dataset.name.toLowerCase();
      const found = Object.values(state.nmG).find(n => (n.label || n.id).toLowerCase() === name || (n.label || n.id).toLowerCase().includes(name));
      if (found) {
        openPanel(found);
        transform.x = state.width/2 - found.x * transform.k;
        transform.y = state.height/2 - found.y * transform.k;
      }
    };
  });

  const tags = d.tags || [];
  if (tags.length) {
    document.getElementById('ptags').innerHTML = tags.map(t => `<span class="tag">${t}</span>`).join('');
    document.getElementById('tags-sec').style.display = '';
  } else {
    document.getElementById('tags-sec').style.display = 'none';
  }

  // Relations
  const cats = {requires:[], enables:[], uses:[], extends:[], part_of:[], contrasts_with:[], evaluated_by:[]};
  state.edgesG.forEach(l => {
    const s = rid(l.source);
    const t = rid(l.target);
    const r = l.relation;
    if (cats[r] === undefined) return;
    if (s === d.id) { const n = state.nmG[t]; if (n) cats[r].push({node: n, dir: 'out', rel: r}); }
    if (t === d.id) { const n = state.nmG[s]; if (n) cats[r].push({node: n, dir: 'in', rel: r}); }
  });

  mkList('plr','psr','rcnt',cats.requires,'#a78bfa','↑');
  mkList('ple','pse','ecnt',cats.enables, '#10b981','↓');
  mkList('plu','psu','ucnt',cats.uses,    '#0ea5e9','◈');
  mkList('plx','psx','xcnt',cats.extends, '#f97316','⤳');
  mkList('plp','psp','pcnt',cats.part_of, '#d946ef','⊂');
  mkList('plc','psc','ccnt',cats.contrasts_with,'#ef4444','≠');
  mkList('plv','psv','vcnt',cats.evaluated_by,  '#f59e0b','📊');

  // Sources
  const srcs = d.sources || [];
  if (srcs.length) {
    document.getElementById('psrc').innerHTML = srcs.map(s =>
      `<div><span class="doc">${(s.doc_id||'').split('/').pop()}</span> · ${s.chunk_id||''} · p${s.page_number||'?'}<br>
      <span style="color:#4e4e75;font-size:8.5px">${s.section_title||''}</span></div>`).join('');
    document.getElementById('src-sec').style.display = '';
  } else {
    document.getElementById('src-sec').style.display = 'none';
  }

  panel.classList.add('open');
  document.getElementById('gw').classList.add('rp');
}

function closePanel() {
  state.activeNode = null;
  panel.classList.remove('open');
  document.getElementById('gw').classList.remove('rp');
}

document.getElementById('rcls').onclick = () => { closePanel(); };

export { closePanel, findNodeAt, getMousePos, mkList, openPanel, panel };
