// Auto-split from ui/chat/index.html — 11-populate-topology.js
// Feature module 12 of 22.
import { _nodeId, _nodeLabel, _nodeSummary, selectGraphNode } from './10-populate-pipeline.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { _initGraphRipple } from './18--init-graph-ripple.js';
import { storageKey } from './storage-key.js';

        function populateTopology(anchor, prereqs, unlocks, related, isReset = false) {
            const placeholder = document.getElementById('topology-placeholder');
            const view = document.getElementById('topology-view');
            const bottomMapContainer = document.getElementById('bottom-svg-map-container');

            if (!anchor) {
                if (placeholder) {
                    placeholder.classList.remove('hidden');
                    placeholder.innerHTML = `
                        <div class="p-4 rounded-xl bg-white/5 border border-white/10 text-center flex flex-col items-center gap-2">
                            <i class="fa-solid fa-circle-nodes text-gray-500 text-lg"></i>
                            <p class="text-xs font-semibold text-gray-300">No Verified Graph Match</p>
                            <p class="text-[10px] text-gray-400">Lexical and literature fallback executed without concept substitution.</p>
                        </div>
                    `;
                }
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

                const preX = Math.max(64, cx - Math.min(cx - 48, large ? 200 : 130));
                const unX = Math.min(w - 64, cx + Math.min(w - cx - 48, large ? 200 : 130));
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
                    const charW = large ? 7.2 : 6.0;
                    const textW = short.length * charW;
                    const halfW = textW / 2;
                    let clampedX = n.x;
                    if (clampedX - halfW < 8) clampedX = 8 + halfW;
                    if (clampedX + halfW > w - 8) clampedX = w - 8 - halfW;
                    text.setAttribute('x', clampedX);

                    let textY = n.y + r + 14;
                    if (textY > h - 6) textY = n.y - r - 6;
                    text.setAttribute('y', textY);
                    text.setAttribute('text-anchor', 'middle');
                    text.setAttribute('fill', '#e5e7eb');
                    text.setAttribute('font-size', large ? '12px' : '10.5px');
                    text.setAttribute('font-weight', '700');
                    text.setAttribute('font-family', "system-ui, -apple-system, sans-serif");
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

export { dismissGraphChoiceModal, getOrCreateInteractiveZone, getOrCreateOkfNodesZone, getOrCreateQuizZone, populateTopology, renderOkfNodesCard, renderQuizSectionCard, showGraphChoiceModal, toggleGraphCardsSetting, toggleHorizontalGraphCard, updateGraphToggleUI };
