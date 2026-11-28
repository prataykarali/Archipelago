// D11-B-UX: Contextual Follow-Up Chips & Per-Query Sanitized Evidence Export.
// Follow-up chips ONLY execute on explicit user click (never auto-submitted)
// and never claim unreviewed graph edges are verified.
// Evidence export strips all cookies, bearer tokens, JWTs, and credentials.

const MAX_FOLLOW_UP_CHIPS = 5;
const MAX_FALLBACK_FOLLOW_UP_CHIPS = 3;

const SENSITIVE_KEY_RE = /(?:token|cookie|auth|secret|password|passwd|credential|api[_-]?key|bearer|jwt|session[_-]?id|supabase|private[_-]?key|set-cookie|x-api-key)/i;
const SENSITIVE_VALUE_RE = /(?:Bearer\s+[A-Za-z0-9\-._~+/]+=*|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|(?:^|[\s;])(?:session|auth|sb-[a-z0-9_-]+)=[^\s;]+|sk-[A-Za-z0-9_-]{12,}|sbp_[A-Za-z0-9_-]{12,})/i;

function _escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function extractFollowUpQuestions(metadata) {
    if (!metadata || typeof metadata !== 'object') return [];
    const raw = Array.isArray(metadata.follow_up_questions)
        ? metadata.follow_up_questions
        : Array.isArray(metadata.followups)
            ? metadata.followups
            : [];

    const isFallback = metadata.fallback_mode === 'abstention' || metadata.fallback_mode === 'general_explanation';
    const limit = isFallback ? MAX_FALLBACK_FOLLOW_UP_CHIPS : MAX_FOLLOW_UP_CHIPS;
    const seen = new Set();
    const out = [];
    for (const item of raw) {
        const text = typeof item === 'string'
            ? item.trim()
            : String(item?.query || item?.question || item?.text || item?.label || '').trim();
        if (!text) continue;
        const key = text.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(text);
        if (out.length >= limit) break;
    }
    return out;
}

function renderFollowUpChips(msgEl, assistantMsgId, metadata) {
    if (!msgEl || typeof document === 'undefined') return null;
    const questions = extractFollowUpQuestions(metadata);
    const zoneId = `followup-chips-zone-${assistantMsgId}`;
    const existing = document.getElementById(zoneId);
    if (!questions.length) {
        if (existing) existing.remove();
        return null;
    }

    const zone = existing || document.createElement('div');
    zone.id = zoneId;
    zone.className = 'followup-chips-zone';
    zone.setAttribute('role', 'region');
    zone.setAttribute('aria-label', 'Suggested follow-up questions');

    const chipsHtml = questions
        .map((q) => `
            <button type="button" class="followup-chip" data-followup-query="${_escapeHtml(q)}">
                <svg class="followup-chip-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="15 10 20 15 15 20"></polyline>
                    <path d="M4 4v7a4 4 0 0 0 4 4h12"></path>
                </svg>
                <span>${_escapeHtml(q)}</span>
            </button>
        `)
        .join('');

    zone.innerHTML = `
        <div class="followup-chips-header">
            <span class="followup-chips-label">Suggested follow-ups</span>
        </div>
        <div class="followup-chips-list">
            ${chipsHtml}
        </div>
    `;

    zone.querySelectorAll('.followup-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
            const query = chip.getAttribute('data-followup-query') || '';
            if (query && typeof window !== 'undefined' && typeof window.autoPrompt === 'function') {
                window.autoPrompt(query);
            }
        });
    });

    if (!zone.parentNode) {
        msgEl.appendChild(zone);
    }
    return zone;
}

