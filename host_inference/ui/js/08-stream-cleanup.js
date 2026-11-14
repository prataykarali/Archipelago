// Restore the composer and avatar after every chat request.
import { state } from './00-state.js';
import { _updateGlowState } from './01--hide-welcome-with-transitio.js';
import { setSendButtonState } from './07-open-page-viewer-modal.js';
import { setLibrarianThinking } from './00-current-origin.js';

export function resetChatUi({ responseTimeoutId, streamIdleTimeoutId, chatMsgs, checkUserScroll }) {
                window.clearTimeout(responseTimeoutId);
                if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                if (chatMsgs) chatMsgs.removeEventListener('scroll', checkUserScroll);
                state.isGenerating = false;
                try { window.isGenerating = false; } catch (_) {}
                _updateGlowState(false);
                setSendButtonState('send');
                setLibrarianThinking(false);
                state.currentAssistantRow = null;
                state.currentAbortController = null;
                const sendBtn = document.getElementById('send-btn');
                if (sendBtn) {
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
