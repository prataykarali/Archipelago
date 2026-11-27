// Incremental stream control-marker parser safe across arbitrary network chunk boundaries.
const MARKER_TAIL_GUARD = 48;
const STREAM_STATUS_RE = /\[(STREAM_TRUNCATED|STREAM_INCOMPLETE):([a-zA-Z0-9_-]+)\]/g;

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
    const cleaned = String(text || '').replace(STREAM_STATUS_RE, (_m, kind, reason) => {
        streamStatus = kind === 'STREAM_TRUNCATED' ? 'truncated_token_limit' : 'incomplete_stream';
        streamReason = reason || '';
        return '';
    });
    return { cleaned, streamStatus, streamReason };
}
