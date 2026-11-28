// SIGIR Demo Inspector — tabbed right panel (Graph / Evidence / Trace).
// Phase 2–7 of D-UX-1.
import { setPanelOpen, syncPanelToggleUI, isPanelOpen } from './03-wrap-library-inventory-secti.js';
import { citationPageUrl, citationTitle, isNonReadableSourceKind, normalizeSourceKind } from './02--kw-highlights.js';

const TAB_IDS = ['graph', 'books', 'trace'];
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
    const resolvedTab = tabId === 'evidence' ? 'trace' : tabId;
    for (const id of TAB_IDS) {
        const btn = document.getElementById(`inspector-tab-btn-${id}`);
        const pane = document.getElementById(`inspector-pane-${id}`);
        if (!btn || !pane) continue;
        const isActive = id === resolvedTab;
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
    const kind = normalizeSourceKind(cite);
    if (kind === 'metadata_only_record') {
        return { label: 'Metadata-Only Record', icon: 'fa-tag', color: 'text-amber-300', badgeCls: 'bg-amber-500/20 border-amber-400/40 text-amber-200', kind };
    }
    if (kind === 'unavailable_document') {
        return { label: 'Unavailable Document', icon: 'fa-file-circle-xmark', color: 'text-rose-300', badgeCls: 'bg-rose-500/20 border-rose-400/40 text-rose-200', kind };
    }
    if (kind === 'institutional_licensed') {
        return { label: 'Institutional Licensed', icon: 'fa-building-columns', color: 'text-amber-400', badgeCls: 'bg-amber-500/20 border-amber-500/35 text-amber-300', kind };
    }
    if (kind === 'verified_full_text_passage') {
        return { label: 'Verified Full-Text Passage', icon: 'fa-circle-check', color: 'text-emerald-300', badgeCls: 'bg-emerald-500/20 border-emerald-400/40 text-emerald-200', kind };
    }
    const cat = (cite.source_category || cite.category || cite.type || '').toLowerCase();
    const isPearson = Boolean(cite.is_pearson || cite.subscription_id || (cite.book_id && !isNaN(Number(cite.book_id))));
    if (isPearson || cat.includes('library') || cat.includes('pearson') || cat.includes('restricted')) {
        return { label: 'Restricted Library Holding', icon: 'fa-building-columns', color: 'text-amber-400', badgeCls: 'bg-amber-500/20 border-amber-500/35 text-amber-300', kind: 'institutional_licensed' };
    }
    if (cat.includes('graph') || cat.includes('okf')) {
        return { label: 'Indexed Graph Reference', icon: 'fa-diagram-project', color: 'text-accentPurple', badgeCls: 'bg-accentPurple/20 border-accentPurple/35 text-accentPurple', kind: '' };
    }
    if (cat.includes('open') || cat.includes('arxiv') || cat.includes('paper')) {
        return { label: 'Open-Access Paper', icon: 'fa-globe', color: 'text-accentCyan', badgeCls: 'bg-cyan-500/20 border-cyan-500/35 text-cyan-300', kind: '' };
    }
    return { label: 'Canonical Research Reference', icon: 'fa-file-lines', color: 'text-gray-400', badgeCls: 'bg-white/10 border-white/15 text-gray-300', kind: '' };
}

