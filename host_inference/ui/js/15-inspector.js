// SIGIR Demo Inspector — tabbed right panel (Graph / Evidence / Trace).
// Phase 2–7 of D-UX-1.
import { setPanelOpen, syncPanelToggleUI, isPanelOpen } from './03-wrap-library-inventory-secti.js';

const TAB_IDS = ['graph', 'evidence', 'trace'];
const BADGE_COLORS = {
    verified: { bg: 'bg-emerald-500/20', border: 'border-emerald-400/40', text: 'text-emerald-300', dot: 'bg-emerald-400' },
    partial:  { bg: 'bg-amber-500/20',   border: 'border-amber-400/40',   text: 'text-amber-300',   dot: 'bg-amber-400'   },
    general:  { bg: 'bg-sky-500/20',      border: 'border-sky-400/40',     text: 'text-sky-300',     dot: 'bg-sky-400'     },
    unmatched:{ bg: 'bg-gray-500/20',      border: 'border-gray-500/40',    text: 'text-gray-400',    dot: 'bg-gray-500'    },
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
    const cat = (cite.source_category || cite.category || '').toLowerCase();
    if (cat.includes('graph') || cat.includes('okf')) return { label: 'Graph Evidence', icon: 'fa-diagram-project', color: 'text-accentPurple' };
    if (cat.includes('open') || cat.includes('arxiv')) return { label: 'Open-Access Paper', icon: 'fa-globe', color: 'text-accentCyan' };
    if (cat.includes('library') || cat.includes('pearson')) return { label: 'Library Holding', icon: 'fa-building-columns', color: 'text-amber-400' };
    if (cat.includes('licensed') || cat.includes('ebook')) return { label: 'Licensed E-Book', icon: 'fa-book', color: 'text-accentPink' };
    return { label: 'Source', icon: 'fa-file-lines', color: 'text-gray-400' };
}

function _renderCitation(cite, index) {
    const cat = _sourceCategory(cite);
    const title = cite.title || cite.label || cite.doc_id || 'Untitled';
    const page = cite.page_number ? `p. ${cite.page_number}` : '';
    const passage = cite.text_passage || cite.passage || '';
    const docId = cite.doc_id || '';
    const truncPassage = passage.length > 200 ? passage.substring(0, 200) + '…' : passage;  // noqa: PLR2004

    return `
        <div class="p-3 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-all cursor-pointer group"
             id="evidence-cite-${index}" data-cite-index="${index}">
            <div class="flex items-start gap-2">
                <span class="mt-0.5 w-5 h-5 rounded-full bg-accentPurple/25 text-accentPurple text-[10px] font-black flex items-center justify-center shrink-0">${index + 1}</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-1.5 mb-1">
                        <i class="fa-solid ${cat.icon} ${cat.color} text-[10px]"></i>
                        <span class="text-[9px] font-bold uppercase tracking-wider ${cat.color}">${cat.label}</span>
                        ${page ? `<span class="text-[9px] text-gray-500 ml-auto">${page}</span>` : ''}
                    </div>
                    <p class="text-xs font-semibold text-white truncate">${_escHTML(title)}</p>
                    ${docId ? `<p class="text-[10px] text-gray-500 font-mono truncate">${_escHTML(docId)}</p>` : ''}
                    ${truncPassage ? `<p class="text-[10px] text-gray-400 leading-snug mt-1 line-clamp-3 group-hover:line-clamp-none transition-all">${_escHTML(truncPassage)}</p>` : ''}
                </div>
            </div>
        </div>`;
}

function populateEvidence(citations) {
    const container = document.getElementById('inspector-evidence-list');
    if (!container) return;
    const validCites = (citations || []).filter(c => c && typeof c === 'object' && (c.label || c.doc_id || c.text_passage || c.passage));
    if (validCites.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500 italic p-3 rounded bg-white/5 border border-white/5">No source evidence for this query.</p>';
        return;
    }
    container.innerHTML = validCites.map((c, i) => _renderCitation(c, i)).join('');
}

