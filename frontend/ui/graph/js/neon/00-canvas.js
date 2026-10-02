// Auto-split from ui/chat/index.html — 00-canvas.js
// Feature module 1 of 2.
import { state } from './00-state.js';
import { findNodeAt, getMousePos, openPanel } from './01-get-mouse-pos.js';

/* ══ CANVAS CONFIG ═════════════════════════════════ */
const canvas = document.getElementById('g_canvas');

const ctx = canvas.getContext('2d');

canvas.width = state.width;

canvas.height = state.height;

window.addEventListener('resize', () => {
  state.width = window.innerWidth;
  state.height = window.innerHeight;
  canvas.width = state.width;
  canvas.height = state.height;
});

// Viewport Zoom & Transform state
const transform = { x: state.width/2, y: state.height/2, k: 0.38 };

/* ── Load image textures ───────────────────────── */
const textures = {
  method: new Image(),
  technique: new Image(),
  definition: new Image(),
  metric: new Image(),
  result: new Image()
};

textures.method.src = '/node_method.png';

textures.technique.src = '/node_technique.png';

textures.definition.src = '/node_definition.png';

textures.metric.src = '/node_metric.png';

textures.result.src = '/node_result.png';

const totalTextures = Object.keys(textures).length;

function checkTextures() {
  state.texturesLoaded++;
  if (state.texturesLoaded === totalTextures) {
    document.getElementById('loader').classList.add('gone');
    setTimeout(() => document.getElementById('loader').style.display = 'none', 500);
  }
}

Object.values(textures).forEach(img => {
  img.onload = checkTextures;
  img.onerror = checkTextures; // fallback if image fails to load
});

const CLRS = {
  requires: '#b55fe6',       // Electric Violet
  enables: '#10b981',        // Vibrant Emerald
  uses: '#0ea5e9',           // Cyan Sky Blue
  extends: '#f97316',        // Neon Orange
  part_of: '#ec4899',        // Hot Pink
  contrasts_with: '#ef4444',  // Bright Red
  evaluated_by: '#eab308'    // Neon Yellow
};

const TCLRS = {
  method: '#a78bfa',
  technique: '#0ea5e9',
  definition: '#c4b5fd',
  theory: '#f97316',
  metric: '#f59e0b',
  result: '#ef4444',
  dataset: '#818cf8',
  tool: '#10b981'
};

function spawnParticles() {
  if (state.edgesG.length === 0) return;
  // Spawn a particle on a random edge occasionally
  if (Math.random() < 0.28) {
    const edge = state.edgesG[Math.floor(Math.random() * state.edgesG.length)];
    if (edge.source.x !== undefined && edge.target.x !== undefined) {
      state.linkParticles.push({
        edge: edge,
        progress: 0,
        speed: 0.007 + Math.random() * 0.012,
        color: CLRS[edge.relation] || '#ffffff',
        size: 2.2 + Math.random() * 2
      });
    }
  }
}

/* ── Fetch Live API data ───────────────────────── */
fetch('/api/graph')
  .then(r => r.json())
  .then(data => {
    initGraph(data);
  });

function initGraph(data) {
  const rawNodes = data.nodes;
  const rawEdges = data.edges;

  // Degrees
  const deg = {};
  rawEdges.forEach(e => {
    deg[e.source] = (deg[e.source] || 0) + 1;
    deg[e.target] = (deg[e.target] || 0) + 1;
  });
  rawNodes.forEach(n => { n._d = deg[n.id] || 0; });

  const nm = {};
  rawNodes.forEach(n => nm[n.id] = n);
  state.nmG = nm;

  // Layout stats
  const linked = new Set();
  rawEdges.forEach(e => { linked.add(e.source); linked.add(e.target); });
  const iso = rawNodes.filter(n => !linked.has(n.id)).length;
  document.getElementById('stn').textContent = rawNodes.length;
  document.getElementById('ste').textContent = rawEdges.length;
  document.getElementById('sti').textContent = iso;

  // D3 force simulation setup
  const sim = d3.forceSimulation(rawNodes)
    .force('link', d3.forceLink(rawEdges).id(d => d.id)
      .distance(d => {
        const s = nm[d.source.id || d.source];
        const t = nm[d.target.id || d.target];
        return 120 + (s?._d || 0) * 2.2 + (t?._d || 0) * 2.2;
      }).strength(0.35))
    .force('charge', d3.forceManyBody().strength(d => -220 - (d._d || 0) * 18))
    .force('center', d3.forceCenter(0, 0))
    .force('collide', d3.forceCollide().radius(d => {
      const g = d._d || 0;
      return (g >= 30 ? 28 : g >= 15 ? 20 : g >= 8 ? 14 : 10) + 18;
    }).strength(0.85))
    .alphaDecay(0.015);

  state.nodesG = rawNodes;
  state.edgesG = rawEdges;

  // Transform to fit content initially
  setTimeout(() => {
    transform.x = state.width / 2;
    transform.y = state.height / 2;
    transform.k = 0.38;
  }, 100);

  // Render Loop
  requestAnimationFrame(loop);
}

