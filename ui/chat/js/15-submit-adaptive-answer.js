import { renderGapResources } from './learning-memory.js';
// Auto-split from ui/chat/index.html — 15-submit-adaptive-answer.js
// Feature module 16 of 22.
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { getOrCreateInteractiveZone } from './11-populate-topology.js';
import { renderAdaptiveMCQCard } from './14-render-adaptive-mcqcard.js';
import { renderPersonalizedGraphCard } from './16-render-personalized-graph-ca.js';

        async function submitAdaptiveAnswer(msgId) {
            const state = window._adaptiveState[msgId];
            if (!state || !state.current_mcq) return;

            const checked = document.querySelector(`input[name="adaptive_radio_${msgId}"]:checked`);
            if (!checked) return;

            const userChoice = checked.value;
            const submitBtn = document.getElementById(`btn-submit-adaptive-${msgId}`);
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-xs"></i> <span>Evaluating...</span>';
            }

            // Disable radio inputs
            document.querySelectorAll(`input[name="adaptive_radio_${msgId}"]`).forEach(inp => {
                inp.disabled = true;
            });

            try {
                const resp = await fetch('/api/chat/adaptive-step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: state.session_id,
                        question_id: state.current_mcq.question_id,
                        confidence: document.getElementById(`adaptive-confidence-${msgId}`)?.value || 'medium',
                        preference: document.getElementById(`adaptive-preference-${msgId}`)?.value || state.preference || 'conceptual',
                        user_choice: userChoice
                    })
                });
                const data = await resp.json();
                if (!resp.ok || data.error) throw new Error(data.error || 'Diagnostic failed');
                state.preference = document.getElementById(`adaptive-preference-${msgId}`)?.value || state.preference;
                sessionStorage.setItem('archipelago_learning_preference', state.preference);
                const explanation = document.getElementById(`adaptive-explanation-${msgId}`);
                const citation = document.getElementById(`adaptive-citation-${msgId}`);
                if (explanation) explanation.textContent = [
                    data.misconception?.prompt,
                    data.current_record?.explanation
                ].filter(Boolean).join('\n\n');
                if (citation) citation.textContent = data.current_record?.citation || '';


                // Update styling of radio choices
                const isTick = data.is_tick;
                const rec = data.current_record || {};
                const correctAns = rec.correct_answer;

                ['A', 'B', 'C', 'D'].forEach(k => {
                    const lbl = document.getElementById(`adaptive-label-${msgId}-${k}`);
                    if (!lbl) return;
                    if (k === correctAns) {
                        lbl.classList.add('correct');
                    } else if (k === userChoice && !isTick) {
                        lbl.classList.add('incorrect');
                    }
                });

                // Reveal literature citation box
                const expEl = document.getElementById(`adaptive-exp-${msgId}`);
                if (expEl) expEl.classList.remove('hidden');

                // Update state
                state.consecutive_ticks = data.consecutive_ticks || 0;
                state.history = data.history || state.history || [];

                // Update tick boxes in header
                for (let i = 1; i <= 3; i++) {
                    const tBox = document.getElementById(`tick-box-${msgId}-${i}`);
                    if (tBox) {
                        if (state.consecutive_ticks >= i) {
                            tBox.className = 'w-5 h-5 rounded flex items-center justify-center font-bold text-xs border border-emerald-400 bg-emerald-500/30 text-emerald-300 shadow-sm';
                            tBox.textContent = '✓';
                        } else {
                            tBox.className = 'w-5 h-5 rounded flex items-center justify-center font-bold text-xs border border-white/20 bg-white/5 text-gray-500';
                            tBox.textContent = String(i);
                        }
                    }
                }

                const banner = document.getElementById(`adaptive-banner-${msgId}`);
                const btnContainer = document.getElementById(`adaptive-btn-container-${msgId}`);
                const hint = document.getElementById(`adaptive-hint-${msgId}`);

                if (data.completed) {
                    state.gap_resources = data.gap_resources || [];
                    state.submitted = true;
                    if (banner) {
                        banner.classList.remove('hidden');
                        if (data.evaluation?.passed === true) {
                            banner.className = 'rounded-xl p-4 bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-xs space-y-1 shadow-lg shadow-emerald-500/10';
                            banner.innerHTML = `
                                <div class="flex items-center gap-2 text-sm font-extrabold text-emerald-300">
                                    <i class="fa-solid fa-circle-check text-base"></i>
                                    <span>Assessed Prerequisites Confirmed</span>
                                </div>
                                <p class="text-emerald-200/90 text-xs">You demonstrated foundational mastery across prerequisites. The personalized curriculum graph for <strong>${escapeHTML(state.target_label)}</strong> is now generated below!</p>
                            `;
                        } else {
                            banner.className = 'rounded-xl p-4 bg-amber-500/20 border border-amber-500/40 text-amber-200 text-xs space-y-1 shadow-lg shadow-amber-500/10';
                            banner.innerHTML = `
                                <div class="flex items-center gap-2 text-sm font-extrabold text-amber-300">
                                    <i class="fa-solid fa-triangle-exclamation text-base"></i>
                                    <span>Diagnostic Complete (${data.total_asked || state.question_count} Questions). Targeted Review Ready</span>
                                </div>
                                <p class="text-amber-200/90 text-xs">Knowledge gaps mapped. Review the literature citations above and your personalized curriculum pathway below.</p>
                            `;
                        }
                    }

                    if (btnContainer) {
                        btnContainer.innerHTML = `
                            <button onclick="document.getElementById('visualize-card-pers-graph-${msgId}')?.scrollIntoView({behavior:'smooth'})" type="button" class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-accentPurple to-indigo-600 hover:brightness-110 text-white font-extrabold text-xs shadow-lg shadow-accentPurple/25 transition-all flex items-center gap-2 cursor-pointer">
                                <i class="fa-solid fa-graduation-cap text-xs"></i> <span>View Personalized Knowledge Graph</span>
                            </button>
                            <button onclick="switchToNormalGraph('${msgId}')" type="button" class="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-diagram-project text-xs"></i> <span>View Normal Graph</span>
                            </button>
                        `;
                    }
                    if (hint) hint.textContent = 'Assessment finished. Personalized topology rendered below.';

                    // Store evaluation for this browser tab only and render Personalized Graph
                    const evalData = data.evaluation || {
                        target_concept: state.target_concept,
                        score: `${state.history.filter(h => h.is_correct).length}/${state.history.length}`,
                        passed: false,
                        full_score: false,
                        personalized_graph: data.personalized_graph || {},
                    };
                    try {
                        sessionStorage.setItem('archipelago_eval_' + state.target_concept, JSON.stringify(evalData));
                        localStorage.setItem('archipelago_choice_' + state.target_concept, 'personalized');
                    } catch (_) {}

                    revealFinalCorrectQuestionAndFinish(msgId, data, evalData, state.metadata);

                } else {
                    // Not completed: store next question and render advance / leap-back button
                    state.next_concept = data.next_concept;
                    state.next_question = data.next_question;

                    if (btnContainer) {
                        if (data.stride_action === 'advance') {
                            btnContainer.innerHTML = `
                                <button onclick="advanceAdaptiveStep('${msgId}')" type="button" class="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs shadow-lg shadow-emerald-600/30 transition-all flex items-center gap-2 cursor-pointer">
                                    <i class="fa-solid fa-arrow-right text-xs"></i> <span>Advance Towards Target (Next Question)</span>
                                </button>
                                <button onclick="switchToNormalGraph('${msgId}')" type="button" class="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer">
                                    <i class="fa-solid fa-diagram-project text-xs"></i> <span>Skip / Normal Graph</span>
                                </button>
                            `;
                        } else {
                            btnContainer.innerHTML = `
                                <button onclick="advanceAdaptiveStep('${msgId}')" type="button" class="px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-extrabold text-xs shadow-lg shadow-amber-600/30 transition-all flex items-center gap-2 cursor-pointer">
                                    <i class="fa-solid fa-backward-step text-xs"></i> <span>Review Next Prerequisite</span>
                                </button>
                                <button onclick="switchToNormalGraph('${msgId}')" type="button" class="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer">
                                    <i class="fa-solid fa-diagram-project text-xs"></i> <span>Skip / Normal Graph</span>
                                </button>
                            `;
                        }
                    }
                    if (hint) {
                        hint.textContent = isTick ? 'Correct! Advancing towards target concept.' : 'A review gap was recorded. The next question checks remaining coverage.';
                    }
                }

            } catch (err) {
                console.error('Error in submitAdaptiveAnswer:', err);
                const hint = document.getElementById(`adaptive-hint-${msgId}`);
                if (hint) hint.textContent = err.message + ' You can restart or switch to Normal Graph.';
                document.querySelectorAll(`input[name="adaptive_radio_${msgId}"]`).forEach(input => { input.disabled = false; });
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fa-solid fa-rotate-right text-xs"></i> <span>Retry</span>';
                }
            }
        }

        window.submitAdaptiveAnswer = submitAdaptiveAnswer;

        function advanceAdaptiveStep(msgId) {
            const state = window._adaptiveState[msgId];
            if (!state || !state.next_question) return;

            // Swipe out current card before showing next
            const zone = getOrCreateInteractiveZone(msgId);
            const currentCard = zone ? zone.querySelector('.adaptive-card-content') : null;
            if (currentCard) {
                currentCard.classList.add('swipe-out-left');
                setTimeout(() => {
                    state.question_count += 1;
                    state.current_concept = state.next_concept;
                    state.current_mcq = state.next_question;
                    state.next_question = null;
                    state.selected_option = null;
                    state.submitted = false;
                    // Remove old card so renderAdaptiveMCQCard creates a fresh one with swipe-in
                    if (currentCard.parentNode) currentCard.parentNode.removeChild(currentCard);
                    renderAdaptiveMCQCard(msgId);
                }, 400);
            } else {
                state.question_count += 1;
                state.current_concept = state.next_concept;
                state.current_mcq = state.next_question;
                state.next_question = null;
                state.selected_option = null;
                state.submitted = false;
                renderAdaptiveMCQCard(msgId);
            }
        }

        window.advanceAdaptiveStep = advanceAdaptiveStep;

        // ── Final Correct Question Celebration + Transition to Graph ──
        function revealFinalCorrectQuestionAndFinish(msgId, completionData, evalData, metadata) {
            const zone = getOrCreateInteractiveZone(msgId);
            if (!zone) {
                renderPersonalizedGraphCard(msgId, evalData, metadata);
                        renderGapResources(getOrCreateInteractiveZone(msgId), window._adaptiveState[msgId]?.gap_resources);
                return;
            }

            // Swipe out current MCQ card
            const currentCard = zone.querySelector('.adaptive-card-content');
            if (currentCard) {
                currentCard.classList.add('swipe-out-left');
            }

            setTimeout(() => {
                zone.innerHTML = '';

                // Unhide evidence rail (resources) now that the quiz is complete
                const msgEl = document.getElementById(`msg-body-${msgId}`);
                if (msgEl) {
                    const rail = msgEl.querySelector('.evidence-rail');
                    if (rail) rail.classList.remove('hidden');
                    const inv = msgEl.querySelector('.library-inventory-section');
                    if (inv) inv.classList.remove('hidden');
                }

                const state = window._adaptiveState[msgId] || {};
                const finalQ = completionData.final_correct_question || null;
                const mastered = completionData.mastered || state.mastered || [];
                const gaps = completionData.gaps || state.gaps || [];
                const totalAsked = completionData.total_asked || state.question_count || 0;
                const targetLabel = state.target_label || metadata?.anchor_concept || 'Target';
                const isPassed = completionData.evaluation?.passed === true;

                // Celebration card
                const celebCard = document.createElement('div');
                celebCard.className = 'w-full swipe-in-scale';
                celebCard.innerHTML = `
                    <div class="rounded-2xl border ${isPassed ? 'border-emerald-500/40 bg-gradient-to-br from-emerald-950/60 to-emerald-900/20' : 'border-amber-500/40 bg-gradient-to-br from-amber-950/60 to-amber-900/20'} p-5 space-y-4 shadow-xl">
                        <!-- Status Header -->
                        <div class="flex items-center gap-3">
                            <div class="w-12 h-12 rounded-xl ${isPassed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'} flex items-center justify-center text-2xl">
                                <i class="fa-solid ${isPassed ? 'fa-trophy' : 'fa-flag-checkered'}"></i>
                            </div>
                            <div class="min-w-0 flex-1">
                                <div class="${isPassed ? 'text-emerald-300' : 'text-amber-300'} font-extrabold text-sm">
                                    ${isPassed ? 'Diagnostic Complete — Prerequisites Mastered!' : 'Diagnostic Complete — Knowledge Map Ready'}
                                </div>
                                <div class="text-gray-400 text-[11px] font-mono mt-0.5">
                                    ${totalAsked} questions · ${mastered.length} mastered · ${gaps.length} gap${gaps.length !== 1 ? 's' : ''} detected
                                </div>
                            </div>
                        </div>

                        ${finalQ ? `
                        <!-- Final Correct Question Highlight -->
                        <div class="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-2">
                            <div class="flex items-center gap-2 text-emerald-400 text-xs font-bold">
                                <i class="fa-solid fa-circle-check"></i>
                                <span>Final Correct Answer</span>
                            </div>
                            <div class="text-gray-200 text-xs leading-relaxed font-medium">${escapeHTML(finalQ.question || '')}</div>
                            <div class="flex items-center gap-2 mt-2">
                                <span class="px-2.5 py-1 rounded-lg bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 text-[11px] font-bold">
                                    <i class="fa-solid fa-check mr-1"></i>${escapeHTML(finalQ.correct_answer || '')}
                                </span>
                            </div>
                            ${finalQ.citation ? `<div class="text-gray-500 text-[10px] mt-1 italic">📚 ${escapeHTML(finalQ.citation)}</div>` : ''}
                        </div>` : ''}

                        ${mastered.length > 0 ? `
                        <!-- Mastered Concepts -->
                        <div class="flex flex-wrap gap-1.5">
                            ${mastered.map(c => `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">✓ ${escapeHTML(typeof c === 'string' ? c.replace(/_/g, ' ') : c)}</span>`).join('')}
                        </div>` : ''}

                        ${gaps.length > 0 ? `
                        <!-- Gaps -->
                        <div class="flex flex-wrap gap-1.5">
                            ${gaps.map(g => `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-rose-500/15 border border-rose-500/30 text-rose-400">✗ ${escapeHTML(typeof g === 'string' ? g.replace(/_/g, ' ') : g)}</span>`).join('')}
                        </div>` : ''}

                        <!-- Explore Graph Button -->
                        <button id="explore-graph-btn-${msgId}" type="button" class="w-full mt-2 px-4 py-3 rounded-xl bg-gradient-to-r ${isPassed ? 'from-emerald-600 to-teal-600 shadow-emerald-600/30' : 'from-accentPurple to-indigo-600 shadow-accentPurple/25'} hover:brightness-110 text-white font-extrabold text-xs shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer">
                            <i class="fa-solid fa-diagram-project text-sm"></i>
                            <span>Explore Your Personalized Knowledge Graph</span>
                        </button>
                    </div>
                `;
                zone.appendChild(celebCard);

                // Auto-transition after 1.8s OR on button click
                const exploreBtn = document.getElementById(`explore-graph-btn-${msgId}`);
                let transitioned = false;
                const doTransition = () => {
                    if (transitioned) return;
                    transitioned = true;
                    celebCard.classList.add('swipe-out-left');
                    setTimeout(() => {
                        zone.innerHTML = '';
                        renderPersonalizedGraphCard(msgId, evalData, metadata);
                        renderGapResources(getOrCreateInteractiveZone(msgId), window._adaptiveState[msgId]?.gap_resources);
                    }, 400);
                };
                if (exploreBtn) exploreBtn.addEventListener('click', doTransition);
                // Don't auto-transition, let user click the button to see the graph
            }, 450);
        }

        window.revealFinalCorrectQuestionAndFinish = revealFinalCorrectQuestionAndFinish;

export { advanceAdaptiveStep, revealFinalCorrectQuestionAndFinish, submitAdaptiveAnswer };
