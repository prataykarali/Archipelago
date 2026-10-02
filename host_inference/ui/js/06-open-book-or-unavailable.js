// Auto-split from ui/chat/index.html — 06-open-book-or-unavailable.js
// Feature module 7 of 22.
import { state } from './00-state.js';
import { citationPageUrl, copyPearsonCreds } from './02--kw-highlights.js';
import { resolveLibraryReaderLink } from './05-display-books.js';
import { openPageViewerModal, setReadingView } from './07-open-page-viewer-modal.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { API_HOST } from './00-current-origin.js';

function openBookOrUnavailable(book) {
    // Direct launch to external Pearson or HuggingFace dataset PDF (NOWHERE ELSE!)
    const directUrl = citationPageUrl(book);
    if (directUrl) {
        if (directUrl.includes('pearson.com')) copyPearsonCreds();
        window.open(directUrl, '_blank', 'noopener,noreferrer');
        return;
    }
    const libraryHref = resolveLibraryReaderLink(book);
    if (libraryHref) {
        window.location.href = libraryHref;
        return;
    }

    // Prefer real page-view (doc+page+topic), else PDF modal, else summary.
    const title = book && book.title ? book.title : 'Untitled Document';
    const authors = (book && book.authors) || 'Corpus Document';
    const year = (book && book.year) || 2025;
    const topics = (book && book.topics) || [];
    const docId = (book && (book.doc_id || book.document_id || book.source_id || book.pdf)) || '';
    const pageNum = Number(book && (book.page_number || book.page)) || 1;
    const topic = (book && (book.topic || book.section_title || (topics[0] || ''))) || '';
    const summary = (book && (book.summary || book.passage || book.content)) || '';
    // Last-resort: still route PDFs to library rather than the in-chat iframe.
    if (docId && /\.pdf/i.test(String(docId))) {
        const bare = String(docId).split('#')[0].replace(/^\/+/, '').replace(/^pdfs\//i, '');
        const params = new URLSearchParams();
        params.set('book', bare.split('/').pop().replace(/\.pdf$/i, ''));
        params.set('pdf', bare);
        if (pageNum > 1) params.set('page', String(pageNum));
        window.location.href = '/library?' + params.toString() + '#book-reader';
        return;
    }
    if (book && book.page_url && String(book.page_url).includes('page-view')) {
        try {
            const u = new URL(book.page_url, window.location.origin);
            openPageViewerModal(u.searchParams.get('doc_id') || docId, u.searchParams.get('page') || pageNum, u.searchParams.get('highlight') || topic);
            return;
        } catch (_) { /* fall through */ }
    }
    const hasPdf = !!(book && book.pdf && /\.(pdf|md)$/i.test(book.pdf));

    if (hasPdf) {
        // Pure PDF view — page-first, no summary panel, no view-toggle tabs.
        openReadingMode({
            title: title,
            authors: authors,
            type: book.type || book.cat || 'paper',
            year: year,
            pdf: book.pdf,
            preferSummary: false,
            preferSplit: false,
            hideViewToggle: true,
            content: ''
        });
        setReadingView('pdf');
        return;
    }

    // Summary-only holdings (e.g. Silberschatz reference without pilot PDF)
    if (summary) {
        openReadingMode({
            title: title,
            authors: authors,
            type: book.type || 'paper',
            year: year,
            pdf: null,
            preferSummary: true,
            preferSplit: false,
            hideViewToggle: false,
            content: `
                <div style="display:flex;flex-direction:column;gap:14px;padding:8px 4px;">
                    <div class="passage-meta-card" style="padding:14px 16px;border-radius:10px;">
                        <span class="passage-label">Library summary</span>
                        <h4 class="passage-title" style="margin:5px 0 3px;">${escapeHTML(title)}</h4>
                        <p class="passage-meta">${escapeHTML(authors)}${year ? ' · ' + escapeHTML(String(year)) : ''}${topic ? ' · ' + escapeHTML(topic) : ''}</p>
                    </div>
                    <div class="passage-text-card" style="padding:16px;border-radius:10px;">${escapeHTML(summary)}</div>
                    <p class="reader-info-note" style="display:flex;align-items:center;gap:6px;"><i class="fa-solid fa-circle-info"></i>Full PDF is on the reference shelf — summary shown from library card.</p>
                </div>
            `
        });
        setReadingView('summary');
        return;
    }

    // No PDF and no summary — rich reference card (dark-on-light, readable)
    const topicRows = topics.length
        ? topics.map(t => `<span class="ref-topic-badge">${escapeHTML(t)}</span>`).join('')
        : '<span class="ref-topic-badge">Reference Only</span>';
    openReadingMode({
        title: title,
        authors: authors,
        type: book.type || 'paper',
        year: year,
        pdf: null,
        preferSummary: true,
        preferSplit: false,
        hideViewToggle: true,
        content: `
            <div class="reader-unavailable flex flex-col items-center gap-6 py-10 px-6" style="min-height:320px;">
                <!-- Cover icon + title block -->
                <div class="reader-ref-card w-full max-w-lg px-6 py-5 flex items-start gap-5">
                    <div style="width:52px;height:68px;border-radius:6px;background:linear-gradient(145deg,#4c1d95,#1e3a8a);flex-shrink:0;display:flex;align-items:center;justify-content:center;box-shadow:3px 3px 10px rgba(0,0,0,0.18);">
                        <i class="fa-solid fa-book" style="color:#fff;font-size:1.4rem;"></i>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <p style="font-size:0.65rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#7c3aed;margin-bottom:4px;">Reference Book · Library Index</p>
                        <h3 style="font-size:1.05rem;font-weight:800;color:#0f172a;line-height:1.35;margin-bottom:3px;">${escapeHTML(title)}</h3>
                        <p style="font-size:0.8rem;color:#475569;">${escapeHTML(authors)}${year ? ' &middot; ' + escapeHTML(String(year)) : ''}</p>
                    </div>
                </div>

                <!-- Index / Contents section -->
                <div style="width:100%;max-width:28rem;">
                    <p style="font-size:0.68rem;font-weight:700;letter-spacing:0.07em;text-transform:uppercase;color:#6b7280;margin-bottom:8px;">Topics Indexed</p>
                    <div class="reader-ref-topics" style="display:flex;flex-wrap:wrap;gap:6px;">
                        ${topicRows}
                    </div>
                </div>

                <!-- Helpful prompt box -->
                <div class="reader-ref-prompt w-full max-w-lg px-4 py-3 flex items-start gap-3">
                    <i class="fa-solid fa-comment-dots" style="margin-top:2px;font-size:0.95rem;color:#2563eb;"></i>
                    <span>This textbook is indexed for search &amp; citation — the full PDF is on the reference shelf. Ask the chat a question about it (e.g. &ldquo;<em>${escapeHTML(topics[0] || title.split(' ')[0])}</em>&rdquo;) to retrieve page-linked passages.</span>
                </div>

                <button type="button" onclick="closeReadingMode()" style="margin-top:4px;padding:9px 22px;border-radius:8px;border:1px solid #c7d2fe;background:#eef2ff;color:#3730a3;font-size:0.78rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:8px;" onmouseover="this.style.background='#e0e7ff'" onmouseout="this.style.background='#eef2ff'">
                    <i class="fa-solid fa-arrow-left"></i> Back to Chat
                </button>
            </div>
        `
    });
    setReadingView('summary');
}

function openReadingMode(book) {
    const modal = document.getElementById('reading-modal');
    const titleEl = document.getElementById('reading-title');
    const typeEl = document.getElementById('reading-type-badge');
    const contentEl = document.getElementById('reading-content');
    if (!modal || !titleEl || !typeEl || !contentEl) return;
    state._readingBook = book;

    const typeLabel = book.type === 'textbook' ? 'Textbook' : book.type === 'paper' ? 'Paper' : book.type === 'passage' ? 'Passage' : 'Syllabus';
    const typeColor = book.type === 'textbook' ? 'bg-amber-400/15 text-amber-400 border-amber-400/20'
        : book.type === 'paper' || book.type === 'passage' ? 'bg-accentCyan/15 text-accentCyan border-accentCyan/20'
        : 'bg-accentPurple/15 text-accentPurple border-accentPurple/20';

    titleEl.textContent = book.title;
    typeEl.textContent = typeLabel;
    typeEl.className = `px-2 py-0.5 rounded-full text-[9px] font-extrabold uppercase tracking-wide border ${typeColor}`;

    let warningHtml = '';
    if (book.type === 'textbook' && (!book.pdf || (!book.pdf.endsWith('.pdf') && !book.pdf.endsWith('.md')))) {
        warningHtml = `
            <div class="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-center gap-2">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p><strong>PDF Not Available:</strong> This textbook is indexed for search, but the full PDF is not available in the pilot corpus.</p>
            </div>
        `;
    }
    contentEl.innerHTML = warningHtml + book.content;

    if (!modal.classList.contains('flex')) {
        history.pushState({ modal: 'reading' }, '', '');
    }

    // /pdfs/<path>#page=N&zoom=page-fit opens the cited page full-width.
    // Citation opens default to PAGE view (no left summary panel).
    const toggle = document.getElementById('reading-view-toggle');
    const openTab = document.getElementById('reading-open-tab');
    // Stack-of-Books clicks set hideViewToggle so the reader shows ONLY the PDF
    // (or ONLY the "Not available" banner) — no Page/Split/Passage tabs.
    if (book.hideViewToggle) {
        toggle.classList.add('hidden');
        toggle.classList.remove('flex');
        openTab.classList.add('hidden');
        openTab.classList.remove('flex');
        if (book.pdf) {
            setReadingView('pdf');
        } else {
            setReadingView('summary');
        }
    } else if (book.pdf) {
        openTab.href = buildPagePdfUrl(book.pdf);
        openTab.classList.remove('hidden');
        openTab.classList.add('flex');
        toggle.classList.remove('hidden');
        toggle.classList.add('flex');
        // preferSummary only when explicitly requested; citations open page-first
        setReadingView(book.preferSummary ? 'summary' : (book.preferSplit ? 'split' : 'pdf'));
    } else {
        toggle.classList.add('hidden');
        toggle.classList.remove('flex');
        openTab.classList.add('hidden');
        openTab.classList.remove('flex');
        setReadingView('summary');
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    
    // Ensure modal is on top and focused
    modal.style.zIndex = '50';
    titleEl.focus({preventScroll: true});
}

function closeReadingMode(fromPopstate = false) {
    const modal = document.getElementById('reading-modal');
    if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
    const frame = document.getElementById('reading-pdf-frame');
    if (frame) frame.removeAttribute('src');
    state._readingBook = null;
    if (!fromPopstate && window.history.state && window.history.state.modal === 'reading') {
        window.history.back();
    }
}

function highlightPassageText(text, highlight, citedSpans) {
    const raw = String(text || '');
    if (!raw.trim()) return '<p class="text-gray-500 italic text-xs">No passage text available for this page.</p>';

    // Prefer exact char spans from /api/page-view when present
    if (Array.isArray(citedSpans) && citedSpans.length && citedSpans.some(s => s && (s.start_char != null || s.start != null))) {
        const spans = citedSpans
            .map(s => ({
                start: Number(s.start_char != null ? s.start_char : s.start),
                end: Number(s.end_char != null ? s.end_char : s.end),
                text: s.matched_text || s.text || ''
            }))
            .filter(s => Number.isFinite(s.start) && Number.isFinite(s.end) && s.end > s.start)
            .sort((a, b) => b.start - a.start);
        let html = raw;
        spans.forEach(s => {
            const before = html.slice(0, s.start);
            const mid = html.slice(s.start, s.end);
            const after = html.slice(s.end);
            html = before + '@@HL_OPEN@@' + mid + '@@HL_CLOSE@@' + after;
        });
        return escapeHTML(html)
            .replace(/@@HL_OPEN@@/g, '<mark class="page-hl">')
            .replace(/@@HL_CLOSE@@/g, '</mark>')
            .replace(/\n/g, '<br>');
    }

    const safe = escapeHTML(raw);
    const terms = [];
    if (Array.isArray(citedSpans)) {
        citedSpans.forEach(s => {
            const t = (typeof s === 'string' ? s : (s && (s.matched_text || s.text || s.span || s.quote))) || '';
            if (t && t.length > 2) terms.push(t);
        });
    }
    if (highlight) {
        terms.push(String(highlight));
        String(highlight).split(/[\s,;|]+/).forEach(t => {
            if (t && t.length > 2) terms.push(t);
        });
    }
    terms.sort((a, b) => b.length - a.length);
    if (!terms.length) return safe.replace(/\n/g, '<br>');

    let out = safe;
    const used = new Set();
    terms.forEach(term => {
        const key = term.toLowerCase();
        if (used.has(key)) return;
        used.add(key);
        const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        try {
            out = out.replace(new RegExp(escaped, 'gi'), m => `<mark class="page-hl">${m}</mark>`);
        } catch (_) { /* ignore bad regex */ }
    });
    return out.replace(/\n/g, '<br>');
}

/** Build a same-origin PDF URL that jumps to one page and fits it to the viewer. */
function buildPagePdfUrl(pdfRef) {
    const raw = String(pdfRef || '');
    const path = raw.split('#')[0].replace(/^\/+/, '');
    const hashRaw = raw.includes('#') ? raw.split('#').slice(1).join('#') : '';
    let page = 1;
    const m = /(?:^|[&#?])page=(\d+)/i.exec(hashRaw);
    if (m) page = Math.max(1, parseInt(m[1], 10) || 1);
    // Chrome/Edge built-in viewer: page + page-width keeps ONE page large, not a thumbnail strip.
    // pagemode=none hides sidebar thumbnails that steal horizontal space.
    const frag = `page=${page}&zoom=page-width&pagemode=none&navpanes=0`;
    // Encode path segments but keep slashes
    const encoded = path.split('/').map(seg => encodeURIComponent(seg)).join('/');
    return `${API_HOST}/pdfs/${encoded}#${frag}`;
}

export { buildPagePdfUrl, closeReadingMode, highlightPassageText, openBookOrUnavailable, openReadingMode };