function loop() {
  update();
  draw();
  requestAnimationFrame(loop);
}

function update() {
  // Update particles
  spawnParticles();
  for (let i = state.linkParticles.length - 1; i >= 0; i--) {
    const p = state.linkParticles[i];
    p.progress += p.speed;
    if (p.progress >= 1) {
      state.linkParticles.splice(i, 1);
    }
  }
}

function draw() {
  ctx.clearRect(0, 0, state.width, state.height);

  // Background Nebula gas/dust overlay
  ctx.save();
  ctx.fillStyle = 'rgba(5, 5, 12, 0.98)';
  ctx.fillRect(0, 0, state.width, state.height);
  ctx.restore();

  // Apply camera translation & scale
  ctx.save();
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  // Enable Screen Composite for additive neon glowing layers!
  ctx.globalCompositeOperation = 'screen';

  // 1. Draw Edges
  state.edgesG.forEach(edge => {
    const s = edge.source;
    const t = edge.target;
    if (s.x === undefined || t.x === undefined) return;

    let isDim = state.activeNode && (rid(s) !== state.activeNode.id && rid(t) !== state.activeNode.id);
    let isHigh = state.activeNode && (rid(s) === state.activeNode.id || rid(t) === state.activeNode.id);

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);

    const clr = CLRS[edge.relation] || '#ffffff';
    ctx.strokeStyle = clr;
    ctx.lineWidth = isHigh ? 3.5 : (isDim ? 0.3 : 1.6);
    ctx.globalAlpha = isHigh ? 0.95 : (isDim ? 0.06 : 0.55);

    // Dynamic laser blur/glow on connections
    ctx.shadowBlur = isHigh ? 12 : (isDim ? 0 : 5);
    ctx.shadowColor = clr;

    ctx.stroke();
    ctx.restore();
  });

  // 2. Draw Edge Flow Particles
  state.linkParticles.forEach(p => {
    const s = p.edge.source;
    const t = p.edge.target;
    if (s.x === undefined || t.x === undefined) return;

    let isDim = state.activeNode && (rid(s) !== state.activeNode.id && rid(t) !== state.activeNode.id);
    if (isDim) return; // don't draw particles on dimmed lines

    // Interpolate position along link path
    const px = s.x + (t.x - s.x) * p.progress;
    const py = s.y + (t.y - s.y) * p.progress;

    ctx.save();
    ctx.beginPath();
    ctx.arc(px, py, p.size, 0, Math.PI * 2);
    ctx.fillStyle = p.color;
    ctx.shadowBlur = 10;
    ctx.shadowColor = p.color;
    ctx.fill();
    ctx.restore();
  });

  // 3. Draw Nodes (glowing cyber spheres)
  state.nodesG.forEach(node => {
    if (node.x === undefined) return;

    let isDim = state.activeNode && (node.id !== state.activeNode.id && !isNeighbor(node.id, state.activeNode.id));
    let isSel = state.activeNode && (node.id === state.activeNode.id);

    const deg = node._d || 0;
    const baseR = deg >= 30 ? 24 : deg >= 15 ? 18 : deg >= 8 ? 13 : 9;
    const r = isSel ? baseR * 1.25 : (state.hoverNode && node.id === state.hoverNode.id ? baseR * 1.15 : baseR);

    ctx.save();
    ctx.globalAlpha = isDim ? 0.08 : 1.0;

    // Pick texture matching concept_type
    const type = node.concept_type || 'definition';
    const tex = textures[type] || textures.definition;

    // Draw cyber orb texture
    if (tex && tex.complete && tex.naturalWidth !== 0) {
      // Glow shadow behind node
      ctx.shadowBlur = isSel ? 24 : (state.hoverNode && node.id === state.hoverNode.id ? 18 : 12);
      ctx.shadowColor = TCLRS[type] || '#ffffff';
      ctx.drawImage(tex, node.x - r, node.y - r, r * 2, r * 2);
    } else {
      // Fallback: procedural glowing neon circles
      const grad = ctx.createRadialGradient(node.x, node.y, 1, node.x, node.y, r);
      const clr = TCLRS[type] || '#ffffff';
      grad.addColorStop(0, '#ffffff');
      grad.addColorStop(0.3, clr);
      grad.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Interactive selected Ring overlay
    if (isSel) {
      ctx.strokeStyle = TCLRS[type] || '#a78bfa';
      ctx.lineWidth = 2.5;
      ctx.shadowBlur = 10;
      ctx.shadowColor = ctx.strokeStyle;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 6, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Node Labels
    if (deg >= 3 || isSel || (state.hoverNode && node.id === state.hoverNode.id)) {
      ctx.font = `500 ${isSel ? '12px' : '10px'} 'Inter', sans-serif`;
      ctx.fillStyle = isSel ? '#ffffff' : 'rgba(235, 235, 255, 0.9)';
      ctx.textAlign = 'center';
      ctx.shadowBlur = isSel ? 4 : 0;
      ctx.shadowColor = '#ffffff';

      // Text background outline for readability
      ctx.strokeStyle = 'rgba(5, 5, 12, 0.95)';
      ctx.lineWidth = 4;
      const label = node.label || node.id;
      const shortLabel = label.length > 22 ? label.slice(0, 20) + '…' : label;
      ctx.strokeText(shortLabel, node.x, node.y + r + 14);
      ctx.fillText(shortLabel, node.x, node.y + r + 14);
    }

    ctx.restore();
  });

  ctx.restore(); // restore viewport transform
}

function isNeighbor(id1, id2) {
  return state.edgesG.some(e => {
    const s = rid(e.source);
    const t = rid(e.target);
    return (s === id1 && t === id2) || (s === id2 && t === id1);
  });
}

/* ── VIEWPORT NAVIGATION ────────────────────────── */
// Mouse Drag dragging viewport
canvas.addEventListener('mousedown', ev => {
  const m = getMousePos(ev);
  const found = findNodeAt(m.x, m.y);
  if (found) {
    state.activeNode = found;
    openPanel(found);
    return;
  }
  state.isDragging = true;
  state.dragStart = { x: ev.clientX - transform.x, y: ev.clientY - transform.y };
});

canvas.addEventListener('mousemove', ev => {
  const m = getMousePos(ev);
  state.hoverNode = findNodeAt(m.x, m.y);

  if (state.isDragging) {
    transform.x = ev.clientX - state.dragStart.x;
    transform.y = ev.clientY - state.dragStart.y;
  }
});

canvas.addEventListener('mouseup', () => { state.isDragging = false; });

canvas.addEventListener('mouseleave', () => { state.isDragging = false; });

// Wheel Zoom
canvas.addEventListener('wheel', ev => {
  ev.preventDefault();
  const zoomFactor = 1.08;
  const m = getMousePos(ev);

  const prevK = transform.k;
  if (ev.deltaY < 0) {
    transform.k = Math.min(9, transform.k * zoomFactor);
  } else {
    transform.k = Math.max(0.02, transform.k / zoomFactor);
  }

  // Zoom centered on cursor position!
  transform.x = ev.clientX - (ev.clientX - transform.x) * (transform.k / prevK);
  transform.y = ev.clientY - (ev.clientY - transform.y) * (transform.k / prevK);
});

export { CLRS, TCLRS, canvas, checkTextures, ctx, draw, initGraph, isNeighbor, loop, spawnParticles, textures, totalTextures, transform, update };
