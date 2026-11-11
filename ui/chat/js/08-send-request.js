// Build the bounded chat request and surface quota headers/errors.
import { state } from './00-state.js';
import { API_HOST, MAX_HISTORY_TURNS_SENT } from './00-current-origin.js';

export async function postChatRequest(inputVal, signal) {
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
                        synthesis: true
                    })
                });

                const quotaLabel = document.getElementById('query-limit-status');
                const remaining = response.headers.get('X-Queries-Remaining');
                if (quotaLabel && remaining !== null) {
                    quotaLabel.textContent = `AI queries today: ${40 - Number(remaining)} / 40`;
                }

                if (!response.ok) {
                    const problem = await response.json().catch(() => ({}));
                    if (response.status === 429 && quotaLabel) {
                        const minutes = Math.ceil(Number(problem.retry_after || 60) / 60);
                        quotaLabel.textContent = `AI cooldown: ${minutes} min · ${40 - Number(problem.remaining ?? 0)} / 40 today`;
                    }
                    throw new Error(problem.detail || `HTTP Error ${response.status}`);
                }

    return response;
}