function _renderCitation(cite, index) {
    const cat = _sourceCategory(cite);
    const sourceKind = normalizeSourceKind(cite);
    const isNonReadableRecord = isNonReadableSourceKind(cite);
    const title = typeof citationTitle === 'function'
        ? citationTitle(cite, 'Untitled Resource')
        : (cite.title || cite.doc_title || cite.label || cite.doc_id || 'Untitled Resource');
    const authors = cite.authors || cite.author || 'Archipelago Academic Index';
    const year = cite.year || cite.publication_year || '';
    const isbn = cite.isbn || '';
    const edition = cite.edition || cite.venue || '';
    const pageNum = cite.page_number || cite.page || '';
    const page = pageNum && !isNonReadableRecord ? `p. ${pageNum}` : '';
    const passage = cite.text_passage || cite.passage || cite.snippet || '';
    const docId = cite.doc_id || cite.document_id || '';
    const rawReaderUrl = (!isNonReadableRecord && typeof citationPageUrl === 'function') ? citationPageUrl(cite) : '';
    const readerUrl = (rawReaderUrl && !/^\/chat(?:[?#]|$)/i.test(rawReaderUrl.trim())) ? rawReaderUrl : '';
    const truncPassage = passage.length > 240 ? passage.substring(0, 240) + '…' : passage;
    const recordNotice = sourceKind === 'metadata_only_record'
        ? 'Catalog / metadata record only — no full-text reader link.'
        : sourceKind === 'unavailable_document'
            ? 'Full-text document unavailable in this corpus.'
            : '';

    return `
        <div class="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/60 hover:border-accentPurple/50 transition-all cursor-pointer group shadow-sm"
             id="evidence-cite-${index}" data-cite-index="${index}" data-source-kind="${_escHTML(sourceKind)}" onclick="scrollToEvidence(${index})">
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
                    ${recordNotice ? `
                        <div class="mt-2 pt-1.5 border-t border-slate-700/50 text-[10px] text-slate-400 italic">${_escHTML(recordNotice)}</div>
                    ` : readerUrl ? `
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
    const latencyStr = trace.stage_timings_ms?.total_ms != null ? `${trace.stage_timings_ms.total_ms} ms` : 'Pending completion';
    const passagesStr = `${trace.grounded_passages || 0} cited passage${(trace.grounded_passages || 0) === 1 ? '' : 's'}`;
    const hopsStr = `${trace.graph_hops || 0} hop${(trace.graph_hops || 0) === 1 ? '' : 's'}`;

    const rows = [
        _traceRow('Routed Intent', trace.intent || 'GENERAL_EXPLANATION', 'fa-route', 'text-accentPurple'),
        _traceRow('Resolved Concept', trace.concept_label || trace.concept_id || 'None (Fallback)', 'fa-circle-nodes', 'text-accentCyan'),
        _traceRow('Graph Hops', hopsStr, 'fa-arrows-split-up-and-left', 'text-amber-400'),
        _traceRow('Retrieval Mode', trace.retrieval_mode || 'Unknown', 'fa-magnifying-glass-chart', 'text-accentPink'),
        _traceRow('Generation Mode', trace.synthesis_mode || 'Unknown', 'fa-wand-magic-sparkles', 'text-emerald-400'),
        _traceRow('Execution Provider', trace.provider || 'Unknown', 'fa-microchip', 'text-emerald-400'),
        ...(trace.provider_error ? [_traceRow('Provider Failure', trace.provider_error, 'fa-triangle-exclamation', 'text-amber-400')] : []),
        ...(trace.stream_status ? [_traceRow('Stream Status', trace.stream_status, 'fa-wave-square', 'text-amber-400')] : []),
        _traceRow('Model', trace.model || 'None', 'fa-robot', 'text-emerald-400'),
        _traceRow('Response Cache', trace.cache_status || 'Unknown', 'fa-box-archive', 'text-sky-400'),
        _traceRow('Release / Graph', `${trace.release_sha || 'Unknown'} / ${trace.graph_revision || 'Unknown'}`, 'fa-code-commit', 'text-slate-300'),
        _traceRow('Source Documents', (trace.source_document_ids || []).join(', ') || 'None', 'fa-book', 'text-slate-300'),
        _traceRow('Passage IDs', (trace.passage_ids || []).join(', ') || 'None', 'fa-paragraph', 'text-slate-300'),
        _traceRow('Retrieval Time', trace.stage_timings_ms?.evidence_retrieval_ms != null ? `${trace.stage_timings_ms.evidence_retrieval_ms} ms` : 'Not reported', 'fa-magnifying-glass', 'text-slate-300'),
        _traceRow('Provider TTFT', trace.stage_timings_ms?.provider_ttft_ms != null ? `${trace.stage_timings_ms.provider_ttft_ms} ms` : 'Not reported', 'fa-stopwatch', 'text-slate-300'),
        _traceRow('Template', trace.template_id ? `${trace.template_id} (${trace.template_influenced ? 'used' : 'not used'})` : 'None', 'fa-file-lines', 'text-slate-300'),
        _traceRow('Evidence Coverage', passagesStr, 'fa-file-lines', 'text-sky-400'),
        _traceRow('Measured Latency', latencyStr, 'fa-stopwatch', 'text-amber-300'),
        _traceRow('Passage Provenance', trace.provenance_status || 'Unknown', 'fa-shield-halved', 'text-emerald-400'),
        _traceRow('Claim Support', trace.claim_support_status || 'Not assessed', 'fa-circle-question', 'text-amber-300'),
        _traceRow('Reader Page', trace.reader_page_verified ? 'Automatically checked' : 'Not checked', 'fa-book-open', 'text-amber-300'),
    ];
    container.innerHTML = `<div class="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 flex flex-col">${rows.join('')}</div>`;
}

// ── Grounding status bar (above each assistant chat answer) ─────────────────

const CONVERSATIONAL_INTENTS = new Set([
    'GREETING', 'THANKS', 'HELP', 'CONVERSATIONAL', 'CAPABILITIES', 'SMALL_TALK', 'CHAT_HELP',
]);

function renderGroundingBadge(trace, metadata = null) {
    if (!trace) return '';
    const rawCitations = Array.isArray(metadata?.citations)
        ? metadata.citations
        : Array.isArray(trace.citations)
            ? trace.citations
            : [];
    const verifiedCitations = rawCitations.filter((cite) => {
        if (!cite || typeof cite !== 'object') return false;
        return !isNonReadableSourceKind(cite);
    });
    const explicitNotEvidenceBacked = metadata?.evidence_backed === false || trace.evidence_backed === false;
    const hasCitationEvidence = metadata
        ? verifiedCitations.length > 0
        : (verifiedCitations.length > 0 || Number(trace.grounded_passages || 0) > 0);
    const isEvidenceBacked = !explicitNotEvidenceBacked && hasCitationEvidence;

    const intentUpper = String(trace.intent || '').toUpperCase().trim();
    const isConversational = CONVERSATIONAL_INTENTS.has(intentUpper)
        || String(trace.synthesis_mode || '').toLowerCase() === 'conversational';
    const isAbstention = intentUpper === 'OUT_OF_DOMAIN' || intentUpper === 'UNSUPPORTED' || trace.grounding_status === 'abstained';

    const st = isEvidenceBacked
        ? (trace.grounding_status || 'verified')
        : (isConversational ? 'general' : isAbstention ? 'unmatched' : 'general');
    const c = BADGE_COLORS[st] || BADGE_COLORS.unmatched;
    const hops = trace.graph_hops || 0;
    const passages = isEvidenceBacked ? (Number(trace.grounded_passages || 0) || verifiedCitations.length) : 0;
    const latency = trace.stage_timings_ms?.total_ms != null ? `${trace.stage_timings_ms.total_ms} ms` : '';

    const modeLabels = {
        xkiro_synthesis: 'Live Provider (XKIRO)',
        nvidia_fallback: 'Live Provider (Fallback)',
        verified_deterministic: 'Deterministic · Evidence-Backed',
        provider_unavailable_fallback: 'Provider Unavailable · Grounded Fallback',
    };
    const streamStatusLabels = {
        truncated_token_limit: 'Truncated (Token Limit)',
        incomplete_stream: 'Incomplete Stream',
        timed_out: 'Timed Out',
        cancelled: 'Cancelled',
        stream_error: 'Stream Error',
    };
    const parts = [];
    if (trace.stream_status && streamStatusLabels[trace.stream_status]) {
        parts.push(streamStatusLabels[trace.stream_status]);
    } else if (isConversational && !isEvidenceBacked) {
        parts.push('Conversational');
    } else if (isAbstention) {
        parts.push(isEvidenceBacked ? 'Abstention' : 'Abstention · No Source Passages');
    } else if (!isEvidenceBacked) {
        parts.push('General Explanation · No Source Passages');
    } else if (trace.synthesis_mode && modeLabels[trace.synthesis_mode]) {
        parts.push(modeLabels[trace.synthesis_mode]);
    } else {
        parts.push('Evidence-Backed');
    }
    if (passages > 0 && isEvidenceBacked) parts.push(`${passages} cited passage${passages > 1 ? 's' : ''}`);
    if (hops > 0) parts.push(`${hops} graph hop${hops > 1 ? 's' : ''}`);
    if (latency) parts.push(latency);

    return `<div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${c.bg} border ${c.border} text-[10px] font-mono font-bold ${c.text} mb-2 w-fit select-none shadow-sm" data-evidence-backed="${isEvidenceBacked ? 'true' : 'false'}" title="${_escHTML(trace.grounding_badge || parts[0] || '')}">
        <span class="w-1.5 h-1.5 rounded-full ${c.dot}"></span>
        <span>${_escHTML(parts.join(' · '))}</span>
    </div>`;
}

// ── Retrieval mode indicator ────────────────────────────────────────────────

function updateRetrievalModeIndicator(trace) {
    const el = document.getElementById('retrieval-mode-indicator');
    if (!el) return;
    const mode = (trace && trace.retrieval_mode) ? trace.retrieval_mode : 'Graph-Assisted Traversal (OKF + Provenance-Checked Passages; Graph Edges Review Pending)';
    el.textContent = mode;
    el.classList.remove('hidden');
}

// ── Main population (called from 08-send-message.js) ────────────────────────

function populateInspector(metadata) {
    if (!metadata) {
        populateEvidence([]);
        populateTrace(null);
        return;
    }
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
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ── Global exports ──────────────────────────────────────────────────────────

if (typeof window !== 'undefined') {
    window.switchInspectorTab = switchInspectorTab;
    window.populateInspector = populateInspector;
    window.scrollToEvidence = scrollToEvidence;
    window.renderGroundingBadge = renderGroundingBadge;
}

export { _renderCitation, _sourceCategory, populateEvidence, populateInspector, populateTrace, renderGroundingBadge, scrollToEvidence, switchInspectorTab, updateRetrievalModeIndicator };
