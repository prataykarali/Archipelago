// Auto-split from ui/chat/index.html — 21-generate-roadmap.js
// Feature module 22 of 22.
import { API_CONTRACT, API_HOST } from './00-current-origin.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { citationPageUrl, copyPearsonCreds, getPearsonBookEntry } from './02--kw-highlights.js';
import { setChatAvailability } from './03-wrap-library-inventory-secti.js';
import { updateGraphToggleUI } from './11-populate-topology.js';
import { setupFilterButtons } from './04-start-new-chat.js';
import { renderBookStack } from './05-display-books.js';
import { renderChatHistory } from './20--compact-history.js';

        async function generateRoadmap() {
            const topicName = window._lastChatMetadata?.anchor_concept?.name || document.getElementById('chat-input').value.trim();
            if (!topicName) {
                alert("Please ask a question or provide a topic first to generate a roadmap.");
                return;
            }
            
            const modal = document.getElementById('roadmap-modal');
            const content = document.getElementById('roadmap-content');
            const loading = document.getElementById('roadmap-loading');
            const titleEl = document.getElementById('roadmap-title');
            
            
            if (modal.classList.contains('hidden')) {
                history.pushState({ modal: 'roadmap' }, '', '');
            }
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            titleEl.textContent = "Learning Roadmap: " + topicName;
            content.innerHTML = '';
            loading.classList.remove('hidden');
            loading.classList.add('flex');
            
            try {
                const res = await fetch(API_CONTRACT.roadmap, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: topicName }),
                });
                const data = await res.json();
                loading.classList.remove('flex');
                loading.classList.add('hidden');
                if (!res.ok || data.error) {
                    content.innerHTML = `<div class="p-4 bg-rose-500/20 text-rose-300 rounded-lg text-sm">${data.error || 'Failed to generate roadmap'}</div>`;
                    return;
                }
                
                // Render the roadmap stages
                data.stages.forEach((stage, idx) => {
                    let itemsHtml = '';
                    stage.items.forEach(item => {
                        let citesHtml = '';
                        if (item.citations && item.citations.length) {
                            citesHtml = `<div class="mt-2 text-[10px] text-gray-400 flex flex-wrap gap-1">
                                <span class="text-accentCyan"><i class="fa-solid fa-book"></i> Books:</span>
                                ${item.citations.map(c => `<span class="px-1.5 py-0.5 rounded bg-white/5 border border-white/10">${escapeHTML(c)}</span>`).join('')}
                            </div>`;
                        }
                        
                        itemsHtml += `
                            <div class="bg-black/50 p-4 rounded-xl border border-white/10 hover:border-accentPurple/50 transition-colors">
                                <div class="flex justify-between items-start mb-2 gap-3">
                                    <h5 class="text-sm font-bold text-white">${escapeHTML(item.name)}</h5>
                                    <label class="flex items-center gap-2 cursor-pointer shrink-0">
                                        <input type="checkbox" class="w-4 h-4 rounded border-gray-600 text-accentPurple focus:ring-accentPurple/50 bg-black/40">
                                        <span class="text-[10px] text-gray-400 font-medium">~${item.study_hours}h</span>
                                    </label>
                                </div>
                                <p class="text-xs text-gray-400 line-clamp-2">${escapeHTML(item.summary)}</p>
                                ${citesHtml}
                            </div>
                        `;
                    });
                    
                    if (!stage.items.length) {
                        itemsHtml = `<div class="text-xs text-gray-500 italic p-3 rounded bg-white/5 border border-white/10">No items in this stage.</div>`;
                    }
                    
                    const badgeColors = ['accentCyan', 'accentPurple', 'accentPink'];
                    const badgeColor = badgeColors[idx % badgeColors.length];
                    
                    const stageHtml = `
                        <div class="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                            <!-- Timeline Dot -->
                            <div class="flex items-center justify-center w-10 h-10 rounded-full border-4 border-black bg-${badgeColor} shadow-[0_0_15px_rgba(139,92,246,0.3)] shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                                <i class="fa-solid fa-graduation-cap text-white text-xs"></i>
                            </div>
                            <!-- Card content -->
                            <div class="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] p-5 rounded-2xl glass border border-white/10 shadow-lg relative">
                                <div class="flex items-center gap-2 mb-4">
                                    <span class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider bg-${badgeColor}/20 text-${badgeColor} border border-${badgeColor}/30">Stage ${idx + 1}</span>
                                    <h4 class="text-base font-bold text-white">${escapeHTML(stage.stage)}</h4>
                                </div>
                                <div class="space-y-3">
                                    ${itemsHtml}
                                </div>
                            </div>
                        </div>
                    `;
                    content.insertAdjacentHTML('beforeend', stageHtml);
                });
                
            } catch (err) {
                loading.classList.remove('flex');
                loading.classList.add('hidden');
                content.innerHTML = `<div class="p-4 bg-rose-500/20 text-rose-300 rounded-lg text-sm">Failed to connect to API</div>`;
            }
        }

        async function generateQuiz() {
            const topicName = window._lastChatMetadata?.anchor_concept?.name || document.getElementById('chat-input').value.trim();
            if (!topicName) {
                alert("Please ask a question or enter a topic first to generate a quiz.");
                return;
            }
            try {
                const res = await fetch(API_HOST + '/api/quiz', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic: topicName }),
                });
                const data = await res.json();
                if (!res.ok || !data.quiz) throw new Error(data.error || 'Quiz generation failed');
                
                let html = `<div class="p-5 glass-glow rounded-2xl space-y-4 my-4 border border-accentPink/30"><div class="flex items-center justify-between"><h4 class="text-sm font-bold text-accentPink uppercase tracking-wider"><i class="fa-solid fa-pen-to-square"></i> Practice Quiz: ${escapeHTML(topicName)}</h4><span class="text-[10px] text-gray-400 font-mono">3 Questions</span></div>`;
                (data.quiz.questions || []).forEach((q, idx) => {
                    html += `<div class="p-3 bg-white/5 rounded-xl border border-white/10 space-y-2"><p class="text-xs font-bold text-gray-200">${idx+1}. ${escapeHTML(q.question)}</p><div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">`;
                    (q.options || []).forEach(opt => {
                        html += `<button onclick="this.className=this.innerText.startsWith('${escapeHTML(q.answer).slice(0,2)}')?'p-2 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-left font-semibold':'p-2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 text-left'" class="p-2 rounded bg-white/5 hover:bg-white/10 border border-white/10 text-left text-gray-300">${escapeHTML(opt)}</button>`;
                    });
                    html += `</div><p class="text-[11px] text-gray-400 italic mt-1">Explanation: ${escapeHTML(q.explanation)}</p></div>`;
                });
                html += `</div>`;
                
                const chatMsgs = document.getElementById('chat-messages');
                const quizWrap = document.createElement('div');
                quizWrap.className = 'w-full flex justify-start animate-fade-in';
                quizWrap.innerHTML = `<div class="max-w-[90%] w-full">${html}</div>`;
                chatMsgs.appendChild(quizWrap);
                chatMsgs.scrollTop = chatMsgs.scrollHeight;
            } catch (err) {
                alert("Quiz generation requires Ollama server to be online.");
            }
        }

        // Global PDF / Pearson / HuggingFace link interceptor (Redirects exact pages ONLY to Pearson or HuggingFace)
        document.addEventListener('click', function(e) {
            const link = e.target.closest('a');
            if (!link) return;
            let href = (link.getAttribute('href') || '').trim();
            if (!href) return;

            // 1. Direct Pearson reader navigation with page
            if (href.includes('pearson.com')) {
                e.preventDefault();
                e.stopPropagation();
                copyPearsonCreds();
                const match = href.match(/#book\/([^/]+)(?:\/page\/(\d+))?/);
                const targetUrl = match
                    ? `/open/${encodeURIComponent(match[1])}?page=${match[2] || 1}`
                    : href;
                window.open(targetUrl, '_blank', 'noopener,noreferrer');
                return;
            }

            // 1b. Direct /open/ Pearson gateway navigation
            if (href.startsWith('/open/') || href.includes('/open/')) {
                e.preventDefault();
                e.stopPropagation();
                copyPearsonCreds();
                window.open(href, '_blank', 'noopener,noreferrer');
                return;
            }

            // 2. Direct HuggingFace PDF navigation with page
            if (href.includes('huggingface.co')) {
                e.preventDefault();
                e.stopPropagation();
                window.open(href, '_blank', 'noopener,noreferrer');
                return;
            }

            // 3. Any page-view / view-page link
            const isPageLink = href.includes('view-page') || href.includes('/api/page-view')
                || href.includes('/pdfs/') || href.includes('#page=')
                || link.classList.contains('curriculum-pdf-link')
                || link.classList.contains('view-page-link')
                || link.classList.contains('citation-card');
            if (!isPageLink) return;

            if (link.dataset.openMode === 'library' || href.includes('open-in-library')) {
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            let doc_id = '', page = 1;
            try {
                if (link.dataset.pageUrl) {
                    const u = new URL(link.dataset.pageUrl, window.location.origin);
                    doc_id = u.searchParams.get('doc_id') || u.searchParams.get('doc') || '';
                    page = parseInt(u.searchParams.get('page') || '1', 10);
                } else if (href.includes('view-page') || href.includes('/api/page-view') || href.includes('?')) {
                    const urlObj = new URL(href.includes('://') || href.startsWith('/') || href.startsWith('?') || href.startsWith('view-page')
                        ? (href.startsWith('view-page') ? (window.location.origin + '/' + href) : href)
                        : href, window.location.origin);
                    doc_id = urlObj.searchParams.get('doc_id') || urlObj.searchParams.get('doc') || '';
                    page = parseInt(urlObj.searchParams.get('page') || '1', 10);
                } else if (href.includes('#page=')) {
                    const parts = href.split('#page=');
                    doc_id = parts[0].replace(/.*\/pdfs\//, '').replace(/^\//, '');
                    page = parseInt(parts[1] || '1', 10);
                } else if (href.includes('/pdfs/')) {
                    doc_id = href.replace(/.*\/pdfs\//, '').split('#')[0].split('?')[0];
                }
            } catch (_) {}
            if (!doc_id && link.dataset.docId) doc_id = link.dataset.docId;

            // Direct Pearson match
            const pEntry = typeof getPearsonBookEntry === 'function' ? getPearsonBookEntry(doc_id) : null;
            if (pEntry) {
                copyPearsonCreds();
                const bId = pEntry.id;
                if (!bId) return;
                window.open(`/open/${encodeURIComponent(bId)}?page=${page || 1}`, '_blank', 'noopener,noreferrer');
                return;
            }

            const targetUrl = citationPageUrl({ doc_id: doc_id, page_number: page });
            if (targetUrl) {
                if (targetUrl.includes('pearson.com') || targetUrl.startsWith('/open/')) copyPearsonCreds();
                window.open(targetUrl, '_blank', 'noopener,noreferrer');
            } else {
                window.open(href, '_blank', 'noopener,noreferrer');
            }
        });

        // Student chat has no ingestion lifecycle hooks.
        setChatAvailability(true);

        if (typeof updateGraphToggleUI === 'function') updateGraphToggleUI();

        // Init catalog filters + 55-doc stack on load
        try {
            if (typeof setupFilterButtons === 'function') setupFilterButtons();
            if (typeof renderBookStack === 'function') renderBookStack();
            if (typeof renderChatHistory === 'function') renderChatHistory();
        } catch (err) {
            console.error('Catalog init failed:', err);
        }

        // Auto-prefill and auto-submit from library deep-link (?query= and/or ?book=)
        (() => {
            const params = new URLSearchParams(window.location.search);
            const queryVal = params.get('query');
            const bookId = params.get('book');
            let finalQuery = queryVal || '';
            if (bookId && finalQuery) {
                // Prefer exact id lookup; keep human title for the bubble.
                if (!/id:/i.test(finalQuery) && !/book[_-]?id=/i.test(finalQuery)) {
                    finalQuery = finalQuery.replace(/\s+$/, '') + ' id:' + bookId;
                }
            } else if (bookId && !finalQuery) {
                finalQuery = 'Tell me about this book: id:' + bookId;
            }
            if (finalQuery) {
                const input = document.getElementById('chat-input');
                if (input) {
                    input.value = finalQuery;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    const trySend = (attempt) => {
                        const sendBtn = document.getElementById('send-btn');
                        if (sendBtn && !sendBtn.disabled) {
                            sendBtn.click();
                            return;
                        }
                        // Retry once after bootstrap (catalog/readiness race).
                        if (attempt < 2) {
                            setTimeout(() => trySend(attempt + 1), 700);
                        }
                    };
                    setTimeout(() => trySend(0), 500);
                }
            }
        })();

export { generateQuiz, generateRoadmap };
