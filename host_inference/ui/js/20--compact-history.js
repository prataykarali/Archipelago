// Auto-split from ui/chat/index.html — 20--compact-history.js
// Feature module 21 of 22.
import { state } from './00-state.js';
import { populateTopology } from './11-populate-topology.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { API_HOST, showStickyAvatar } from './00-current-origin.js';
import { appendMessage } from './09-patterns.js';
import { renderGraphExperiencePrompt } from './12-choose-graph-experience.js';
import { populatePipeline } from './10-populate-pipeline.js';
import { startNewChat } from './04-start-new-chat.js';

        window.populateTopology = populateTopology;

        // LocalStorage Chat History Management
        function _compactHistory(history) {
            // Keep role, content, citations, and graph metadata so restored chats display concept graph
            const MAX_TURNS = 40;
            const MAX_CONTENT = 4000;
            const src = Array.isArray(history) ? history : [];
            return src.slice(-MAX_TURNS).map((m) => {
                const item = {
                    role: m.role,
                    content: String(m.content || '').slice(0, MAX_CONTENT),
                };
                if (m.citations) item.citations = m.citations;
                if (m.metadata) item.metadata = m.metadata;
                return item;
            });
        }

        function _writeSessions(sessions) {
            const key = 'archipelago_sessions';
            const payload = JSON.stringify(sessions || []);
            try {
                localStorage.setItem(key, payload);
                return true;
            } catch (err) {
                const isQuota = !!(
                    err && (
                        err.name === 'QuotaExceededError'
                        || err.code === 22
                        || err.code === 1014
                        || /quota/i.test(String(err.message || ''))
                    )
                );
                if (!isQuota) {
                    console.warn('localStorage setItem failed', err);
                    return false;
                }
                // Evict oldest sessions, then retry with a compacted current list.
                try {
                    let trimmed = Array.isArray(sessions) ? sessions.slice() : [];
                    while (trimmed.length > 1) {
                        trimmed.pop();
                        try {
                            localStorage.setItem(key, JSON.stringify(trimmed));
                            return true;
                        } catch (_) { /* keep trimming */ }
                    }
                    // Last resort: store only compact current session.
                    if (trimmed.length === 1) {
                        trimmed[0] = {
                            ...trimmed[0],
                            history: _compactHistory(trimmed[0].history),
                            lastMetadata: null,
                        };
                        localStorage.setItem(key, JSON.stringify(trimmed));
                        return true;
                    }
                    localStorage.removeItem(key);
                } catch (inner) {
                    console.warn('QuotaExceededError recovery failed', inner);
                }
                return false;
            }
        }

        function clearAllSessions() {
            try { localStorage.removeItem('archipelago_sessions'); } catch (_) {}
            try { renderChatHistory(); } catch (_) {}
        }

        window.clearAllSessions = clearAllSessions;

        function saveSession() {
            if (!state.chatHistory.length) return;
            let sessions = [];
            try {
                sessions = JSON.parse(localStorage.getItem('archipelago_sessions') || '[]');
            } catch (_) {
                sessions = [];
            }
            if (!Array.isArray(sessions)) sessions = [];
            const existingIdx = sessions.findIndex(s => s.id === state.conversationSessionId);

            // Generate a title from the first user query
            const userMsgs = state.chatHistory.filter(m => m.role === 'user');
            const title = userMsgs[0]?.content || "New Chat";
            const cleanTitle = title.length > 25 ? title.substring(0, 22) + "..." : title;

            const sessionData = {
                id: state.conversationSessionId,
                title: cleanTitle,
                history: _compactHistory(state.chatHistory),
                lastMetadata: window._lastChatMetadata || null,
                timestamp: Date.now()
            };

            if (existingIdx !== -1) {
                sessions[existingIdx] = sessionData;
            } else {
                sessions.unshift(sessionData);
            }
            // Cap total saved sessions to reduce quota pressure.
            if (sessions.length > 20) sessions = sessions.slice(0, 20);
            _writeSessions(sessions);
            renderChatHistory();
        }

        function renderChatHistory() {
            const listEl = document.getElementById('chat-history-list');
            if (!listEl) return;
            const sessions = JSON.parse(localStorage.getItem('archipelago_sessions') || '[]');
            listEl.innerHTML = '';
            
            if (sessions.length === 0) {
                listEl.innerHTML = '<p class="text-[10px] text-gray-500 italic px-1">No saved chats.</p>';
                return;
            }
            
            sessions.forEach(s => {
                const item = document.createElement('div');
                item.className = `glass-card group flex items-center justify-between p-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all duration-200 ${s.id === state.conversationSessionId ? 'bg-accentPurple/20 text-white border-accentPurple/40 shadow-[0_0_15px_rgba(139,92,246,0.2)]' : 'text-gray-300 hover:bg-white/10 hover:text-white'}`;
                
                const titleWrapper = document.createElement('div');
                titleWrapper.className = 'flex items-center gap-2 truncate min-w-0 flex-1';
                titleWrapper.onclick = () => loadSession(s.id);
                titleWrapper.innerHTML = `<img src="/ui/assets/note_btn2.png" class="w-5 h-5 object-contain shrink-0" alt="chat"><span class="truncate">${escapeHTML(s.title)}</span>`;
                
                const delBtn = document.createElement('button');
                delBtn.className = 'opacity-0 group-hover:opacity-100 text-gray-500 hover:text-rose-400 transition-opacity px-1';
                delBtn.innerHTML = '<i class="fa-regular fa-trash-can text-[10px]"></i>';
                delBtn.onclick = (e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                };
                
                item.append(titleWrapper, delBtn);
                listEl.appendChild(item);
            });
        }

        function loadSession(id) {
            const sessions = JSON.parse(localStorage.getItem('archipelago_sessions') || '[]');
            const session = sessions.find(s => s.id === id);
            if (!session) return;
            
            state.conversationSessionId = session.id;
            state.chatHistory = session.history;
            window._lastChatMetadata = session.lastMetadata;
            
            // Sticky single avatar for restored chats
            if (typeof showStickyAvatar === 'function') showStickyAvatar(false);

            // Clear & render messages
            const chatMsgs = document.getElementById('chat-messages');
            chatMsgs.innerHTML = '';
            
            state.chatHistory.forEach(msg => {
                const msgId = appendMessage(msg.role, msg.content, false, msg.citations || [], msg.metadata || null);
                if (msg.role === 'assistant') {
                    const meta = msg.metadata || window._lastChatMetadata;
                    if (meta && typeof renderGraphExperiencePrompt === 'function') {
                        renderGraphExperiencePrompt(msgId, meta, { showPopup: false });
                    }
                }
            });
            document.querySelectorAll('.model-reply-status').forEach(el => {
                el.classList.remove('is-visible');
                el.dataset.active = '0';
                el.hidden = true;
            });
            
            // Populate pipeline and topology flow
            if (window._lastChatMetadata) {
                populatePipeline(window._lastChatMetadata);
                populateTopology(window._lastChatMetadata.anchor_concept, window._lastChatMetadata.prerequisites, window._lastChatMetadata.unlocks, window._lastChatMetadata.related_concepts || window._lastChatMetadata.related || []);
            } else {
                populateTopology(null, null, null, null, true);
            }
            
            renderChatHistory();
        }

        function deleteSession(id) {
            let sessions = [];
            try {
                sessions = JSON.parse(localStorage.getItem('archipelago_sessions') || '[]');
            } catch (_) {
                sessions = [];
            }
            if (!Array.isArray(sessions)) sessions = [];
            sessions = sessions.filter(s => s.id !== id);
            _writeSessions(sessions);
            if (state.conversationSessionId === id) {
                startNewChat();
            } else {
                renderChatHistory();
            }
        }

        // ── Share chat: snapshot → server → copy link ─────────────────
        async function shareChat() {
            const btn = document.getElementById('share-chat-btn');
            if (!state.chatHistory.length) {
                flashShareBtn(btn, 'Nothing to share yet', true);
                return;
            }
            const userMsgs = state.chatHistory.filter(m => m.role === 'user');
            const title = (userMsgs[0]?.content || 'Archipelago chat').substring(0, 100);
            try {
                const res = await fetch(API_HOST + '/api/share', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, history: state.chatHistory }),
                });
                const data = await res.json();
                if (!res.ok || !data.share_id) throw new Error(data.error || 'share failed');
                const link = `${window.location.origin}${window.location.pathname}?share=${data.share_id}`;
                try {
                    await navigator.clipboard.writeText(link);
                    flashShareBtn(btn, 'Link copied!');
                } catch {
                    window.prompt('Copy this share link:', link);
                }
            } catch (err) {
                console.error('shareChat failed:', err);
                flashShareBtn(btn, 'Share failed', true);
            }
        }

        function flashShareBtn(btn, text, isError = false) {
            if (!btn) return;
            const orig = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid ${isError ? 'fa-triangle-exclamation' : 'fa-check'}"></i><span class="hidden md:inline">${text}</span>`;
            btn.classList.toggle('text-rose-400', isError);
            setTimeout(() => { btn.innerHTML = orig; btn.classList.remove('text-rose-400'); }, 2200);
        }

        async function loadSharedChat(shareId) {
            try {
                const res = await fetch(API_HOST + '/api/share/' + encodeURIComponent(shareId));
                const data = await res.json();
                if (!res.ok || !Array.isArray(data.history)) throw new Error(data.error || 'not found');
                state.conversationSessionId = 'shared-' + shareId;
                state.chatHistory = data.history;
                if (typeof showStickyAvatar === 'function') showStickyAvatar(false);
                const chatMsgs = document.getElementById('chat-messages');
                chatMsgs.innerHTML = '';
                const banner = document.createElement('div');
                banner.className = 'max-w-2xl mx-auto mb-4 p-3 rounded-xl bg-accentCyan/10 border border-accentCyan/25 text-xs text-accentCyan flex items-center gap-2';
                banner.innerHTML = `<i class="fa-solid fa-share-nodes"></i><span>Viewing a shared conversation${data.title ? ': <b>' + escapeHTML(data.title) + '</b>' : ''}. Continue the chat below to make it yours.</span>`;
                chatMsgs.appendChild(banner);

                // Restore last assistant metadata for panel population
                let lastMeta = null;
                state.chatHistory.forEach(msg => {
                    appendMessage(msg.role, msg.content, false, msg.citations || [], msg.metadata || null);
                    if (msg.role === 'assistant' && msg.metadata) {
                        lastMeta = msg.metadata;
                    }
                });

                // Populate side panels from last assistant message's metadata
                if (lastMeta) {
                    window._lastChatMetadata = lastMeta;
                    populatePipeline(lastMeta);
                    populateTopology(
                        lastMeta.anchor_concept,
                        lastMeta.prerequisites,
                        lastMeta.unlocks,
                        lastMeta.related_concepts || lastMeta.related || []
                    );
                } else {
                    populateTopology(null, null, null, null, true);
                }

                renderChatHistory();
                chatMsgs.scrollTop = chatMsgs.scrollHeight;
            } catch (err) {
                console.error('loadSharedChat failed:', err);
            }
        }

        // Open shared conversation when the URL carries ?share=<id>
        (() => {
            const shareId = new URLSearchParams(window.location.search).get('share');
            if (shareId && /^[A-Za-z0-9_-]{6,32}$/.test(shareId)) loadSharedChat(shareId);
        })();

        // ── Visual Learning Roadmap ──────────────────────────────────
        function closeRoadmapModal(fromPopstate = false) {
            const modal = document.getElementById('roadmap-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }
            if (!fromPopstate && window.history.state && window.history.state.modal === 'roadmap') {
                window.history.back();
            }
        }

export { _compactHistory, _writeSessions, clearAllSessions, closeRoadmapModal, deleteSession, flashShareBtn, loadSession, loadSharedChat, renderChatHistory, saveSession, shareChat };
