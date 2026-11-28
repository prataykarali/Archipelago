// Auto-split from ui/chat/index.html — 11-populate-topology.js
// Feature module 12 of 22.
import { _nodeId, _nodeLabel, _nodeSummary, selectGraphNode } from './10-populate-pipeline.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { _initGraphRipple } from './18--init-graph-ripple.js';
import { storageKey } from './storage-key.js';
import { buildArrowMarkerDefs, buildDeduplicatedTopology, clearStaleInspectorState, computeEdgeEndpoints, ensureSidebarEdgeLegend, renderTopologyPlaceholder, resolveLabelPositions } from './11a-topology-layout.js';

        function populateTopology(anchor, prereqs, unlocks, related, isReset = false) {
            const placeholder = document.getElementById('topology-placeholder');
            const view = document.getElementById('topology-view');
            const bottomMapContainer = document.getElementById('bottom-svg-map-container');

            if (!anchor) {
                clearStaleInspectorState(isReset);
                renderTopologyPlaceholder(placeholder, isReset);
                if (view) view.classList.add('hidden');
                if (bottomMapContainer) {
                    bottomMapContainer.classList.add('hidden');
                    bottomMapContainer.classList.remove('is-visible');
                }
                window._graphNeighborhood = { anchor: null, prereqs: [], unlocks: [], related: [] };
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
                    <filter id="neon-${sid}" filterUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}">
                        <feGaussianBlur stdDeviation="2.6" result="b"/>
                        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                    <linearGradient id="grad-anchor-${sid}" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#c4b5fd"/><stop offset="100%" stop-color="#8b5cf6"/>
                    </linearGradient>
                    ${buildArrowMarkerDefs(sid, { size: large ? 9 : 8, prereqColor: '#c084fc', unlockColor: '#22d3ee', relatedColor: '#fbbf24' })}
                `;
                svgElement.appendChild(defs);

                const { nodes, edges } = buildDeduplicatedTopology({
                    anchor: activeAnchor,
                    prereqs: safePrereqs,
                    unlocks: safeUnlocks,
                    related: safeRelated,
                    getNodeId: _nodeId,
                    getNodeLabel: _nodeLabel,
                    getNodeSummary: _nodeSummary,
                    width: w,
                    height: h,
                    large,
                });

                const colors = {
                    anchor:  { fill: `url(#grad-anchor-${sid})`, stroke: '#c4b5fd', glow: '#8b5cf6', edge: '#22d3ee' },
                    prereq:  { fill: 'rgba(168,85,247,0.35)', stroke: '#c084fc', glow: '#a855f7', edge: '#c084fc' },
                    unlock:  { fill: 'rgba(6,182,212,0.35)', stroke: '#22d3ee', glow: '#06b6d4', edge: '#22d3ee' },
                    related: { fill: 'rgba(245,158,11,0.28)', stroke: '#fbbf24', glow: '#f59e0b', edge: '#fbbf24' }
                };

                const anchorRadius = large ? 18 : 14;
                const peerRadius = large ? 12 : 10;

                // Edges (supports multi-relation edges on deduplicated nodes without duplicate circles)
                edges.forEach((edge) => {
                    const n = edge.node;
                    const relType = edge.type;
                    const curveBias = (edge.relationIndex || 0) * 18;
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    let d, marker = '', cls = '', fromId = '', toId = '';
                    if (relType === 'prereq') {
                        const { sx, sy, ex, ey } = computeEdgeEndpoints(n.x, n.y, cx, cy, peerRadius, anchorRadius, 5);
                        d = `M ${sx} ${sy} C ${(sx + ex) / 2} ${sy - curveBias}, ${(sx + ex) / 2} ${ey - curveBias}, ${ex} ${ey}`;
                        marker = `url(#arr-pre-${sid})`;
                        cls = 'graph-edge-prereq';
                        fromId = n.id;
                        toId = _nodeId(activeAnchor, 'anchor');
                    } else if (relType === 'unlock') {
                        const { sx, sy, ex, ey } = computeEdgeEndpoints(cx, cy, n.x, n.y, anchorRadius, peerRadius, 5);
                        d = `M ${sx} ${sy} C ${(sx + ex) / 2} ${sy + curveBias}, ${(sx + ex) / 2} ${ey + curveBias}, ${ex} ${ey}`;
                        marker = `url(#arr-unl-${sid})`;
                        cls = 'graph-edge-unlock';
                        fromId = _nodeId(activeAnchor, 'anchor');
                        toId = n.id;
                    } else {
                        const { sx, sy, ex, ey } = computeEdgeEndpoints(cx, cy, n.x, n.y, anchorRadius, peerRadius, 5);
                        const qShift = (n.y < cy ? -18 : 18) + curveBias;
                        d = `M ${sx} ${sy} Q ${(sx + ex) / 2} ${(sy + ey) / 2 + qShift} ${ex} ${ey}`;
                        marker = `url(#arr-rel-${sid})`;
                        cls = 'graph-edge-related';
                        fromId = _nodeId(activeAnchor, 'anchor');
                        toId = n.id;
                    }
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', colors[relType].edge);
                    path.setAttribute('stroke-opacity', relType === 'related' ? '0.82' : '0.94');
                    path.setAttribute('stroke-width', relType === 'related' ? '1.7' : '2.2');
                    path.setAttribute('stroke-linecap', 'round');
                    if (marker) path.setAttribute('marker-end', marker);
                    path.setAttribute('class', cls);
                    path.setAttribute('data-edge-type', relType);
                    path.setAttribute('data-relation', relType === 'prereq' ? 'REQUIRES' : relType === 'unlock' ? 'UNLOCKS' : 'RELATED_TO');
                    path.setAttribute('data-from', fromId);
                    path.setAttribute('data-to', toId);
                    path.setAttribute('data-review-status', 'review_pending');
                    if (relType === 'related') path.setAttribute('stroke-dasharray', '4 4');
                    svgElement.appendChild(path);
                });

                const charW = large ? 7.2 : 6.0;
                const labelSpecs = nodes.map((n) => {
                    const r = n.type === 'anchor' ? (large ? 18 : 14) : (large ? 12 : 10);
                    const raw = n.label || n.id || '';
                    const short = raw.length > 26 ? raw.slice(0, 25) + '…' : raw;
                    return {
                        node: n,
                        short,
                        radius: r,
                        x: n.x,
                        y: n.y,
                        textWidth: short.length * charW,
                    };
                });
                const placedLabels = resolveLabelPositions(labelSpecs, w, h);

                // Nodes (deduplicated by canonical concept ID)
                placedLabels.forEach((spec) => {
                    const n = spec.node;
                    const c = colors[n.type];
                    const r = spec.radius;
                    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    g.setAttribute('class', 'graph-node-group');
                    g.setAttribute('data-node-id', n.id);
                    g.setAttribute('data-canonical-id', n.canonicalId);
                    g.setAttribute('data-node-type', n.type);
                    g.setAttribute('data-relations', (n.relations || [n.type]).join(','));
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

                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', spec.labelX);
                    text.setAttribute('y', spec.labelY);
                    text.setAttribute('text-anchor', 'middle');
                    text.setAttribute('fill', '#e5e7eb');
                    text.setAttribute('font-size', large ? '12px' : '10.5px');
                    text.setAttribute('font-weight', '600');
                    text.setAttribute('font-family', "Inter, system-ui, -apple-system, sans-serif");
                    text.textContent = spec.short;
                    g.appendChild(text);

                    const badge = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    badge.setAttribute('class', 'graph-node-badge');
                    badge.setAttribute('x', spec.labelX);
                    badge.setAttribute('y', Math.min(h - 2, spec.labelY + 12));
                    badge.setAttribute('text-anchor', 'middle');
                    badge.setAttribute('fill', c.stroke);
                    badge.setAttribute('font-size', '9px');
                    badge.setAttribute('font-weight', '600');
                    badge.setAttribute('font-family', "Inter, system-ui, -apple-system, sans-serif");
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
                    ensureSidebarEdgeLegend();
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

        function toggleGraphCardsSetting() {
            window.showGraphCards = !window.showGraphCards;
            localStorage.setItem(storageKey('showGraphCards'), window.showGraphCards ? 'true' : 'false');
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

        function getOrCreateOkfNodesZone(msgId) {
            const msgEl = document.getElementById(`msg-body-${msgId}`);
            if (!msgEl) return null;
            let zone = document.getElementById(`okf-nodes-zone-${msgId}`);
            if (!zone) {
                zone = document.createElement('div');
                zone.id = `okf-nodes-zone-${msgId}`;
                zone.className = 'w-full mt-4 pt-3 border-t border-white/10';
                msgEl.appendChild(zone);
            }
            return zone;
        }

        function renderOkfNodesCard(msgId, metadata) {
            if (!metadata || typeof metadata !== 'object') return;
            const anchor = metadata.anchor_concept || null;
            const prereqs = Array.isArray(metadata.prerequisites) ? metadata.prerequisites : [];
            const unlocks = Array.isArray(metadata.unlocks) ? metadata.unlocks : [];
            const related = Array.isArray(metadata.related_concepts || metadata.related) ? (metadata.related_concepts || metadata.related) : [];
            if (!anchor && !prereqs.length && !unlocks.length && !related.length) return;

            const zone = getOrCreateOkfNodesZone(msgId);
            if (!zone) return;

            const renderPills = (items, pillCls, iconCls, emptyLabel) => {
                if (!items.length) return `<span class="text-[11px] text-slate-400 italic">${emptyLabel}</span>`;
                return items.slice(0, 6).map(item => {
                    const lbl = _nodeLabel(item);
                    const safeLbl = escapeHTML(lbl);
                    return `<button type="button" onclick="promptFromConcept('${safeLbl.replace(/'/g, "\\'")}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-all cursor-pointer ${pillCls}"><i class="${iconCls} text-[10px]"></i><span>${safeLbl}</span></button>`;
                }).join('');
            };

            const anchorHtml = anchor
                ? `<button type="button" onclick="promptFromConcept('${escapeHTML(_nodeLabel(anchor)).replace(/'/g, "\\'")}')" class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-500/20 border border-amber-400/50 text-amber-200 hover:bg-amber-500/30 text-xs font-bold transition-all cursor-pointer"><i class="fa-solid fa-bullseye text-[11px]"></i><span>${escapeHTML(_nodeLabel(anchor))}</span></button>`
                : `<span class="text-[11px] text-slate-400 italic">General topic</span>`;

            const anchorType = anchor && (anchor.concept_type || anchor.kind || anchor.type);
            const anchorDiff = anchor && anchor.difficulty;
            const anchorMetaBadges = [
                anchorType ? `<span class="px-2 py-0.5 rounded bg-indigo-500/20 border border-indigo-400/40 text-[10px] font-mono text-indigo-200 uppercase">${escapeHTML(String(anchorType))}</span>` : '',
                anchorDiff ? `<span class="px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-400/40 text-[10px] font-mono text-emerald-200 uppercase">${escapeHTML(String(anchorDiff))}</span>` : '',
            ].filter(Boolean).join(' ');

            zone.innerHTML = `
                <div class="rounded-2xl border border-indigo-500/30 bg-slate-950/70 p-4 space-y-3 shadow-lg">
                    <div class="flex items-center justify-between gap-2 border-b border-white/10 pb-2.5">
                        <div class="flex items-center gap-2">
                            <span class="w-6 h-6 rounded-lg bg-indigo-500/20 border border-indigo-400/40 flex items-center justify-center text-indigo-300 text-xs"><i class="fa-solid fa-diagram-project"></i></span>
                            <span class="text-xs font-extrabold uppercase tracking-wider text-indigo-200">OKF Knowledge Nodes</span>
                            ${anchorMetaBadges}
                        </div>
                        <span class="text-[10px] font-mono text-slate-400">Click any node to explore</span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div class="space-y-1.5">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-amber-300">Target Concept</div>
                            <div class="flex flex-wrap gap-1.5">${anchorHtml}</div>
                        </div>
                        <div class="space-y-1.5">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-purple-300">Requires (Prerequisites)</div>
                            <div class="flex flex-wrap gap-1.5">${renderPills(prereqs, 'bg-purple-500/15 border-purple-400/40 text-purple-200 hover:bg-purple-500/30', 'fa-solid fa-arrow-up-right-from-square', 'None indexed')}</div>
                        </div>
                        <div class="space-y-1.5">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-emerald-300">Unlocks (Next Topics)</div>
                            <div class="flex flex-wrap gap-1.5">${renderPills(unlocks, 'bg-emerald-500/15 border-emerald-400/40 text-emerald-200 hover:bg-emerald-500/30', 'fa-solid fa-unlock-keyhole', 'None indexed')}</div>
                        </div>
                        <div class="space-y-1.5">
                            <div class="text-[10px] font-bold uppercase tracking-wider text-cyan-300">Related Concepts</div>
                            <div class="flex flex-wrap gap-1.5">${renderPills(related, 'bg-cyan-500/15 border-cyan-400/40 text-cyan-200 hover:bg-cyan-500/30', 'fa-solid fa-link', 'None indexed')}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        function getOrCreateInteractiveZone(msgId) {
            const msgEl = document.getElementById(`msg-body-${msgId}`);
            if (!msgEl) return null;
            let zone = document.getElementById(`interactive-zone-${msgId}`);
            if (!zone) {
                zone = document.createElement('div');
                zone.id = `interactive-zone-${msgId}`;
                zone.className = 'w-full mt-4 relative overflow-hidden transition-all duration-300';
                msgEl.appendChild(zone);
            }
            return zone;
        }

        function getOrCreateQuizZone(msgId) {
            const msgEl = document.getElementById(`msg-body-${msgId}`);
            if (!msgEl) return null;
            let zone = document.getElementById(`quiz-zone-${msgId}`);
            if (!zone) {
                zone = document.createElement('div');
                zone.id = `quiz-zone-${msgId}`;
                zone.className = 'w-full mt-4 relative overflow-hidden transition-all duration-300';
                msgEl.appendChild(zone);
            }
            return zone;
        }

        function renderQuizSectionCard(msgId, metadata) {
            if (!metadata || !metadata.anchor_concept) return;
            const route = (metadata.routing && metadata.routing.route) || metadata.contract || '';
            const isResearchGraph = route === 'RESEARCH_EVIDENCE' || Boolean(metadata.graph_mode === 'research' || metadata.research_run_id);
            if (isResearchGraph) return;

            const zone = getOrCreateQuizZone(msgId);
            if (!zone) return;
            // Don't clobber an active or completed quiz already mounted in this zone
            if (zone.querySelector('.diagnostic-mcq-card, .personalized-graph-card')) return;

            const anchor = metadata.anchor_concept;
            const anchorLabel = _nodeLabel(anchor) || 'this concept';
            const existingAdaptive = window._adaptiveState && window._adaptiveState[msgId];
            const hasOngoingQuiz = existingAdaptive && existingAdaptive.current_mcq && !existingAdaptive.submitted;
            const btnLabel = hasOngoingQuiz
                ? `Resume Quiz (Q${existingAdaptive.question_count}/${existingAdaptive.max_questions})`
                : 'Take Adaptive Quiz & Build Personalized Graph';

            zone.innerHTML = `
                <div class="rounded-2xl border border-purple-500/35 bg-gradient-to-br from-slate-900/95 via-purple-950/25 to-slate-900/95 p-4 sm:p-5 shadow-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div class="space-y-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="w-7 h-7 rounded-xl bg-purple-500/25 border border-purple-400/50 flex items-center justify-center text-purple-200 text-xs shrink-0"><i class="fa-solid fa-graduation-cap"></i></span>
                            <h4 class="text-sm font-extrabold text-white tracking-tight">Personalized Learning Path &amp; Diagnostic Quiz</h4>
                        </div>
                        <p class="text-xs text-slate-300 leading-relaxed">Test your mastery of <strong class="text-purple-200">${escapeHTML(anchorLabel)}</strong> and its prerequisite/unlocked OKF nodes to generate your personalized mastery graph.</p>
                    </div>
                    <button id="quiz-start-${msgId}" onclick="switchToPersonalizedGraph('${msgId}')" type="button" class="shrink-0 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-extrabold shadow-lg shadow-purple-600/30 transition-all cursor-pointer">
                        <i class="fa-solid fa-play text-[11px]"></i>
                        <span>${btnLabel}</span>
                    </button>
                </div>
            `;
        }

        window.getOrCreateOkfNodesZone = getOrCreateOkfNodesZone;
        window.renderOkfNodesCard = renderOkfNodesCard;
        window.getOrCreateInteractiveZone = getOrCreateInteractiveZone;
        window.getOrCreateQuizZone = getOrCreateQuizZone;
        window.renderQuizSectionCard = renderQuizSectionCard;

        function showGraphChoiceModal(msgId, metadata) {
            const modal = document.getElementById('graph-choice-modal');
            if (!modal) return;
            window._activeChoiceContext = { msgId, metadata };
            const badge = document.getElementById('choice-concept-badge');
            if (badge && metadata && metadata.anchor_concept) {
                badge.textContent = _nodeLabel(metadata.anchor_concept) || 'Concept';
            }
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            const cardP = document.getElementById('choice-card-personalized');
            if (cardP) setTimeout(() => cardP.focus(), 50);
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

export { clearStaleInspectorState, dismissGraphChoiceModal, getOrCreateInteractiveZone, getOrCreateOkfNodesZone, getOrCreateQuizZone, populateTopology, renderOkfNodesCard, renderQuizSectionCard, showGraphChoiceModal, toggleGraphCardsSetting, toggleHorizontalGraphCard, updateGraphToggleUI };
