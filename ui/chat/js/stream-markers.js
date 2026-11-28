// Incremental stream control-marker parser safe across arbitrary network chunk boundaries.
const MARKER_TAIL_GUARD = 512;
const STREAM_STATUS_RE = /\[(STREAM_TRUNCATED|STREAM_INCOMPLETE):([a-zA-Z0-9_-]+)\]/g;
const STREAM_META_RE = /\[STREAM_META:(\{[^\n]*\})\]/g;

/**
 * Split ``incoming`` into a safe-to-consume prefix and a trailing guard slice
 * so terminal markers ([STREAM_DONE], [STREAM_TRUNCATED:*], [STREAM_INCOMPLETE:*],
 * [MODEL_REWRITE], [CLEAN]) split across chunks are reassembled before parsing.
 */
export function splitSafeStreamChunk(buffered, { finalFlush = false } = {}) {
    if (!buffered) return { ready: '', remainder: '' };
    if (finalFlush) return { ready: buffered, remainder: '' };
    const lastBracket = buffered.lastIndexOf('[');
    if (lastBracket === -1) {
        return { ready: buffered, remainder: '' };
    }
    const tailLen = buffered.length - lastBracket;
    if (tailLen <= MARKER_TAIL_GUARD && buffered.indexOf(']', lastBracket) === -1) {
        return {
            ready: buffered.slice(0, lastBracket),
            remainder: buffered.slice(lastBracket),
        };
    }
    return { ready: buffered, remainder: '' };
}

/**
 * Extract [STREAM_TRUNCATED:<reason>] and [STREAM_INCOMPLETE:<reason>] control
 * tags from ``text``, returning cleaned prose plus any detected terminal status.
 */
export function extractStreamStatusMarkers(text) {
    let streamStatus = null;
    let streamReason = null;
    let terminalMeta = null;
    let cleaned = String(text || '').replace(STREAM_STATUS_RE, (_m, kind, reason) => {
        streamStatus = kind === 'STREAM_TRUNCATED' ? 'truncated_token_limit' : 'incomplete_stream';
        streamReason = reason || '';
        return '';
    });
    cleaned = cleaned.replace(STREAM_META_RE, (_m, jsonStr) => {
        try {
            terminalMeta = JSON.parse(jsonStr);
            if (window && window._lastChatMetadata && terminalMeta) {
                Object.assign(window._lastChatMetadata, terminalMeta);
                const trace = (window._lastChatMetadata.trace && typeof window._lastChatMetadata.trace === 'object')
                    ? window._lastChatMetadata.trace
                    : (window._lastChatMetadata.trace = {});
                const timings = (trace.stage_timings_ms && typeof trace.stage_timings_ms === 'object')
                    ? trace.stage_timings_ms
                    : (trace.stage_timings_ms = {});
                const rootTimings = (window._lastChatMetadata.stage_timings_ms && typeof window._lastChatMetadata.stage_timings_ms === 'object')
                    ? window._lastChatMetadata.stage_timings_ms
                    : (window._lastChatMetadata.stage_timings_ms = {});
                const timingFields = [
                    'auth_ms',
                    'query_resolution_ms',
                    'retrieval_ms',
                    'evidence_retrieval_ms',
                    'reranking_ms',
                    'provider_ttft_ms',
                    'visible_ttft_ms',
                    'ttft_visible_ms',
                    'provider_stream_ms',
                    'total_ms',
                ];
                for (const key of timingFields) {
                    if (Object.prototype.hasOwnProperty.call(terminalMeta, key) && terminalMeta[key] !== undefined) {
                        timings[key] = terminalMeta[key];
                        rootTimings[key] = terminalMeta[key];
                    }
                }
                for (const key of ['request_id', 'provider_status', 'fallback_reason', 'cache_status', 'stream_status', 'completion_status', 'finish_reason']) {
                    if (Object.prototype.hasOwnProperty.call(terminalMeta, key) && terminalMeta[key] !== undefined) {
                        trace[key] = terminalMeta[key];
                    }
                }
                if (typeof window.populateInspector === 'function') {
                    window.populateInspector(window._lastChatMetadata);
                }
            }
        } catch (_err) {
            // Ignore malformed terminal metadata frame
        }
        return '';
    });
    return { cleaned, streamStatus, streamReason, terminalMeta };
}

/**
 * Parse the leading [STREAM_START] metadata JSON and hydrate pipeline/graph UI.
 */
export function parseAndApplyStreamMetadata(
    metaStr,
    { applyCorpusProfileUi, populatePipeline, populateTopology, updateBookStackForQuery },
) {
    try {
        const metadata = JSON.parse(metaStr);
        window._lastChatMetadata = metadata;
        applyCorpusProfileUi(metadata);
        populatePipeline(metadata);
        populateTopology(
            metadata.anchor_concept,
            metadata.prerequisites,
            metadata.unlocks,
            metadata.related_concepts || metadata.related || [],
        );
        if (typeof window.populateInspector === 'function') {
            window.populateInspector(metadata);
        }
        if (typeof updateBookStackForQuery === 'function') {
            updateBookStackForQuery(metadata);
        }
        return metadata;
    } catch (err) {
        console.error('Error parsing pipeline metadata:', err);
        return null;
    }
}
