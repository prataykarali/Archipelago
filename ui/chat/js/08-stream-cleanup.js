// Restore the composer and avatar after every chat request.
import { state } from './00-state.js';
import { _updateGlowState } from './01--hide-welcome-with-transitio.js';
import { setSendButtonState } from './07-open-page-viewer-modal.js';
import { setLibrarianThinking } from './00-current-origin.js';

export function resetChatUi({ responseTimeoutId, streamIdleTimeoutId, chatMsgs, checkUserScroll }) {
                window.clearTimeout(responseTimeoutId);
                if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                if (state.activeResponseTimeoutId) {
                    window.clearTimeout(state.activeResponseTimeoutId);
                    state.activeResponseTimeoutId = null;
                }
                if (state.activeStreamIdleTimeoutId) {
                    window.clearTimeout(state.activeStreamIdleTimeoutId);
                    state.activeStreamIdleTimeoutId = null;
                }
                if (state.activeTypewriter) {
                    try { state.activeTypewriter.stop(); } catch (_) {}
                    state.activeTypewriter = null;
                }
                if (chatMsgs && checkUserScroll) chatMsgs.removeEventListener('scroll', checkUserScroll);
                if (state.activeScrollTarget && state.activeScrollHandler) {
                    try { state.activeScrollTarget.removeEventListener('scroll', state.activeScrollHandler); } catch (_) {}
                }
                state.activeScrollTarget = null;
                state.activeScrollHandler = null;
                state.isGenerating = false;
                try { window.isGenerating = false; } catch (_) {}
                window.archipelagoChatAuthChecking = false;
                _updateGlowState(false);
                setSendButtonState('send');
                setLibrarianThinking(false);
                state.currentAssistantRow = null;
                state.currentAbortController = null;
                document.querySelectorAll('.model-reply-status').forEach((el) => {
                    try { el.remove(); } catch (_) {}
                });
                document.querySelectorAll('.msg-bubble-wrap.is-thinking, .ai-typewriter-cursor, .is-live-streaming').forEach((el) => {
                    el.classList.remove('is-thinking', 'ai-typewriter-cursor', 'is-live-streaming');
                });
                const sendBtn = document.getElementById('send-btn');
                if (sendBtn) {
                    sendBtn.removeAttribute('aria-busy');
                    const quotaBlocked = Boolean(state.quotaLimitedUntil && Date.now() < state.quotaLimitedUntil);
                    sendBtn.disabled = quotaBlocked;
                    sendBtn.classList.toggle('opacity-50', quotaBlocked);
                    sendBtn.classList.toggle('pointer-events-none', quotaBlocked);
                }
                const inputEl = document.getElementById('chat-input');
                if (inputEl) {
                    inputEl.disabled = false;
                    setTimeout(() => { try { inputEl.focus(); } catch (_) {} }, 50);
                }
                // Single sticky librarian: think → hi (loops constantly)
                setLibrarianThinking(false);
}