function sanitizeEvidenceValue(value, depth = 0) {
    if (depth > 8) return null;
    if (value === null || value === undefined) return value;
    if (typeof value === 'string') {
        if (SENSITIVE_VALUE_RE.test(value)) {
            return '[REDACTED]';
        }
        return value;
    }
    if (typeof value === 'number' || typeof value === 'boolean') return value;
    if (Array.isArray(value)) {
        return value
            .map((item) => sanitizeEvidenceValue(item, depth + 1))
            .filter((item) => item !== undefined);
    }
    if (typeof value === 'object') {
        const clean = {};
        for (const [key, val] of Object.entries(value)) {
            if (SENSITIVE_KEY_RE.test(key)) continue;
            const cleanedVal = sanitizeEvidenceValue(val, depth + 1);
            if (cleanedVal !== undefined) {
                clean[key] = cleanedVal;
            }
        }
        return clean;
    }
    return String(value);
}

function _nodeIdentifier(node) {
    if (!node) return '';
    if (typeof node === 'string') return node.trim();
    return String(node.canonical_id || node.id || node.concept_id || node.label || node.name || '').trim();
}

function _nodeTitle(node) {
    if (!node) return '';
    if (typeof node === 'string') return node.trim();
    return String(node.label || node.name || node.title || node.id || '').trim();
}

function buildSanitizedEvidenceBundle({ query = '', answerText = '', metadata = null } = {}) {
    const meta = (metadata && typeof metadata === 'object') ? metadata : {};
    const trace = (meta.trace && typeof meta.trace === 'object') ? meta.trace : {};

    const rawCitations = Array.isArray(meta.citations)
        ? meta.citations
        : Array.isArray(meta.evidence)
            ? meta.evidence
            : [];

    const citations = rawCitations
        .filter((c) => c && typeof c === 'object')
        .map((c) => sanitizeEvidenceValue({
            title: c.title || c.doc_title || c.label || c.doc_id || '',
            doc_id: c.doc_id || c.document_id || '',
            passage_id: c.passage_id || '',
            page_number: c.page_number ?? c.page ?? null,
            authors: c.authors || c.author || '',
            year: c.year || c.publication_year || null,
            source_category: c.source_category || c.category || '',
            snippet: c.text_passage || c.passage || c.snippet || '',
        }));

    const passageIdSet = new Set();
    const pushIds = (arr) => {
        if (!Array.isArray(arr)) return;
        for (const id of arr) {
            const s = String(id || '').trim();
            if (s) passageIdSet.add(s);
        }
    };
    pushIds(trace.passage_ids);
    pushIds(trace.cited_passage_ids);
    pushIds(trace.retrieved_passage_ids);
    for (const c of citations) {
        if (c && c.passage_id) passageIdSet.add(String(c.passage_id));
    }

    const graphEdges = [];
    const anchor = meta.anchor_concept || null;
    const anchorId = _nodeIdentifier(anchor);
    const anchorLabel = _nodeTitle(anchor);
    if (anchorId) {
        const pushEdges = (list, relation, fromAnchor) => {
            if (!Array.isArray(list)) return;
            for (const item of list) {
                const targetId = _nodeIdentifier(item);
                const targetLabel = _nodeTitle(item);
                if (!targetId) continue;
                graphEdges.push({
                    source: fromAnchor ? anchorId : targetId,
                    source_label: fromAnchor ? anchorLabel : targetLabel,
                    relation,
                    target: fromAnchor ? targetId : anchorId,
                    target_label: fromAnchor ? targetLabel : anchorLabel,
                });
            }
        };
        pushEdges(meta.prerequisites, 'REQUIRES', true);
        pushEdges(meta.unlocks, 'UNLOCKS', true);
        pushEdges(meta.related_concepts || meta.related, 'RELATED', true);
    }

    return sanitizeEvidenceValue({
        schema_version: 'archipelago-evidence-v1',
        exported_at: new Date().toISOString(),
        query: String(query || ''),
        answer: String(answerText || ''),
        citations,
        passage_ids: Array.from(passageIdSet),
        graph_edges: graphEdges,
        execution_trace: sanitizeEvidenceValue(trace),
    });
}

