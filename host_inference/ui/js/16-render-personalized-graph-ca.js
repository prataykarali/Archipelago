// Auto-split from ui/chat/index.html — 16-render-personalized-graph-ca.js
// Feature module 17 of 22.
import { getOrCreateInteractiveZone } from './11-populate-topology.js';
import { _nodeLabel } from './10-populate-pipeline.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { drawPersonalizedSVG } from './17-draw-personalized-svg.js';

        // ── Personalized Knowledge Graph Card Rendering ──
        function renderPersonalizedGraphCard(msgId, evalData, metadata) {
            const zone = getOrCreateInteractiveZone(msgId);
            if (!zone) return;

            const cardId = `pers-graph-${msgId}`;
            let cardWrapper = document.getElementById(`visualize-card-${cardId}`);
            if (!cardWrapper) {
                cardWrapper = document.createElement('div');
                cardWrapper.id = `visualize-card-${cardId}`;
                cardWrapper.className = 'personalized-graph-card-wrapper w-full swipe-in-right';
                zone.innerHTML = '';
                zone.appendChild(cardWrapper);
            }

            const anchor = metadata ? metadata.anchor_concept : (evalData ? evalData.target_concept : null);
            const anchorLabel = _nodeLabel(anchor) || 'Target Concept';
            const baseline = (evalData?.personalized_graph?.nodes || []).filter(n => n.status === 'mastered').map(n => n.label).join(', ');
            const score = evalData ? evalData.score : '0/3';
            const isZero = evalData ? evalData.zero_score : false;
            const isFull = evalData ? evalData.full_score : false;

            const pGraph = (evalData && evalData.personalized_graph) || { nodes: [], edges: [] };
            const nodes = pGraph.nodes || [];
            const gapNodes = nodes.filter(n => ['review_gap', 'missing', 'fading'].includes(n.status));
            const targetNode = nodes.find(n => n.role === 'target') || { label: anchorLabel, summary: '' };

            let statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300">Score: ${score} · Targeted Remediation</span>`;
            if (isFull) {
                statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">Score: ${score} · Fully Unlocked</span>`;
            } else if (isZero) {
                statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/20 border border-rose-500/40 text-rose-300">Score: ${score} · Foundational Bridge</span>`;
            }

            cardWrapper.innerHTML = `
                <div class="concept-visualize-card border border-accentPurple/30 rounded-2xl bg-panelBg/95 shadow-xl overflow-hidden">
                    <!-- Header bar with Normal Graph switcher -->
                    <div class="w-full px-4 py-3 flex items-center justify-between bg-white/5 border-b border-white/10">
                        <div class="flex items-center gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-accentPurple/25 border border-accentPurple/40 flex items-center justify-center text-accentPurple shrink-0">
                                <i class="fa-solid fa-graduation-cap text-sm"></i>
                            </div>
                            <div class="flex flex-col text-left min-w-0">
                                <span class="font-extrabold text-white text-xs tracking-tight flex items-center gap-2">
                                    Personalized Knowledge Graph
                                    <span class="px-2 py-0.5 rounded-full bg-accentPurple/25 border border-accentPurple/40 text-[10px] text-accentPurple font-mono font-bold truncate max-w-[140px] sm:max-w-[200px]">${escapeHTML(anchorLabel)}</span>
                                </span>
                                <span class="text-[10px] text-gray-400 font-medium">Adaptive learning pathway derived from your diagnostic answers</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 shrink-0">
                            ${statusPill}
                            <button onclick="switchToNormalGraph('${msgId}')" type="button" class="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/20 border border-white/20 text-gray-200 text-[10px] font-bold transition-all flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-diagram-project text-[10px]"></i>
                                <span>View Normal Graph</span>
                            </button>
                        </div>
                    </div>

                    <!-- Card Body -->
                    <div class="p-4 space-y-4">
                        <!-- Pedagogical Flow Breadcrumb -->
                        <div class="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs">
                            <div class="flex items-center gap-1.5 text-amber-300 font-bold">
                                <i class="fa-solid fa-triangle-exclamation text-xs"></i>
                                <span class="text-[10px] uppercase tracking-wider text-amber-300">Gaps to Review:</span>
                                <span class="text-white font-extrabold">${gapNodes.length ? gapNodes.map(n => escapeHTML(n.label)).join(', ') : 'No assessed gaps'}</span>
                            </div>
                            <i class="fa-solid fa-angles-right text-accentPurple/60 text-xs hidden sm:inline-block"></i>
                            <div class="flex items-center gap-1.5 text-emerald-400 font-bold">
                                <i class="fa-solid fa-circle-check text-xs"></i>
                                <span class="text-[10px] uppercase tracking-wider text-emerald-300">Mastered Baseline:</span>
                                <span class="text-white font-extrabold">${escapeHTML(baseline || 'None')}</span>
                            </div>
                            <i class="fa-solid fa-angles-right text-amber-400/60 text-xs hidden sm:inline-block"></i>
                            <div class="flex items-center gap-1.5 text-amber-300 font-extrabold">
                                <i class="fa-solid fa-bullseye text-xs"></i>
                                <span class="text-[10px] uppercase tracking-wider text-amber-300">Target Goal:</span>
                                <span class="text-white font-extrabold underline decoration-amber-400/50">${escapeHTML(anchorLabel)}</span>
                            </div>
                        </div>

                        <!-- Personalized Interactive SVG Canvas Map (Proper Interactive Scrollable Multi-Hop Topology Graph) -->
                        <div class="relative w-full group/persgraph">
                            <div class="scrollable-graph-container w-full h-64 rounded-xl glass-light border border-white/10 relative overflow-x-auto overflow-y-hidden shadow-inner custom-scrollbar" id="pers-canvas-${cardId}">
                                <svg id="svg-pers-${cardId}" style="height: 100%; display: block;"></svg>
                            </div>
                            <!-- Interactive Scrollable Arrows to move across nodes smoothly -->
                            <button type="button" onclick="scrollInChatGraph('${cardId}', -200)" class="absolute left-2.5 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-black/80 hover:bg-black/95 text-white/90 hover:text-white border border-white/20 hover:border-amber-400/60 backdrop-blur-md flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110 active:scale-95 cursor-pointer" title="Scroll left" aria-label="Scroll left">
                                <i class="fa-solid fa-chevron-left text-sm"></i>
                            </button>
                            <button type="button" onclick="scrollInChatGraph('${cardId}', 200)" class="absolute right-2.5 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-black/80 hover:bg-black/95 text-white/90 hover:text-white border border-white/20 hover:border-sky-400/60 backdrop-blur-md flex items-center justify-center shadow-lg transition-all duration-200 hover:scale-110 active:scale-95 cursor-pointer" title="Scroll right" aria-label="Scroll right">
                                <i class="fa-solid fa-chevron-right text-sm"></i>
                            </button>
                        </div>

                        <!-- Active Node Inspector with Click-to-Reader Deep Link & Micro-Actions -->
                        <div id="pers-inspector-${cardId}" class="p-3.5 rounded-xl glass-glow border border-accentPurple/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gradient-to-r from-accentPurple/10 via-black/40 to-accentPink/10">
                            <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-2">
                                    <span id="pers-insp-badge-${cardId}" class="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm">
                                        ${gapNodes.length ? 'Review / Unverified Node' : 'Selected Node'}
                                    </span>
                                    <span id="pers-insp-citation-${cardId}" class="text-[10px] text-gray-400 font-mono">Click any node on the graph above to inspect literature citations</span>
                                </div>
                                <h5 id="pers-insp-title-${cardId}" class="text-sm font-extrabold text-white mt-1 truncate">
                                    ${escapeHTML((gapNodes[0] || targetNode).label)}
                                </h5>
                                <p id="pers-insp-summary-${cardId}" class="text-xs text-gray-300 leading-snug mt-0.5 line-clamp-2">
                                    ${escapeHTML((gapNodes[0] || targetNode).summary || 'Foundational prerequisite component in this curriculum pathway.')}
                                </p>
                            </div>
                            <div id="pers-insp-actions-${cardId}" class="flex items-center gap-2 shrink-0">
                                ${(gapNodes[0] && gapNodes[0].doc_id) ? `
                                    <button onclick="openPrerequisiteRemediationReader('${gapNodes[0].doc_id}', ${gapNodes[0].page_number || 1}, '${escapeHTML(gapNodes[0].label)}', '${escapeHTML(gapNodes[0].summary)}')" type="button" class="px-3 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer shadow-sm">
                                        <i class="fa-solid fa-book-open text-xs"></i> <span>View Textbook (p. ${gapNodes[0].printed_page || gapNodes[0].page_number || 1})</span>
                                    </button>
                                ` : ''}
                                <button onclick="autoPrompt('Explain prerequisite concept ${escapeHTML((gapNodes[0] || targetNode).label)} for mastering ${escapeHTML(anchorLabel)}')" type="button" class="px-3 py-2 rounded-lg bg-accentPurple hover:bg-accentPurple/80 text-white font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer shadow-md shadow-accentPurple/25">
                                    <i class="fa-solid fa-comment-dots text-xs"></i> <span>Explain Gap</span>
                                </button>
                            </div>
                        </div>

                        <!-- Structured Step-by-Step Curriculum Roadmap -->
                        ${evalData.roadmap && evalData.roadmap.steps && evalData.roadmap.steps.length ? `
                            <div class="p-3.5 rounded-xl bg-white/5 border border-white/10 space-y-2.5">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-extrabold text-white flex items-center gap-1.5">
                                        <i class="fa-solid fa-route text-accentPurple"></i>
                                        Step-by-Step Learning Progression (${evalData.roadmap.hops} hops)
                                    </span>
                                    <span class="text-[10px] text-gray-400 font-mono">DAG Verified Path</span>
                                </div>
                                <div class="space-y-2">
                                    ${evalData.roadmap.steps.map((st, i) => `
                                        <div class="p-2.5 rounded-lg bg-black/40 border border-white/5 flex items-center justify-between gap-3 text-xs">
                                            <div class="flex items-center gap-2.5 min-w-0">
                                                <span class="w-5 h-5 rounded-full bg-accentPurple/20 text-accentPurple font-mono text-[10px] font-bold flex items-center justify-center shrink-0">${i + 1}</span>
                                                <div class="flex flex-col min-w-0">
                                                    <span class="font-bold text-white truncate">${escapeHTML(st.name || st.id)}</span>
                                                    <span class="text-[10px] text-gray-400 truncate">${escapeHTML(st.summary || '')}</span>
                                                </div>
                                            </div>
                                            <div class="flex items-center gap-2 shrink-0">
                                                ${st.doc_id ? `
                                                    <button onclick="openPrerequisiteRemediationReader('${st.doc_id}', ${st.page_number}, '${escapeHTML(st.name || st.id)}', '${escapeHTML(st.summary)}')" class="px-2 py-1 rounded bg-white/10 hover:bg-white/15 text-[10px] font-bold text-gray-300 hover:text-white transition-all flex items-center gap-1">
                                                        <i class="fa-solid fa-book-bookmark text-[9px]"></i> <span>p. ${st.printed_page || st.page_number}</span>
                                                    </button>
                                                ` : ''}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;

            requestAnimationFrame(() => {
                setTimeout(() => {
                    const svgEl = document.getElementById(`svg-pers-${cardId}`);
                    if (svgEl) {
                        drawPersonalizedSVG(svgEl, nodes, pGraph.edges || [], cardId, anchorLabel);
                    }
                }, 40);
            });
        }

        window.renderPersonalizedGraphCard = renderPersonalizedGraphCard;

export { renderPersonalizedGraphCard };
