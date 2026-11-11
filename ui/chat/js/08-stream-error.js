// Preserve partial answers when a chat stream aborts or fails.
import { state } from './00-state.js';
import { renderMarkdownSafely } from './01--hide-welcome-with-transitio.js';
import { getResponseCitations } from './02--kw-highlights.js';
import { saveSession } from './20--compact-history.js';

export function handleStreamError(err, context) {
    const { msgEl, staticStreamBuffer, assistantText, rewriteBuffer, typewriter, finalizeStreamedBubble, inputVal } = context;
                console.error(err);
                // Keep any grounded / partial SLM text already painted. Wiping the
                // bubble on AbortError ("BodyStreamBuffer was aborted") made GPU
                // replies look like total failures after metadata + first paint.
                const partial = (staticStreamBuffer && staticStreamBuffer.trim())
                    || (assistantText && assistantText.trim())
                    || (rewriteBuffer && rewriteBuffer.trim())
                    || '';
                const aborted = !!(err && (err.name === 'AbortError' || /aborted|BodyStreamBuffer/i.test(String(err.message || err))));
                if (partial) {
                    try { if (typewriter && typeof typewriter.flush === 'function') typewriter.flush(); } catch (_) {}
                    try {
                        if (typeof finalizeStreamedBubble === 'function') finalizeStreamedBubble();
                        else {
                            renderMarkdownSafely(
                                msgEl,
                                partial,
                                window._lastChatMetadata ? getResponseCitations(window._lastChatMetadata) : null
                            );
                        }
                    } catch (_) {
                        try {
                            renderMarkdownSafely(
                                msgEl,
                                partial,
                                window._lastChatMetadata ? getResponseCitations(window._lastChatMetadata) : null
                            );
                        } catch (__) {}
                    }
                    if (aborted && msgEl && !msgEl.querySelector('.stream-abort-note')) {
                        const note = document.createElement('div');
                        note.className = 'stream-abort-note text-amber-300/90 text-xs mt-2 opacity-80';
                        note.textContent = 'Generation stopped — showing the answer received so far.';
                        msgEl.appendChild(note);
                    }
                    try {
                        state.chatHistory.push({ role: 'user', content: inputVal });
                        state.chatHistory.push({
                            role: 'assistant',
                            content: partial,
                            citations: getResponseCitations(window._lastChatMetadata),
                            metadata: window._lastChatMetadata,
                        });
                        saveSession();
                    } catch (_) {}
                } else {
                    if (msgEl && msgEl.querySelector('.typing-indicator, .thinking-orb-loader, .thinking-lightgrid')) {
                        msgEl.innerHTML = '';
                    }
                    const why = aborted
                        ? ((err.message && err.message !== 'The user aborted a request.') ? err.message : 'stream was interrupted')
                        : (err && err.message ? err.message : 'unknown error');
                    if (msgEl) {
                        msgEl.textContent = why;
                    }
                }
}
