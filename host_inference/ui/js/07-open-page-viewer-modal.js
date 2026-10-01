// Auto-split from ui/chat/index.html — 07-open-page-viewer-modal.js
// Feature module 8 of 22.
import { state } from './00-state.js';
import { buildPagePdfUrl, highlightPassageText, openBookOrUnavailable, openReadingMode } from './06-open-book-or-unavailable.js';
import { API_HOST, setLibrarianThinking } from './00-current-origin.js';
import { _updateGlowState, escapeHTML } from './01--hide-welcome-with-transitio.js';
import { sendMessage } from './08-send-message.js';

async function openPageViewerModal(docId, page = 1, highlight = '') {
    if (!docId) return;
    let resolvedDoc = String(docId).split('#')[0].replace(/^\/+/, '');
    let cleanDoc = resolvedDoc.replace(/^.*[\\\/]/, '').replace(/\.pdf$/i, '');
    cleanDoc = cleanDoc.replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim() || cleanDoc;
    const pageNum = parseInt(page, 10) || 1;
    const hl = highlight || '';
    // Keep full relative doc path (papers/…) so /pdfs/ resolves correctly
    let pdfPath = resolvedDoc.toLowerCase().endsWith('.pdf') ? `${resolvedDoc}#page=${pageNum}` : '';

    // Page-first: large PDF only. Passage text loads in the background for the Passage tab.
    openReadingMode({
        title: `${cleanDoc} — p.${pageNum}${hl ? ' · ' + hl : ''}`,
        authors: 'Library corpus',
        type: 'passage',
        year: new Date().getFullYear(),
        pdf: pdfPath || null,
        preferSummary: false,
        preferSplit: false,
        highlight: hl,
        content: `
            <div class="flex flex-col items-center justify-center gap-3 py-16 text-gray-400">
                <i class="fa-solid fa-spinner fa-spin text-2xl text-accentPurple"></i>
                <span class="text-sm font-medium">Loading indexed passage…</span>
                <span class="text-xs text-gray-500">PDF page is open — switch to Passage when text is ready.</span>
            </div>
        `
    });
    // Force PDF page into view immediately when we have a path.
    if (pdfPath) setReadingView('pdf');
    else setReadingView('summary');

    try {
        const params = new URLSearchParams({
            doc_id: docId,
            page: String(pageNum),
        });
        if (hl) params.set('highlight', hl);
        const res = await fetch(`${API_HOST}/api/page-view?${params.toString()}`);
        let data = null;
        if (res.ok) {
            data = await res.json();
        }

        if (data && data.doc_id) {
            resolvedDoc = String(data.doc_id).split('#')[0].replace(/^\/+/, '');
            pdfPath = `${resolvedDoc}#page=${(data.page || pageNum)}`;
        }
        const prettyTitle = (data && data.title) ? String(data.title) : cleanDoc;
        const prettyAuthors = (data && data.authors) ? String(data.authors) : 'Library corpus';
        const passage = (data && (data.passage || data.text || data.text_passage)) || '';
        const section = (data && (data.section_title || data.section)) || '';
        const cited = (data && data.cited_spans) || [];
        const startPage = (data && data.start_page) || (data && data.page) || pageNum;
        const endPage = (data && data.end_page) || startPage;
        const highlighted = highlightPassageText(passage || (hl ? `… ${hl} …` : ''), hl, cited);
        const pagePdfUrl = buildPagePdfUrl(pdfPath);
        const titleElLive = document.getElementById('reading-title');
        if (titleElLive) titleElLive.textContent = `${prettyTitle} — p.${startPage}${hl ? ' · ' + hl : ''}`;

        const contentHtml = `
            <div class="space-y-4 passage-transition">
                <div class="passage-meta-card p-4 rounded-xl bg-accentPurple/10 border border-accentPurple/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div class="min-w-0">
                        <span class="passage-label text-xs font-mono text-accentPurple font-bold uppercase tracking-wider">Indexed passage</span>
                        <h4 class="passage-title text-base font-bold text-white truncate">${escapeHTML(prettyTitle)}</h4>
                        <p class="passage-meta text-sm text-gray-300 mt-0.5">
                            ${escapeHTML(prettyAuthors)} · Page ${escapeHTML(String(startPage))}${endPage !== startPage ? '–' + escapeHTML(String(endPage)) : ''}
                            ${section ? ' · ' + escapeHTML(section) : ''}
                            ${hl ? ' · topic: ' + escapeHTML(hl) : ''}
                        </p>
                    </div>
                    <a href="${pagePdfUrl}"
                       target="_blank" rel="noopener noreferrer"
                       class="px-3 py-1.5 rounded-lg bg-accentPurple text-white text-sm font-bold hover:bg-accentPurple/80 transition-all shrink-0">
                        Open this page ↗
                    </a>
                </div>
                ${hl ? `<div class="passage-highlight p-3 rounded-lg text-sm text-amber-300/90 font-mono"><i class="fa-solid fa-highlighter mr-1"></i>Highlight: ${escapeHTML(hl)}</div>` : ''}
                <div class="passage-text-card p-4 rounded-xl glass-light border border-white/10 text-base text-gray-100 leading-relaxed">
                    ${highlighted || '<p class="text-gray-500 italic text-sm">No passage text returned. Stay on the <b>Page</b> tab for the PDF.</p>'}
                </div>
                ${!res.ok ? `<p class="text-sm text-rose-300/90">Could not load /api/page-view (${res.status}). Showing the PDF page if available.</p>` : ''}
            </div>
        `;

        const contentEl = document.getElementById('reading-content');
        if (contentEl) contentEl.innerHTML = contentHtml;
        if (state._readingBook) {
            state._readingBook.content = contentHtml;
            state._readingBook.title = `${prettyTitle} — p.${startPage}${hl ? ' · ' + hl : ''}`;
            state._readingBook.authors = prettyAuthors;
            state._readingBook.pdf = (data && data.pdf_available === false) ? null : pdfPath;
            state._readingBook.summary = passage;
        }
        // PDF when available; else Passage tab with summary
        if (state._readingBook && state._readingBook.pdf) setReadingView('pdf');
        else setReadingView('summary');
    } catch (err) {
        console.error('openPageViewerModal failed:', err);
        const contentEl = document.getElementById('reading-content');
        if (contentEl) {
            contentEl.innerHTML = `
                <div class="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-200 text-sm space-y-2">
                    <p class="font-bold">Failed to load passage</p>
                    <p class="text-rose-300/80">${escapeHTML(err.message || String(err))}</p>
                    <p class="text-gray-400">Use the <b>Page</b> tab if a PDF is available.</p>
                </div>
            `;
        }
        // Still try to show the PDF page even if the passage API failed
        if (state._readingBook && state._readingBook.pdf) setReadingView('pdf');
        else setReadingView('summary');
    }
}

