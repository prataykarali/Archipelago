// Restore the composer and avatar after every chat request.
import { state } from './00-state.js';
import { _updateGlowState } from './01--hide-welcome-with-transitio.js';
import { setSendButtonState } from './07-open-page-viewer-modal.js';
import { setLibrarianThinking } from './00-current-origin.js';

export function resetChatUi({
    responseTimeoutId,
    streamIdleTimeoutId,
    chatMsgs,
    checkUserScroll,
    typewriter = null,
    reader = null,
} = {}) {
    if (responseTimeoutId) {
        try { window.clearTimeout(responseTimeoutId); } catch (_) {}
    }
    if (streamIdleTimeoutId) {
        try { window.clearTimeout(streamIdleTimeoutId); } catch (_) {}
    }
    if (chatMsgs && checkUserScroll) {
        try { chatMsgs.removeEventListener('scroll', checkUserScroll); } catch (_) {}
    }
    if (typewriter && typeof typewriter.stop === 'function') {
        try { typewriter.stop(); } catch (_) {}
    }
    if (state.activeTypewriter && typeof state.activeTypewriter.stop === 'function') {
        try { state.activeTypewriter.stop(); } catch (_) {}
    }
    state.activeTypewriter = null;

    if (reader && typeof reader.cancel === 'function') {
        try {
            const p = reader.cancel();
            if (p && typeof p.catch === 'function') p.catch(() => {});
        } catch (_) {}
    }
    state.activeStreamReader = null;

    state.isGenerating = false;
    try { window.isGenerating = false; } catch (_) {}
    window.archipelagoChatAuthChecking = false;
    state.currentAssistantRow = null;
    state.currentAbortController = null;

    try { _updateGlowState(false); } catch (_) {}
    try { setSendButtonState('send'); } catch (_) {}
    try { setLibrarianThinking(false); } catch (_) {}

    try {
        document.querySelectorAll('.model-reply-status').forEach((el) => {
            try { el.remove(); } catch (_) {}
        });
        document.querySelectorAll('.msg-bubble-wrap.is-thinking, .ai-typewriter-cursor, .is-live-streaming').forEach((el) => {
            el.classList.remove('is-thinking', 'ai-typewriter-cursor', 'is-live-streaming');
        });
        document.querySelectorAll('.typing-indicator, .thinking-orb-loader, .thinking-lightgrid').forEach((el) => {
            try { el.remove(); } catch (_) {}
        });
    } catch (_) {}

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
    try { setLibrarianThinking(false); } catch (_) {}
}
