// Build the bounded chat request and surface quota headers/errors.
import { state } from './00-state.js';
import { API_HOST, MAX_HISTORY_TURNS_SENT } from './00-current-origin.js';

export function formatQuotaResetTime(resetAt, retryAfter) {
    let targetMs = 0;
    if (resetAt) {
        const parsed = Date.parse(String(resetAt));
        if (!Number.isNaN(parsed)) {
            targetMs = parsed;
        }
    }
    if (!targetMs) {
        const seconds = Math.max(1, Number(retryAfter || 60));
        targetMs = Date.now() + seconds * 1000;
    }
    try {
        return new Date(targetMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (_) {
        const minutes = Math.max(1, Math.ceil((targetMs - Date.now()) / 60000));
        return `${minutes} min`;
    }
}

export function applyQuotaCooldown(resetAt, retryAfter) {
    let targetMs = 0;
    if (resetAt) {
        const parsed = Date.parse(String(resetAt));
        if (!Number.isNaN(parsed) && parsed > Date.now()) {
            targetMs = parsed;
        }
    }
    if (!targetMs) {
        const seconds = Math.max(1, Number(retryAfter || 60));
        targetMs = Date.now() + seconds * 1000;
    }
    state.quotaLimitedUntil = targetMs;
    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.classList.add('opacity-50', 'pointer-events-none');
    }
    if (state.quotaTimerId) {
        window.clearTimeout(state.quotaTimerId);
    }
    const delayMs = Math.max(500, targetMs - Date.now());
    state.quotaTimerId = window.setTimeout(async () => {
        state.quotaLimitedUntil = 0;
        state.quotaTimerId = null;
        if (!state.isGenerating) {
            const btn = document.getElementById('send-btn');
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'pointer-events-none');
            }
        }
        const quotaLabel = document.getElementById('query-limit-status');
        try {
            const res = await fetch('/api/chat/quota');
            if (res.ok && quotaLabel) {
                const quota = await res.json();
                if (!quota.unrestricted && !quota.limited && Number(quota.retry_after || 0) <= 0) {
                    const limit = Number(quota.limit || 10);
                    quotaLabel.textContent = `Student chat queries: ${quota.used ?? 0} / ${limit} this hour`;
                }
            }
        } catch (_) {
            if (quotaLabel) {
                quotaLabel.textContent = 'Student chat queries: rolling hourly window';
            }
        }
    }, delayMs);
}

export async function postChatRequest(inputVal, signal, options = { synthesis: true }) {
    // Send only the last N turns — long chats must not bloat the request body.
    const cleanHistory = state.chatHistory
        .slice(-MAX_HISTORY_TURNS_SENT)
        .map(h => ({
            role: h.role,
            content: typeof h.content === 'string' ? h.content : JSON.stringify(h.content || '')
        }));

    const response = await fetch(`${API_HOST}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal,
        body: JSON.stringify({
            query: inputVal,
            reply_detail: 'expanded',
            request_id: crypto.randomUUID(),
            mode: state.currentMode,
            history: cleanHistory,
            session_id: state.conversationSessionId,
            // Enable synthesis so that local SLM generates natural academic answers
            synthesis: options?.synthesis !== false
        })
    });

    const quotaLabel = document.getElementById('query-limit-status');
    const usedHeader = response.headers.get('X-Queries-Used');
    const remainingHeader = response.headers.get('X-Queries-Remaining');
    const limitHeader = response.headers.get('X-Queries-Limit');
    if (quotaLabel && (usedHeader !== null || remainingHeader !== null)) {
        const limit = limitHeader !== null
            ? Number(limitHeader)
            : (usedHeader !== null && remainingHeader !== null
                ? Number(usedHeader) + Number(remainingHeader)
                : 10);
        const used = usedHeader !== null
            ? Number(usedHeader)
            : Math.max(0, limit - Number(remainingHeader));
        quotaLabel.textContent = `Student chat queries: ${used} / ${limit} this hour`;
    }

    if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        if (response.status === 401) {
            const err = new Error(problem.detail || 'Sign in to send your question.');
            err.status = 401;
            err.reason = problem.reason || 'unauthorized';
            throw err;
        }
        if (response.status === 429) {
            const resetText = formatQuotaResetTime(problem.reset_at, problem.retry_after);
            const message = problem.detail
                || `Hourly chat limit reached (10/10). You can ask another question after ${resetText}.`;
            if (quotaLabel) {
                quotaLabel.textContent = message;
            }
            applyQuotaCooldown(problem.reset_at, problem.retry_after);
            const err = new Error(message);
            err.status = 429;
            err.quota = problem;
            throw err;
        }
        throw new Error(problem.detail || `HTTP Error ${response.status}`);
    }

    return response;
}