function formatEvidenceMarkdown(bundle) {
    const safe = sanitizeEvidenceValue(bundle || {});
    const lines = [
        '# Archipelago Evidence Bundle',
        '',
        `- **Exported At:** ${safe.exported_at || ''}`,
        `- **Query:** ${safe.query || ''}`,
        '',
        '## Answer',
        '',
        safe.answer || '_No answer text._',
        '',
        '## Citations',
        '',
    ];

    const cites = Array.isArray(safe.citations) ? safe.citations : [];
    if (!cites.length) {
        lines.push('_No citations recorded._');
    } else {
        cites.forEach((c, idx) => {
            const page = c.page_number != null ? ` (p. ${c.page_number})` : '';
            const pid = c.passage_id ? ` \`${c.passage_id}\`` : '';
            lines.push(`${idx + 1}. **${c.title || c.doc_id || 'Source'}**${page}${pid}`);
            if (c.snippet) {
                lines.push(`   > ${String(c.snippet).replace(/\n+/g, ' ').slice(0, 320)}`);
            }
        });
    }

    lines.push('', '## Passage IDs', '');
    const pids = Array.isArray(safe.passage_ids) ? safe.passage_ids : [];
    lines.push(pids.length ? pids.map((id) => `- \`${id}\``).join('\n') : '_None recorded._');

    lines.push('', '## Graph Edges', '');
    const edges = Array.isArray(safe.graph_edges) ? safe.graph_edges : [];
    if (!edges.length) {
        lines.push('_No graph edges recorded._');
    } else {
        edges.forEach((e) => {
            lines.push(`- ${e.source_label || e.source} --[${e.relation}]--> ${e.target_label || e.target}`);
        });
    }

    lines.push('', '## Execution Trace', '', '```json', JSON.stringify(safe.execution_trace || {}, null, 2), '```', '');
    return lines.join('\n');
}

function downloadEvidenceBundle(bundle, format = 'json') {
    if (typeof document === 'undefined' || typeof Blob === 'undefined' || typeof URL === 'undefined') return false;
    const safeBundle = sanitizeEvidenceValue(bundle);
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const isMd = format === 'md' || format === 'markdown';
    const content = isMd ? formatEvidenceMarkdown(safeBundle) : JSON.stringify(safeBundle, null, 2);
    const mime = isMd ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8';
    const ext = isMd ? 'md' : 'json';
    const filename = `archipelago-evidence-${stamp}.${ext}`;

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => {
        try { URL.revokeObjectURL(url); } catch (_) {}
    }, 1000);
    return true;
}

function renderEvidenceExportBar(msgEl, assistantMsgId, { query = '', answerText = '', metadata = null } = {}) {
    if (!msgEl || typeof document === 'undefined') return null;
    const barId = `evidence-export-bar-${assistantMsgId}`;
    const existing = document.getElementById(barId);
    const bar = existing || document.createElement('div');
    bar.id = barId;
    bar.className = 'evidence-export-bar';
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'Export evidence bundle');

    bar.innerHTML = `
        <button type="button" class="evidence-export-btn" data-export-format="json" title="Download sanitized evidence bundle as JSON">
            <i class="fa-solid fa-file-arrow-down" aria-hidden="true"></i>
            <span>Export Evidence (JSON)</span>
        </button>
        <button type="button" class="evidence-export-btn evidence-export-btn-secondary" data-export-format="md" title="Download sanitized evidence bundle as Markdown">
            <i class="fa-solid fa-file-lines" aria-hidden="true"></i>
            <span>Markdown</span>
        </button>
    `;

    bar.querySelectorAll('.evidence-export-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
            const fmt = btn.getAttribute('data-export-format') || 'json';
            const bundle = buildSanitizedEvidenceBundle({ query, answerText, metadata });
            downloadEvidenceBundle(bundle, fmt);
        });
    });

    if (!bar.parentNode) {
        msgEl.appendChild(bar);
    }
    return bar;
}

export {
    MAX_FOLLOW_UP_CHIPS,
    SENSITIVE_KEY_RE,
    SENSITIVE_VALUE_RE,
    buildSanitizedEvidenceBundle,
    downloadEvidenceBundle,
    extractFollowUpQuestions,
    formatEvidenceMarkdown,
    renderEvidenceExportBar,
    renderFollowUpChips,
    sanitizeEvidenceValue,
};