// ── Trace tab ────────────────────────────────────────────────────────────────

function _traceRow(label, value, icon, color) {
    return `
        <div class="flex items-center gap-2.5 py-1.5">
            <i class="fa-solid ${icon} ${color} text-[11px] w-4 text-center"></i>
            <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider w-28 shrink-0">${label}</span>
            <span class="text-xs text-white font-medium">${_escHTML(String(value ?? '—'))}</span>
        </div>`;
}

function populateTrace(trace) {
    const container = document.getElementById('inspector-trace-list');
    if (!container) return;
    if (!trace) {
        container.innerHTML = '<p class="text-xs text-gray-500 italic p-3">No trace data available.</p>';
        return;
    }
    const rows = [
        _traceRow('Intent', trace.intent, 'fa-route', 'text-accentPurple'),
        _traceRow('Concept', trace.concept_label || trace.concept_id || 'None', 'fa-circle-nodes', 'text-accentCyan'),
        _traceRow('Graph Hops', trace.graph_hops, 'fa-arrows-split-up-and-left', 'text-amber-400'),
        _traceRow('Retrieval', trace.retrieval_mode, 'fa-magnifying-glass-chart', 'text-accentPink'),
        _traceRow('Provider', trace.provider, 'fa-microchip', 'text-emerald-400'),
        _traceRow('Passages', trace.grounded_passages, 'fa-file-lines', 'text-sky-400'),
        _traceRow('Grounding', trace.grounding_status, 'fa-shield-check', 'text-amber-300'),
    ];
    container.innerHTML = `<div class="divide-y divide-white/5">${rows.join('')}</div>`;
}

// ── Grounding badge (above each chat answer) ────────────────────────────────

function renderGroundingBadge(trace) {
    if (!trace) return '';
    const st = trace.grounding_status || 'unmatched';
    const c = BADGE_COLORS[st] || BADGE_COLORS.unmatched;
    const hops = trace.graph_hops || 0;
    const passages = trace.grounded_passages || 0;
    const parts = [];
    if (passages > 0) parts.push(`${passages} verified passage${passages > 1 ? 's' : ''}`);
    if (hops > 0) parts.push(`${hops} graph hop${hops > 1 ? 's' : ''}`);
    if (parts.length === 0) parts.push(trace.grounding_badge || 'Unmatched');
    return `<div class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg ${c.bg} border ${c.border} text-[10px] font-bold ${c.text} mb-1.5 w-fit select-none" title="${_escHTML(trace.grounding_badge || '')}">
        <span class="w-1.5 h-1.5 rounded-full ${c.dot}"></span>
        ${_escHTML(parts.join(' · '))}
    </div>`;
}

// ── Retrieval mode indicator ────────────────────────────────────────────────

function updateRetrievalModeIndicator(trace) {
    const el = document.getElementById('retrieval-mode-indicator');
    if (!el) return;
    const mode = (trace && trace.retrieval_mode) ? trace.retrieval_mode : 'Graph-Assisted Hybrid';
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

    // Decide which tab to show and auto-open the inspector
    const hasAnchor = metadata.anchor_concept && metadata.anchor_concept.id;
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

    // Auto-open the inspector panel if it's closed
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
            el.classList.add('ring-2', 'ring-accentPurple/60');
            setTimeout(() => el.classList.remove('ring-2', 'ring-accentPurple/60'), 2000);
        }
    });
}

// ── Utilities ────────────────────────────────────────────────────────────────

function _escHTML(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ── Global exports ──────────────────────────────────────────────────────────

window.switchInspectorTab = switchInspectorTab;
window.populateInspector = populateInspector;
window.scrollToEvidence = scrollToEvidence;
window.renderGroundingBadge = renderGroundingBadge;

export { populateEvidence, populateInspector, populateTrace, renderGroundingBadge, scrollToEvidence, switchInspectorTab, updateRetrievalModeIndicator };
