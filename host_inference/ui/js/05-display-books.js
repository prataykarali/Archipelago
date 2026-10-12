// Auto-split from ui/chat/index.html — 05-display-books.js
// Feature module 6 of 22.
import { state } from './00-state.js';
import { CATALOG_55, DOM_SECTIONS, getCategory, getDocCollection } from './04-start-new-chat.js';
import { openBookOrUnavailable } from './06-open-book-or-unavailable.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { API_HOST } from './00-current-origin.js';
import { citationPageUrl } from './02--kw-highlights.js';

function displayBooks() {
    const container = document.getElementById('books-list');
    const countEl = document.getElementById('books-count');
    if (!container) return;

    const entries = [];
    Object.keys(state.GLOBAL_DOC_MAP).forEach(k => {
        const doc = state.GLOBAL_DOC_MAP[k];
        if (state.currentFilter !== 'all' && doc.dom !== state.currentFilter) return;
        if (state.currentTypeFilter !== 'all') {
            const col = getDocCollection(doc);
            if (state.currentTypeFilter === 'library_pearson' && col !== 'library_pearson') return;
            if (state.currentTypeFilter === 'open_source' && col !== 'open_source') return;
            if (state.currentTypeFilter === 'paper' && doc.cat !== 'paper') return;
            if (state.currentTypeFilter === 'textbook' && doc.cat !== 'textbook') return;
        }
        entries.push(doc);
    });

    if (countEl) countEl.textContent = `(${entries.length} docs)`;
    if (!entries.length) {
        container.innerHTML = '<p class="text-xs text-gray-500 italic p-2">No docs match filter.</p>';
        return;
    }

    container.innerHTML = '';

    // Render Query-Connected Literature Section if metadata citations exist
    const qMeta = state.currentQueryMetadata;
    const citations = (qMeta && Array.isArray(qMeta.citations)) ? qMeta.citations : [];
    if (citations.length > 0) {
        const querySec = document.createElement('div');
        querySec.className = "mb-4 p-3 rounded-2xl bg-accentPurple/10 border border-accentPurple/30 space-y-2.5";
        querySec.innerHTML = `
            <div class="flex items-center justify-between pb-1.5 border-b border-accentPurple/20">
                <span class="text-xs font-black uppercase tracking-wider text-accentPurple flex items-center gap-1.5">
                    <i class="fa-solid fa-bookmark"></i> Query-Connected Literature
                </span>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-accentPurple/20 text-accentPurple font-mono font-bold">${citations.length} cited</span>
            </div>
        `;
        const qList = document.createElement('div');
        qList.className = "space-y-2";
        citations.forEach(cite => {
            const title = cite.doc_title || cite.title || (cite.doc_id ? cite.doc_id.split('/').pop() : 'Cited Resource');
            const page = cite.page_number || cite.printed_page || 1;
            const hfUrl = cite.doc_id && cite.doc_id.endsWith('.pdf')
                ? `/papers/${String(cite.doc_id).split('/').map(encodeURIComponent).join('/')}#page=${page}`
                : null;
            const openUrl = citationPageUrl(cite) || `/read/${encodeURIComponent(cite.doc_id || '')}?page=${page}#page=${page}`;
            const shelfLoc = cite.shelf || (cite.call_number ? `Shelf: ${cite.call_number}` : (cite.location || null));
            const isPearson = !!(cite.is_pearson || (cite.book_id && !isNaN(Number(cite.book_id))));

            const cCard = document.createElement('div');
            cCard.className = "p-2.5 rounded-xl bg-white/5 border border-white/10 hover:border-accentPurple/50 transition-all text-xs space-y-1.5";
            cCard.innerHTML = `
                <div class="flex items-start justify-between gap-2">
                    <div class="font-bold text-gray-100 hover:text-white flex-1 leading-snug">
                        ${escapeHTML(title)}
                    </div>
                    <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30 shrink-0">
                        p. ${page}
                    </span>
                </div>
                <div class="flex flex-wrap items-center gap-1.5 pt-1 text-[10px]">
                    <a href="${openUrl}" target="_blank" class="px-2 py-0.5 rounded bg-accentPurple/25 hover:bg-accentPurple/40 text-purple-200 border border-accentPurple/40 font-semibold flex items-center gap-1 transition-colors">
                        <i class="fa-solid fa-book-open text-[9px]"></i> Open Exact Page
                    </a>
                    ${hfUrl ? `
                        <a href="${hfUrl}" target="_blank" class="px-2 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 font-semibold flex items-center gap-1 transition-colors">
                            <i class="fa-solid fa-file-pdf text-[9px]"></i> Open PDF
                        </a>
                    ` : ''}
                    ${isPearson ? `
                        <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">
                            🏛️ Pearson
                        </span>
                    ` : ''}
                    ${shelfLoc ? `
                        <span class="px-2 py-0.5 rounded bg-white/10 text-gray-300 border border-white/10 flex items-center gap-1" title="Physical Library Location">
                            <i class="fa-solid fa-location-dot text-[9px] text-amber-400"></i> ${escapeHTML(shelfLoc)}
                        </span>
                    ` : ''}
                </div>
            `;
            qList.appendChild(cCard);
        });
        querySec.appendChild(qList);
        container.appendChild(querySec);
    }
    DOM_SECTIONS.forEach(sec => {
        const secEntries = entries.filter(d => d.dom === sec.key);
        if (!secEntries.length) return;

        const secHeader = document.createElement('div');
        secHeader.className = "mt-3 mb-1.5 pt-2 border-t border-white/5 first:mt-0 first:border-0";
        secHeader.innerHTML = `
            <div class="flex items-center justify-between px-1 mb-1.5">
                <span class="text-xs font-extrabold uppercase tracking-wider text-gray-300 flex items-center gap-2">
                    <img src="${sec.btn}" class="w-5 h-5 object-contain shrink-0" alt="${sec.label}"> ${sec.label}
                </span>
                <span class="text-[10px] px-2 py-0.5 rounded-full border border-white/10 text-gray-400 font-mono font-bold">${secEntries.length} docs</span>
            </div>
        `;
        container.appendChild(secHeader);

        const listDiv = document.createElement('div');
        listDiv.className = "space-y-2";

        secEntries.forEach(doc => {
            const btn = document.createElement('button');
            btn.className = 'book-card w-full text-left p-3 rounded-xl text-sm font-medium cursor-pointer transition-all duration-200 flex items-start gap-3 group';
            
            const typeImg = doc.cat === 'textbook' ? '/ui/assets/book_btn.png' : doc.cat === 'syllabus' ? '/ui/assets/note_btn2.png' : '/ui/assets/pdf_btn.png';
            const pdfPath = doc.pdf || doc.id;

            // Only attach a PDF path when it looks like a real file (avoids broken iframe for empty catalog stubs)
            const hasPdf = !!(doc.pdf && /\.(pdf|md)$/i.test(doc.pdf));
            btn.onclick = () => openBookOrUnavailable({
                id: doc.id,
                book_id: doc.id,
                isbn: doc.isbn,
                title: doc.title,
                authors: doc.authors || 'Corpus Document',
                type: doc.cat || 'paper',
                year: doc.year || 2025,
                pdf: hasPdf ? doc.pdf : null,
                is_pearson: doc.is_pearson,
                open_url: doc.open_url,
                page_number: doc.page_number,
                topics: doc.topics || []
            });
            
            const col = getDocCollection(doc);
            const colBadge = col === 'library_pearson'
                ? `<span class="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/35 font-semibold shrink-0" title="Pearson eLibrary & Central Library Holding">🏛️ Pearson / Library</span>`
                : `<span class="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/35 font-semibold shrink-0" title="Peer-reviewed Open-Source Paper & Open Textbook">${doc.cat === 'paper' ? '🌐 Open Paper' : '🌐 Open Access'}</span>`;

            const tlist = doc.topics ? doc.topics.slice(0, 2).map(escapeHTML).join(', ') : '';
            btn.innerHTML = `
                <div class="w-9 h-9 flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110">
                    <img src="${typeImg}" class="w-full h-full object-contain" alt="${doc.cat}">
                </div>
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5 mb-0.5">
                        <p class="text-sm font-bold text-gray-100 truncate group-hover:text-white transition-colors flex-1">${escapeHTML(doc.title)}</p>
                        ${colBadge}
                    </div>
                    <div class="flex items-center justify-between text-[11px] text-gray-400 mt-0.5 gap-2">
                        <span class="truncate max-w-[55%]">${escapeHTML(doc.authors || 'Corpus')}${doc.year ? ' ('+doc.year+')' : ''}</span>
                        ${tlist ? `<span class="text-accentCyan font-semibold truncate max-w-[40%]">${tlist}</span>` : ''}
                    </div>
                </div>
                <i class="fa-solid fa-chevron-right text-[9px] text-gray-600 group-hover:text-white transition-all shrink-0"></i>
            `;
            listDiv.appendChild(btn);
        });
        container.appendChild(listDiv);
    });
}

