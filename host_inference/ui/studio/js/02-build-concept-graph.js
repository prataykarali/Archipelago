// Auto-split from ui/chat/index.html — 02-build-concept-graph.js
// Feature module 3 of 6.
import { state } from './00-state.js';
import { EC, EO, EW, bk, nC, nR, rid } from './00-escape-html.js';
import { showConcepts } from './01-books-module.js';
import { closeFlashcard, openFC } from './03-open-fc.js';

function buildConceptGraph(nodes, edges, nm, bookId){
  const svg = d3.select('#graph-svg');
  const wrap = document.getElementById('graph-wrap');
  let W = wrap.clientWidth, H = wrap.clientHeight;
  const root = svg.append('g').attr('class', 'root');
  const isLarge = nodes.length > 180;

  state.svgZoom = d3.zoom().scaleExtent([.03, 8]).on('zoom', ev => {
    if (!state.flashcardOpen) root.attr('transform', ev.transform);
  });
  svg.call(state.svgZoom).on('dblclick.zoom', null);
  svg.classed('locked', false);

  const resetV = () => svg.transition().duration(600).call(state.svgZoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(bookId ? .55 : .26));
  document.getElementById('z-in').onclick = () => { if (!state.flashcardOpen) svg.transition().duration(300).call(state.svgZoom.scaleBy, 1.4); };
  document.getElementById('z-out').onclick = () => { if (!state.flashcardOpen) svg.transition().duration(300).call(state.svgZoom.scaleBy, 1 / 1.4); };
  document.getElementById('z-reset').onclick = resetV;

  // ── UNTANGLED SIMULATION PHYSICS (NO CENTRAL HAIRBALL) ──
  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      const s = typeof d.source === 'object' ? d.source : nm[d.source];
      const t = typeof d.target === 'object' ? d.target : nm[d.target];
      const sDeg = s?._d || 0, tDeg = t?._d || 0;
      return isLarge ? (110 + sDeg * 1.8 + tDeg * 1.8) : (135 + sDeg * 2.2 + tDeg * 2.2);
    }).strength(isLarge ? 0.22 : 0.35))
    .force('charge', d3.forceManyBody().strength(d => {
      const deg = d._d || 0;
      return isLarge ? (-280 - deg * 8) : (-360 - deg * 12);
    }))
    .force('center', d3.forceCenter(0, 0).strength(0.02)) // Center force lowered to 0.06!
    .force('collide', d3.forceCollide().radius(d => nR(d) + (isLarge ? 18 : 26)).strength(0.75))
    .alphaDecay(isLarge ? 0.035 : 0.02);

  if (!bookId && nodes.length > 50) {
    const bkIds = [...new Set(nodes.map(n => n._book))];
    const ctrs = {};
    bkIds.forEach((b, i) => {
      const a = (2 * Math.PI * i) / bkIds.length;
      const r = Math.min(W, H) * .7;
      ctrs[b] = { x: Math.cos(a) * r, y: Math.sin(a) * r };
    });
    sim.force('cluster', al => {
      nodes.forEach(n => {
        const c = ctrs[n._book];
        if (c) {
          n.vx += (c.x - n.x) * al * 0.04;
          n.vy += (c.y - n.y) * al * 0.04;
        }
      });
    });
  }

  state.simulation = sim;
  let st = setTimeout(() => sim.stop(), isLarge ? 5000 : 7000);
  function wake(){ sim.alpha(.25).restart(); clearTimeout(st); st = setTimeout(() => sim.stop(), 5000); }

  // Curvature calculation
  function linkArc(d) {
    const sx = d.source.x, sy = d.source.y;
    const tx = d.target.x, ty = d.target.y;
    const dx = tx - sx, dy = ty - sy;
    const midX = (sx + tx) / 2 - dy * 0.12;
    const midY = (sy + ty) / 2 + dx * 0.12;
    return `M${sx},${sy} Q${midX},${midY} ${tx},${ty}`;
  }

  const defs = svg.selectAll('defs.graph-defs').data([1]).join('defs').attr('class', 'graph-defs');
  Object.keys(EC).forEach(rel => {
    defs.selectAll(`#arrow-${rel}`).data([rel]).join('marker')
      .attr('id', `arrow-${rel}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 5.5)
      .attr('markerHeight', 5.5)
      .attr('orient', 'auto')
      .selectAll('path').data([rel]).join('path')
      .attr('d', 'M0,-4L8,0L0,4Z')
      .attr('fill', EC[rel])
      .attr('opacity', 0.85);
  });

  const eG = root.append('g');
  const eS = eG.selectAll('.edge-path').data(edges).join('path')
    .attr('class', d => `edge-path e-${d.relation}${d._external ? ' external' : ''}`)
    .attr('fill', 'none')
    .attr('stroke', d => EC[d.relation] || '#8b5cf6')
    .attr('stroke-width', d => d._external ? (EW[d.relation] || 1.2) * .7 : (EW[d.relation] || 1.8))
    .attr('stroke-opacity', d => d._external ? (EO[d.relation] || .4) * .5 : (EO[d.relation] || .85))
    .attr('marker-end', d => `url(#arrow-${d.relation || 'uses'})`);
  state.eSel = eS;
  eS.classed('hidden-edge', true);

  // Nodes
  const nG = root.append('g');
  const nS = nG.selectAll('.node-g').data(nodes).join('g')
    .attr('class', d => d._ghost ? 'node-g ghost' : 'node-g')
    .classed('highlighted-gold', d => window._highlightIds && window._highlightIds.includes(d.id))
    .call(d3.drag()
      .on('start', (e, d) => { wake(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => { d.fx = null; d.fy = null; }));
  state.nSel = nS;

  nS.append('circle').attr('class', d => d._d >= 15 ? 'node-glow hub-glow' : 'node-glow')
    .attr('r', d => nR(d) * (d._d >= 15 ? 2.2 : 1.6))
    .attr('fill', d => nC(d))
    .attr('opacity', d => d._d >= 30 ? .16 : d._d >= 15 ? .12 : .06);

  nS.append('circle').attr('class', 'node-ring')
    .attr('r', d => nR(d) + 8)
    .attr('stroke', d => nC(d));

  nS.append('circle').attr('class', 'node-core')
    .attr('r', d => nR(d))
    .attr('fill', d => nC(d));

  const lt = isLarge ? 5 : 2;
  nS.filter(d => d._d >= lt || d._ghost).append('text').attr('class', 'node-label')
    .attr('dy', d => nR(d) + 12)
    .attr('text-anchor', 'middle')
    .text(d => {
      const n = d.label || d.id;
      return n.length > 22 ? n.slice(0, 21) + '…' : n;
    });

  nS.filter(d => d._ghost).append('text').attr('class', 'ghost-book-tag')
    .attr('dy', d => nR(d) + 22)
    .attr('text-anchor', 'middle')
    .text(d => bk(d._book).name);

  // Tooltip & interactions
  const tip = document.getElementById('tip');
  nS.on('mousemove', (e, d) => {
    tip.style.left = (e.clientX + 18) + 'px';
    tip.style.top = (e.clientY - 12) + 'px';
    document.getElementById('tip-name').textContent = d.label || d.id;
    const gt = d._ghost ? ` · from ${bk(d._book).name}` : '';
    document.getElementById('tip-type').textContent = `${d.concept_type || 'concept'} · ${d.difficulty || 'level'} · ${d._d} connections${gt}`;
    document.getElementById('tip-summ').textContent = d._ghost ? `Click to explore in ${bk(d._book).name}` : (d.summary || 'Click to view OKF details');
    tip.classList.add('v');
  })
  .on('mouseenter', () => {})
  .on('mouseleave', () => {
    tip.classList.remove('v');
  })
  .on('click', (e, d) => {
    e.stopPropagation();
    if (d._ghost) {
      showConcepts(d._book);
      setTimeout(() => {
        const g = window._gNM && window._gNM[d.id];
        if (g) openFC(g);
      }, 500);
    } else {
      openFC(d);
    }
  });

  svg.on('click', () => {
    closeFlashcard();
    clearHL();
  });

  sim.on('tick', () => {
    eS.attr('d', linkArc);
    nS.attr('transform', d => `translate(${d.x},${d.y})`);
  });

  setTimeout(() => { W = wrap.clientWidth; H = wrap.clientHeight; resetV(); }, 120);
  addEventListener('resize', () => { W = wrap.clientWidth; H = wrap.clientHeight; });

  // Gold highlighting for newly ingested concepts
  if (window._highlightIds && window._highlightIds.length > 0) {
    setTimeout(() => {
      if (state.simulation !== sim) return;
      const curW = wrap.clientWidth, curH = wrap.clientHeight;
      const highlightedNodes = nodes.filter(d => window._highlightIds.includes(d.id));
      if (highlightedNodes.length > 0) {
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        highlightedNodes.forEach(d => {
          const r = nR(d) + 40;
          if (d.x - r < minX) minX = d.x - r;
          if (d.x + r > maxX) maxX = d.x + r;
          if (d.y - r < minY) minY = d.y - r;
          if (d.y + r > maxY) maxY = d.y + r;
        });

        const dx = maxX - minX, dy = maxY - minY;
        const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
        const boxW = dx > 0 ? dx : 120, boxH = dy > 0 ? dy : 120;

        let scale = Math.min((curW - 200) / boxW, (curH - 200) / boxH);
        scale = Math.min(Math.max(scale, 0.15), 2.0);

        const tx = curW / 2 - scale * cx, ty = curH / 2 - scale * cy;
        const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);
        svg.transition().duration(1200).call(state.svgZoom.transform, transform);
      }
    }, 800);
  }

  // Chips filtering
  document.querySelectorAll('.chip').forEach(ch => {
    ch.onclick = () => {
      const r = ch.dataset.r;
      document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
      ch.classList.add('on');
      eS.style('display', r === 'all' ? null : l => l.relation === r ? null : 'none');
    };
  });
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
  document.querySelector('.chip[data-r=all]').classList.add('on');

  function hlNode(id){
    const conn = new Set([id]);
    edges.forEach(l => {
      const s = rid(l.source), t = rid(l.target);
      if (s === id || t === id) { conn.add(s); conn.add(t); }
    });
    nS.classed('dim', nd => !conn.has(nd.id)).classed('sel', nd => nd.id === id);
    eS.classed('hidden-edge', l => !(rid(l.source) === id || rid(l.target) === id))
      .classed('dim', l => !(rid(l.source) === id || rid(l.target) === id))
      .classed('hl', l => rid(l.source) === id || rid(l.target) === id)
      .classed('active-flow', l => rid(l.source) === id || rid(l.target) === id);
  }

  function clearHL(){
    if (state.nSel) state.nSel.classed('dim', false).classed('sel', false);
    if (state.eSel) state.eSel.classed('hidden-edge', true).classed('dim', false).classed('hl', false).classed('active-flow', false);
  }

  window._hlNode = hlNode;
  window._clearHL = clearHL;
  window._gNM = nm;
  window._gEdges = edges;

  document.getElementById('st-n').textContent = nodes.length;
  document.getElementById('st-e').textContent = edges.length;
  document.getElementById('st-view').textContent = bookId ? bk(bookId).name : 'All Concepts';
  document.getElementById('srch').placeholder = `Search ${nodes.length} concepts…`;
}

export { buildConceptGraph };
