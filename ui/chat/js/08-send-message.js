import { state } from './00-state.js';
import { setSendButtonState, stopGeneration } from './07-open-page-viewer-modal.js';
import { dismissGraphChoiceModal, populateTopology } from './11-populate-topology.js';
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
import { postChatRequest } from './08-send-request.js';
import { handleStreamError } from './08-stream-error.js';
import { resetChatUi } from './08-stream-cleanup.js';

        // Main Send Function
        async function sendMessage() {
            if (state.isGenerating) return;
            if (typeof dismissGraphChoiceModal === 'function') {
                dismissGraphChoiceModal();
            }

            const inputEl = document.getElementById('chat-input');
            const inputVal = (inputEl ? inputEl.value : '').trim();
            if (!inputVal) return;

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

            state.isGenerating = true;
            try { window.isGenerating = true; } catch (_) {}
            _updateGlowState(true);
            setLibrarianThinking(true);
            setSendButtonState('stop');

            state.currentAbortController = new AbortController();
            const responseTimeoutId = window.setTimeout(() => {
                state.currentAbortController?.abort('The response timed out.');
            }, Math.max(CHAT_RESPONSE_TIMEOUT_MS, STREAM_HARD_TIMEOUT_MS));
            let streamIdleTimeoutId = null;
            const armStreamIdleWatchdog = () => {
                if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                streamIdleTimeoutId = window.setTimeout(() => {
                    state.currentAbortController?.abort('Stream idle timeout — no tokens received.');
                }, STREAM_IDLE_TIMEOUT_MS);
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
            let finalizeStreamedBubble = null;
            const chatMsgs = document.getElementById('chat-messages');
            const checkUserScroll = () => {
                if (!chatMsgs) return;
                const distanceFromBottom = chatMsgs.scrollHeight - chatMsgs.scrollTop - chatMsgs.clientHeight;
                userScrolledUp = distanceFromBottom > 90;
            };
            if (chatMsgs) {
                chatMsgs.addEventListener('scroll', checkUserScroll, { passive: true });
            }

            try {
                const response = await postChatRequest(inputVal, state.currentAbortController.signal);

                const reader = response.body.getReader();
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
                    speed: 12,
                    onLiveChange: (live) => {
                        if (!msgEl) return;
                        msgEl.classList.toggle('is-live-streaming', !!live);
                    }
                });

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
                        // Always re-mount paper cards after markdown paint.
                        appendEvidenceRail(msgEl, window._lastChatMetadata);
                        wrapLibraryInventorySection(msgEl, window._lastChatMetadata);
                    }
                    if (firstFinalize && window._lastChatMetadata) {
                        if (typeof updateBookStackForQuery === 'function') {
                            updateBookStackForQuery(window._lastChatMetadata);
                        }
                        if (typeof renderGraphExperiencePrompt === 'function') {
                            renderGraphExperiencePrompt(assistantMsgId, window._lastChatMetadata, { showPopup: true });
                        }
                    }
                };

                const _finishStreamUi = () => {
                    typewriter.flush();
                    finalizeStreamedBubble();
                    setModelStatus(false);
                    state.isGenerating = false;
                    try { window.isGenerating = false; } catch (_) {}
                    _updateGlowState(false);
                    setSendButtonState('send');
                    setLibrarianThinking(false);
                };

                const consumeTextChunk = (chunk) => {
                    if (!chunk) return;
                    let rest = chunk;
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
                            awaitingFinalFrame = false;
                            rest = "";
                            _finishStreamUi();
                            break;
                        }
                        // The final payload may arrive in the next network chunk.
                        rest = "";
                        break;
                    }
                };

                while (true) {
                    const { done, value } = await reader.read();
                    armStreamIdleWatchdog();
                    if (done) {
                        if (streamIdleTimeoutId) window.clearTimeout(streamIdleTimeoutId);
                        typewriter.flush();
                        if (!cleanedIndicator && msgEl) {
                            msgEl.innerHTML = '';
                            cleanedIndicator = true;
                            const wrap = msgEl.closest('.msg-bubble-wrap');
                            if (wrap) wrap.classList.remove('is-thinking');
                        }
                        if (buffer) {
                            consumeTextChunk(buffer);
                            buffer = '';
                        }
                        // Always re-finalize after the terminal flush so paper
                        // cards survive the innerHTML wipe from flush/render.
                        finalizeStreamedBubble();
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

                            try {
                                const metadata = JSON.parse(metaStr);
                                window._lastChatMetadata = metadata;
                                populatePipeline(metadata);
                                populateTopology(metadata.anchor_concept, metadata.prerequisites, metadata.unlocks, metadata.related_concepts || metadata.related || []);
                                if (typeof updateBookStackForQuery === 'function') {
                                    updateBookStackForQuery(metadata);
                                }
                                // renderHorizontalGraphCard & roadmap_assessment deferred until typing finishes
                            } catch (err) {
                                console.error('Error parsing pipeline metadata:', err);
                            }
                        }
                    }

                    if (metadataParsed && buffer) {
                        consumeTextChunk(buffer);
                        buffer = '';
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
                handleStreamError(err, {
                    msgEl, staticStreamBuffer, assistantText, rewriteBuffer,
                    typewriter, finalizeStreamedBubble, inputVal
                });
            } finally {
                resetChatUi({ responseTimeoutId, streamIdleTimeoutId, chatMsgs, checkUserScroll });
            }
        }

export { sendMessage };
