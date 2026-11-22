// Auto-split from ui/chat/index.html — 01--hide-welcome-with-transitio.js
// Feature module 2 of 22.
import { pauseAvatarRoot } from './00-current-origin.js';
import { citationPageUrl, getResponseCitations } from './02--kw-highlights.js';

        // ── 5. SwitchboardCard lightgrid (lives under hero — always on) ─
        (function initSwitchboard() {
            const grid = document.getElementById('sw-grid');
            if (!grid || grid.dataset.wired === '1') return;
            grid.dataset.wired = '1';
            const COLS = 28, ROWS = 3;
            const total = COLS * ROWS;
            grid.style.gridTemplateColumns = `repeat(${COLS}, minmax(0, 1fr))`;
            grid.style.gridTemplateRows = `repeat(${ROWS}, minmax(0, 1fr))`;
            const bulbs = [];
            for (let i = 0; i < total; i++) {
                const b = document.createElement('div');
                b.className = 'sw-bulb';
                grid.appendChild(b);
                bulbs.push(b);
            }
            const states = new Array(total).fill(0);
            function tick() {
                const n = Math.floor(total * 0.18);
                const indices = Array.from({length: total}, (_, i) => i).sort(() => Math.random() - 0.5).slice(0, n);
                indices.forEach(i => {
                    if (states[i] === 0) states[i] = 1;
                    else if (states[i] === 1) states[i] = 2;
                    else states[i] = 0;
                    bulbs[i].className = 'sw-bulb' + (states[i] === 1 ? ' medium' : states[i] === 2 ? ' high' : '');
                });
            }
            setInterval(tick, 220);
            tick();
        })();

        // ── 3. TypewriterText — welcome subtitle (loops: type → pause → erase → repeat)
        window.WELCOME_SUBTITLE_TEXT = 'A high-fidelity local RAG research tool. Ask questions to query the concept database, traverse topology, and receive streamed synthesis answers.';

        window._welcomeTypewriterTimer = null;

        window.startWelcomeTypewriter = function startWelcomeTypewriter(el) {
            if (!el) return;
            const text = window.WELCOME_SUBTITLE_TEXT;
            if (window._welcomeTypewriterTimer) {
                clearTimeout(window._welcomeTypewriterTimer);
                window._welcomeTypewriterTimer = null;
            }
            const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            if (reduced) {
                el.textContent = text;
                el.classList.add('done', 'is-static');
                return;
            }
            el.classList.remove('done', 'is-static');
            el.textContent = '';
            const TYPE_MS = 22;
            const ERASE_MS = 12;
            const HOLD_FULL_MS = 2600;
            const HOLD_EMPTY_MS = 480;
            // `shown` = number of characters currently visible
            let shown = 0;
            let erasing = false;
            function tick() {
                // Abort if the node was removed (e.g. chat started)
                if (!el.isConnected) {
                    window._welcomeTypewriterTimer = null;
                    return;
                }
                if (!erasing) {
                    shown += 1;
                    el.textContent = text.slice(0, shown);
                    if (shown < text.length) {
                        window._welcomeTypewriterTimer = setTimeout(tick, TYPE_MS);
                    } else {
                        // Fully typed — hold, then erase
                        window._welcomeTypewriterTimer = setTimeout(() => {
                            erasing = true;
                            tick();
                        }, HOLD_FULL_MS);
                    }
                } else {
                    shown -= 1;
                    el.textContent = text.slice(0, Math.max(shown, 0));
                    if (shown > 0) {
                        window._welcomeTypewriterTimer = setTimeout(tick, ERASE_MS);
                    } else {
                        erasing = false;
                        shown = 0;
                        el.textContent = '';
                        window._welcomeTypewriterTimer = setTimeout(tick, HOLD_EMPTY_MS);
                    }
                }
            }
            window._welcomeTypewriterTimer = setTimeout(tick, 320);
        };

        (function initTypewriter() {
            window.startWelcomeTypewriter(document.getElementById('welcome-subtitle'));
        })();

        // ── 4. DepthParallaxWords — suggestion prompt cards ────────────
        (function initDepthWords() {
            const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            const targets = document.querySelectorAll('.depth-word-target');
            targets.forEach((span, cardIdx) => {
                const text = span.textContent.trim();
                const words = text.split(' ');
                span.innerHTML = '';
                words.forEach((word, wi) => {
                    const w = document.createElement('span');
                    w.className = 'depth-word';
                    w.textContent = word;
                    if (reduced) w.classList.add('visible');
                    else w.style.transitionDelay = `${cardIdx * 45 + wi * 55}ms`;
                    span.appendChild(w);
                    if (wi < words.length - 1) span.appendChild(document.createTextNode(' '));
                });
            });
            if (reduced) return;
            // Reveal on a small delay after page load
            setTimeout(() => {
                document.querySelectorAll('.depth-word').forEach(w => w.classList.add('visible'));
            }, 150);
        })();

        // ── 7. Hover-3d tilt on suggestion cards only ─────────────────
        (function initHover3d() {
            const PERSPECTIVE = 800;
            document.querySelectorAll('.hover-3d-card').forEach(card => {
                card.addEventListener('mousemove', e => {
                    const rect = card.getBoundingClientRect();
                    const cx = rect.left + rect.width / 2;
                    const cy = rect.top + rect.height / 2;
                    const dx = (e.clientX - cx) / (rect.width / 2);
                    const dy = (e.clientY - cy) / (rect.height / 2);
                    card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
                    card.style.setProperty('--my', `${e.clientY - rect.top}px`);
                    card.style.transform = `perspective(${PERSPECTIVE}px) rotateY(${dx * 8}deg) rotateX(${-dy * 6}deg) scale(1.03)`;
                    card.style.transition = 'transform 0.08s ease-out';
                });
                card.addEventListener('mouseleave', () => {
                    card.style.transform = '';
                    card.style.transition = 'transform 0.35s cubic-bezier(0.22,1,0.36,1)';
                });
            });
        })();

        // ── 9. VisionOS Spatial Glass cursor spotlight & 3D micro-parallax ────────
        (function initSpatialGlassEffects() {
            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            document.addEventListener('mousemove', (e) => {
                const target = e.target.closest('.glass-card, .citation-card, .book-card, .concept-card');
                if (!target) return;
                const rect = target.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                target.style.setProperty('--mouse-x', `${x}px`);
                target.style.setProperty('--mouse-y', `${y}px`);
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                const tiltX = ((y - centerY) / centerY) * -5;
                const tiltY = ((x - centerX) / centerX) * 5;
                target.style.transform = `perspective(800px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translateY(-2px)`;
                target.style.transition = 'transform 0.08s ease-out';
            }, { passive: true });
            document.addEventListener('mouseout', (e) => {
                const target = e.target.closest('.glass-card, .citation-card, .book-card, .concept-card');
                if (target) {
                    target.style.transform = '';
                    target.style.transition = 'transform 0.35s cubic-bezier(0.22, 1, 0.36, 1)';
                }
            }, { passive: true });
        })();

        // ── 1. Chromatic Waves — full chat-stage background (persistent) ─
        (function initChromaticWavesChatBg() {
            function tryMount() {
                const mount = window.mountChromaticWavesOnChat || window.mountChromaticWaves;
                if (typeof mount !== 'function') {
                    window.addEventListener('chromatic-waves-ready', function onReady() {
                        window.removeEventListener('chromatic-waves-ready', onReady);
                        tryMount();
                    }, { once: true });
                    return;
                }
                if (typeof window.mountChromaticWavesOnChat === 'function') {
                    window.mountChromaticWavesOnChat();
                } else {
                    const host = document.getElementById('chat-stage')
                        || document.querySelector('main.flex-1');
                    if (host) window.mountChromaticWaves(host);
                }
            }
            tryMount();
            window._remountChromaticWaves = tryMount;
        })();

        // ── 8. Reveal-push transition — welcome only (hero stays) ──────
        function _hideWelcomeWithTransition() {
            const wc = document.getElementById('welcome-container');
            if (!wc || wc.dataset.exiting === '1' || wc.dataset.gone === '1') return;
            wc.dataset.exiting = '1';
            wc.classList.add('reveal-exit');
            wc.style.pointerEvents = 'none';
            // Chromatic waves stay mounted on #chat-stage for the whole session
            setTimeout(() => {
                // Force remove — Tailwind `hidden` can lose to `flex` utility order
                wc.dataset.gone = '1';
                wc.dataset.exiting = '0';
                wc.classList.remove('reveal-exit');
                wc.setAttribute('aria-hidden', 'true');
                wc.style.display = 'none';
                wc.remove();
                // Pause welcome avatar only — sticky librarian takes over
                pauseAvatarRoot(document.getElementById('welcome-avatar'));
            }, 390);
        }

        window._hideWelcomeWithTransition = _hideWelcomeWithTransition;

        // ── 6. Glow border — pause during streaming ────────────────────
        const _glowWrap = document.querySelector('.glow-border-wrap');

        function _updateGlowState(streaming) {
            if (!_glowWrap) return;
            if (streaming) _glowWrap.classList.add('glow-paused');
            else _glowWrap.classList.remove('glow-paused');
        }

        // Bridge local isGenerating ↔ glow (declareProperty on window alone
        // does not track the script-scope `let isGenerating` used by sendMessage)
        const _isGenDesc = Object.getOwnPropertyDescriptor(window, 'isGenerating');

        if (!_isGenDesc || _isGenDesc.configurable) {
            let _glowGenFlag = false;
            Object.defineProperty(window, 'isGenerating', {
                get() { return _glowGenFlag; },
                set(v) {
                    _glowGenFlag = !!v;
                    _updateGlowState(_glowGenFlag);
                },
                configurable: true
            });
        }

        // Patch: keep glow in sync when local isGenerating is assigned
        // (sendMessage uses script-scope let — we also call _updateGlowState there)

        const escapeHTML = (value) => String(value ?? '').replace(/[&<>'"]/g, char => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        })[char]);

        function sanitizeMarkdown(html) {
            const template = document.createElement('template');
            template.innerHTML = html;
            // Remove dangerous tags but KEEP <a> anchors (curriculum #page=N PDF links)
            template.content.querySelectorAll('script, style, iframe, object, embed').forEach(node => node.remove());
            template.content.querySelectorAll('*').forEach(node => {
                [...node.attributes].forEach(attribute => {
                    const name = attribute.name.toLowerCase();
                    const value = attribute.value.trim().toLowerCase();
                    if (name.startsWith('on')) node.removeAttribute(attribute.name);
                    if (name === 'href' && value.startsWith('javascript:')) node.removeAttribute(attribute.name);
                });
            });
            // Harden PDF / external links for Session 2 multi-hop curriculum bubbles
            template.content.querySelectorAll('a[href]').forEach(a => {
                const href = (a.getAttribute('href') || '').trim();
                // Permit ordinary Markdown links as well as local evidence paths; reject executable/data schemes.
                const ok = /^(https?:\/\/|mailto:|\/|\.\/|\.\.\/|#|\?)/i.test(href);
                if (!ok) {
                    a.removeAttribute('href');
                    return;
                }
                a.setAttribute('target', '_blank');
                a.setAttribute('rel', 'noopener noreferrer');
                if (href.includes('#page=') || href.includes('/pdfs/') || href.includes('view-page') || href.includes('/api/page-view')) {
                    a.classList.add('curriculum-pdf-link');
                }
            });
            return template.innerHTML;
        }

        function renderMarkdownSafely(target, text, citations = null) {
            let processedText = String(text || '');
            const citationMap = {};
            const cites = citations || (window._lastChatMetadata ? getResponseCitations(window._lastChatMetadata) : []);
            cites.forEach(c => {
                if (c.evidence_id) {
                    citationMap[c.evidence_id] = c;
                }
            });

            // Expand [S1] and bare S1 markers into clickable direct page links (Pearson / HuggingFace only)
            const linkForCitation = (id) => {
                const cit = citationMap[id];
                if (!cit) return null;
                const pageNum = cit.page_number || cit.page || 1;
                const targetUrl = citationPageUrl(cit);
                const label = `(p.${pageNum} ↗)`;
                return targetUrl ? `[${label}](${targetUrl})` : `[${label}]`;
            };
            processedText = processedText.replace(/\[(S\d+)(?:\s*:[^\]]*)?\]/g, (match, id) => {
                const res = linkForCitation(id);
                return res !== null ? res : '';
            });
            // Bare S1 / S2 the model sometimes emits without brackets
            processedText = processedText.replace(/(?<!\[)\b(S\d+)\b(?!\])/g, (match, id) => {
                const res = linkForCitation(id);
                return res !== null ? res : '';
            });
            // Strip trailing incomplete bracket citation markers during live streaming (e.g. "[S", "[S1", "[S1:")
            processedText = processedText.replace(/\[S\d*:?[^\]]*$/i, '');
            // Clean up spaces / soft hyphens / weird mid-word en-dashes from model output.
            // CRITICAL: never collapse newlines — that destroys markdown structure.
            processedText = processedText
                .replace(/\r\n/g, '\n')
                .replace(/\u00ad/g, '')                 // soft hyphens
                // Normalize fancy unicode dashes mid-word to ASCII hyphen (keep compounds)
                .replace(/(\w)[\u2010\u2011\u2012\u2013\u2014\u2212](\w)/g, '$1-$2')
                .replace(/[^\S\n]+([.,;!?])/g, '$1')
                .replace(/[^\S\n]{2,}/g, ' ')
                .replace(/\n{3,}/g, '\n\n')
                // Drop trailing model notes that look like metadata noise
                .replace(/\n*---+\s*Note:[\s\S]*$/i, '')
                .replace(/\n*Note:\s*The provided text confirms[\s\S]*$/i, '');

            // Strip residual style control tokens / bare S# crumbs if any slipped through
            processedText = processedText
                .replace(/\/{2,}\s*CITE\s+FIRST\s*\/{2,}/gi, '')
                .replace(/<<<[^>\n]*>>>/g, '')
                .replace(/\bTHE\s+END\.?\b/gi, '')
                .replace(/\[END\]/gi, '')
                .replace(/\[DONE\]/gi, '')
                .replace(/\[STREAM_DONE\]/gi, '')
                .replace(/\[MODEL_REWRITE\]/gi, '')
                .replace(/\[\s*S#\s*\]\s*to\b/gi, '')
                .replace(/\[\s*S#\s*\]/gi, '')
                .replace(/\[\s*S\d+(?:\s*:[^\]]*)?\s*\]\s*to\b/gi, '')
                // Multiline via the m flag (Python-style inline flags crash JS parse).
                .replace(/^\s*to\s+(?=\(p\.)/gim, '');

            // Prefer GFM with soft line breaks for chat answers
            let html = '';
            try {
                if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
                    if (typeof marked.setOptions === 'function') {
                        marked.setOptions({ gfm: true, breaks: true });
                    }
                    html = marked.parse(processedText);
                } else {
                    html = processedText
                        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                        .replace(/\n/g, '<br>');
                }
            } catch (err) {
                console.warn('Markdown parse failed:', err);
                html = processedText
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/\n/g, '<br>');
            }
            target.innerHTML = sanitizeMarkdown(html);
        }

export { _glowWrap, _hideWelcomeWithTransition, _isGenDesc, _updateGlowState, escapeHTML, renderMarkdownSafely, sanitizeMarkdown };
