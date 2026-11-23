// Auto-split from ui/chat/index.html — 09-patterns.js
// Feature module 10 of 22.
import { renderMarkdownSafely } from './01--hide-welcome-with-transitio.js';
import { _enrichAssistantMarkup, appendEvidenceRail } from './02--kw-highlights.js';
import { wrapLibraryInventorySection } from './03-wrap-library-inventory-secti.js';
import { renderGraphExperiencePrompt } from './12-choose-graph-experience.js';

        const PATTERNS = {
            "solo-center": [[0,0,0],[0,1,0],[0,0,0]], "solo-tl": [[1,0,0],[0,0,0],[0,0,0]], "solo-tr": [[0,0,1],[0,0,0],[0,0,0]], "solo-bl": [[0,0,0],[0,0,0],[1,0,0]], "solo-br": [[0,0,0],[0,0,0],[0,0,1]],
            "line-h-top": [[1,1,1],[0,0,0],[0,0,0]], "line-h-mid": [[0,0,0],[1,1,1],[0,0,0]], "line-h-bot": [[0,0,0],[0,0,0],[1,1,1]],
            "line-v-left": [[1,0,0],[1,0,0],[1,0,0]], "line-v-mid": [[0,1,0],[0,1,0],[0,1,0]], "line-v-right": [[0,0,1],[0,0,1],[0,0,1]],
            "line-diag-1": [[1,0,0],[0,1,0],[0,0,1]], "line-diag-2": [[0,0,1],[0,1,0],[1,0,0]],
            "corners-only": [[1,0,1],[0,0,0],[1,0,1]], "corners-sync": [[1,0,1],[0,0,0],[1,0,1]], "corners": [[1,0,1],[0,0,0],[1,0,1]],
            "plus-hollow": [[0,1,0],[1,0,1],[0,1,0]], "plus-full": [[0,1,0],[1,1,1],[0,1,0]],
            "L-tl": [[1,1,0],[1,0,0],[0,0,0]], "L-tr": [[0,1,1],[0,0,1],[0,0,0]], "L-bl": [[0,0,0],[1,0,0],[1,1,0]], "L-br": [[0,0,0],[0,0,1],[0,1,1]],
            "T-top": [[1,1,1],[0,1,0],[0,0,0]], "T-bot": [[0,0,0],[0,1,0],[1,1,1]], "T-left": [[1,0,0],[1,1,0],[1,0,0]], "T-right": [[0,0,1],[0,1,1],[0,0,1]],
            "duo-h": [[0,0,0],[1,1,0],[0,0,0]], "duo-v": [[0,1,0],[0,1,0],[0,0,0]], "duo-diag": [[1,0,0],[0,1,0],[0,0,0]],
            "frame": [[1,1,1],[1,0,1],[1,1,1]], "frame-sync": [[1,1,1],[1,0,1],[1,1,1]],
            "sparse-1": [[1,0,0],[0,0,1],[0,1,0]], "sparse-2": [[0,1,0],[1,0,0],[0,0,1]], "sparse-3": [[0,0,1],[0,1,0],[1,0,0]],
            "wave-lr": [[1,1,0],[1,1,0],[1,1,0]], "wave-rl": [[0,1,1],[0,1,1],[0,1,1]], "wave-tb": [[1,1,1],[1,1,1],[0,0,0]], "wave-bt": [[0,0,0],[1,1,1],[1,1,1]],
            "diagonal-tl": [[1,1,0],[1,1,0],[0,0,0]], "diagonal-tr": [[0,1,1],[0,1,1],[0,0,0]], "diagonal-bl": [[0,0,0],[1,1,0],[1,1,0]], "diagonal-br": [[0,0,0],[0,1,1],[0,1,1]],
            "ripple-out": [[1,1,1],[1,0,1],[1,1,1]], "ripple-in": [[0,0,0],[0,1,0],[0,0,0]],
            "cross": [[0,1,0],[1,1,1],[0,1,0]], "x-shape": [[1,0,1],[0,1,0],[1,0,1]], "diamond": [[0,1,0],[1,0,1],[0,1,0]],
            "stripes-h": [[1,1,1],[0,0,0],[1,1,1]], "stripes-v": [[1,0,1],[1,0,1],[1,0,1]],
            "checkerboard": [[1,0,1],[0,1,0],[1,0,1]], "rows-alt": [[1,1,1],[0,0,0],[1,1,1]],
            "spiral-cw": [[1,1,1],[0,0,1],[0,0,1]], "spiral-ccw": [[1,1,1],[1,0,0],[1,0,0]],
            "snake": [[1,1,0],[0,1,0],[0,0,0]], "snake-rev": [[0,0,0],[0,1,0],[0,1,1]],
            "rain": [[0,1,0],[0,1,0],[0,0,0]], "rain-rev": [[0,0,0],[0,1,0],[0,1,0]],
            "waterfall": [[1,1,0],[0,0,0],[0,0,0]], "breathing": [[0,0,0],[0,1,0],[0,0,0]], "heartbeat": [[0,1,0],[1,1,1],[0,1,0]],
            "twinkle": [[1,0,0],[0,0,1],[0,1,0]], "sparkle": [[1,0,1],[0,1,0],[1,0,1]], "chaos": [[1,0,1],[0,1,0],[1,0,0]],
            "edge-cw": [[1,1,1],[0,0,0],[0,0,0]], "border": [[1,1,1],[1,0,1],[1,1,1]]
        };

        function initThinkingOrbLoader(container, options = {}) {
            if (!container) return null;
            const mode = options.mode || 'sequence';
            const color = options.color || '#a78bfa';
            const size = options.size || 42;
            const gap = options.gap !== undefined ? options.gap : 5;
            const speed = options.speed || 'normal';
            const rounded = options.rounded !== undefined ? options.rounded : true;
            const pattern = options.pattern || 'plus-hollow';
            const sequence = options.sequence || ["plus-hollow", "diamond", "corners-only", "cross", "x-shape", "heartbeat", "frame", "ripple-out"];
            
            const speedMsMap = { slow: 1500, normal: 800, fast: 400 };
            const cycleDuration = speedMsMap[speed] || 800;
            
            container.innerHTML = '';
            container.className = 'thinking-orb-loader';
            container.style.width = `${size}px`;
            container.style.height = `${size}px`;
            container.style.gap = `${gap}px`;
            
            const cells = [];
            for (let i = 0; i < 9; i++) {
                const cell = document.createElement('div');
                cell.className = 'orb-cell';
                if (rounded) cell.style.borderRadius = '50%';
                container.appendChild(cell);
                cells.push(cell);
            }
            
            let sequenceIndex = 0;
            const render = () => {
                let currentGrid;
                if (mode === 'sequence' && sequence && sequence.length > 0) {
                    const pName = sequence[sequenceIndex];
                    currentGrid = (typeof pName === 'string' ? PATTERNS[pName] : pName) || PATTERNS['plus-hollow'];
                } else {
                    currentGrid = (typeof pattern === 'string' ? PATTERNS[pattern] : pattern) || PATTERNS['plus-hollow'];
                }
                
                const flatGrid = currentGrid.flat();
                let activeIndices = [];
                if (mode === 'stagger') {
                    flatGrid.forEach((val, idx) => {
                        if (val === 1) activeIndices.push(idx);
                    });
                }
                const delayPerCell = cycleDuration / (activeIndices.length + 2);
                
                flatGrid.forEach((val, idx) => {
                    const cell = cells[idx];
                    if (val === 1) {
                        cell.style.backgroundColor = color;
                        cell.style.boxShadow = `0 0 6px ${color}, 0 0 14px ${color}8c, 0 0 28px ${color}4d`;
                        cell.className = 'orb-cell is-active';
                        
                        if (mode === 'stagger') {
                            cell.classList.add('animate-stagger');
                            const activeIdx = activeIndices.indexOf(idx);
                            cell.style.animationDelay = `${(activeIdx * delayPerCell) / 1000}s`;
                        } else if (mode === 'pulse') {
                            cell.classList.add('animate-pulse');
                            cell.style.animationDelay = '0s';
                        }
                    } else {
                        cell.className = 'orb-cell';
                        cell.style.backgroundColor = 'transparent';
                        cell.style.boxShadow = 'none';
                        cell.style.animationDelay = '0s';
                    }
                });
            };
            
            render();
            
            let timer = null;
            if (mode === 'sequence' && sequence && sequence.length > 1) {
                timer = setInterval(() => {
                    if (!container.isConnected) {
                        clearInterval(timer);
                        return;
                    }
                    sequenceIndex = (sequenceIndex + 1) % sequence.length;
                    render();
                }, cycleDuration);
            }
            return timer;
        }

        // Render standard chat bubbles (no per-message avatar — sticky dock owns the video)
        // NO 3D tilt / overflow masks on bubbles — those clipped AI text
        function appendMessage(role, text, isTyping = false, citations = [], metadata = null) {
            const chatMsgs = document.getElementById('chat-messages');
            const msgId = Date.now() + Math.floor(Math.random() * 1000);
            
            const messageWrapper = document.createElement('div');
            messageWrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} w-full`;
            
            if (!window.hasOwnProperty('_nextLoaderStyle')) {
                window._nextLoaderStyle = 'lightgrid';
            }
            const currentLoaderStyle = window._nextLoaderStyle;
            
            let messageHtml = '';
            if (role === 'user') {
                messageHtml = `
                    <div class="msg-bubble-wrap user-wrap">
                        <div data-user-message class="user-bubble"></div>
                    </div>
                `;
            } else {
                let thinkingHtml = '';
                if (isTyping) {
                    if (currentLoaderStyle === 'orb') {
                        thinkingHtml = `
                            <div class="thinking-shimmer" aria-live="polite" aria-label="Archipelago is thinking">
                                <div class="thinking-label">Archipelago · thinking</div>
                                <div class="thinking-orb-loader" id="thinking-orb-loader-${msgId}"></div>
                            </div>
                        `;
                    } else {
                        thinkingHtml = `
                            <div class="thinking-shimmer" aria-live="polite" aria-label="Archipelago is thinking">
                                <div class="thinking-label">Archipelago · thinking</div>
                                <div class="thinking-lightgrid" id="thinking-grid-${msgId}"></div>
                                <div class="typing-indicator flex items-center h-5">
                                    <span></span><span></span><span></span>
                                </div>
                            </div>
                        `;
                    }
                }
                messageHtml = `
                    <div class="assistant-row">
                        <div class="msg-bubble-wrap ai-wrap flex flex-col gap-1 min-w-0 flex-1${isTyping ? ' is-thinking' : ''}">
                            <div id="msg-body-${msgId}" class="chat-bubble">
                                ${thinkingHtml}
                            </div>
                        </div>
                    </div>
                `;
            }
            
            messageWrapper.innerHTML = messageHtml;
            if (role === 'user') {
                const u = messageWrapper.querySelector('[data-user-message]');
                if (u) u.textContent = text;
            }

            // Slide message in from below (reveal-push enter)
            messageWrapper.classList.add('reveal-enter');
            messageWrapper.dataset.msgId = String(msgId);
            chatMsgs.appendChild(messageWrapper);
            chatMsgs.scrollTop = chatMsgs.scrollHeight;

            // Alternate between lightgrid and 3x3 GridLoader orbs
            if (role === 'assistant' && isTyping) {
                if (currentLoaderStyle === 'orb') {
                    const container = document.getElementById(`thinking-orb-loader-${msgId}`);
                    if (container) {
                        const timer = initThinkingOrbLoader(container, {
                            mode: 'sequence',
                            color: '#a78bfa',
                            size: 42,
                            gap: 5,
                            speed: 'normal',
                            rounded: true
                        });
                        container.dataset.timer = String(timer);
                    }
                } else {
                    const grid = document.getElementById(`thinking-grid-${msgId}`);
                    if (grid) {
                        const COLS = 28, ROWS = 3, total = COLS * ROWS;
                        const bulbs = [];
                        const states = new Array(total).fill(0);
                        for (let i = 0; i < total; i++) {
                            const b = document.createElement('div');
                            b.className = 'sw-bulb';
                            grid.appendChild(b);
                            bulbs.push(b);
                        }
                        const tick = () => {
                            if (!grid.isConnected) {
                                clearInterval(timer);
                                return;
                            }
                            const n = Math.floor(total * 0.22);
                            Array.from({ length: total }, (_, i) => i)
                                .sort(() => Math.random() - 0.5)
                                .slice(0, n)
                                .forEach(i => {
                                    states[i] = states[i] === 0 ? 1 : states[i] === 1 ? 2 : 0;
                                    bulbs[i].className = 'sw-bulb' + (states[i] === 1 ? ' medium' : states[i] === 2 ? ' high' : '');
                                });
                        };
                        const timer = setInterval(tick, 180);
                        tick();
                        grid.dataset.timer = String(timer);
                    }
                }
                window._nextLoaderStyle = currentLoaderStyle === 'orb' ? 'lightgrid' : 'orb';
            }
            
            if (role === 'assistant' && !isTyping) {
                const el = document.getElementById(`msg-body-${msgId}`);
                if (el) {
                    renderMarkdownSafely(el, text, citations);
                    if (typeof Prism !== 'undefined') Prism.highlightAllUnder(el);
                    if (typeof _enrichAssistantMarkup === 'function') _enrichAssistantMarkup(el);
                    // Resources rail AFTER markdown paint so it is not wiped
                    appendEvidenceRail(el, metadata || citations);
                    if (typeof wrapLibraryInventorySection === 'function') wrapLibraryInventorySection(el, metadata);
                    if (metadata && typeof renderGraphExperiencePrompt === 'function') {
                        renderGraphExperiencePrompt(msgId, metadata, { showPopup: false });
                    }
                    _addChatBubbleEffects(el);
                }
            }
            return msgId;
        }

        /**
         * Premium effects injected into completed AI chat bubbles:
         * 1) Line ripple SVG canvas background
         * 2) Shimmer on h1/h2/h3 (via CSS)
         * 3) Vibrant strong/em/code colors (via CSS)
         */
        function _addChatBubbleEffects(bubbleEl) {
            if (!bubbleEl || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
            // Line ripple SVG canvas background
            _addBubbleRipple(bubbleEl);
        }

        function _addBubbleRipple(bubbleEl) {
            if (!bubbleEl || bubbleEl.querySelector('.chat-bubble-ripple-bg')) return;
            const bg = document.createElement('div');
            bg.className = 'chat-bubble-ripple-bg';
            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');
            bg.appendChild(svg);
            bubbleEl.insertBefore(bg, bubbleEl.firstChild);

            const path = document.createElementNS(svgNS, 'path');
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', 'rgba(196,160,255,0.08)');
            path.setAttribute('stroke-width', '1');
            path.setAttribute('stroke-linecap', 'round');
            svg.appendChild(path);

            // Simple ambient drift animation (no mouse tracking inside bubbles)
            let frame;
            const animate = (t) => {
                if (!bg.isConnected) { cancelAnimationFrame(frame); return; }
                const W = bubbleEl.clientWidth || 400;
                const H = bubbleEl.clientHeight || 200;
                const drift = t * 4e-4;
                const gap = 55;
                const cols = Math.ceil(W / gap);
                const rows = Math.ceil(H / gap);
                let d = '';
                for (let c = 0; c < cols; c++) {
                    for (let r = 0; r < rows; r++) {
                        const x = c * gap + 20;
                        const y = r * gap + 15;
                        const angle = Math.sin(x * 0.01 + drift) * Math.cos(y * 0.01 - drift) * Math.PI;
                        const hl = 10;
                        const ux = Math.cos(angle) * hl;
                        const uy = Math.sin(angle) * hl;
                        d += `M${(x-ux).toFixed(1)} ${(y-uy).toFixed(1)}L${(x+ux).toFixed(1)} ${(y+uy).toFixed(1)} `;
                    }
                }
                path.setAttribute('d', d);
                frame = requestAnimationFrame(animate);
            };
            frame = requestAnimationFrame(animate);
            setTimeout(() => bg.classList.add('is-ready'), 100);
        }

export { PATTERNS, _addBubbleRipple, _addChatBubbleEffects, appendMessage, initThinkingOrbLoader };