function setReadingView(view) {
    const pdfWrap = document.getElementById('reading-pdf-wrap');
    const frame = document.getElementById('reading-pdf-frame');
    const content = document.getElementById('reading-content');
    const btnPdf = document.getElementById('reading-tab-pdf');
    const btnSum = document.getElementById('reading-tab-summary');
    const btnSplit = document.getElementById('reading-tab-split');
    if (!pdfWrap || !frame || !content) return;

    content.classList.remove('passage-transition');
    void content.offsetWidth;
    content.classList.add('passage-transition');

    const inactiveClass = 'px-3 py-1 rounded-md text-xs font-bold transition-all text-slate-300 hover:text-white hover:bg-slate-700/60';
    const activeClassPdf = 'px-3 py-1 rounded-md text-xs font-bold transition-all bg-cyan-400 text-slate-950 shadow-md';
    const activeClassSum = 'px-3 py-1 rounded-md text-xs font-bold transition-all bg-violet-500 text-white shadow-md';
    const activeClassSplit = 'px-3 py-1 rounded-md text-xs font-bold transition-all bg-emerald-400 text-slate-950 shadow-md';

    if (btnPdf) btnPdf.className = inactiveClass;
    if (btnSum) btnSum.className = inactiveClass;
    if (btnSplit) btnSplit.className = inactiveClass;

    if (state._readingBook && state._readingBook.pdf) {
        const pdfUrl = buildPagePdfUrl(state._readingBook.pdf);
        // Probe same-origin /pdfs proxy first so a Flask HTML 404 never paints
        // inside the iframe. On failure, flip to the honest Not Available panel.
        const barePath = String(state._readingBook.pdf).split('#')[0];
        const probeUrl = `${API_HOST}/pdfs/${barePath.split('/').map(seg => encodeURIComponent(seg)).join('/')}`;
        frame.src = 'about:blank';
        // Prefer HEAD (cheap). Fall back to a tiny ranged GET when HEAD is blocked.
        const probe = (method, headers = {}) =>
            fetch(probeUrl, { method, headers, cache: 'no-store' }).then(res => {
                if (!res.ok) throw new Error('pdf-missing');
                const ct = (res.headers.get('Content-Type') || '').toLowerCase();
                if (ct.includes('text/html') || ct.includes('application/json')) throw new Error('pdf-missing');
                return res;
            });
        probe('HEAD')
            .catch(() => probe('GET', { Range: 'bytes=0-3' }))
            .then(() => { setTimeout(() => { frame.src = pdfUrl; }, 15); })
            .catch(() => {
                // Replace reader with Not Available banner instead of embedding 404 HTML
                if (state._readingBook && state._readingBook.pdf) {
                    openBookOrUnavailable({
                        title: state._readingBook.title || barePath,
                        authors: state._readingBook.authors || 'Corpus Document',
                        type: state._readingBook.type || 'paper',
                        year: state._readingBook.year || new Date().getFullYear(),
                        pdf: null,
                        topics: state._readingBook.topics || []
                    });
                }
            });
        const openTab = document.getElementById('reading-open-tab');
        if (openTab) openTab.href = pdfUrl;
    }

    if (view === 'pdf' && state._readingBook && state._readingBook.pdf) {
        // Full-bleed page — no left summary panel. flex-1 + h-full so iframe paints the page.
        pdfWrap.className = 'w-full h-full min-h-0 flex-1 bg-black/50';
        pdfWrap.style.display = 'block';
        content.className = 'hidden';
        content.style.display = 'none';
        if (btnPdf) {
            btnPdf.className = activeClassPdf;
            btnPdf.setAttribute('aria-selected', 'true');
        }
        if (btnSum) btnSum.setAttribute('aria-selected', 'false');
        if (btnSplit) btnSplit.setAttribute('aria-selected', 'false');
    } else if (view === 'split' && state._readingBook && state._readingBook.pdf) {
        pdfWrap.className = 'w-3/5 h-full min-h-0 flex-1 bg-black/50 border-l border-white/10';
        pdfWrap.style.display = 'block';
        content.className = 'w-2/5 h-full overflow-y-auto p-5 text-base text-gray-200 leading-relaxed space-y-4 passage-transition';
        content.style.display = 'block';
        if (btnSplit) {
            btnSplit.className = activeClassSplit;
            btnSplit.setAttribute('aria-selected', 'true');
        }
        if (btnPdf) btnPdf.setAttribute('aria-selected', 'false');
        if (btnSum) btnSum.setAttribute('aria-selected', 'false');
    } else {
        pdfWrap.className = 'hidden';
        pdfWrap.style.display = 'none';
        content.className = 'w-full h-full overflow-y-auto p-5 text-base text-gray-200 leading-relaxed space-y-4 passage-transition';
        content.style.display = 'block';
        if (btnSum) {
            btnSum.className = activeClassSum;
            btnSum.setAttribute('aria-selected', 'true');
        }
        if (btnPdf) btnPdf.setAttribute('aria-selected', 'false');
        if (btnSplit) btnSplit.setAttribute('aria-selected', 'false');
    }
}

