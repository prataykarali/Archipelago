// Auto-split from ui/chat/index.html — 13-render-horizontal-graph-card.js
// Feature module 14 of 22.
import { getOrCreateInteractiveZone } from './11-populate-topology.js';
import { _nodeId, _nodeLabel, _nodeSummary } from './10-populate-pipeline.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { _initGraphRipple, selectHorizontalNode } from './18--init-graph-ripple.js';
import { drawHorizontalSVG } from './19-draw-horizontal-svg.js';

        function renderHorizontalGraphCard(msgId, metadata) {
            if (window.showGraphCards === false) return;
            const msgEl = document.getElementById(`msg-body-${msgId}`);
            if (!msgEl) return;

            let anchor = metadata ? metadata.anchor_concept : null;
            if (!anchor) {
                // Do not render a horizontal graph card if there is no concept associated with this message
                return;
            }
            let prereqs = metadata ? (metadata.prerequisites || []) : [];
            let unlocks = metadata ? (metadata.unlocks || []) : [];
            let related = metadata ? (metadata.related_concepts || metadata.related || []) : [];

            const zone = getOrCreateInteractiveZone(msgId);
            if (!zone) return;
            const cardId = `hgraph-${msgId}`;
            const cardWrapper = zone;

            const anchorLabel = _nodeLabel(anchor) || 'Concept Node';
            const anchorSummary = _nodeSummary(anchor) || 'Knowledge graph node topology and OKF relationship dependencies.';
            const formatConceptList = (items, maxCount = 3) => {
                if (!items || !items.length) return 'None indexed';
                const names = items.slice(0, maxCount).map(_nodeLabel);
                const remainder = items.length - maxCount;
                return names.join(', ') + (remainder > 0 ? ` (+${remainder} more)` : '');
            };
            const prereqNames = formatConceptList(prereqs, 3);
            const unlockNames = formatConceptList(unlocks, 3);

            const existingAdaptive = (window._adaptiveState && window._adaptiveState[msgId]);
            const hasOngoingQuiz = existingAdaptive && existingAdaptive.current_mcq && !existingAdaptive.submitted;
            const quizBtnLabel = hasOngoingQuiz
                ? `Resume Quiz (Q${existingAdaptive.question_count}/${existingAdaptive.max_questions})`
                : 'Take Quiz';
            const quizBtnCls = hasOngoingQuiz
                ? 'bg-amber-500/25 hover:bg-amber-500/40 border border-amber-400 text-amber-300 font-extrabold shadow-lg shadow-amber-500/20'
                : 'bg-accentPurple/25 hover:bg-accentPurple/40 border border-accentPurple/50 text-accentPurple hover:text-white font-bold shadow-sm';

            cardWrapper.innerHTML = `
                <div class="concept-visualize-card border border-[#0d3829] rounded-xl overflow-hidden bg-[#03140d] shadow-[0_12px_32px_rgba(0,0,0,0.8),0_0_20px_rgba(0,255,163,0.05)]">
                    <!-- Terminal Traffic Light Bar -->
                    <div class="terminal-traffic-bar flex items-center justify-between px-3.5 py-2 bg-[#041a12] border-b border-[#0d3829] select-none">
                        <div class="flex items-center gap-1.5">
                            <span class="w-2.5 h-2.5 rounded-full bg-[#ff5f56] inline-block"></span>
                            <span class="w-2.5 h-2.5 rounded-full bg-[#ffbd2e] inline-block"></span>
                            <span class="w-2.5 h-2.5 rounded-full bg-[#27c93f] inline-block"></span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-mono font-bold text-[#00ffa3] tracking-wide">graphify</span>
                            <span class="text-[10px] font-mono text-[#34d399] opacity-85">shortest path</span>
                        </div>
                        <div class="text-[10px] font-mono text-[#52796f]">3 hops. Zero files opened.</div>
                    </div>
                    <!-- Header toggle bar -->
                    <button onclick="toggleHorizontalGraphCard('${cardId}')" type="button" class="w-full px-4 py-2.5 flex items-center justify-between bg-black/40 hover:bg-white/5 text-xs font-bold text-[#00ffa3] transition-all border-b border-[#0d3829] group cursor-pointer">
                        <div class="flex items-center gap-2.5 min-w-0">
                            <div class="w-7 h-7 flex items-center justify-center shrink-0">
                                <img src="/ui/assets/graph_btn.png" class="w-full h-full object-contain" alt="Graph">
                            </div>
                            <div class="flex flex-col text-left min-w-0">
                                <span class="font-extrabold text-white text-xs tracking-tight flex items-center gap-2">
                                    Visualize Concept Graph & OKF Keys
                                    <span class="px-2 py-0.5 rounded-full bg-accentPurple/25 border border-accentPurple/40 text-[10px] text-accentPurple font-mono font-bold truncate max-w-[180px] sm:max-w-[260px]">${escapeHTML(anchorLabel)}</span>
                                </span>
                                <span class="text-[10px] text-gray-400 font-medium">Click to expand/collapse horizontal node topology card</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 shrink-0">
                            <button onclick="event.stopPropagation(); switchToPersonalizedGraph('${msgId}')" type="button" class="px-2.5 py-1 rounded-lg ${quizBtnCls} text-[10px] transition-all flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-graduation-cap text-xs"></i> <span>${quizBtnLabel}</span>
                            </button>
                            <span class="text-[10px] text-amber-200/80 font-mono hidden sm:inline-block px-2 py-0.5 rounded bg-amber-400/10 border border-amber-400/20">Normal Graph</span>
                            <i id="toggle-icon-${cardId}" class="fa-solid fa-chevron-up text-xs text-amber-300 transition-transform"></i>
                        </div>
                    </button>

                    <!-- Card Body -->
                    <div id="card-body-${cardId}" class="p-4 space-y-4">
                        <!-- Flow Breadcrumb Header -->
                        ${metadata && metadata.query_mode === 'mode_b' ? `
                            <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-sans">
                                <div class="flex items-center gap-1.5 text-accentCyan font-bold min-w-0">
                                    <i class="fa-solid fa-code-compare text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-cyan-300 shrink-0">Mode B:</span>
                                    <span class="text-white font-extrabold truncate max-w-[140px] sm:max-w-[180px]">${escapeHTML(_nodeLabel(anchor))}</span>
                                </div>
                                <i class="fa-solid fa-arrows-left-right text-accentCyan/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-accentPurple font-bold min-w-0">
                                    <i class="fa-solid fa-bridge-water text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-purple-300 shrink-0">Path:</span>
                                    <span class="text-gray-200 font-semibold truncate max-w-[140px] sm:max-w-[200px]">Shortest Directed (5-10 Nodes)</span>
                                </div>
                                <i class="fa-solid fa-angles-right text-amber-400/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-amber-300 font-extrabold min-w-0">
                                    <i class="fa-solid fa-circle-nodes text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-amber-300 shrink-0">Connected:</span>
                                    <span class="text-white font-extrabold">${metadata.subgraph ? metadata.subgraph.node_count : 'Active'}</span>
                                </div>
                            </div>
                        ` : (metadata && metadata.query_mode === 'mode_c' ? `
                            <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-sans">
                                <div class="flex items-center gap-1.5 text-accentPurple font-bold min-w-0">
                                    <i class="fa-solid fa-arrow-up-long text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-purple-300 shrink-0">Prerequisites:</span>
                                    <span class="text-gray-200 font-semibold truncate max-w-[140px] sm:max-w-[220px]">${escapeHTML(prereqNames)}</span>
                                </div>
                                <i class="fa-solid fa-angles-right text-amber-400/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-amber-300 font-extrabold min-w-0">
                                    <i class="fa-solid fa-graduation-cap text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-amber-300 shrink-0">Target:</span>
                                    <span class="text-white font-extrabold underline decoration-amber-400/50 underline-offset-2 truncate max-w-[140px] sm:max-w-[180px]">${escapeHTML(anchorLabel)}</span>
                                </div>
                                <i class="fa-solid fa-angles-right text-emerald-400/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-emerald-400 font-bold min-w-0">
                                    <i class="fa-solid fa-arrow-down-long text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-emerald-300 shrink-0">Unlocks:</span>
                                    <span class="text-gray-200 font-semibold truncate max-w-[140px] sm:max-w-[220px]">${escapeHTML(unlockNames)}</span>
                                </div>
                            </div>
                        ` : `
                            <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-sans">
                                <div class="flex items-center gap-1.5 text-accentPurple font-bold min-w-0">
                                    <i class="fa-solid fa-arrow-up-long text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-purple-300 shrink-0">Requires:</span>
                                    <span class="text-gray-200 font-semibold truncate max-w-[140px] sm:max-w-[220px]">${escapeHTML(prereqNames)}</span>
                                </div>
                                <i class="fa-solid fa-angles-right text-amber-400/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-amber-300 font-extrabold min-w-0">
                                    <i class="fa-solid fa-bullseye text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-amber-300 shrink-0">Target:</span>
                                    <span class="text-white font-extrabold underline decoration-amber-400/50 underline-offset-2 truncate max-w-[140px] sm:max-w-[180px]">${escapeHTML(anchorLabel)}</span>
                                </div>
                                <i class="fa-solid fa-angles-right text-emerald-400/60 text-xs hidden sm:inline-block"></i>
                                <div class="flex items-center gap-1.5 text-emerald-400 font-bold min-w-0">
                                    <i class="fa-solid fa-arrow-down-long text-xs shrink-0"></i>
                                    <span class="text-[10px] uppercase tracking-wider text-emerald-300 shrink-0">Unlocks:</span>
                                    <span class="text-gray-200 font-semibold truncate max-w-[140px] sm:max-w-[220px]">${escapeHTML(unlockNames)}</span>
                                </div>
                            </div>
                        `)}

                        <!-- Wide Horizontal SVG Canvas Map (Proper Interactive Scrollable Multi-Hop Topology Graph) -->
                        <div class="relative w-full group/hgraph">
                            <div class="scrollable-graph-container w-full h-64 rounded-xl glass-light border border-white/10 relative overflow-x-auto overflow-y-hidden shadow-inner custom-scrollbar" id="hgraph-canvas-${cardId}">
                                <div class="graph-ripple-bg" id="hgraph-ripple-${cardId}"></div>
                                <svg id="svg-horizontal-${cardId}" style="height: 100%; display: block;"></svg>
                            </div>
                            <!-- Interactive Scrollable Arrows to move across nodes smoothly -->
                            <button type="button" onclick="scrollInChatGraph('${cardId}', -200)" class="absolute left-2.5 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-black/80 hover:bg-black/95 text-white/90 hover:text-white border border-white/20 hover:border-accentPurple/60 backdrop-blur-md flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110 active:scale-95 cursor-pointer" title="Scroll left across prerequisite nodes" aria-label="Scroll left">
                                <i class="fa-solid fa-chevron-left text-sm"></i>
                            </button>
                            <button type="button" onclick="scrollInChatGraph('${cardId}', 200)" class="absolute right-2.5 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-black/80 hover:bg-black/95 text-white/90 hover:text-white border border-white/20 hover:border-emerald-400/60 backdrop-blur-md flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110 active:scale-95 cursor-pointer" title="Scroll right across unlock nodes" aria-label="Scroll right">
                                <i class="fa-solid fa-chevron-right text-sm"></i>
                            </button>
                        </div>

                        <!-- Card Inspector (Active Node Info) -->
                        <div id="node-info-${cardId}" class="p-3.5 rounded-xl glass-glow border border-accentPurple/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gradient-to-r from-accentPurple/10 via-black/40 to-accentPink/10">
                            <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-2">
                                    <span id="node-info-badge-${cardId}" class="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase bg-accentPurple/25 text-accentPurple border border-accentPurple/40 shadow-sm">Target Concept</span>
                                    <span id="node-info-diff-${cardId}" class="text-[9px] text-amber-300 font-mono font-bold">${escapeHTML((anchor && anchor.difficulty) || 'Foundational')}</span>
                                </div>
                                <h5 id="node-info-title-${cardId}" class="text-sm font-extrabold text-white mt-1 truncate">${escapeHTML(anchorLabel)}</h5>
                                <p id="node-info-summary-${cardId}" class="text-xs text-gray-300 leading-snug mt-0.5 line-clamp-2">${escapeHTML(anchorSummary)}</p>
                            </div>
                            <button id="node-info-btn-${cardId}" onclick="autoPrompt('Tell me about ${escapeHTML(anchorLabel)}')" type="button" class="px-3.5 py-2 rounded-lg bg-accentPurple text-white text-xs font-bold hover:bg-accentPurple/80 transition-all flex items-center justify-center gap-1.5 shrink-0 shadow-md shadow-accentPurple/30">
                                <i class="fa-solid fa-magnifying-glass text-xs"></i> <span>Explore Node</span>
                            </button>
                        </div>

                        <!-- OKF Key Relationships Badge Grid -->
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-2.5 text-xs">
                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10 space-y-1.5">
                                <span class="text-[10px] font-extrabold text-accentPurple uppercase tracking-wider flex items-center gap-1">
                                    <i class="fa-solid fa-arrow-up text-accentPurple"></i> REQUIRES (PREREQUISITES)
                                </span>
                                <div id="okf-card-req-${cardId}" class="flex flex-wrap gap-1.5"></div>
                            </div>

                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10 space-y-1.5">
                                <span class="text-[10px] font-extrabold text-emerald-400 uppercase tracking-wider flex items-center gap-1">
                                    <i class="fa-solid fa-arrow-down text-emerald-400"></i> UNLOCKS (ENABLES)
                                </span>
                                <div id="okf-card-unl-${cardId}" class="flex flex-wrap gap-1.5"></div>
                            </div>

                            <div class="p-2.5 rounded-xl bg-white/5 border border-white/10 space-y-1.5">
                                <span class="text-[10px] font-extrabold text-accentCyan uppercase tracking-wider flex items-center gap-1">
                                    <i class="fa-solid fa-link text-accentCyan"></i> CONNECTS (USES / PART OF)
                                </span>
                                <div id="okf-card-con-${cardId}" class="flex flex-wrap gap-1.5"></div>
                            </div>
                        </div>
                    </div>
                    <!-- Switchboard lightgrid strip below graph card -->
                    <div class="graph-card-lightgrid" id="lightgrid-${cardId}"></div>
                </div>
            `;

            // Compute effective prerequisites (do not leave empty if curriculum chain or defaults exist)
            let effectivePrereqs = (prereqs && prereqs.length) ? prereqs.slice() : [];
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
            prereqs = effectivePrereqs;

            // Show ALL graph nodes (not restricted to slice(0, 3))
            const reqDiv = document.getElementById(`okf-card-req-${cardId}`);
            const unlDiv = document.getElementById(`okf-card-unl-${cardId}`);
            const conDiv = document.getElementById(`okf-card-con-${cardId}`);

            const activePrereqs = (prereqs || []);
            const activeUnlocks = (unlocks || []);
            const activeRelated = (related || []);

            const makeCardBadge = (item, colorCls) => {
                const span = document.createElement('span');
                span.className = `px-2 py-1 rounded-lg border cursor-pointer hover:scale-105 transition-all text-[10px] font-bold ${colorCls}`;
                span.textContent = _nodeLabel(item);
                span.title = _nodeSummary(item) || _nodeLabel(item);
                span.onclick = () => selectHorizontalNode(cardId, _nodeId(item), item, anchor, prereqs, unlocks, related);
                return span;
            };
            const emptyBadge = () => { const s = document.createElement('span'); s.className = 'text-[10px] text-gray-500 italic'; s.textContent = 'None indexed'; return s; };

            if (reqDiv) {
                reqDiv.innerHTML = '';
                if (activePrereqs.length) activePrereqs.forEach(p => reqDiv.appendChild(makeCardBadge(p, 'text-accentPurple border-accentPurple/40 bg-accentPurple/15 hover:bg-accentPurple/25')));
                else reqDiv.appendChild(emptyBadge());
            }
            if (unlDiv) {
                unlDiv.innerHTML = '';
                if (activeUnlocks.length) activeUnlocks.forEach(u => unlDiv.appendChild(makeCardBadge(u, 'text-emerald-300 border-emerald-400/40 bg-emerald-400/15 hover:bg-emerald-400/25')));
                else unlDiv.appendChild(emptyBadge());
            }
            if (conDiv) {
                conDiv.innerHTML = '';
                if (activeRelated.length) activeRelated.forEach(r => conDiv.appendChild(makeCardBadge(r, 'text-cyan-300 border-cyan-400/40 bg-cyan-400/15 hover:bg-cyan-400/25')));
                else conDiv.appendChild(emptyBadge());
            }


            // Draw horizontal SVG map
            requestAnimationFrame(() => {
                setTimeout(() => {
                    const svgEl = document.getElementById(`svg-horizontal-${cardId}`);
                    if (svgEl) {
                        drawHorizontalSVG(svgEl, anchor, prereqs, unlocks, related, cardId, metadata);
                    }
                }, 40);
            });

            // ── Premium effects on graph card ──

            // D. SwitchboardCard lightgrid animation
            const lgGrid = document.getElementById(`lightgrid-${cardId}`);
            if (lgGrid) {
                const COLS = 28, ROWS = 3, total = COLS * ROWS;
                const bulbs = [], states = new Array(total).fill(0);
                for (let i = 0; i < total; i++) {
                    const b = document.createElement('div');
                    b.className = 'sw-bulb';
                    lgGrid.appendChild(b);
                    bulbs.push(b);
                }
                const tick = () => {
                    if (!lgGrid.isConnected) { clearInterval(lgTimer); return; }
                    const n = Math.floor(total * 0.18);
                    Array.from({ length: total }, (_, i) => i)
                        .sort(() => Math.random() - 0.5)
                        .slice(0, n)
                        .forEach(i => {
                            states[i] = states[i] === 0 ? 1 : states[i] === 1 ? 2 : 0;
                            bulbs[i].className = 'sw-bulb' + (states[i] === 1 ? ' medium' : states[i] === 2 ? ' high' : '');
                        });
                };
                const lgTimer = setInterval(tick, 220);
                tick();
            }

            // F. Hover-3D tilt on concept-visualize-card
            const vizCard = cardWrapper.querySelector('.concept-visualize-card');
            if (vizCard) {
                vizCard.addEventListener('mousemove', (e) => {
                    const rect = vizCard.getBoundingClientRect();
                    const cx = rect.left + rect.width / 2;
                    const cy = rect.top + rect.height / 2;
                    const rx = (e.clientY - cy) / rect.height * -6;
                    const ry = (e.clientX - cx) / rect.width * 6;
                    vizCard.style.transform = `perspective(900px) rotateX(${rx.toFixed(1)}deg) rotateY(${ry.toFixed(1)}deg)`;
                }, { passive: true });
                vizCard.addEventListener('mouseleave', () => {
                    vizCard.style.transform = 'perspective(900px) rotateX(0) rotateY(0)';
                }, { passive: true });
            }

            // I. Interactive Line Ripple background on graph canvas + wheel scroll passthrough
            const hCanvas = document.getElementById(`hgraph-canvas-${cardId}`);
            const hRipple = document.getElementById(`hgraph-ripple-${cardId}`);
            if (hRipple && hCanvas) _initGraphRipple(hRipple, hCanvas);
            if (hCanvas) {
                hCanvas.addEventListener('wheel', (e) => {
                    const chatMsgs = document.getElementById('chat-messages');
                    if (chatMsgs && Math.abs(e.deltaY) > 0) {
                        chatMsgs.scrollTop += e.deltaY;
                    }
                }, { passive: true });
            }
        }

        window.renderHorizontalGraphCard = renderHorizontalGraphCard;

        /**
         * Interactive Adaptive Leap-Back Diagnostic MCQ Layer (Mode C Prerequisite Verification)
         * Tests on-the-spot immediate prerequisite topic Y first.
         * 4 distinct HTML <input type="radio"> buttons.
         * Advance on correct (tick ✓). If 3 consecutive ticks, declare mastery & unlock target concept.
         * On incorrect (gap ✗): Leap back 2 hops towards foundational leaf node (skip-list stride).
         * Total questions bounded between 5 and 10 questions max.
         */
        window._adaptiveState = window._adaptiveState || {};

        window._diagnosticState = window._diagnosticState || {};

export { renderHorizontalGraphCard };
