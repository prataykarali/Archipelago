// Auto-split from ui/chat/index.html — 14-render-adaptive-mcqcard.js
// Feature module 15 of 22.
import { getOrCreateInteractiveZone } from './11-populate-topology.js';
import { _nodeLabel } from './10-populate-pipeline.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';

        function renderAdaptiveMCQCard(msgId) {
            const state = window._adaptiveState[msgId];
            if (!state || !state.current_mcq) return;

            const zone = getOrCreateInteractiveZone(msgId);
            if (!zone) return;

            const cardId = `diagnostic-mcq-${msgId}`;
            let cardContent = document.getElementById(cardId);
            if (!cardContent) {
                cardContent = document.createElement('div');
                cardContent.id = cardId;
                cardContent.className = 'adaptive-card-content w-full swipe-in-right';
                zone.innerHTML = '';
                zone.appendChild(cardContent);
            }
            const mcq = state.current_mcq;
            const targetLabel = state.target_label || 'Target Concept';
            const currentName = mcq.concept_name || (state.current_concept ? state.current_concept.replace(/_/g, ' ').toUpperCase() : 'Prerequisite');
            const diff = (mcq.difficulty || 'intermediate').toLowerCase();
            const diffCls = diff === 'foundational' ? 'diagnostic-badge-foundational' : (diff === 'advanced' ? 'diagnostic-badge-advanced' : 'diagnostic-badge-intermediate');

            // Skip-list chain breadcrumb items
            const chain = state.chain && state.chain.length ? state.chain : (state.prereq_chain || []);
            const breadcrumbs = chain.map(cid => {
                const isCurrent = cid === state.current_concept;
                const isTarget = cid === state.target_concept;
                const hRecord = (state.history || []).find(h => h.concept_id === cid);
                let badgeClass = 'bg-white/5 border-white/10 text-gray-400';
                let icon = '';
                if (isCurrent) {
                    badgeClass = 'bg-accentPurple/30 border-accentPurple text-white font-extrabold ring-2 ring-accentPurple/40';
                    icon = '<i class="fa-solid fa-location-dot text-[9px] text-accentPurple mr-1 animate-pulse"></i>';
                } else if (hRecord && hRecord.is_correct) {
                    badgeClass = 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold';
                    icon = '<i class="fa-solid fa-check text-[9px] text-emerald-400 mr-1"></i>';
                } else if (hRecord && !hRecord.is_correct) {
                    badgeClass = 'bg-rose-500/20 border-rose-500/40 text-rose-300 font-bold';
                    icon = '<i class="fa-solid fa-triangle-exclamation text-[9px] text-rose-400 mr-1"></i>';
                } else if (isTarget) {
                    badgeClass = 'bg-amber-400/20 border-amber-400/40 text-amber-300 font-bold';
                    icon = '<i class="fa-solid fa-bullseye text-[9px] text-amber-400 mr-1"></i>';
                }
                const label = _nodeLabel(cid) || cid.replace(/_/g, ' ');
                return `<span class="px-2 py-0.5 rounded-lg border text-[10px] font-mono flex items-center shrink-0 ${badgeClass}">${icon}${escapeHTML(label)}</span>`;
            }).join('<i class="fa-solid fa-circle text-[8px] text-gray-500 shrink-0"></i>');

            // Persist adaptive quiz state to sessionStorage
            try {
                sessionStorage.setItem('archipelago_adaptive_' + msgId, JSON.stringify(state));
            } catch (_) {}

            cardContent.innerHTML = `
                <div class="diagnostic-mcq-card p-5 sm:p-6 space-y-4 rounded-2xl bg-panelBg/95 border border-accentPurple/40 shadow-2xl">
                    <!-- Top Header -->
                    <div class="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/10">
                        <div class="flex items-center gap-3">
                            <div class="w-9 h-9 rounded-xl bg-accentPurple/25 border border-accentPurple/40 flex items-center justify-center text-accentPurple shadow-sm shrink-0">
                                <i class="fa-solid fa-graduation-cap text-base"></i>
                            </div>
                            <div class="flex flex-col">
                                <div class="flex items-center gap-2">
                                    <span class="text-sm sm:text-base font-extrabold text-white tracking-tight">On-the-Spot Adaptive Diagnostic</span>
                                    <span class="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-accentPurple/25 border border-accentPurple/40 text-accentPurple uppercase">Leap-Back Skip-List</span>
                                </div>
                                <span class="text-xs text-gray-300 font-medium mt-0.5">
                                    Testing prerequisite: <strong class="text-white">${escapeHTML(currentName)}</strong> for target <strong class="text-amber-300">${escapeHTML(targetLabel)}</strong>
                                </span>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <!-- Question Counter -->
                            <span class="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-mono text-gray-200 font-bold">
                                Question ${state.question_count} / ${state.max_questions}
                            </span>
                            <!-- 3 Ticks Mastery Meter -->
                            <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-black/50 border border-white/10">
                                <span class="text-[10px] uppercase font-bold text-gray-400">Mastery:</span>
                                <span id="tick-box-${msgId}-1" class="w-5 h-5 rounded flex items-center justify-center font-bold text-xs ${state.consecutive_ticks >= 1 ? 'border border-emerald-400 bg-emerald-500/30 text-emerald-300 shadow-sm' : 'border border-white/20 bg-white/5 text-gray-500'}">
                                    ${state.consecutive_ticks >= 1 ? '✓' : '1'}
                                </span>
                                <span id="tick-box-${msgId}-2" class="w-5 h-5 rounded flex items-center justify-center font-bold text-xs ${state.consecutive_ticks >= 2 ? 'border border-emerald-400 bg-emerald-500/30 text-emerald-300 shadow-sm' : 'border border-white/20 bg-white/5 text-gray-500'}">
                                    ${state.consecutive_ticks >= 2 ? '✓' : '2'}
                                </span>
                                <span id="tick-box-${msgId}-3" class="w-5 h-5 rounded flex items-center justify-center font-bold text-xs ${state.consecutive_ticks >= 3 ? 'border border-emerald-400 bg-emerald-500/30 text-emerald-300 shadow-sm' : 'border border-white/20 bg-white/5 text-gray-500'}">
                                    ${state.consecutive_ticks >= 3 ? '✓' : '3'}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Topological Sequence Breadcrumbs (Leaf -> Prerequisites -> Immediate Y -> Target X) -->
                    <div class="flex items-center gap-2 overflow-x-auto py-1 px-1 custom-scrollbar">
                        <span class="text-[9px] uppercase font-bold text-gray-400 shrink-0">Prerequisite Coverage:</span>
                        <div class="flex items-center gap-1.5 min-w-max">
                            ${breadcrumbs}
                        </div>
                    </div>

                    <!-- Result Banner (Revealed upon answer / completion) -->
                    <div id="adaptive-banner-${msgId}" class="hidden rounded-xl p-3.5 text-xs transition-all"></div>

                    <!-- Question Block with Enhanced Font & Spacing -->
                    <div class="p-5 rounded-2xl bg-white/5 border border-white/10 space-y-3" id="adaptive-block-${msgId}">
                        <div class="flex items-center justify-between gap-2">
                            <span class="text-xs sm:text-sm font-bold text-white flex items-center gap-2">
                                <span class="w-6 h-6 rounded-full bg-accentPurple/30 border border-accentPurple/50 text-accentPurple font-mono text-xs font-bold flex items-center justify-center">${state.question_count}</span>
                                <span>Concept: ${escapeHTML(currentName)}</span>
                            </span>
                            <span class="px-2.5 py-0.5 rounded text-[10px] font-extrabold uppercase font-mono ${diffCls}">${escapeHTML(diff)}</span>
                        </div>
                        <p class="text-sm sm:text-base text-gray-100 font-semibold leading-relaxed tracking-wide my-3">${escapeHTML(mcq.question)}</p>

                        <!-- 4 Distinct Radio Buttons A, B, C, D in Clean 2-Column Grid -->
                        <div class="mcq-radio-group mt-3" id="adaptive-radio-group-${msgId}">
                            ${Object.keys(mcq.options || {}).map(k => {
                                const optText = (mcq.options && mcq.options[k]) || '';
                                return `
                                    <label class="mcq-radio-label" id="adaptive-label-${msgId}-${k}">
                                        <input type="radio" name="adaptive_radio_${msgId}" value="${k}" class="mcq-radio-input" onchange="handleAdaptiveRadioChange('${msgId}', '${k}')">
                                        <span class="mcq-radio-badge">${k}</span>
                                        <span class="mcq-radio-text">${escapeHTML(optText)}</span>
                                    </label>
                                `;
                            }).join('')}
                        </div>

                        <div class="flex flex-wrap gap-3 text-xs">
                            <label>Confidence
                                <select id="adaptive-confidence-${msgId}" class="rounded bg-gray-900 border border-white/20 p-2">
                                    <option value="low">Guessing</option>
                                    <option value="medium" selected>Somewhat sure</option>
                                    <option value="high">Very sure</option>
                                </select>
                            </label>
                            <label>Learning preference (optional)
                                <select id="adaptive-preference-${msgId}" class="rounded bg-gray-900 border border-white/20 p-2">
                                    ${[['conceptual', 'Conceptual / Intuitive'], ['mathematical', 'Mathematical'], ['code', 'Code / Implementation']].map(([value, label]) =>
                                        `<option value="${value}" ${state.preference === value ? 'selected' : ''}>${label}</option>`).join('')}
                                </select>
                            </label>
                        </div>
                        <!-- Literature Citation & Pedagogical Explanation Box (Hidden until submitted) -->
                        <div id="adaptive-exp-${msgId}" class="hidden p-3.5 rounded-xl border border-white/10 bg-black/60 text-xs space-y-1.5 mt-3 shadow-inner">
                            <div class="flex items-center gap-2 text-accentPurple font-bold">
                                <i class="fa-solid fa-book-bookmark text-xs"></i>
                                <span id="adaptive-citation-${msgId}">${escapeHTML(mcq.citation || 'Foundational Literature Citation')}</span>
                            </div>
                            <p id="adaptive-explanation-${msgId}" class="text-gray-300 leading-relaxed">${escapeHTML(mcq.explanation || '')}</p>
                        </div>
                    </div>

                    <!-- Actions Bar -->
                    <div id="adaptive-actions-${msgId}" class="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-white/10">
                        <div class="flex items-center gap-2.5" id="adaptive-btn-container-${msgId}">
                            <button id="btn-submit-adaptive-${msgId}" onclick="submitAdaptiveAnswer('${msgId}')" type="button" disabled class="opacity-50 cursor-not-allowed px-4 py-2.5 rounded-xl bg-gradient-to-r from-accentPurple to-indigo-600 hover:brightness-110 text-white font-extrabold text-xs shadow-lg shadow-accentPurple/25 transition-all flex items-center gap-2">
                                <i class="fa-solid fa-check-double text-xs"></i>
                                <span>Submit Answer</span>
                            </button>
                            <button onclick="switchToNormalGraph('${msgId}')" type="button" class="px-3.5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer">
                                <i class="fa-solid fa-diagram-project text-xs"></i>
                                <span>View Full Normal Graph</span>
                            </button>
                        </div>
                        <span id="adaptive-hint-${msgId}" class="text-[11px] text-gray-400 font-medium">Select one of the 4 options above</span>
                    </div>
                </div>
            `;
        }

        window.renderAdaptiveMCQCard = renderAdaptiveMCQCard;

        window.renderDiagnosticMCQCard = renderAdaptiveMCQCard;

 // Compatibility shim

        function handleAdaptiveRadioChange(msgId, key) {
            const state = window._adaptiveState[msgId];
            if (!state || state.submitted) return;
            state.selected_option = key;

            const submitBtn = document.getElementById(`btn-submit-adaptive-${msgId}`);
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                submitBtn.classList.add('cursor-pointer');
            }
            const hint = document.getElementById(`adaptive-hint-${msgId}`);
            if (hint) {
                hint.textContent = `Option ${key} selected. Click Submit Answer to verify.`;
            }
        }

        window.handleAdaptiveRadioChange = handleAdaptiveRadioChange;

export { handleAdaptiveRadioChange, renderAdaptiveMCQCard };
