import { storageKey } from './storage-key.js';
// Auto-split from ui/chat/index.html — 12-choose-graph-experience.js
// Feature module 13 of 22.
import { dismissGraphChoiceModal, getOrCreateInteractiveZone, showGraphChoiceModal } from './11-populate-topology.js';
import { _nodeId, _nodeLabel } from './10-populate-pipeline.js';
import { renderHorizontalGraphCard } from './13-render-horizontal-graph-card.js';
import { renderAdaptiveMCQCard } from './14-render-adaptive-mcqcard.js';
import { openReadingMode } from './06-open-book-or-unavailable.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { setReadingView } from './07-open-page-viewer-modal.js';

        function chooseGraphExperience(choice, explicitMsgId) {
            const ctx = window._activeChoiceContext || {};
            const msgId = explicitMsgId || ctx.msgId;
            const metadata = ctx.metadata || window._lastChatMetadata;
            dismissGraphChoiceModal();

            if (!msgId || !metadata) return;
            const anchor = metadata.anchor_concept;
            const anchorId = _nodeId(anchor);

            try {
                localStorage.setItem(storageKey('archipelago_choice_' + anchorId), choice);
            } catch (_) {}

            try {
                fetch('/api/chat/telemetry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ event: 'graph_choice', mode: choice, concept_id: anchorId })
                }).catch(() => {});
            } catch (_) {}

            const promptEl = document.getElementById(`interactive-prompt-${msgId}`);
            if (promptEl) {
                promptEl.classList.add('swipe-out-left');
            }

            setTimeout(() => {
                if (choice === 'personalized') {
                    startPersonalizedQnA(msgId, metadata);
                } else {
                    renderHorizontalGraphCard(msgId, metadata);
                }
            }, 200);
        }

        window.chooseGraphExperience = chooseGraphExperience;

        function renderGraphExperiencePrompt(msgId, metadata, options = {}) {
            if (window.showGraphCards === false) return;
            if (!metadata || !metadata.anchor_concept) return;
            const route = (metadata.routing && metadata.routing.route) || metadata.contract || '';
            // Administrative, inventory, or guardrail queries remain uncluttered without concept graphs
            if (route === 'CATALOG_SHELF_ROUTING' || route === 'AUTH_GATEWAY' || route === 'GUARDRAIL_INTERCEPT') {
                dismissGraphChoiceModal();
                return;
            }

            const anchorId = _nodeId(metadata.anchor_concept);
            let savedChoice = null;
            try { savedChoice = localStorage.getItem(storageKey('archipelago_choice_' + anchorId)); } catch (_) {}
            const isDiagnostic = route === 'MCQ_DIAGNOSTIC' || options.forceDiagnostic || metadata.wants_quiz || metadata.query_mode === 'personalized';

            if (isDiagnostic) {
                if (savedChoice === 'personalized') {
                    dismissGraphChoiceModal();
                    startPersonalizedQnA(msgId, metadata);
                } else if (savedChoice === 'normal') {
                    dismissGraphChoiceModal();
                    renderHorizontalGraphCard(msgId, metadata);
                } else {
                    showGraphChoiceModal(msgId, metadata);
                }
                return;
            }

            // Pure GRAPH_SYNTHESIS or standard exploratory queries render Graph 2 directly
            dismissGraphChoiceModal();
            renderHorizontalGraphCard(msgId, metadata);
        }

        window.renderGraphExperiencePrompt = renderGraphExperiencePrompt;

        async function startPersonalizedQnA(msgId, metadata) {
            const anchor = metadata.anchor_concept;
            const anchorId = _nodeId(anchor);
            const anchorLabel = _nodeLabel(anchor) || 'Target Concept';
            const zone = getOrCreateInteractiveZone(msgId);
            if (!zone) return;
            try {
                const saved = localStorage.getItem(storageKey('archipelago_eval_' + anchorId));
                if (saved) {
                    const { renderPersonalizedGraphCard } = await import('./16-render-personalized-graph-ca.js');
                    renderPersonalizedGraphCard(msgId, JSON.parse(saved), metadata);
                    return;
                }
            } catch (_) {}

            zone.innerHTML = `
                <div id="skel-mcq-${msgId}" class="diagnostic-mcq-card p-5 space-y-4 animate-pulse border border-accentPurple/30 rounded-2xl bg-panelBg/95 swipe-in-right">
                    <div class="flex items-center justify-between pb-3 border-b border-white/10">
                        <div class="flex items-center gap-2.5">
                            <div class="w-8 h-8 rounded-xl bg-accentPurple/30"></div>
                            <div class="space-y-1">
                                <div class="h-3.5 w-48 rounded bg-white/20"></div>
                                <div class="h-2.5 w-64 rounded bg-white/10"></div>
                            </div>
                        </div>
                        <div class="h-6 w-24 rounded bg-white/10"></div>
                    </div>
                    <div class="space-y-3">
                        <div class="p-4 rounded-xl bg-white/5 space-y-2">
                            <div class="h-3 w-1/3 rounded bg-white/20"></div>
                            <div class="h-3 w-4/5 rounded bg-white/10"></div>
                            <div class="mcq-options-grid mt-3">
                                <div class="h-12 rounded-xl bg-white/5"></div>
                                <div class="h-12 rounded-xl bg-white/5"></div>
                                <div class="h-12 rounded-xl bg-white/5"></div>
                                <div class="h-12 rounded-xl bg-white/5"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            try {
                const resp = await fetch(`/api/chat/diagnostic-mcqs?concept=${encodeURIComponent(anchorId)}`);
                const data = await resp.json();

                if (resp.ok && data.completed && data.evaluation) {
                    const { renderPersonalizedGraphCard } = await import('./16-render-personalized-graph-ca.js');
                    try { localStorage.setItem(storageKey('archipelago_eval_' + anchorId), JSON.stringify(data.evaluation)); } catch (_) {}
                    renderPersonalizedGraphCard(msgId, data.evaluation, metadata);
                    return;
                }

                if (data && data.success !== false && (data.initial_question || (data.mcqs && data.mcqs.length))) {
                    window._adaptiveState = window._adaptiveState || {};
                    const initialQ = data.initial_question || data.mcqs[0];
                    window._adaptiveState[msgId] = {
                        metadata: metadata,
                        target_concept: data.target_concept || anchorId,
                        target_label: anchorLabel,
                        chain: data.chain || [],
                        prereq_chain: data.prereq_chain || [],
                        immediate_prerequisite: data.immediate_prerequisite,
                        current_concept: (initialQ && initialQ.concept_id) || data.immediate_prerequisite || anchorId,
                        current_mcq: initialQ,
                        consecutive_ticks: 0,
                        question_count: 1,
                        max_questions: 10,
                        min_questions: 3,
                        history: [],
                        eval_stack: data.eval_stack || [],
                        mastered: [],
                        gaps: [],
                        selected_option: null,
                        submitted: false
                    };
                    try {
                        sessionStorage.setItem(storageKey('archipelago_adaptive_' + msgId), JSON.stringify(window._adaptiveState[msgId]));
                    } catch (_) {}

                    // Hide evidence rail (resources) while quiz is active
                    const msgEl = document.getElementById(`msg-body-${msgId}`);
                    if (msgEl) {
                        const rail = msgEl.querySelector('.evidence-rail');
                        if (rail) rail.classList.add('hidden');
                        const inv = msgEl.querySelector('.library-inventory-section');
                        if (inv) inv.classList.add('hidden');
                    }

                    renderAdaptiveMCQCard(msgId);
                } else {
                    renderHorizontalGraphCard(msgId, metadata);
                }
            } catch (err) {
                console.error('Error fetching diagnostic MCQs:', err);
                renderHorizontalGraphCard(msgId, metadata);
            }
        }

        window.startPersonalizedQnA = startPersonalizedQnA;

        function switchToPersonalizedGraph(msgId) {
            const completed = window._adaptiveState && window._adaptiveState[msgId];
            if (completed && completed.finished) {
                startPersonalizedQnA(msgId, completed.metadata);
                return;
            }
            if (completed && completed.submitted && completed.next_question) {
                window.advanceAdaptiveStep(msgId);
                return;
            }
            // 1. Check if an active quiz state exists in memory — RESUME without resetting to Q1!
            const state = (window._adaptiveState && window._adaptiveState[msgId]);
            if (state && state.current_mcq) {
                const anchorId = state.target_concept || (state.metadata && _nodeId(state.metadata.anchor_concept));
                try { localStorage.setItem(storageKey('archipelago_choice_' + anchorId), 'personalized'); } catch (_) {}
                const zone = getOrCreateInteractiveZone(msgId);
                if (zone) {
                    zone.innerHTML = '';
                    renderAdaptiveMCQCard(msgId);
                    // Hide resources while quiz is active
                    const msgEl = document.getElementById(`msg-body-${msgId}`);
                    if (msgEl) {
                        const rail = msgEl.querySelector('.evidence-rail');
                        if (rail) rail.classList.add('hidden');
                        const inv = msgEl.querySelector('.library-inventory-section');
                        if (inv) inv.classList.add('hidden');
                    }
                }
                return;
            }

            // 2. Check sessionStorage for persisted quiz progress
            try {
                const saved = sessionStorage.getItem(storageKey('archipelago_adaptive_' + msgId));
                if (saved) {
                    const parsed = JSON.parse(saved);
                    if (parsed && parsed.current_mcq) {
                        window._adaptiveState = window._adaptiveState || {};
                        window._adaptiveState[msgId] = parsed;
                        if (parsed.submitted && parsed.next_question) {
                            window.advanceAdaptiveStep(msgId);
                            return;
                        }
                        const zone = getOrCreateInteractiveZone(msgId);
                        if (zone) {
                            zone.innerHTML = '';
                            renderAdaptiveMCQCard(msgId);
                            const msgEl = document.getElementById(`msg-body-${msgId}`);
                            if (msgEl) {
                                const rail = msgEl.querySelector('.evidence-rail');
                                if (rail) rail.classList.add('hidden');
                                const inv = msgEl.querySelector('.library-inventory-section');
                                if (inv) inv.classList.add('hidden');
                            }
                            return;
                        }
                    }
                }
            } catch (_) {}

            // 3. Fall back to fresh start only if no quiz in progress
            const meta = (state && state.metadata) || window._lastChatMetadata;
            if (meta) {
                const anchorId = _nodeId(meta.anchor_concept);
                try { localStorage.setItem(storageKey('archipelago_choice_' + anchorId), 'personalized'); } catch (_) {}
                startPersonalizedQnA(msgId, meta);
            }
        }

        window.switchToPersonalizedGraph = switchToPersonalizedGraph;

        function switchToNormalGraph(msgId) {
            const state = (window._adaptiveState && window._adaptiveState[msgId]) || (window._diagnosticState && window._diagnosticState[msgId]);
            const meta = (state && state.metadata) || window._lastChatMetadata;
            if (meta) {
                const anchorId = _nodeId(meta.anchor_concept);
                try { localStorage.setItem(storageKey('archipelago_choice_' + anchorId), 'normal'); } catch (_) {}
                // Unhide resources when viewing full normal graph
                const msgEl = document.getElementById(`msg-body-${msgId}`);
                if (msgEl) {
                    const rail = msgEl.querySelector('.evidence-rail');
                    if (rail) rail.classList.remove('hidden');
                    const inv = msgEl.querySelector('.library-inventory-section');
                    if (inv) inv.classList.remove('hidden');
                }
                renderHorizontalGraphCard(msgId, meta);
            }
        }

        window.switchToNormalGraph = switchToNormalGraph;

        function openPrerequisiteRemediationReader(docId, pageNum, conceptName, summary) {
            const pdfPath = docId ? (docId.startsWith('/') ? docId : '/' + docId) : '';
            const fullPdf = pdfPath ? `/pdfs${pdfPath}#page=${pageNum || 1}&zoom=page-fit` : '';
            if (typeof openReadingMode === 'function') {
                openReadingMode({
                    title: `Prerequisite Review: ${conceptName}`,
                    type: 'textbook',
                    pdf: fullPdf,
                    page: pageNum || 1,
                    preferSummary: !fullPdf,
                    preferSplit: false,
                    hideViewToggle: !!fullPdf,
                    content: `
                        <div class="space-y-3 p-3">
                            <div class="passage-meta-card p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                                <span class="text-[10px] uppercase font-bold text-amber-300">Prerequisite Knowledge Gap</span>
                                <h4 class="text-sm font-bold text-white mt-1">${escapeHTML(conceptName)}</h4>
                                <p class="text-xs text-gray-300 mt-1">Textbook Page Citation: ${docId || 'Core Corpus'} p. ${pageNum || 1}</p>
                            </div>
                            <div class="p-4 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-200 leading-relaxed">
                                ${escapeHTML(summary || 'Review foundational concept prerequisites to bridge your understanding.')}
                            </div>
                        </div>
                    `
                });
                if (fullPdf && typeof setReadingView === 'function') {
                    setReadingView('pdf');
                } else if (typeof setReadingView === 'function') {
                    setReadingView('summary');
                }
            }
        }

        window.openPrerequisiteRemediationReader = openPrerequisiteRemediationReader;

        document.addEventListener('keydown', (e) => {
            const modal = document.getElementById('graph-choice-modal');
            if (modal && !modal.classList.contains('hidden')) {
                if (e.key === 'Escape') {
                    dismissGraphChoiceModal();
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                    const cardP = document.getElementById('choice-card-personalized');
                    if (cardP) cardP.focus();
                } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                    const cardN = document.getElementById('choice-card-normal');
                    if (cardN) cardN.focus();
                } else if (e.key === 'Enter') {
                    const activeEl = document.activeElement;
                    if (activeEl && activeEl.id === 'choice-card-personalized') {
                        chooseGraphExperience('personalized');
                    } else if (activeEl && activeEl.id === 'choice-card-normal') {
                        chooseGraphExperience('normal');
                    }
                }
            }
        });

export { chooseGraphExperience, openPrerequisiteRemediationReader, renderGraphExperiencePrompt, startPersonalizedQnA, switchToNormalGraph, switchToPersonalizedGraph };
