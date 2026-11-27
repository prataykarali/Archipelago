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
                        if (window._lastChatMetadata?.trace) {
                            window._lastChatMetadata.trace.stream_status = 'incomplete_stream';
                            if (typeof window.populateInspector === 'function') {
                                window.populateInspector(window._lastChatMetadata);
                            }
                        }
                        const note = document.createElement('div');
                        note.className = 'stream-abort-note text-amber-300/90 text-xs mt-2 opacity-80';
                        note.textContent = 'Incomplete stream — response interrupted before completion (showing partial text received).';
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
                    if (msgEl) {
                        msgEl.classList.remove('ai-typewriter-cursor', 'is-live-streaming');
                        const wrap = msgEl.closest('.msg-bubble-wrap');
                        if (wrap) wrap.classList.remove('is-thinking');
                        if (msgEl.querySelector('.typing-indicator, .thinking-orb-loader, .thinking-lightgrid')) {
                            msgEl.innerHTML = '';
                        }
                    }
                    if (window._lastChatMetadata?.trace) {
                        window._lastChatMetadata.trace.stream_status = aborted ? 'incomplete_stream' : 'stream_error';
                        if (typeof window.populateInspector === 'function') {
                            window.populateInspector(window._lastChatMetadata);
                        }
                    }
                    // Preserve unsent/unanswered question on recoverable error or timeout so user can retry.
                    const draftEl = document.getElementById('chat-input');
                    if (draftEl && inputVal && !draftEl.value.trim()) {
                        draftEl.value = inputVal;
                        draftEl.style.height = 'auto';
                        draftEl.style.height = Math.min(draftEl.scrollHeight, 200) + 'px';
                    }
                    const why = aborted
                        ? ((err.message && err.message !== 'The user aborted a request.') ? err.message : 'Incomplete stream — connection was interrupted. Your question was restored below so you can retry.')
                        : (err && err.message ? err.message : 'An unexpected error occurred. Your question was restored below so you can retry.');
                    if (msgEl) {
                        msgEl.textContent = why;
                    }
                }
}
