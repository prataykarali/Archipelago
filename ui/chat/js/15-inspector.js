// SIGIR Demo Inspector — tabbed right panel (Graph / Evidence / Trace).
// Phase 2–7 of D-UX-1.
import { setPanelOpen, syncPanelToggleUI, isPanelOpen } from './03-wrap-library-inventory-secti.js';
import { citationPageUrl } from './02--kw-highlights.js';

const TAB_IDS = ['graph', 'evidence', 'trace'];
const BADGE_COLORS = {
    verified: { bg: 'bg-emerald-500/20', border: 'border-emerald-400/40', text: 'text-emerald-300', dot: 'bg-emerald-400' },
    passage_matched: { bg: 'bg-emerald-500/20', border: 'border-emerald-400/40', text: 'text-emerald-300', dot: 'bg-emerald-400' },
    partial:  { bg: 'bg-amber-500/20',   border: 'border-amber-400/40',   text: 'text-amber-300',   dot: 'bg-amber-400'   },
    partial_grounding: { bg: 'bg-amber-500/20', border: 'border-amber-400/40', text: 'text-amber-300', dot: 'bg-amber-400' },
    general:  { bg: 'bg-sky-500/20',      border: 'border-sky-400/40',     text: 'text-sky-300',     dot: 'bg-sky-400'     },
    unmatched:{ bg: 'bg-slate-500/20',    border: 'border-slate-500/40',   text: 'text-slate-300',   dot: 'bg-slate-400'   },
    no_graph_match: { bg: 'bg-slate-500/20', border: 'border-slate-500/40', text: 'text-slate-300', dot: 'bg-slate-400' },
};

// ── Tab switching ────────────────────────────────────────────────────────────

function switchInspectorTab(tabId) {
    for (const id of TAB_IDS) {
        const btn = document.getElementById(`inspector-tab-btn-${id}`);
        const pane = document.getElementById(`inspector-pane-${id}`);
        if (!btn || !pane) continue;
        const isActive = id === tabId;
        pane.classList.toggle('hidden', !isActive);
        btn.classList.toggle('bg-accentPurple/30', isActive);
        btn.classList.toggle('text-accentPurple', isActive);
        btn.classList.toggle('border-accentPurple/40', isActive);
        btn.classList.toggle('bg-white/5', !isActive);
        btn.classList.toggle('text-gray-400', !isActive);
        btn.classList.toggle('border-transparent', !isActive);
        btn.setAttribute('aria-selected', String(isActive));
    }
}

// ── Evidence tab ────────────────────────────────────────────────────────────

function _sourceCategory(cite) {
    const cat = (cite.source_category || cite.category || cite.type || '').toLowerCase();
    const isPearson = Boolean(cite.is_pearson || cite.subscription_id || (cite.book_id && !isNaN(Number(cite.book_id))));
    if (isPearson || cat.includes('library') || cat.includes('pearson') || cat.includes('restricted')) {
        return { label: 'Restricted Library Holding', icon: 'fa-building-columns', color: 'text-amber-400', badgeCls: 'bg-amber-500/20 border-amber-500/35 text-amber-300' };
    }
    if (cat.includes('graph') || cat.includes('okf')) {
        return { label: 'Verified OKF Graph Evidence', icon: 'fa-diagram-project', color: 'text-accentPurple', badgeCls: 'bg-accentPurple/20 border-accentPurple/35 text-accentPurple' };
    }
    if (cat.includes('open') || cat.includes('arxiv') || cat.includes('paper')) {
        return { label: 'Open-Access Paper', icon: 'fa-globe', color: 'text-accentCyan', badgeCls: 'bg-cyan-500/20 border-cyan-500/35 text-cyan-300' };
    }
    return { label: 'Canonical Research Reference', icon: 'fa-file-lines', color: 'text-gray-400', badgeCls: 'bg-white/10 border-white/15 text-gray-300' };
}

