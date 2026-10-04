// Auto-split from ui/chat/index.html — 17-draw-personalized-svg.js
// Feature module 18 of 22.
import { _nodeLabel, _nodeSummary } from './10-populate-pipeline.js';
import { selectHorizontalNode } from './18--init-graph-ripple.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';

        function drawPersonalizedSVG(svgElement, nodes, edges, cardId, anchorLabel) {
            if (!svgElement) return;
            svgElement.innerHTML = '';

            const totalCount = Math.max((nodes || []).length, 6);
            const w = Math.max(980, totalCount * 140);
            const h = 220;
            svgElement.setAttribute('viewBox', `0 0 ${w} ${h}`);
            svgElement.setAttribute('preserveAspectRatio', 'xMidYMid meet');
            svgElement.style.width = `${w}px`;
            svgElement.style.minWidth = `${w}px`;
            svgElement.style.height = '100%';

            const sid = `psvg-${cardId}`;
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            defs.innerHTML = `
                <filter id="neon-${sid}" x="-80%" y="-80%" width="260%" height="260%">
                    <feGaussianBlur stdDeviation="3.5" result="b"/>
                    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
                <linearGradient id="grad-target-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#fde68a"/><stop offset="100%" stop-color="#d97706"/>
                </linearGradient>
                <linearGradient id="grad-master-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#a7f3d0"/><stop offset="100%" stop-color="#059669"/>
                </linearGradient>
                <linearGradient id="grad-gap-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#fed7aa"/><stop offset="100%" stop-color="#ea580c"/>
                </linearGradient>
                <marker id="arr-pers-${sid}" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M0,1 L10,5 L0,9 Z" fill="#38bdf8"/>
                </marker>
                <marker id="arr-gap-${sid}" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                    <path d="M0,1 L10,5 L0,9 Z" fill="#f59e0b"/>
                </marker>
            `;
            svgElement.appendChild(defs);

            const cy = h / 2;
            const cx = w / 2;
            const gapNodes = nodes.filter(n => ['review_gap', 'missing', 'fading'].includes(n.status));
            const mastNodes = nodes.filter(n => n.status === 'mastered');
            const targetNode = nodes.find(n => n.role === 'target') || nodes[nodes.length - 1];
            const unlockedNodes = nodes.filter(n => n.status === 'downstream_unlocked');

            const nodeCoords = {};

            // Place gap nodes on the left (x = 120)
            gapNodes.forEach((n, i) => {
                const y = (h / (gapNodes.length + 1)) * (i + 1);
                const x = 120 + (i % 2 === 1 ? 40 : 0);
                nodeCoords[n.id] = { x, y, node: n, color: `url(#grad-gap-${sid})`, stroke: '#f59e0b', glow: '#ea580c', badge: n.status === 'missing' ? 'Missing' : n.status === 'fading' ? 'Fading' : 'Review Gap' };
            });

            // Place mastered nodes in the center (x = cx - 120)
            mastNodes.forEach((n, i) => {
                const y = (h / (mastNodes.length + 1)) * (i + 1);
                const x = (cx - 120) + (i % 2 === 1 ? 35 : 0);
                nodeCoords[n.id] = { x, y, node: n, color: `url(#grad-master-${sid})`, stroke: '#10b981', glow: '#059669', badge: 'Mastered' };
            });

            // Place target concept on the right (x = cx + 120)
            if (targetNode) {
                nodeCoords[targetNode.id] = {
                    x: unlockedNodes.length ? cx + 120 : cx + 160,
                    y: cy,
                    node: targetNode,
                    color: `url(#grad-target-${sid})`,
                    stroke: '#fbbf24',
                    glow: '#d97706',
                    badge: targetNode.status === 'unlocked' ? 'Fully Unlocked' : 'Target Goal'
                };
            }

            // Place downstream unlocked nodes (x = w - 160)
            unlockedNodes.forEach((n, i) => {
                const y = (h / (unlockedNodes.length + 1)) * (i + 1);
                nodeCoords[n.id] = { x: w - 160 + (i % 2 === 1 ? 40 : 0), y, node: n, color: '#38bdf8', stroke: '#0284c7', glow: '#38bdf8', badge: 'Downstream' };
            });

            // Draw directed edges
            edges.forEach(e => {
                const u = nodeCoords[e.from_id || e.source];
                const v = nodeCoords[e.to_id || e.target];
                if (u && v && u !== v) {
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const midX = (u.x + v.x) / 2;
                    const midY = (u.y + v.y) / 2;
                    const d = `M ${u.x} ${u.y} Q ${midX} ${midY} ${v.x} ${v.y}`;
                    const marker = e.relation.includes('REVIEW') ? `url(#arr-gap-${sid})` : `url(#arr-pers-${sid})`;
                    const strokeColor = e.relation.includes('REVIEW') ? 'rgba(245, 158, 11, 0.7)' : 'rgba(56, 189, 248, 0.7)';
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', strokeColor);
                    path.setAttribute('stroke-width', '2.2');
                    path.setAttribute('filter', `url(#neon-${sid})`);
                    path.setAttribute('marker-end', marker);
                    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                    title.textContent = `${u.node.label} ${e.relation} ${v.node.label}`;
                    path.appendChild(title);
                    path.setAttribute('tabindex', '0');
                    path.setAttribute('aria-label', title.textContent);
                    svgElement.appendChild(path);
                }
            });

            // Draw interactive nodes
            Object.values(nodeCoords).forEach(item => {
                const n = item.node;
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                g.setAttribute('class', 'cursor-pointer group');
                g.setAttribute('transform', `translate(${item.x}, ${item.y})`);

                const isTarget = n.role === 'target';
                const r = isTarget ? 18 : 14;

                const cGlow = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                cGlow.setAttribute('r', String(r + 6));
                cGlow.setAttribute('fill', item.glow);
                cGlow.setAttribute('opacity', '0.2');
                cGlow.setAttribute('filter', `url(#neon-${sid})`);
                g.appendChild(cGlow);

                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('r', String(r));
                circle.setAttribute('fill', item.color);
                circle.setAttribute('stroke', item.stroke);
                circle.setAttribute('stroke-width', isTarget ? '3' : '2');
                g.appendChild(circle);

                const sym = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                sym.setAttribute('text-anchor', 'middle');
                sym.setAttribute('dominant-baseline', 'central');
                sym.setAttribute('font-size', isTarget ? '11' : '9');
                sym.setAttribute('font-weight', 'bold');
                sym.setAttribute('fill', '#000');
                sym.textContent = n.status === 'mastered' ? '✓' : (n.status === 'review_gap' ? '!' : (isTarget ? '★' : '→'));
                g.appendChild(sym);

                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('y', String(r + 14));
                text.setAttribute('font-size', '10');
                text.setAttribute('font-weight', 'bold');
                text.setAttribute('fill', item.stroke);
                text.setAttribute('filter', `drop-shadow(0 1px 2px rgba(0,0,0,0.8))`);
                text.textContent = (n.label || n.id).substring(0, 18);
                g.appendChild(text);

                g.onclick = () => {
                    selectPersonalizedNode(cardId, n, anchorLabel);
                };

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
                    span.onclick = () => selectPersonalizedNode(cardId, n, anchorLabel);
                    container.appendChild(span);
                });
            };

            const graphPrereqs = nodes.filter(n => n.type === 'prereq');
            const graphUnlocks = nodes.filter(n => n.type === 'unlock');
            const graphRelated = nodes.filter(n => n.type === 'related');

            syncGraphBadges(reqDiv, graphPrereqs, 'text-accentPurple border-accentPurple/40 bg-accentPurple/15 hover:bg-accentPurple/25');
            syncGraphBadges(unlDiv, graphUnlocks, 'text-emerald-300 border-emerald-400/40 bg-emerald-400/15 hover:bg-emerald-400/25');
            syncGraphBadges(conDiv, graphRelated, 'text-cyan-300 border-cyan-400/40 bg-cyan-400/15 hover:bg-cyan-400/25');
        }

        window.drawPersonalizedSVG = drawPersonalizedSVG;

        function selectPersonalizedNode(cardId, node, anchorLabel) {
            const titleEl = document.getElementById(`pers-insp-title-${cardId}`);
            const summaryEl = document.getElementById(`pers-insp-summary-${cardId}`);
            const badgeEl = document.getElementById(`pers-insp-badge-${cardId}`);
            const citationEl = document.getElementById(`pers-insp-citation-${cardId}`);
            const actionsEl = document.getElementById(`pers-insp-actions-${cardId}`);

            if (titleEl) titleEl.textContent = node.label || node.id;
            if (summaryEl) summaryEl.textContent = [node.summary, node.why].filter(Boolean).join('\n\n');
            if (badgeEl) {
                badgeEl.textContent = ['missing', 'fading'].includes(node.status) ? node.status.toUpperCase() : node.status === 'mastered' ? 'Prerequisite Mastered (🟢)' : (node.status === 'review_gap' ? 'Review Gap (🟡)' : 'Target Goal (🌟)');
                badgeEl.className = `px-2 py-0.5 rounded text-[9px] font-extrabold uppercase ${node.status === 'mastered' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : (node.status === 'review_gap' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-accentPurple/25 text-accentPurple border border-accentPurple/40')}`;
            }
            if (citationEl) {
                citationEl.textContent = node.citation ? `Citation: ${node.citation}` : '';
            }
            if (actionsEl) {
                actionsEl.replaceChildren();
                if (node.url && (node.url.startsWith('/read?') || node.url.startsWith('/open/'))) {
                    const link = document.createElement('a');
                    link.href = node.url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.className = 'px-3 py-2 rounded-lg bg-amber-500/20 text-amber-300 text-xs';
                    link.textContent = `View source (p. ${node.page_number || '?'})`;
                    actionsEl.appendChild(link);
                }
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'px-3 py-2 rounded-lg bg-accentPurple text-white text-xs';
                button.textContent = 'Explain this prerequisite';
                button.addEventListener('click', () => window.autoPrompt(`Explain ${node.label} for ${anchorLabel}`));
                actionsEl.appendChild(button);
            }
        }

        window.selectPersonalizedNode = selectPersonalizedNode;

export { drawPersonalizedSVG, selectPersonalizedNode };
