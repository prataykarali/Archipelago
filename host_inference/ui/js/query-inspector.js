/** Optional, text-only diagnostics. Never render trace fields as HTML. */
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
    const body = document.createElement('pre');
    body.className = 'whitespace-pre-wrap break-words mt-3 text-xs';
    body.textContent = JSON.stringify(trace, null, 2);
    details.append(summary, body);
    host.appendChild(details);
}