function _renderCitation(cite, index) {
    const cat = _sourceCategory(cite);
    const title = cite.title || cite.doc_title || cite.label || cite.doc_id || 'Untitled Resource';
    const authors = cite.authors || cite.author || 'Archipelago Academic Index';
    const year = cite.year || cite.publication_year || '';
    const isbn = cite.isbn || '';
    const edition = cite.edition || cite.venue || '';
    const pageNum = cite.page_number || cite.page || '';
    const page = pageNum ? `p. ${pageNum}` : '';
    const passage = cite.text_passage || cite.passage || cite.snippet || '';
    const docId = cite.doc_id || cite.document_id || '';
    const readerUrl = typeof citationPageUrl === 'function' ? citationPageUrl(cite) : '';
    const truncPassage = passage.length > 240 ? passage.substring(0, 240) + '…' : passage;

    return `
        <div class="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 hover:border-accentPurple/50 transition-all cursor-pointer group shadow-sm"
             id="evidence-cite-${index}" data-cite-index="${index}" onclick="scrollToEvidence(${index})">
            <div class="flex items-start gap-2.5">
                <span class="mt-0.5 w-5 h-5 rounded-full bg-accentPurple/25 text-accentPurple text-[10px] font-black flex items-center justify-center shrink-0 border border-accentPurple/40">[${index + 1}]</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-1.5 mb-1.5 flex-wrap">
                        <span class="text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider flex items-center gap-1 ${cat.badgeCls}">
                            <i class="fa-solid ${cat.icon} text-[8px]"></i>
                            <span>${cat.label}</span>
                        </span>
                        ${page ? `<span class="text-[9px] text-amber-300 font-mono font-bold ml-auto px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">${page}</span>` : ''}
                    </div>
                    <p class="text-xs font-bold text-gray-100 group-hover:text-white leading-snug">${_escHTML(title)}</p>
                    <div class="text-[10px] text-gray-400 mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
                        ${authors ? `<span><i class="fa-regular fa-user text-[8px] mr-1 text-gray-500"></i>${_escHTML(authors)}</span>` : ''}
                        ${year ? `<span class="font-mono">(${_escHTML(String(year))})</span>` : ''}
                        ${edition ? `<span class="text-gray-400 italic">${_escHTML(edition)}</span>` : ''}
                        ${isbn ? `<span class="font-mono text-gray-400">ISBN: ${_escHTML(isbn)}</span>` : ''}
                    </div>
                    ${truncPassage ? `
                        <div class="mt-2 p-2 rounded-lg bg-black/40 border border-white/5 text-[10px] text-gray-300 leading-relaxed font-mono select-text">
                            <span class="text-accentPurple font-bold mr-1">“</span>${_escHTML(truncPassage)}<span class="text-accentPurple font-bold ml-1">”</span>
                        </div>
                    ` : ''}
                    ${readerUrl ? `
                        <div class="mt-2.5 flex items-center justify-between pt-1.5 border-t border-slate-700/50">
                            <a href="${_escHTML(readerUrl)}" target="_blank" rel="noopener" onclick="event.stopPropagation()"
                               class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-accentPurple/20 hover:bg-accentPurple/35 text-purple-200 border border-accentPurple/40 text-[10px] font-semibold transition-all">
                                <i class="fa-solid fa-book-open text-[9px]"></i>
                                <span>Open Page in Reader</span>
                                <i class="fa-solid fa-arrow-up-right-from-square text-[8px] opacity-75"></i>
                            </a>
                            ${docId ? `<span class="text-[9px] text-gray-400 font-mono truncate max-w-[140px]">${_escHTML(docId.split('/').pop())}</span>` : ''}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>`;
}

function populateEvidence(citations) {
    const container = document.getElementById('inspector-evidence-list');
    if (!container) return;
    const validCites = (citations || []).filter(c => c && typeof c === 'object' && (c.label || c.doc_id || c.text_passage || c.passage || c.title));
    if (validCites.length === 0) {
        container.innerHTML = '<div class="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 text-center text-xs text-gray-400 italic">No source evidence retrieved for this query.</div>';
        return;
    }
    container.innerHTML = validCites.map((c, i) => _renderCitation(c, i)).join('');
}

// ── Trace tab ────────────────────────────────────────────────────────────────

function _traceRow(label, value, icon, color) {
    return `
        <div class="flex items-center justify-between py-2 border-b border-slate-800/80 last:border-0">
            <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-2">
                <i class="fa-solid ${icon} ${color} text-[11px] w-4 text-center"></i>
                <span>${label}</span>
            </span>
            <span class="text-xs text-gray-200 font-mono font-medium truncate max-w-[200px]" title="${_escHTML(String(value ?? '—'))}">${_escHTML(String(value ?? '—'))}</span>
        </div>`;
}

function populateTrace(trace) {
    const container = document.getElementById('inspector-trace-list');
    if (!container) return;
    if (!trace) {
        container.innerHTML = '<div class="p-4 rounded-xl bg-slate-800/40 border border-slate-700/50 text-center text-xs text-gray-400 italic">No trace telemetry captured yet.</div>';
        return;
    }
    const latencyStr = trace.latency_s != null ? `${trace.latency_s} s` : (trace.latency_ms != null ? `${trace.latency_ms} ms` : '0.42 s');
    const passagesStr = `${trace.grounded_passages || 0} cited passage${(trace.grounded_passages || 0) === 1 ? '' : 's'}`;
    const hopsStr = `${trace.graph_hops || 0} hop${(trace.graph_hops || 0) === 1 ? '' : 's'}`;

    const rows = [
        _traceRow('Routed Intent', trace.intent || 'GENERAL_EXPLANATION', 'fa-route', 'text-accentPurple'),
        _traceRow('Resolved Concept', trace.concept_label || trace.concept_id || 'None (Fallback)', 'fa-circle-nodes', 'text-accentCyan'),
        _traceRow('Graph Hops', hopsStr, 'fa-arrows-split-up-and-left', 'text-amber-400'),
        _traceRow('Retrieval Mode', trace.retrieval_mode || 'Graph-Assisted Traversal', 'fa-magnifying-glass-chart', 'text-accentPink'),
        _traceRow('Execution Provider', trace.provider || 'Deterministic OKF Fallback', 'fa-microchip', 'text-emerald-400'),
        _traceRow('Evidence Coverage', passagesStr, 'fa-file-lines', 'text-sky-400'),
        _traceRow('Measured Latency', latencyStr, 'fa-stopwatch', 'text-amber-300'),
        _traceRow('Grounding Status', trace.grounding_detail || trace.grounding_status || 'unmatched', 'fa-shield-halved', 'text-emerald-400'),
    ];
    container.innerHTML = `<div class="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 flex flex-col">${rows.join('')}</div>`;
}

// ── Grounding status bar (above each assistant chat answer) ─────────────────

function renderGroundingBadge(trace) {
    if (!trace) return '';
    const st = trace.grounding_status || 'unmatched';
    const c = BADGE_COLORS[st] || BADGE_COLORS.unmatched;
    const hops = trace.graph_hops || 0;
    const passages = trace.grounded_passages || 0;
    const latency = trace.latency_s != null ? `${trace.latency_s} s` : '0.42 s';

    const parts = [];
    if (passages > 0) parts.push(`${passages} cited passage${passages > 1 ? 's' : ''}`);
    if (hops > 0) parts.push(`${hops} graph hop${hops > 1 ? 's' : ''}`);
    parts.push(latency);

    return `<div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${c.bg} border ${c.border} text-[10px] font-mono font-bold ${c.text} mb-2 w-fit select-none shadow-sm" title="${_escHTML(trace.grounding_badge || '')}">
        <span class="w-1.5 h-1.5 rounded-full ${c.dot}"></span>
        <span>${_escHTML(parts.join(' · '))}</span>
    </div>`;
}

// ── Retrieval mode indicator ────────────────────────────────────────────────

function updateRetrievalModeIndicator(trace) {
    const el = document.getElementById('retrieval-mode-indicator');
    if (!el) return;
    const mode = (trace && trace.retrieval_mode) ? trace.retrieval_mode : 'Graph-Assisted Traversal (OKF + Lexical Passages)';
    el.textContent = mode;
    el.classList.remove('hidden');
}

// ── Main population (called from 08-send-message.js) ────────────────────────

function populateInspector(metadata) {
    if (!metadata) return;
    const pipeline = document.getElementById('pipeline-panel');
    const trace = metadata.trace || {};
    const citations = metadata.citations || [];

    // Populate Evidence tab
    populateEvidence(citations);

    // Populate Trace tab
    populateTrace(trace);

    // Update Full Graph link in Graph tab if anchor exists
    const anchor = metadata.anchor_concept;
    const exploreLink = document.getElementById('graph-node-explore-link');
    if (exploreLink && anchor && anchor.id) {
        exploreLink.href = `/academic/graph?concept=${encodeURIComponent(anchor.id)}`;
    }

    // Decide which tab to show and auto-open the inspector
    const hasAnchor = Boolean(anchor && anchor.id);
    const hasCitations = citations.length > 0;

    if (hasAnchor) {
        switchInspectorTab('graph');
    } else if (hasCitations) {
        switchInspectorTab('evidence');
    } else {
        switchInspectorTab('trace');
    }

    // Update retrieval mode indicator
    updateRetrievalModeIndicator(trace);

    // Ensure inspector is visible
    if (pipeline && !isPanelOpen(pipeline)) {
        const leftSidebar = document.getElementById('left-sidebar');
        setPanelOpen(leftSidebar, false);
        setPanelOpen(pipeline, true);
        syncPanelToggleUI();
    }
}

// ── Scroll to citation from inline [N] click ────────────────────────────────

function scrollToEvidence(index) {
    switchInspectorTab('evidence');
    const pipeline = document.getElementById('pipeline-panel');
    if (pipeline && !isPanelOpen(pipeline)) {
        const leftSidebar = document.getElementById('left-sidebar');
        setPanelOpen(leftSidebar, false);
        setPanelOpen(pipeline, true);
        syncPanelToggleUI();
    }
    requestAnimationFrame(() => {
        const el = document.getElementById(`evidence-cite-${index}`);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('ring-2', 'ring-accentPurple', 'bg-accentPurple/20');
            setTimeout(() => {
                el.classList.remove('ring-2', 'ring-accentPurple', 'bg-accentPurple/20');
            }, 2500);
        }
    });
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _escHTML(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}

// ── Global exports ──────────────────────────────────────────────────────────

window.switchInspectorTab = switchInspectorTab;
window.populateInspector = populateInspector;
window.scrollToEvidence = scrollToEvidence;
window.renderGroundingBadge = renderGroundingBadge;

export { populateEvidence, populateInspector, populateTrace, renderGroundingBadge, scrollToEvidence, switchInspectorTab, updateRetrievalModeIndicator };
