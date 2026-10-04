/** Optional readable diagnostics. Raw transport details require a second action. */
export function renderQueryInspector(msgId, metadata) {
    const host = document.getElementById(`msg-body-${msgId}`);
    const trace = metadata?.inspector;
    if (!host || !trace || document.getElementById(`query-inspector-${msgId}`)) return;
    const details = document.createElement('details');
    details.id = `query-inspector-${msgId}`;
    details.className = 'mt-3 rounded-xl border border-white/10 p-3 text-xs text-gray-300';
    const summary = document.createElement('summary');
    summary.textContent = 'Query Inspector (optional)';
    summary.className = 'cursor-pointer font-semibold';
    const list = document.createElement('dl');
    list.className = 'grid gap-2 mt-3';
    const fields = [
        ['Response', trace.intent], ['Route', trace.route],
        ['Retrieval', trace.retrieval_type], ['Corpus', trace.corpus_source],
        ['Concepts retrieved', trace.nodes_retrieved],
        ['Source pages', Array.isArray(trace.source_pages) ? trace.source_pages.length : 0],
        ['Privacy', trace.privacy_policy],
    ];
    for (const [label, value] of fields) {
        if (value === undefined || value === null) continue;
        const row = document.createElement('div');
        const term = document.createElement('dt');
        term.className = 'font-semibold';
        term.textContent = label;
        const definition = document.createElement('dd');
        definition.className = 'break-words opacity-80';
        definition.textContent = String(value).replaceAll('_', ' ');
        row.append(term, definition);
        list.append(row);
    }
    const debug = document.createElement('details');
    debug.className = 'mt-3';
    const debugSummary = document.createElement('summary');
    debugSummary.textContent = 'Show raw debug JSON';
    const body = document.createElement('pre');
    body.className = 'whitespace-pre-wrap break-words mt-3 text-xs';
    body.textContent = JSON.stringify(trace, null, 2);
    debug.append(debugSummary, body);
    details.append(summary, list, debug);
    host.appendChild(details);
}