async function renderBookStack() {
    CATALOG_55.forEach(doc => {
        state.GLOBAL_DOC_MAP[doc.id] = {
            id: doc.id,
            title: doc.title,
            authors: doc.authors,
            year: doc.year,
            cat: doc.cat,
            dom: doc.dom || getCategory(doc.id),
            pdf: doc.pdf,
            topics: doc.topics,
            pages: []
        };
    });
    
    displayBooks();

    try {
        const res = await fetch(API_HOST + '/api/catalog/all');
        if (res.ok) {
            const data = await res.json();
            const docs = data.documents || data || [];
            docs.forEach(doc => {
                state.GLOBAL_DOC_MAP[doc.id] = {
                    id: doc.id,
                    title: doc.title,
                    authors: doc.authors,
                    year: doc.year,
                    cat: doc.cat,
                    dom: getCategory(doc.id),
                    pdf: doc.pdf,
                    collection: doc.is_pearson ? 'library_pearson' : 'open_source',
                    is_pearson: doc.is_pearson,
                    open_url: doc.open_url,
                    page_count: doc.page_count,
                    topics: doc.topics,
                    pages: []
                };
            });
            displayBooks();
        }
    } catch (err) {
        console.error("Failed to load catalog from API:", err);
    }
}

/** Map chat stack / catalog docs → library reader deep-link (?book=&pdf=#book-reader). */
function resolveLibraryReaderLink(book) {
    if (!book) return null;
    const title = String(book.title || '').toLowerCase();
    const rawPdf = String(book.pdf || book.id || book.doc_id || '')
        .split('#')[0]
        .replace(/^\/+/, '')
        .replace(/^pdfs\//i, '');
    const pdf = rawPdf.toLowerCase();
    const cat = String(book.cat || book.type || book.kind || '').toLowerCase();
    const page = Number(book.page_number || book.page) || 1;

    const buildHref = (bookId, pdfPath) => {
        const params = new URLSearchParams();
        params.set('book', bookId);
        if (pdfPath) params.set('pdf', pdfPath);
        if (page > 1) params.set('page', String(page));
        return '/library?' + params.toString() + '#book-reader';
    };

    const RULES = [
        { id: 'attention_is_all_you_need', test: (t, p) => p.includes('vaswani') || t.includes('attention is all you need') || p.includes('attention_is_all_you_need') },
        { id: 'deep_learning_goodfellow', test: (t, p) => p.includes('goodfellow') || t.includes('deep learning') },
        { id: 'operating_systems_three_easy_pieces', test: (t, p) => p.includes('ostep') || t.includes('three easy pieces') || t.includes('ostep') || p.includes('operating_systems_three_easy_pieces') },
        { id: 'database_system_concepts', test: (t, p) => t.includes('database system concepts') || p.includes('database_system_concepts') },
        { id: 'lora_paper', test: (t, p) => p.includes('lora') || t.includes('low-rank adaptation') || p.includes('hu2021') || t.includes('lora') },
        { id: 'math_for_ml', test: (t, p) => t.includes('mathematics for machine learning') || p.includes('deisenroth') || p.includes('math_for_ml') },
        { id: 'bert_paper', test: (t, p) => p.includes('bert') || t.includes('bert') || p.includes('devlin') },
        { id: 'rag_paper', test: (t, p) => p.includes('rag') || t.includes('retrieval-augmented generation') || t.includes('retrieval augmented generation') || p.includes('lewis2020') },
        { id: 'database_management_systems_ramakrishnan', test: (t, p) => (t.includes('database management systems') && !t.includes('concepts')) || p.includes('database_management_systems_ramakrishnan') },
        { id: 'operating_system_concepts_silberschatz', test: (t, p) => t.includes('operating system concepts') || p.includes('operating_system_concepts') || t.includes('dinosaur') },
        { id: 'introduction_to_algorithms_clrs', test: (t, p) => t.includes('introduction to algorithms') || t.includes('clrs') || p.includes('introduction_to_algorithms') },
        { id: 'data_structures_algorithm_analysis_weiss', test: (t, p) => t.includes('data structures and algorithm analysis') || p.includes('data_structures_algorithm') },
    ];

    for (let i = 0; i < RULES.length; i++) {
        if (RULES[i].test(title, pdf)) {
            let pdfPath = rawPdf;
            if (pdfPath && /\.pdf$/i.test(pdfPath) && (pdfPath.includes('ostep') || RULES[i].id === 'operating_systems_three_easy_pieces')) {
                if (!pdfPath.includes('/')) pdfPath = 'ostep_three_easy_pieces/' + pdfPath;
            }
            return buildHref(RULES[i].id, pdfPath || undefined);
        }
    }

    // Any stack item with a real PDF (paper, textbook, chapter) → library reader pane.
    if (rawPdf && /\.pdf$/i.test(rawPdf)) {
        const bookKey = String(book.id || book.title || rawPdf)
            .split('/')
            .pop()
            .replace(/\.pdf$/i, '')
            .replace(/[^a-zA-Z0-9._-]+/g, '_')
            .slice(0, 72);
        return buildHref(bookKey || 'doc', rawPdf);
    }

    // Textbook / book card without local PDF still opens library details (metadata / Pearson).
    if (cat === 'textbook' || cat === 'book' || cat === 'hardcopy' || cat === 'ebook' || book.title) {
        const bookKey = String(book.id || book.title || 'book')
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_|_$/g, '')
            .slice(0, 64);
        if (bookKey) return buildHref(bookKey, rawPdf || undefined);
    }
    return buildHref('doc', rawPdf || undefined);
}

function updateBookStackForQuery(metadata) {
    if (!metadata) return;
    state.currentQueryMetadata = metadata;
    displayBooks();
}

window.updateBookStackForQuery = updateBookStackForQuery;

export { displayBooks, renderBookStack, resolveLibraryReaderLink, updateBookStackForQuery };
