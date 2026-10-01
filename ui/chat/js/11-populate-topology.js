// Auto-split from ui/chat/index.html — 11-populate-topology.js
// Feature module 12 of 22.
import { _nodeId, _nodeLabel, _nodeSummary, selectGraphNode } from './10-populate-pipeline.js';
import { _initGraphRipple } from './18--init-graph-ripple.js';

        function populateTopology(anchor, prereqs, unlocks, related, isReset = false) {
            const placeholder = document.getElementById('topology-placeholder');
            const view = document.getElementById('topology-view');
            const bottomMapContainer = document.getElementById('bottom-svg-map-container');

            if (!anchor) {
                if (isReset) {
                    if (placeholder) placeholder.classList.remove('hidden');
                    if (view) view.classList.add('hidden');
                }
                return;
            }

            let activeAnchor = anchor;
            let activePrereqs = prereqs;
            let activeUnlocks = unlocks;
            let activeRelated = related;

            const safePrereqs = (activePrereqs || []).slice(0, 4);
            const safeUnlocks = (activeUnlocks || []).slice(0, 4);
            const safeRelated = (activeRelated || []).slice(0, 4);

            window._graphNeighborhood = {
                anchor: activeAnchor,
                prereqs: safePrereqs,
                unlocks: safeUnlocks,
                related: safeRelated
            };

            if (placeholder) placeholder.classList.add('hidden');
            if (view) view.classList.remove('hidden');
            if (bottomMapContainer) {
                bottomMapContainer.classList.add('hidden');
                bottomMapContainer.classList.remove('is-visible');
            }

            const sidebarSvg = document.getElementById('sidebar-svg-map');
            const bottomSvg = document.getElementById('bottom-svg-map');

            const drawSVG = (svgElement, large) => {
                if (!svgElement) return;
                svgElement.innerHTML = '';
                const isDock = svgElement.id === 'bottom-svg-map';
                const w = Math.max(
                    svgElement.clientWidth || (isDock ? 150 : (large ? 640 : 300)),
                    isDock ? 140 : (large ? 480 : 260)
                );
                const h = Math.max(
                    svgElement.clientHeight || (isDock ? 140 : (large ? 180 : 160)),
                    isDock ? 130 : (large ? 160 : 140)
                );
                svgElement.setAttribute('viewBox', `0 0 ${w} ${h}`);
                svgElement.setAttribute('preserveAspectRatio', 'xMidYMid meet');
                const cx = w / 2;
                const cy = h / 2 + (large ? 4 : 0);
                const sid = svgElement.id || 'g';

                const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                defs.innerHTML = `
                    <filter id="neon-${sid}" x="-80%" y="-80%" width="260%" height="260%">
                        <feGaussianBlur stdDeviation="3.2" result="b"/>
                        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                    <linearGradient id="grad-anchor-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#c4b5fd"/><stop offset="100%" stop-color="#8b5cf6"/>
                    </linearGradient>
                    <linearGradient id="grad-pre-${sid}" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#a855f7"/><stop offset="100%" stop-color="#6366f1"/>
                    </linearGradient>
                    <linearGradient id="grad-unl-${sid}" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="#6366f1"/><stop offset="100%" stop-color="#06b6d4"/>
                    </linearGradient>
                    <marker id="arr-pre-${sid}" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                        <path d="M0,1 L10,5 L0,9 Z" fill="#c084fc"/>
                    </marker>
                    <marker id="arr-unl-${sid}" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="5" markerHeight="5" orient="auto">
                        <path d="M0,1 L10,5 L0,9 Z" fill="#22d3ee"/>
                    </marker>
                `;
                svgElement.appendChild(defs);

                const nodes = [];
                nodes.push({
                    id: _nodeId(activeAnchor, 'anchor'),
                    label: _nodeLabel(activeAnchor),
                    summary: _nodeSummary(activeAnchor),
                    x: cx, y: cy, type: 'anchor', data: activeAnchor
                });

                const preX = Math.max(36, cx - Math.min(cx - 28, large ? 200 : 120));
                const unX = Math.min(w - 36, cx + Math.min(w - cx - 28, large ? 200 : 120));
                const pN = Math.max(safePrereqs.length, 1);
                const uN = Math.max(safeUnlocks.length, 1);
                safePrereqs.forEach((p, i) => {
                    const y = (h / (pN + 1)) * (i + 1);
                    nodes.push({ id: _nodeId(p, 'p'+i), label: _nodeLabel(p), summary: _nodeSummary(p), x: preX, y, type: 'prereq', data: p });
                });
                safeUnlocks.forEach((u, i) => {
                    const y = (h / (uN + 1)) * (i + 1);
                    nodes.push({ id: _nodeId(u, 'u'+i), label: _nodeLabel(u), summary: _nodeSummary(u), x: unX, y, type: 'unlock', data: u });
                });
                safeRelated.forEach((r, i) => {
                    const top = i % 2 === 0;
                    const slot = Math.floor(i / 2);
                    const xOff = (slot - 0.25) * (large ? 70 : 48);
                    nodes.push({
                        id: _nodeId(r, 'r'+i),
                        label: _nodeLabel(r),
                        summary: _nodeSummary(r),
                        x: cx + xOff + (top ? -20 : 20),
                        y: top ? Math.max(18, cy - (large ? 62 : 48)) : Math.min(h - 18, cy + (large ? 62 : 48)),
                        type: 'related',
                        data: r
                    });
                });

                const colors = {
                    anchor:  { fill: `url(#grad-anchor-${sid})`, stroke: '#c4b5fd', glow: '#8b5cf6', edge: `url(#grad-unl-${sid})` },
                    prereq:  { fill: 'rgba(168,85,247,0.35)', stroke: '#c084fc', glow: '#a855f7', edge: `url(#grad-pre-${sid})` },
                    unlock:  { fill: 'rgba(6,182,212,0.35)', stroke: '#22d3ee', glow: '#06b6d4', edge: `url(#grad-unl-${sid})` },
                    related: { fill: 'rgba(245,158,11,0.28)', stroke: '#fbbf24', glow: '#f59e0b', edge: 'rgba(251,191,36,0.7)' }
                };

                // Edges
                nodes.forEach(n => {
                    if (n.type === 'anchor') return;
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    let d, marker = '', cls = '';
                    if (n.type === 'prereq') {
                        d = `M ${n.x} ${n.y} C ${(n.x + cx) / 2} ${n.y}, ${(n.x + cx) / 2} ${cy}, ${cx} ${cy}`;
                        marker = `url(#arr-pre-${sid})`;
                        cls = 'graph-edge-prereq';
                    } else if (n.type === 'unlock') {
                        d = `M ${cx} ${cy} C ${(cx + n.x) / 2} ${cy}, ${(cx + n.x) / 2} ${n.y}, ${n.x} ${n.y}`;
                        marker = `url(#arr-unl-${sid})`;
                        cls = 'graph-edge-unlock';
                    } else {
                        d = `M ${cx} ${cy} Q ${(cx + n.x) / 2} ${(cy + n.y) / 2 + (n.y < cy ? -20 : 20)} ${n.x} ${n.y}`;
                        cls = 'graph-edge-related';
                    }
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', colors[n.type].edge);
                    path.setAttribute('stroke-width', n.type === 'related' ? '1.6' : '2.2');
                    path.setAttribute('filter', `url(#neon-${sid})`);
                    if (marker) path.setAttribute('marker-end', marker);
                    path.setAttribute('class', cls);
                    if (n.type === 'related') path.setAttribute('stroke-dasharray', '3 5');
                    svgElement.appendChild(path);
                });

                // Nodes
                nodes.forEach(n => {
                    const c = colors[n.type];
                    const r = n.type === 'anchor' ? (large ? 18 : 14) : (large ? 12 : 10);
                    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    g.setAttribute('class', 'graph-node-group');
                    g.setAttribute('data-node-id', n.id);
                    g.setAttribute('data-node-type', n.type);
                    g.style.color = c.stroke;
                    g.style.cursor = 'pointer';
                    g.addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        selectGraphNode(n.id, n.type);
                    });

                    const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    pulse.setAttribute('cx', n.x);
                    pulse.setAttribute('cy', n.y);
                    pulse.setAttribute('r', r + 6);
                    pulse.setAttribute('stroke', c.glow);
                    pulse.setAttribute('filter', `url(#neon-${sid})`);
                    if (n.type !== 'anchor') {
                        pulse.style.opacity = '0';
                        pulse.setAttribute('class', 'graph-select-ring');
                        pulse.setAttribute('fill', 'none');
                        pulse.setAttribute('stroke-width', '2');
                        pulse.style.transition = 'opacity 0.2s';
                    } else {
                        pulse.setAttribute('class', 'graph-pulse-ring');
                        pulse.setAttribute('fill', 'none');
                    }
                    g.appendChild(pulse);

                    const core = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    core.setAttribute('class', 'graph-node-core');
                    core.setAttribute('cx', n.x);
                    core.setAttribute('cy', n.y);
                    core.setAttribute('r', r);
                    core.setAttribute('fill', c.fill);
                    core.setAttribute('stroke', c.stroke);
                    core.setAttribute('stroke-width', n.type === 'anchor' ? '2' : '1.5');
                    core.setAttribute('filter', `url(#neon-${sid})`);
                    g.appendChild(core);

                    const inner = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    inner.setAttribute('cx', n.x);
                    inner.setAttribute('cy', n.y);
                    inner.setAttribute('r', Math.max(2.5, r * 0.32));
                    inner.setAttribute('fill', c.stroke);
                    inner.setAttribute('opacity', '0.95');
                    g.appendChild(inner);

                    const short = (n.label || n.id || '').length > 28 ? (n.label || n.id).slice(0, 27) + '…' : (n.label || n.id || '');
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', n.x);
                    text.setAttribute('y', n.y + r + 14);
                    text.setAttribute('text-anchor', 'middle');
                    text.setAttribute('fill', '#e5e7eb');
                    text.setAttribute('font-size', large ? '13px' : '11px');
                    text.setAttribute('font-weight', '700');
                    text.setAttribute('font-family', "'Brigend', sans-serif");
                    text.textContent = short;
                    g.appendChild(text);

                    const badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    badge.setAttribute('class', 'graph-node-badge');
                    badge.setAttribute('x', n.x);
                    badge.setAttribute('y', n.y + r + 26);
                    badge.setAttribute('text-anchor', 'middle');
                    badge.setAttribute('fill', c.stroke);
                    badge.setAttribute('font-size', '9.5px');
                    badge.setAttribute('font-weight', '600');
                    badge.setAttribute('font-family', "'Brigend', sans-serif");
                    badge.textContent = n.type === 'anchor' ? '● TARGET' : n.type === 'prereq' ? '↑ REQUIRES' : n.type === 'unlock' ? '↓ UNLOCKS' : '◈ RELATED';
                    badge.style.opacity = n.type === 'anchor' ? '1' : '0';
                    badge.style.transition = 'opacity 0.2s';
                    g.appendChild(badge);

                    svgElement.appendChild(g);
                });
            };

            requestAnimationFrame(() => {
                setTimeout(() => {
                    drawSVG(sidebarSvg, false);
                    drawSVG(bottomSvg, false);
                    selectGraphNode(_nodeId(activeAnchor), 'anchor');
                    const sRipple = document.getElementById('sidebar-ripple-bg');
                    const sContainer = document.getElementById('sidebar-svg-map-container');
                    if (sRipple && sContainer && typeof _initGraphRipple === 'function') {
                        _initGraphRipple(sRipple, sContainer);
                    }
                }, 40);
            });
        }

        window.populateTopology = populateTopology;

        // ── In-Chat Horizontal Concept Graph Card Component ─────────────
        function toggleHorizontalGraphCard(cardId) {
            const body = document.getElementById(`card-body-${cardId}`);
            const icon = document.getElementById(`toggle-icon-${cardId}`);
            if (!body) return;
            const isHidden = body.classList.contains('hidden');
            if (isHidden) {
                body.classList.remove('hidden');
                if (icon) icon.className = 'fa-solid fa-chevron-up text-xs text-amber-300 transition-transform';
            } else {
                body.classList.add('hidden');
                if (icon) icon.className = 'fa-solid fa-chevron-down text-xs text-amber-300 transition-transform';
            }
        }

        window.toggleHorizontalGraphCard = toggleHorizontalGraphCard;

        // Global setting for rendering in-chat concept graph cards
        // The in-chat graph is part of every grounded reply.  A stale local
        // preference must not silently make it disappear.
        window.showGraphCards = true;

        localStorage.setItem('showGraphCards', 'true');

        function toggleGraphCardsSetting() {
            window.showGraphCards = !window.showGraphCards;
            localStorage.setItem('showGraphCards', window.showGraphCards ? 'true' : 'false');
            updateGraphToggleUI();
        }

        window.toggleGraphCardsSetting = toggleGraphCardsSetting;

        function updateGraphToggleUI() {
            const headerLabel = document.getElementById('graph-toggle-label');
            const sideLabel = document.getElementById('sidebar-graph-toggle-label');
            const headerImg = document.getElementById('header-graph-btn-img');
            const sideImg = document.getElementById('sidebar-graph-btn-img');
            
            if (window.showGraphCards) {
                if (headerLabel) headerLabel.textContent = 'Graph: ON';
                if (sideLabel) sideLabel.textContent = 'ON';
                if (headerImg) headerImg.className = 'w-full h-full object-contain transition-all duration-200';
                if (sideImg) sideImg.className = 'w-full h-full object-contain transition-all duration-200';
            } else {
                if (headerLabel) headerLabel.textContent = 'Graph: OFF';
                if (sideLabel) sideLabel.textContent = 'OFF';
                if (headerImg) headerImg.className = 'w-full h-full object-contain transition-all duration-200 grayscale opacity-40';
                if (sideImg) sideImg.className = 'w-full h-full object-contain transition-all duration-200 grayscale opacity-40';
            }
        }

        window.updateGraphToggleUI = updateGraphToggleUI;

        // ── Interactive Concept Graph Mode Choice (Personalized vs Normal) ──
        window._activeChoiceContext = window._activeChoiceContext || null;

        function getOrCreateInteractiveZone(msgId) {
            const msgEl = document.getElementById(`msg-body-${msgId}`);
            if (!msgEl) return null;
            let zone = document.getElementById(`interactive-zone-${msgId}`);
            if (!zone) {
                zone = document.createElement('div');
                zone.id = `interactive-zone-${msgId}`;
                zone.className = 'w-full mt-4 pt-3 border-t border-white/10 relative overflow-hidden transition-all duration-300';
                msgEl.appendChild(zone);
            }
            return zone;
        }

        window.getOrCreateInteractiveZone = getOrCreateInteractiveZone;

        function showGraphChoiceModal(msgId, metadata) {
            // Dismiss and suppress modal popup; interactive choice is rendered directly inside the chat card
            dismissGraphChoiceModal();
        }

        window.showGraphChoiceModal = showGraphChoiceModal;

        function dismissGraphChoiceModal() {
            const modal = document.getElementById('graph-choice-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
        }

        window.dismissGraphChoiceModal = dismissGraphChoiceModal;

export { dismissGraphChoiceModal, getOrCreateInteractiveZone, populateTopology, showGraphChoiceModal, toggleGraphCardsSetting, toggleHorizontalGraphCard, updateGraphToggleUI };
