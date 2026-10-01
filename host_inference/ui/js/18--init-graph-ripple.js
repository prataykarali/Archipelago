// Auto-split from ui/chat/index.html — 18--init-graph-ripple.js
// Feature module 19 of 22.
import { _nodeId, _nodeLabel, _nodeSummary, selectGraphNode } from './10-populate-pipeline.js';
import { autoPrompt } from './07-open-page-viewer-modal.js';

        /**
         * OriginKit-style Interactive Line Ripple — vanilla JS port.
         * Attaches an animated SVG line field to a container, driven by simplex noise.
         * Responds to mouse movement for an interactive feel.
         */
        function _initGraphRipple(rippleEl, containerEl) {
            if (!rippleEl || rippleEl.dataset.rippleInit) return;
            rippleEl.dataset.rippleInit = '1';

            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');
            rippleEl.appendChild(svg);

            const path = document.createElementNS(svgNS, 'path');
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke', 'rgba(196, 160, 255, 0.18)');
            path.setAttribute('stroke-width', '1.5');
            path.setAttribute('stroke-linecap', 'round');
            svg.appendChild(path);

            // Simplex noise 2D (same as welcome ripple)
            function createNoise2D(seed) {
                const F2 = 0.5 * (Math.sqrt(3) - 1);
                const G2 = (3 - Math.sqrt(3)) / 6;
                const p = new Uint8Array(256);
                for (let i = 0; i < 256; i++) p[i] = i;
                const sr = (idx) => { const x = Math.sin(idx * 12.9898 + seed * 78.233) * 43758.5453; return x - Math.floor(x); };
                for (let i = 255; i > 0; i--) { const n = Math.floor((i + 1) * sr(i)); const q = p[i]; p[i] = p[n]; p[n] = q; }
                const perm = new Uint8Array(512);
                const permMod12 = new Uint8Array(512);
                for (let i = 0; i < 512; i++) { perm[i] = p[i & 255]; permMod12[i] = perm[i] % 12; }
                const grad2 = [1,1,-1,1,1,-1,-1,-1,1,0,-1,0,1,0,-1,0,0,1,0,-1,0,1,0,-1];
                return function(x, y) {
                    const s = (x + y) * F2;
                    const i = Math.floor(x + s), j = Math.floor(y + s);
                    const t = (i + j) * G2;
                    const x0 = x - (i - t), y0 = y - (j - t);
                    const i1 = x0 > y0 ? 1 : 0, j1 = x0 > y0 ? 0 : 1;
                    const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2;
                    const G22 = (3 - Math.sqrt(3)) / 3;
                    const x2 = x0 - 1 + G22, y2 = y0 - 1 + G22;
                    const ii = i & 255, jj = j & 255;
                    const gi0 = permMod12[ii + perm[jj]];
                    const gi1 = permMod12[ii + i1 + perm[jj + j1]];
                    const gi2 = permMod12[ii + 1 + perm[jj + 1]];
                    let n0 = 0, n1 = 0, n2 = 0;
                    let t0 = 0.5 - x0*x0 - y0*y0;
                    if (t0 >= 0) { t0 *= t0; n0 = t0 * t0 * (grad2[gi0*2]*x0 + grad2[gi0*2+1]*y0); }
                    let t1 = 0.5 - x1*x1 - y1*y1;
                    if (t1 >= 0) { t1 *= t1; n1 = t1 * t1 * (grad2[gi1*2]*x1 + grad2[gi1*2+1]*y1); }
                    let t2 = 0.5 - x2*x2 - y2*y2;
                    if (t2 >= 0) { t2 *= t2; n2 = t2 * t2 * (grad2[gi2*2]*x2 + grad2[gi2*2+1]*y2); }
                    return 70 * (n0 + n1 + n2);
                };
            }

            const noise = createNoise2D(0.5);
            const mouse = { x: -10, y: 0, sx: 0, sy: 0, lx: 0, ly: 0, vs: 0, set: false };
            let points = [];
            const CURL = 3;
            const HALF = 13;
            const COUNT = 57;

            function setSize() {
                const W = containerEl.clientWidth || 400;
                const H = containerEl.clientHeight || 200;
                svg.style.width = W + 'px';
                svg.style.height = H + 'px';
                const gap = 90 - ((COUNT - 1) / 99) * 82;
                const cols = Math.ceil((W + gap) / gap);
                const rows = Math.ceil((H + gap) / gap);
                const xStart = (W - gap * (cols - 1)) / 2;
                const yStart = (H - gap * (rows - 1)) / 2;
                points = [];
                for (let i = 0; i < cols; i++) {
                    for (let j = 0; j < rows; j++) {
                        points.push({ x: xStart + gap * i, y: yStart + gap * j, angle: 0, cx: 0, cy: 0, vx: 0, vy: 0 });
                    }
                }
            }

            function draw(time) {
                const dx = mouse.x - mouse.lx, dy = mouse.y - mouse.ly;
                const d = Math.hypot(dx, dy);
                mouse.vs += (d - mouse.vs) * 0.1;
                mouse.vs = Math.min(100, mouse.vs);
                mouse.lx = mouse.x; mouse.ly = mouse.y;
                mouse.sx += (mouse.x - mouse.sx) * 0.1;
                mouse.sy += (mouse.y - mouse.sy) * 0.1;

                const drift = time * 24 * 8e-6;
                points.forEach(p => {
                    const n = noise(p.x * 0.004 - drift, p.y * 0.004 - drift);
                    const target = n * Math.PI * CURL;
                    const mdx = p.x - mouse.sx, mdy = p.y - mouse.sy;
                    const md = Math.hypot(mdx, mdy);
                    const l = Math.max(175, mouse.vs);
                    let bend = 0;
                    if (md < l) {
                        const s = 1 - md / l;
                        const tang = Math.atan2(mdy, mdx) + Math.PI / 2;
                        bend = (tang - target) * s * (0.4 + mouse.vs * 0.008);
                        const f = Math.cos(md * 0.001) * s;
                        p.vx += Math.cos(Math.atan2(mdy, mdx)) * f * l * mouse.vs * 2.8e-4;
                        p.vy += Math.sin(Math.atan2(mdy, mdx)) * f * l * mouse.vs * 2.8e-4;
                    }
                    let diff = target + bend - p.angle;
                    while (diff > Math.PI) diff -= 2 * Math.PI;
                    while (diff < -Math.PI) diff += 2 * Math.PI;
                    p.angle += diff * 0.12;
                    p.vx += (0 - p.cx) * 0.01; p.vy += (0 - p.cy) * 0.01;
                    p.vx *= 0.95; p.vy *= 0.95;
                    p.cx += p.vx; p.cy += p.vy;
                    p.cx = Math.min(50, Math.max(-50, p.cx));
                    p.cy = Math.min(50, Math.max(-50, p.cy));
                });

                let d2 = '';
                for (const p of points) {
                    const cx = p.x + p.cx, cy = p.y + p.cy;
                    const ux = Math.cos(p.angle) * HALF, uy = Math.sin(p.angle) * HALF;
                    d2 += `M${(cx-ux).toFixed(1)} ${(cy-uy).toFixed(1)}L${(cx+ux).toFixed(1)} ${(cy+uy).toFixed(1)} `;
                }
                path.setAttribute('d', d2);
            }

            let raf;
            function loop(t) {
                if (!rippleEl.isConnected) { cancelAnimationFrame(raf); return; }
                draw(t);
                raf = requestAnimationFrame(loop);
            }

            const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            if (!reduced) {
                setSize();
                window.addEventListener('resize', setSize);
                (containerEl || rippleEl.parentElement).addEventListener('mousemove', (e) => {
                    const rect = (containerEl || rippleEl.parentElement).getBoundingClientRect();
                    mouse.x = e.clientX - rect.left;
                    mouse.y = e.clientY - rect.top;
                    if (!mouse.set) { mouse.sx = mouse.x; mouse.sy = mouse.y; mouse.set = true; }
                }, { passive: true });
                // Enable pointer events on the container so mouse tracking works
                if (containerEl) containerEl.style.pointerEvents = 'auto';
                raf = requestAnimationFrame(loop);
            }
        }

        function scrollInChatGraph(cardId, delta) {
            const el = document.getElementById(`hgraph-canvas-${cardId}`) || document.getElementById(`pers-canvas-${cardId}`);
            if (el) {
                el.scrollBy({ left: delta, behavior: 'smooth' });
            }
        }

        window.scrollInChatGraph = scrollInChatGraph;

        function selectHorizontalNode(cardId, nodeId, nodeData, anchor, prereqs, unlocks, related) {
            // Synchronize with left sidebar panel
            window._graphNeighborhood = {
                anchor: anchor,
                prereqs: prereqs,
                unlocks: unlocks,
                related: related
            };
            if (typeof selectGraphNode === 'function') {
                selectGraphNode(nodeId, null);
            }

            const titleEl = document.getElementById(`node-info-title-${cardId}`);
            const badgeEl = document.getElementById(`node-info-badge-${cardId}`);
            const diffEl = document.getElementById(`node-info-diff-${cardId}`);
            const sumEl = document.getElementById(`node-info-summary-${cardId}`);
            const btnEl = document.getElementById(`node-info-btn-${cardId}`);

            const label = _nodeLabel(nodeData || nodeId);
            const summary = _nodeSummary(nodeData) || `Concept node in the Archipelago knowledge graph.`;

            let typeStr = 'Concept Node';
            let typeClass = 'bg-accentPurple/25 text-accentPurple border-accentPurple/40';
            const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
            const targetNorm = norm(_nodeLabel(anchor) || _nodeId(anchor));
            const curNorm = norm(label || nodeId);

            if (curNorm === targetNorm || (nodeData && (nodeData.type === 'anchor' || nodeData.role === 'target'))) {
                typeStr = 'Target Concept';
                typeClass = 'bg-amber-400/25 text-amber-300 border-amber-400/40';
            } else if ((nodeData && (nodeData.type === 'prereq' || nodeData.role === 'prereq' || nodeData.role === 'context')) || (prereqs && prereqs.some(p => norm(_nodeLabel(p) || _nodeId(p)) === curNorm))) {
                typeStr = 'Prerequisite (Requires)';
                typeClass = 'bg-accentPurple/25 text-accentPurple border-accentPurple/40';
            } else if ((nodeData && (nodeData.type === 'unlock' || nodeData.role === 'unlock')) || (unlocks && unlocks.some(u => norm(_nodeLabel(u) || _nodeId(u)) === curNorm))) {
                typeStr = 'Unlocks (Enables)';
                typeClass = 'bg-emerald-400/25 text-emerald-300 border-emerald-400/40';
            } else {
                typeStr = 'Connects (Related)';
                typeClass = 'bg-cyan-400/25 text-cyan-300 border-cyan-400/40';
            }

            if (titleEl) titleEl.textContent = label;
            if (badgeEl) { badgeEl.textContent = typeStr; badgeEl.className = `px-2 py-0.5 rounded text-[9px] font-extrabold uppercase ${typeClass}`; }
            if (diffEl) diffEl.textContent = (nodeData && nodeData.difficulty) || 'Concept';
            if (sumEl) sumEl.textContent = summary;
            if (btnEl) {
                btnEl.onclick = () => autoPrompt('Tell me about ' + label);
            }

            // Highlight node on SVG
            const svgEl = document.getElementById(`svg-horizontal-${cardId}`);
            if (svgEl) {
                svgEl.querySelectorAll('.graph-node-group').forEach(g => {
                    const sel = g.getAttribute('data-node-id') === String(nodeId) || g.getAttribute('data-node-label') === label;
                    g.classList.toggle('graph-node-selected', sel);
                    const core = g.querySelector('circle.graph-node-core');
                    if (core) {
                        core.setAttribute('stroke-width', sel ? '3.5' : (g.getAttribute('data-node-type') === 'anchor' ? '2.5' : '1.5'));
                    }
                    const ring = g.querySelector('circle.graph-select-ring');
                    if (ring) ring.style.opacity = sel ? '1' : '0';
                });
            }
        }

export { _initGraphRipple, scrollInChatGraph, selectHorizontalNode };
