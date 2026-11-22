// Auto-split from ui/chat/index.html — 19-draw-horizontal-svg.js
// Feature module 20 of 22.
import { _nodeId, _nodeLabel, _nodeSummary } from './10-populate-pipeline.js';
import { selectHorizontalNode } from './18--init-graph-ripple.js';

        function drawHorizontalSVG(svgElement, anchor, prereqs, unlocks, related, cardId, metadata) {
            if (!svgElement) return;
            svgElement.innerHTML = '';

            const subNodes = (metadata && metadata.subgraph && metadata.subgraph.nodes) || [];
            const subEdges = (metadata && metadata.subgraph && metadata.subgraph.edges) || [];

            // Collect all multi-hop nodes (do not restrict to 1 earlier and 1 ahead)
            const allPrereqs = (prereqs && prereqs.length) ? prereqs : [];
            const allUnlocks = (unlocks && unlocks.length) ? unlocks : [];
            const allRelated = (related && related.length) ? related : [];

            // If prerequisites are empty (e.g. BERT with 0 immediate prereqs indexed), enrich with foundational predecessors from curriculum chain
            let effectivePrereqs = allPrereqs.slice();
            if (!effectivePrereqs.length) {
                const msgKey = cardId.replace('hgraph-', '');
                const chain = (metadata && metadata.chain) || (window._adaptiveState && window._adaptiveState[msgKey] && window._adaptiveState[msgKey].chain) || [];
                const anchorKey = _nodeId(anchor).toLowerCase();
                const filteredChain = chain.filter(c => _nodeId(c).toLowerCase() !== anchorKey);
                if (filteredChain.length) {
                    effectivePrereqs = filteredChain.map(c => ({ id: _nodeId(c), name: _nodeLabel(c), difficulty: 'foundational' }));
                } else {
                    const canonMap = {
                        'bert': ['transformer', 'attention_mechanism', 'neural_network'],
                        'transformer': ['attention_mechanism', 'neural_network', 'matrix_multiplication'],
                        'low_rank_adaptation': ['fine_tuning', 'transformer', 'linear_algebra'],
                        'retrieval_augmented_generation': ['vector_database', 'transformer', 'dense_passage_retrieval'],
                    };
                    const defaults = canonMap[anchorKey] || ['neural_network', 'machine_learning'];
                    effectivePrereqs = defaults.map(c => ({ id: c, name: c.replace(/_/g, ' ').toUpperCase(), difficulty: 'foundational' }));
                }
            }

            const totalCandidateCount = subNodes.length >= 4 
                ? subNodes.length 
                : (effectivePrereqs.length + allUnlocks.length + allRelated.length + 1);
            
            const w = Math.max(860, Math.min(1380, totalCandidateCount * 115));
            const h = 230;
            svgElement.setAttribute('viewBox', `0 0 ${w} ${h}`);
            svgElement.setAttribute('preserveAspectRatio', 'xMidYMid meet');
            svgElement.style.width = `${w}px`;
            svgElement.style.minWidth = `${w}px`;
            svgElement.style.height = '100%';

            const sid = `hsvg-${cardId}`;
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            defs.innerHTML = `
                <filter id="neon-${sid}" x="-80%" y="-80%" width="260%" height="260%">
                    <feGaussianBlur stdDeviation="3.5" result="b"/>
                    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
                <!-- Warm Gold for Target Anchor -->
                <linearGradient id="grad-target-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#fffbeb"/><stop offset="60%" stop-color="#f59e0b"/><stop offset="100%" stop-color="#d97706"/>
                </linearGradient>
                <!-- Electric Indigo / Violet for Prerequisites -->
                <linearGradient id="grad-prereq-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#e0e7ff"/><stop offset="60%" stop-color="#818cf8"/><stop offset="100%" stop-color="#6366f1"/>
                </linearGradient>
                <!-- Vibrant Emerald for Downstream Unlocks -->
                <linearGradient id="grad-unlock-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#d1fae5"/><stop offset="60%" stop-color="#10b981"/><stop offset="100%" stop-color="#059669"/>
                </linearGradient>
                <!-- Neon Rose for Related Connections -->
                <linearGradient id="grad-related-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#ffe4e6"/><stop offset="60%" stop-color="#f43f5e"/><stop offset="100%" stop-color="#be123c"/>
                </linearGradient>
                <marker id="arr-pre-${sid}" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M0,1 L10,5 L0,9 Z" fill="#818cf8"/>
                </marker>
                <marker id="arr-unl-${sid}" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M0,1 L10,5 L0,9 Z" fill="#10b981"/>
                </marker>
                <marker id="arr-rel-${sid}" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M0,1 L10,5 L0,9 Z" fill="#f43f5e"/>
                </marker>
            `;
            svgElement.appendChild(defs);

            const cx = w / 2;
            const cy = h / 2;

            const colors = {
                anchor:  { fill: `url(#grad-target-${sid})`, stroke: '#fef08a', glow: '#f59e0b', edge: '#f59e0b' },
                prereq:  { fill: `url(#grad-prereq-${sid})`, stroke: '#c7d2fe', glow: '#818cf8', edge: '#818cf8' },
                unlock:  { fill: `url(#grad-unlock-${sid})`, stroke: '#a7f3d0', glow: '#10b981', edge: '#10b981' },
                related: { fill: `url(#grad-related-${sid})`, stroke: '#fecdd3', glow: '#f43f5e', edge: 'rgba(244,63,94,0.65)' }
            };

            let nodes = [];
            let edgesToDraw = [];

            if (subNodes.length >= 4) {
                // Multi-hop subgraph layout across full topological width (closer spacing)
                const targets = subNodes.filter(n => n.role === 'target');
                const p2 = subNodes.filter(n => n.role === 'prereq' && (n.hop >= 2 || n.role === 'context'));
                const p1 = subNodes.filter(n => n.role === 'prereq' && n.hop === 1);
                const unls = subNodes.filter(n => n.role === 'unlock');
                const others = subNodes.filter(n => n.role !== 'target' && n.role !== 'prereq' && n.role !== 'unlock' && n.role !== 'context');

                // Place Targets in center
                if (targets.length === 1) {
                    nodes.push({ id: targets[0].id, label: _nodeLabel(targets[0]), summary: _nodeSummary(targets[0]), x: cx, y: cy, type: 'anchor', data: targets[0] });
                } else if (targets.length >= 2) {
                    targets.forEach((t, i) => {
                        const tx = cx + (i === 0 ? -55 : 55);
                        nodes.push({ id: t.id, label: _nodeLabel(t), summary: _nodeSummary(t), x: tx, y: cy, type: 'anchor', data: t });
                    });
                } else {
                    nodes.push({ id: _nodeId(anchor, 'anchor'), label: _nodeLabel(anchor), summary: _nodeSummary(anchor), x: cx, y: cy, type: 'anchor', data: anchor });
                }

                // Place 2-hop foundational prerequisites (comfortably inset from left)
                const p2X = Math.max(135, cx - 225);
                p2.forEach((p, i) => {
                    const y = (h / (p2.length + 1)) * (i + 1);
                    nodes.push({ id: p.id, label: _nodeLabel(p), summary: _nodeSummary(p), x: p2X, y: y, type: 'prereq', data: p });
                });

                // Place 1-hop immediate prerequisites closer to center
                const p1X = cx - 115;
                p1.forEach((p, i) => {
                    const y = (h / (p1.length + 1)) * (i + 1);
                    nodes.push({ id: p.id, label: _nodeLabel(p), summary: _nodeSummary(p), x: p1X, y: y, type: 'prereq', data: p });
                });

                // Place unlocks closer to center
                const unlX = cx + 115;
                unls.forEach((u, i) => {
                    const y = (h / (unls.length + 1)) * (i + 1);
                    nodes.push({ id: u.id, label: _nodeLabel(u), summary: _nodeSummary(u), x: unlX, y: y, type: 'unlock', data: u });
                });

                // Place others / bridge nodes
                others.forEach((o, i) => {
                    const isTop = i % 2 === 0;
                    const xOff = (i - 1) * 75;
                    nodes.push({ id: o.id, label: _nodeLabel(o), summary: _nodeSummary(o), x: cx + xOff, y: isTop ? 34 : h - 34, type: 'related', data: o });
                });

                const nodeMap = {};
                nodes.forEach(n => { nodeMap[n.id] = n; });

                subEdges.forEach(e => {
                    const u = nodeMap[e.from_id];
                    const v = nodeMap[e.to_id];
                    if (u && v && u !== v) {
                        const rel = (e.relation || 'REQUIRES').toUpperCase();
                        let edgeType = 'related';
                        if (rel === 'REQUIRES') edgeType = 'prereq';
                        else if (rel === 'UNLOCKS') edgeType = 'unlock';
                        edgesToDraw.push({ u: u, v: v, relation: rel, type: edgeType });
                    }
                });

            } else {
                // Multi-hop unconstrained topological layout (closer spacing)
                nodes.push({
                    id: _nodeId(anchor, 'anchor'),
                    label: _nodeLabel(anchor),
                    summary: _nodeSummary(anchor),
                    x: cx, y: cy, type: 'anchor', data: anchor
                });

                // Show all prerequisites, distributing across 2 columns if more than 3
                const deepPrereqs = effectivePrereqs.slice(3, 8);
                const immPrereqs = effectivePrereqs.slice(0, 3);
                const immUnlocks = allUnlocks.slice(0, 3);
                const deepUnlocks = allUnlocks.slice(3, 8);

                if (deepPrereqs.length > 0) {
                    const deepX = Math.max(135, cx - 225);
                    deepPrereqs.forEach((p, i) => {
                        const y = (h / (deepPrereqs.length + 1)) * (i + 1);
                        nodes.push({ id: _nodeId(p, 'dp' + i), label: _nodeLabel(p), summary: _nodeSummary(p), x: deepX, y: y, type: 'prereq', data: p });
                    });
                }

                immPrereqs.forEach((p, i) => {
                    const y = (h / (immPrereqs.length + 1)) * (i + 1);
                    nodes.push({ id: _nodeId(p, 'p' + i), label: _nodeLabel(p), summary: _nodeSummary(p), x: cx - 115, y: y, type: 'prereq', data: p });
                });

                immUnlocks.forEach((u, i) => {
                    const y = (h / (immUnlocks.length + 1)) * (i + 1);
                    nodes.push({ id: _nodeId(u, 'u' + i), label: _nodeLabel(u), summary: _nodeSummary(u), x: cx + 115, y: y, type: 'unlock', data: u });
                });

                if (deepUnlocks.length > 0) {
                    const deepUnlX = Math.min(w - 135, cx + 225);
                    deepUnlocks.forEach((u, i) => {
                        const y = (h / (deepUnlocks.length + 1)) * (i + 1);
                        nodes.push({ id: _nodeId(u, 'du' + i), label: _nodeLabel(u), summary: _nodeSummary(u), x: deepUnlX, y: y, type: 'unlock', data: u });
                    });
                }

                allRelated.slice(0, 4).forEach((r, i) => {
                    const isTop = i % 2 === 0;
                    const xOff = (i - 1) * 75;
                    nodes.push({
                        id: _nodeId(r, 'r' + i),
                        label: _nodeLabel(r),
                        summary: _nodeSummary(r),
                        x: cx + xOff,
                        y: isTop ? 34 : h - 34,
                        type: 'related',
                        data: r
                    });
                });

                // Connect edges from prereqs to target, and target to unlocks
                nodes.forEach(n => {
                    if (n.type === 'anchor') return;
                    if (n.type === 'prereq') {
                        edgesToDraw.push({ u: n, v: nodes[0], relation: 'REQUIRES', type: 'prereq' });
                    } else if (n.type === 'unlock') {
                        edgesToDraw.push({ u: nodes[0], v: n, relation: 'UNLOCKS', type: 'unlock' });
                    } else {
                        edgesToDraw.push({ u: nodes[0], v: n, relation: 'CONNECTS', type: 'related' });
                    }
                });
            }

            // Draw Smooth Animated Edges
            edgesToDraw.forEach(edge => {
                const u = edge.u;
                const v = edge.v;
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                const midX = (u.x + v.x) / 2;
                const midY = (u.y + v.y) / 2;
                const d = `M ${u.x} ${u.y} Q ${midX} ${midY} ${v.x} ${v.y}`;
                const marker = edge.type === 'prereq' ? `url(#arr-pre-${sid})` : (edge.type === 'unlock' ? `url(#arr-unl-${sid})` : `url(#arr-rel-${sid})`);
                path.setAttribute('d', d);
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke', colors[edge.type].edge);
                path.setAttribute('stroke-width', edge.type === 'related' ? '1.5' : '2.2');
                path.setAttribute('filter', `url(#neon-${sid})`);
                if (marker) path.setAttribute('marker-end', marker);
                path.setAttribute('class', `graph-edge-${edge.type}`);
                svgElement.appendChild(path);
            });

            // Draw Clean Glowing Nodes
            nodes.forEach(n => {
                const c = colors[n.type];
                const r = n.type === 'anchor' ? 16 : 11;
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                g.setAttribute('class', 'graph-node-group');
                g.setAttribute('data-node-id', n.id);
                g.setAttribute('data-node-label', n.label);
                g.setAttribute('data-node-type', n.type);
                g.style.color = c.stroke;
                g.style.cursor = 'pointer';

                g.addEventListener('click', (ev) => {
                    ev.stopPropagation();
                    selectHorizontalNode(cardId, n.id, n.data, anchor, prereqs, unlocks, related);
                });

                // Pulse ring ONLY for anchor node
                if (n.type === 'anchor') {
                    const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    pulse.setAttribute('cx', n.x);
                    pulse.setAttribute('cy', n.y);
                    pulse.setAttribute('r', r + 6);
                    pulse.setAttribute('stroke', c.glow);
                    pulse.setAttribute('stroke-width', '2');
                    pulse.setAttribute('filter', `url(#neon-${sid})`);
                    pulse.setAttribute('class', 'graph-pulse-ring');
                    pulse.setAttribute('fill', 'none');
                    g.appendChild(pulse);
                }

                // Core glowing circle
                const core = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                core.setAttribute('class', 'graph-node-core');
                core.setAttribute('cx', n.x);
                core.setAttribute('cy', n.y);
                core.setAttribute('r', r);
                core.setAttribute('fill', c.fill);
                core.setAttribute('stroke', c.stroke);
                core.setAttribute('stroke-width', '2');
                core.setAttribute('filter', `url(#neon-${sid})`);
                g.appendChild(core);

                // Monospace white text label
                const shortLabel = (n.label || n.id || '').length > 26 ? (n.label || n.id).slice(0, 25) + '…' : (n.label || n.id || '');
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', n.x);
                text.setAttribute('y', n.y + r + 15);
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('fill', '#ffffff');
                text.setAttribute('font-size', '11px');
                text.setAttribute('font-weight', '600');
                text.setAttribute('font-family', "'JetBrains Mono', monospace");
                text.textContent = shortLabel;
                g.appendChild(text);

                // Type badge below text
                const badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                badge.setAttribute('class', 'graph-node-badge');
                badge.setAttribute('x', n.x);
                badge.setAttribute('y', n.y + r + 28);
                badge.setAttribute('text-anchor', 'middle');
                badge.setAttribute('fill', c.stroke);
                badge.setAttribute('font-size', '10px');
                badge.setAttribute('font-weight', '700');
                badge.setAttribute('font-family', "'Brigend', sans-serif");
                badge.textContent = n.type === 'anchor' ? '🎯 TARGET' : n.type === 'prereq' ? '↑ REQUIRES' : n.type === 'unlock' ? '↓ UNLOCKS' : '◈ CONNECTS';
                g.appendChild(badge);

                svgElement.appendChild(g);
            });

            // Synchronize OKF Key Relationship badges with ALL nodes displayed in the in-chat graph
            const reqDiv = document.getElementById(`okf-card-req-${cardId}`);
            const unlDiv = document.getElementById(`okf-card-unl-${cardId}`);
            const conDiv = document.getElementById(`okf-card-con-${cardId}`);

            const syncGraphBadges = (container, nodeList, colorCls) => {
                if (!container) return;
                container.innerHTML = '';
                if (!nodeList.length) {
                    const empty = document.createElement('span');
                    empty.className = 'text-[10px] text-gray-500 italic';
                    empty.textContent = 'None indexed';
                    container.appendChild(empty);
                    return;
                }
                const seen = new Set();
                nodeList.forEach(n => {
                    const label = n.label || _nodeLabel(n.data || n);
                    if (!label || seen.has(label.toLowerCase())) return;
                    seen.add(label.toLowerCase());
                    const span = document.createElement('span');
                    span.className = `px-2 py-1 rounded-lg border cursor-pointer hover:scale-105 transition-all text-[10px] font-bold ${colorCls}`;
                    span.textContent = label;
                    span.title = n.summary || _nodeSummary(n.data || n) || label;
                    span.onclick = () => selectHorizontalNode(cardId, n.id, n.data || n, anchor, effectivePrereqs, allUnlocks, allRelated);
                    container.appendChild(span);
                });
            };

            const graphPrereqs = nodes.filter(n => n.type === 'prereq');
            const graphUnlocks = nodes.filter(n => n.type === 'unlock');
            const graphRelated = nodes.filter(n => n.type === 'related');

            syncGraphBadges(reqDiv, graphPrereqs, 'text-accentPurple border-accentPurple/40 bg-accentPurple/15 hover:bg-accentPurple/25');
            syncGraphBadges(unlDiv, graphUnlocks, 'text-emerald-300 border-emerald-400/40 bg-emerald-400/15 hover:bg-emerald-400/25');
            syncGraphBadges(conDiv, graphRelated, 'text-cyan-300 border-cyan-400/40 bg-cyan-400/15 hover:bg-cyan-400/25');

            // Auto-scroll container so that the Target Node is centered in view immediately
            setTimeout(() => {
                const canvasContainer = document.getElementById(`hgraph-canvas-${cardId}`) || svgElement.parentElement;
                if (canvasContainer) {
                    const anchorNode = nodes.find(n => n.type === 'anchor') || nodes[0];
                    if (anchorNode) {
                        canvasContainer.scrollLeft = Math.max(0, anchorNode.x - (canvasContainer.clientWidth / 2));
                    }
                }
            }, 60);
        }

export { drawHorizontalSVG };
