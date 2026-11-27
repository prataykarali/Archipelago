import { state } from './00-state.js';
import { setSendButtonState, stopGeneration } from './07-open-page-viewer-modal.js';
import { dismissGraphChoiceModal, populateTopology, renderOkfNodesCard, renderQuizSectionCard } from './11-populate-topology.js';
import { API_HOST, CHAT_RESPONSE_TIMEOUT_MS, MAX_HISTORY_TURNS_SENT, STREAM_HARD_TIMEOUT_MS, STREAM_IDLE_TIMEOUT_MS, setLibrarianThinking, showStickyAvatar } from './00-current-origin.js';
import { _addChatBubbleEffects, appendMessage } from './09-patterns.js';
import { _updateGlowState, renderMarkdownSafely } from './01--hide-welcome-with-transitio.js';
import { _enrichAssistantMarkup, appendEvidenceRail, getResponseCitations } from './02--kw-highlights.js';
import { wrapLibraryInventorySection } from './03-wrap-library-inventory-secti.js';
import { renderGraphExperiencePrompt } from './12-choose-graph-experience.js';
import { populatePipeline } from './10-populate-pipeline.js';
import { updateBookStackForQuery } from './05-display-books.js';
import { saveSession } from './20--compact-history.js';
import { SmoothTypewriterStream, _normText, _shouldReplaceFinal } from './stream-support.js';
import { extractStreamStatusMarkers, parseAndApplyStreamMetadata, splitSafeStreamChunk } from './stream-markers.js';
import { postChatRequest } from './08-send-request.js';
import { handleStreamError } from './08-stream-error.js';
import { resetChatUi } from './08-stream-cleanup.js';
import { applyCorpusProfileUi } from './22-welcome-suggestions.js';
import { renderEvidenceExportBar, renderFollowUpChips } from './23-followups-export.js';

        // Main Send Function
        async function sendMessage() {
            if (state.isGenerating || window.archipelagoChatAuthChecking) return;
            if (state.quotaLimitedUntil && Date.now() < state.quotaLimitedUntil) return;
            if (typeof dismissGraphChoiceModal === 'function') {
                dismissGraphChoiceModal();
            }

            const inputEl = document.getElementById('chat-input');
            const inputVal = (inputEl ? inputEl.value : '').trim();
            if (!inputVal) return;

            window.archipelagoChatAuthChecking = true;
            const sendBtnCheck = document.getElementById('send-btn');
            const sendIconCheck = document.getElementById('send-btn-icon');
            if (sendBtnCheck) {
                sendBtnCheck.setAttribute('aria-busy', 'true');
                sendBtnCheck.title = 'Checking session…';
            }
            if (sendIconCheck) {
                sendIconCheck.className = 'fa-solid fa-spinner fa-spin text-sm';
            }
            try {
                const session = await window.archipelagoVerifyChatSession();
                if (!session.authenticated) {
                    window.archipelagoPromptChatSignIn(inputVal, session.reason);
                    return;
                }
                window.archipelagoClearChatSignInPrompt?.();
            } catch (error) {
                window.archipelagoPromptChatSignIn(inputVal, error?.reason || 'upstream_unavailable');
                return;
            } finally {
                window.archipelagoChatAuthChecking = false;
                if (sendBtnCheck) {
                    sendBtnCheck.removeAttribute('aria-busy');
                    sendBtnCheck.title = 'Send';
                }
                if (sendIconCheck && !state.isGenerating) {
                    sendIconCheck.className = 'fa-solid fa-arrow-up text-sm';
                }
            }

            // Increment request sequence to guard against race conditions or out-of-order streams
            state.currentQuerySequence = (state.currentQuerySequence || 0) + 1;
            const thisQuerySequence = state.currentQuerySequence;

            if (!state.conversationSessionId) {
                state.conversationSessionId = 'session_' + Date.now();
            }

            // Clear textarea & reset height
            if (inputEl) {
                inputEl.value = '';
                inputEl.style.height = 'auto';
            }

            // Reveal-push: slide welcome out (hero video stays pinned at top)
            if (typeof window._hideWelcomeWithTransition === 'function') {
                window._hideWelcomeWithTransition();
            } else {
                const welcome = document.getElementById('welcome-container');
                if (welcome) welcome.classList.add('hidden');
            }

            // One sticky librarian on the left — character video loops constantly
            showStickyAvatar(true);

            // Append User Message to Chat Window
            appendMessage('user', inputVal);

            // Add Assistant response box with Typing dot indicator (bubble only)
            const assistantMsgId = appendMessage('assistant', '', true);
            const msgEl = document.getElementById(`msg-body-${assistantMsgId}`);
            state.currentAssistantRow = msgEl ? (msgEl.closest('.assistant-row') || msgEl.closest('.flex.w-full') || msgEl.closest('.flex')) : null;

            // Do not let evidence from a prior answer attach to this response if the server omits metadata.
            window._lastChatMetadata = null;
            // Phase 1 — SIGIR Demo: clear stale graph state before each new query
            window._graphNeighborhood = { anchor: null, prereqs: [], unlocks: [], related: [] };
            populateTopology(null, [], [], [], true);

            state.isGenerating = true;
            try { window.isGenerating = true; } catch (_) {}
            _updateGlowState(true);
            setLibrarianThinking(true);
            setSendButtonState('stop');

            state.currentAbortController = new AbortController();
            const responseTimeoutId = window.setTimeout(() => {
                state.currentAbortController?.abort('The response timed out.');
            }, Math.max(CHAT_RESPONSE_TIMEOUT_MS, STREAM_HARD_TIMEOUT_MS));
            state.activeResponseTimeoutId = responseTimeoutId;
            let streamIdleTimeoutId = null;
            const armStreamIdleWatchdog = () => {
                if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                streamIdleTimeoutId = window.setTimeout(() => {
                    state.currentAbortController?.abort('Stream idle timeout — no tokens received.');
                }, STREAM_IDLE_TIMEOUT_MS);
                state.activeStreamIdleTimeoutId = streamIdleTimeoutId;
            };
            armStreamIdleWatchdog();

            // Hoisted so catch/finally can keep partial GPU SLM text on abort.
            let buffer = '';
            let metadataParsed = false;
            let assistantText = '';
            let awaitingFinalFrame = false;
            let userScrolledUp = false;
            let staticStreamBuffer = '';
            let rewriteBuffer = '';
            let liveRewriteMode = false;
            let typewriter = null;
            let reader = null;
            let finalizeStreamedBubble = null;
            const chatMsgs = document.getElementById('chat-messages');
            const checkUserScroll = () => {
                if (!chatMsgs) return;
                const distanceFromBottom = chatMsgs.scrollHeight - chatMsgs.scrollTop - chatMsgs.clientHeight;
                userScrolledUp = distanceFromBottom > 90;
            };
            if (chatMsgs) {
                chatMsgs.addEventListener('scroll', checkUserScroll, { passive: true });
                state.activeScrollTarget = chatMsgs;
                state.activeScrollHandler = checkUserScroll;
            }

            try {
                const response = await postChatRequest(inputVal, state.currentAbortController.signal, { synthesis: true });

                reader = response.body.getReader();
                state.activeStreamReader = reader;
                const decoder = new TextDecoder();

                // Remove typing dots when the first text comes in
                let cleanedIndicator = false;


                                // No status chip — stream the model reply directly.
                const setModelStatus = (_v, _p) => {};
                const clearAllModelStatus = () => {
                    document.querySelectorAll('.model-reply-status').forEach((el) => {
                        try { el.remove(); } catch (_) {}
                    });
                };
                clearAllModelStatus();

                // Declared before paintAssistant so post-finalize re-mounts can
                // close over a live binding (avoids TDZ if a paint races setup).
                let bubbleFinalized = false;

                const paintAssistant = (text) => {
                    if (thisQuerySequence !== state.currentQuerySequence) return;
                    if (!cleanedIndicator) {
                        msgEl.innerHTML = '';
                        cleanedIndicator = true;
                        const wrap = msgEl.closest('.msg-bubble-wrap');
                        if (wrap) wrap.classList.remove('is-thinking');
                        msgEl.classList.add('ai-typewriter-cursor');
                    }
                    assistantText = text;
                    renderMarkdownSafely(msgEl, assistantText, window._lastChatMetadata ? getResponseCitations(window._lastChatMetadata) : null);
                    if (typeof Prism !== 'undefined') Prism.highlightAllUnder(msgEl);
                    if (typeof _enrichAssistantMarkup === 'function') _enrichAssistantMarkup(msgEl);
                    // Re-attach paper cards after every paint once the stream is
                    // finalized — innerHTML above wipes any prior evidence rail.
                    if (bubbleFinalized && window._lastChatMetadata) {
                        appendEvidenceRail(msgEl, window._lastChatMetadata);
                        wrapLibraryInventorySection(msgEl, window._lastChatMetadata);
                    }
                    if (chatMsgs && !userScrolledUp) {
                        chatMsgs.scrollTop = chatMsgs.scrollHeight;
                    }
                };

                typewriter = new SmoothTypewriterStream((textToPaint) => {
                    paintAssistant(textToPaint);
                }, {
                    speed: 4,
                    onLiveChange: (live) => {
                        if (!msgEl || thisQuerySequence !== state.currentQuerySequence) return;
                        msgEl.classList.toggle('is-live-streaming', !!live);
                    }
                });
                state.activeTypewriter = typewriter;

                // liveRewriteMode / rewriteBuffer / staticStreamBuffer hoisted above try.

                

                finalizeStreamedBubble = () => {
                    // Idempotent mount: always re-apply markdown + paper cards.
                    // A second flush() after the first finalize used to wipe the
                    // rail via innerHTML while bubbleFinalized blocked re-add.
                    const firstFinalize = !bubbleFinalized;
                    bubbleFinalized = true;

                    if (msgEl) {
                        msgEl.classList.remove('ai-typewriter-cursor', 'is-live-streaming');
                        // Prefer the active stream buffer (rewrite used rewriteBuffer;
                        // static first-paint used staticStreamBuffer). Falling back
                        // only to assistantText avoided dropping the ranked card.
                        const finalText = (rewriteBuffer && rewriteBuffer.trim())
                            || (staticStreamBuffer && staticStreamBuffer.trim())
                            || assistantText
                            || '';
                        renderMarkdownSafely(
                            msgEl,
                            finalText,
                            window._lastChatMetadata ? getResponseCitations(window._lastChatMetadata) : null
                        );
                        if (typeof Prism !== 'undefined') Prism.highlightAllUnder(msgEl);
                        if (typeof _enrichAssistantMarkup === 'function') _enrichAssistantMarkup(msgEl);
                        if (firstFinalize && typeof _addChatBubbleEffects === 'function') {
                            _addChatBubbleEffects(msgEl);
                        }
                        // Insert Grounding Status Badge above the message text
                        if (window._lastChatMetadata?.trace && typeof window.renderGroundingBadge === 'function') {
                            const badgeWrapId = `grounding-badge-${assistantMsgId}`;
                            if (!document.getElementById(badgeWrapId)) {
                                const badgeHtml = window.renderGroundingBadge(window._lastChatMetadata.trace);
                                if (badgeHtml) {
                                    const wrap = document.createElement('div');
                                    wrap.id = badgeWrapId;
                                    wrap.innerHTML = badgeHtml;
                                    msgEl.parentNode.insertBefore(wrap, msgEl);
                                }
                            }
                        }
                        appendEvidenceRail(msgEl, window._lastChatMetadata);
                        wrapLibraryInventorySection(msgEl, window._lastChatMetadata);
                        if (finalText && finalText.trim()) {
                            renderEvidenceExportBar(msgEl, assistantMsgId, { query: inputVal, answerText: finalText, metadata: window._lastChatMetadata });
                        }
                        if (window._lastChatMetadata) renderFollowUpChips(msgEl, assistantMsgId, window._lastChatMetadata);
                    }
                    if (window._lastChatMetadata) {
                        if (firstFinalize && typeof updateBookStackForQuery === 'function') updateBookStackForQuery(window._lastChatMetadata);
                        if (typeof renderQuizSectionCard === 'function' && window._lastChatMetadata.anchor_concept) renderQuizSectionCard(assistantMsgId, window._lastChatMetadata);
                    }
                };

                const _finishStreamUi = () => {
                    if (thisQuerySequence !== state.currentQuerySequence) return;
                    try { typewriter.flush(); } catch (_) {}
                    try { finalizeStreamedBubble(); } catch (_) {}
                    setModelStatus(false);
                    state.isGenerating = false;
                    try { window.isGenerating = false; } catch (_) {}
                    try { _updateGlowState(false); } catch (_) {}
                    setSendButtonState('send');
                    try { setLibrarianThinking(false); } catch (_) {}
                };

                const consumeTextChunk = (rawChunk) => {
                    if (!rawChunk || thisQuerySequence !== state.currentQuerySequence) return;
                    const { cleaned, streamStatus, streamReason } = extractStreamStatusMarkers(rawChunk);
                    if (streamStatus && window._lastChatMetadata?.trace) {
                        window._lastChatMetadata.trace.stream_status = streamStatus;
                        if (streamReason) window._lastChatMetadata.trace.stream_reason = streamReason;
                        if (typeof window.populateInspector === 'function') {
                            window.populateInspector(window._lastChatMetadata);
                        }
                    }
                    let rest = cleaned;
                    if (!rest) return;
                    while (rest.length) {
                        // Prefer earliest control marker in this buffer slice.
                        const markers = [
                            { tag: '[STREAM_DONE]', len: 13, kind: 'done' },
                            { tag: '[CLEAN]', len: 7, kind: 'done' },
                            { tag: '[MODEL_REWRITE]', len: 15, kind: 'rewrite' },
                        ];
                        let markerIdx = -1;
                        let markerLen = 0;
                        let markerKind = '';
                        for (const m of markers) {
                            const idx = rest.indexOf(m.tag);
                            if (idx !== -1 && (markerIdx === -1 || idx < markerIdx)) {
                                markerIdx = idx;
                                markerLen = m.len;
                                markerKind = m.kind;
                            }
                        }

                        if (markerIdx === -1) {
                            if (awaitingFinalFrame) {
                                const currentDraft = liveRewriteMode
                                    ? (rewriteBuffer || assistantText)
                                    : (staticStreamBuffer || assistantText);
                                // STREAM_DONE payload is authoritative — always take it
                                // when non-empty (avoids keeping a partial rewrite + old card).
                                if (rest && rest.trim() && (_shouldReplaceFinal(rest, currentDraft) || !currentDraft || rest.length >= (currentDraft || '').length * 0.5)) {
                                    typewriter.update(rest, { instant: true });
                                    staticStreamBuffer = rest;
                                    rewriteBuffer = '';
                                    assistantText = rest;
                                }
                                awaitingFinalFrame = false;
                                liveRewriteMode = false;
                                _finishStreamUi();
                            } else if (liveRewriteMode) {
                                // Live model tokens — typewriter word-by-word, never wait for DONE.
                                rewriteBuffer += rest;
                                typewriter.update(rewriteBuffer, { forceTypewriter: true });
                            } else {
                                // Plain chunked static stream: accumulate + typewriter word-by-word.
                                staticStreamBuffer += rest;
                                typewriter.update(staticStreamBuffer, { forceTypewriter: true });
                            }
                            rest = '';
                            break;
                        }

                        const before = rest.substring(0, markerIdx);
                        if (before) {
                            if (awaitingFinalFrame) {
                                // ignore pre-final crumbs
                            } else if (liveRewriteMode) {
                                rewriteBuffer += before;
                                typewriter.update(rewriteBuffer, { forceTypewriter: true });
                            } else {
                                staticStreamBuffer += before;
                                typewriter.update(staticStreamBuffer, { forceTypewriter: true });
                            }
                        }
                        rest = rest.substring(markerIdx + markerLen).replace(/^\n+/, '');

                        if (markerKind === 'rewrite') {
                            // Switch from grounded card → live model typewriter.
                            liveRewriteMode = true;
                            rewriteBuffer = '';
                            staticStreamBuffer = '';
                            typewriter.reset();
                            assistantText = '';
                            if (msgEl) {
                                msgEl.innerHTML = '';
                                cleanedIndicator = true;
                                const wrap = msgEl.closest('.msg-bubble-wrap');
                                if (wrap) wrap.classList.remove('is-thinking');
                                msgEl.classList.add('ai-typewriter-cursor', 'is-live-streaming');
                            }
                            // If the rewrite payload is already in this chunk, continue the loop.
                            continue;
                        }

                        // STREAM_DONE / CLEAN announces the authoritative final frame.
                        awaitingFinalFrame = true;
                        liveRewriteMode = false;
                        if (rest && rest.trim()) {
                            const currentDraft = staticStreamBuffer || rewriteBuffer || assistantText;
                            if (_shouldReplaceFinal(rest, currentDraft) || !currentDraft) {
                                staticStreamBuffer = rest;
                                rewriteBuffer = "";
                                assistantText = rest;
                                typewriter.update(rest, { instant: true });
                            }
                        }
                        awaitingFinalFrame = false;
                        rest = "";
                        _finishStreamUi();
                        break;
                    }
                };

                while (true) {
                    const { done, value } = await reader.read();
                    if (thisQuerySequence !== state.currentQuerySequence) {
                        try { await reader.cancel(); } catch (_) {}
                        return;
                    }
                    armStreamIdleWatchdog();
                    if (done) {
                        if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                        buffer += decoder.decode();
                        if (buffer) {
                            const { ready } = splitSafeStreamChunk(buffer, { finalFlush: true });
                            if (ready) consumeTextChunk(ready);
                            buffer = '';
                        }
                        if (!bubbleFinalized) {
                            typewriter.flush();
                        }
                        if (!cleanedIndicator && msgEl) {
                            msgEl.innerHTML = '';
                            cleanedIndicator = true;
                            const wrap = msgEl.closest('.msg-bubble-wrap');
                            if (wrap) wrap.classList.remove('is-thinking');
                        }
                        // Always re-finalize only if not already finalized (or if buffer above flushed)
                        if (!bubbleFinalized || !document.getElementById(`interactive-zone-${assistantMsgId}`)) {
                            finalizeStreamedBubble();
                        }
                        if (msgEl && window._lastChatMetadata) {
                            appendEvidenceRail(msgEl, window._lastChatMetadata);
                            wrapLibraryInventorySection(msgEl, window._lastChatMetadata);
                        }
                        state.isGenerating = false;
                        try { window.isGenerating = false; } catch (_) {}
                        _updateGlowState(false);
                        setSendButtonState('send');
                        setLibrarianThinking(false);
                        break;
                    }

                    buffer += decoder.decode(value, { stream: true });

                    if (!metadataParsed) {
                        const idx = buffer.indexOf('[STREAM_START]');
                        if (idx !== -1) {
                            const metaStr = buffer.substring(0, idx).trim();
                            buffer = buffer.substring(idx + '[STREAM_START]'.length).replace(/^\n+/, '');
                            metadataParsed = true;
                            parseAndApplyStreamMetadata(metaStr, {
                                applyCorpusProfileUi, populatePipeline, populateTopology, updateBookStackForQuery,
                            });
                        }
                    }

                    if (metadataParsed && buffer) {
                        const { ready, remainder } = splitSafeStreamChunk(buffer, { finalFlush: false });
                        buffer = remainder;
                        if (ready) consumeTextChunk(ready);
                    }
                }

                // Add to conversational history
                state.chatHistory.push({ role: 'user', content: inputVal });
                state.chatHistory.push({ role: 'assistant', content: assistantText, citations: getResponseCitations(window._lastChatMetadata), metadata: window._lastChatMetadata });
                try {
                    saveSession();
                } catch (saveErr) {
                    // Never mis-label a localStorage quota failure as a stream failure.
                    console.warn('saveSession failed after successful stream', saveErr);
                }

            } catch (err) {
                if (thisQuerySequence !== state.currentQuerySequence) return;
                if (err && err.status === 401) {
                    const draftEl = document.getElementById('chat-input');
                    if (draftEl && !draftEl.value.trim()) draftEl.value = inputVal;
                    window.archipelagoPromptChatSignIn(inputVal, err.reason);
                    (msgEl?.closest('.assistant-row') || msgEl?.closest('.flex.w-full'))?.remove();
                    return;
                }
                if (err && err.status === 429) {
                    const draftEl = document.getElementById('chat-input');
                    if (draftEl && !draftEl.value.trim()) {
                        draftEl.value = inputVal;
                        draftEl.style.height = 'auto';
                        draftEl.style.height = Math.min(draftEl.scrollHeight, 200) + 'px';
                    }
                }
                handleStreamError(err, {
                    msgEl, staticStreamBuffer, assistantText, rewriteBuffer,
                    typewriter, finalizeStreamedBubble, inputVal
                });
            } finally {
                window.clearTimeout(responseTimeoutId);
                if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                if (chatMsgs) chatMsgs.removeEventListener('scroll', checkUserScroll);
                if (thisQuerySequence === state.currentQuerySequence) {
                    resetChatUi({ responseTimeoutId, streamIdleTimeoutId, chatMsgs, checkUserScroll, typewriter, reader });
                } else {
                    if (typewriter && typeof typewriter.stop === 'function') {
                        try { typewriter.stop(); } catch (_) {}
                    }
                    if (!state.isGenerating) {
                        setSendButtonState('send');
                    }
                }
            }
        }

export { sendMessage };