function copyBibtex() {
    const bibtexStr = window._currentReadingBibtex;
    if (!bibtexStr) return;
    navigator.clipboard.writeText(bibtexStr).then(() => {
        const btn = document.getElementById('reading-copy-bibtex');
        if (!btn) return;
        const origHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
        btn.classList.add('bg-emerald-500/20', 'text-emerald-400', 'border-emerald-500/50');
        btn.classList.remove('bg-accentPink/15', 'text-accentPink', 'border-accentPink/30');
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.classList.remove('bg-emerald-500/20', 'text-emerald-400', 'border-emerald-500/50');
            btn.classList.add('bg-accentPink/15', 'text-accentPink', 'border-accentPink/30');
        }, 2000);
    });
}

// (Removed duplicate closeReadingMode)

// Toggle between RAG and Conversational Agent (kept as default rag_synthesis mode)
function setMode(mode) {
state.currentMode = mode;
}

        function setSendButtonState(state) {
            const btn = document.getElementById('send-btn');
            const icon = document.getElementById('send-btn-icon');
            if (!btn) return;
            if (state === 'stop') {
                btn.className = 'w-10 h-10 rounded-lg bg-rose-600 hover:bg-rose-500 text-white flex items-center justify-center transition-all duration-200 shadow-md shadow-rose-600/30 z-20 cursor-pointer pointer-events-auto';
                if (icon) icon.className = 'fa-solid fa-stop text-sm';
                btn.title = 'Stop generating response';
                btn.disabled = false;
            } else {
                btn.className = 'w-10 h-10 rounded-lg bg-accentPurple text-white hover:bg-accentPurple/80 flex items-center justify-center transition-all duration-200 shadow-md shadow-accentPurple/20 z-20 cursor-pointer pointer-events-auto';
                if (icon) icon.className = 'fa-solid fa-arrow-up text-sm';
                btn.title = 'Send message';
                btn.disabled = false;
            }
        }

        window.setSendButtonState = setSendButtonState;

        function stopGeneration() {
            if (state.currentAbortController) {
                try { state.currentAbortController.abort(); } catch (_) {}
                state.currentAbortController = null;
            }
            if (state.currentAssistantRow) {
                const msgBody = state.currentAssistantRow.querySelector('[id^="msg-body-"]');
                if (msgBody) {
                    msgBody.classList.remove('ai-typewriter-cursor');
                    const wrap = msgBody.closest('.msg-bubble-wrap');
                    if (wrap) wrap.classList.remove('is-thinking');
                    if (!msgBody.textContent.trim() || msgBody.querySelector('.typing-indicator, .thinking-orb-loader, .thinking-lightgrid')) {
                        try { state.currentAssistantRow.remove(); } catch (_) {}
                    }
                }
                state.currentAssistantRow = null;
            }
            document.querySelectorAll('.model-reply-status').forEach(el => {
                el.classList.remove('is-visible');
                el.dataset.active = '0';
                el.hidden = true;
            });
            document.querySelectorAll('.msg-bubble-wrap.is-thinking, .ai-typewriter-cursor').forEach(el => {
                el.classList.remove('is-thinking', 'ai-typewriter-cursor', 'is-live-streaming');
                if (!el.textContent.trim() || el.querySelector('.typing-indicator, .thinking-orb-loader, .thinking-lightgrid')) {
                    const row = el.closest('.assistant-row') || el.closest('#chat-messages > div') || el.closest('.flex');
                    if (row) { try { row.remove(); } catch (_) {} }
                }
            });

            state.isGenerating = false;
            try { window.isGenerating = false; } catch (_) {}
            _updateGlowState(false);
            setSendButtonState('send');
            setLibrarianThinking(false);

            const inputEl = document.getElementById('chat-input');
            if (inputEl) {
                inputEl.disabled = false;
                try { inputEl.focus(); } catch (_) {}
            }
        }

        window.stopGeneration = stopGeneration;

        function handleSendBtnClick(e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            if (state.isGenerating) {
                stopGeneration();
            } else {
                sendMessage();
            }
        }

        window.handleSendBtnClick = handleSendBtnClick;

        // Auto prompt suggested templates
        function autoPrompt(text) {
            const inputEl = document.getElementById('chat-input');
            if (inputEl) {
                inputEl.value = text;
                inputEl.focus();
            }
            if (state.isGenerating) {
                stopGeneration();
            }
            sendMessage();
        }

        // Trigger prompt from tag click
        function promptFromConcept(label) {
            autoPrompt(`Tell me about the concept of ${label}`);
        }

        // Key handler for Enter key (without Shift)
        function handleKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendBtnClick(e);
            }
        }

export { autoPrompt, copyBibtex, handleKey, handleSendBtnClick, openPageViewerModal, promptFromConcept, setMode, setReadingView, setSendButtonState, stopGeneration };
