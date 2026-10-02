// Auto-split from ui/chat/index.html — 00-current-origin.js
// Feature module 1 of 22.

        // Student chat client — query only.
        const CURRENT_ORIGIN = (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin.startsWith('http'))
            ? window.location.origin
            : '';

        const API_HOST = CURRENT_ORIGIN;

        // Port map: SoFerence chat :5152 → graph :5150; pilot chat :5052 → graph :5050.
        // (Inference API is :5151 / :5051 — never the graph UI host.)
        const _pageHost = (typeof window !== 'undefined' && window.location && window.location.hostname) || 'localhost';

        const _pagePort = (typeof window !== 'undefined' && window.location && window.location.port) || '';

        const _graphPort = (_pagePort === '5152' || _pagePort === '5151' || _pagePort === '5150') ? '5150' : '5050';

        const GRAPH_HOST = `http://${_pageHost}:${_graphPort}`;

        const API_CONTRACT = Object.assign({
            health: API_HOST + '/api/readiness',
            chat: API_HOST + '/api/chat',
            roadmap: API_HOST + '/api/roadmap',
        }, window.ARCHIPELAGO_API || {});

        // Never allow student page to point at librarian mutate APIs
        delete API_CONTRACT.upload;

        delete API_CONTRACT.capabilities;

        delete API_CONTRACT.jobStatus;

        delete API_CONTRACT.cancelJob;

        // Librarian avatar story — 5 clips play in sequence, then loop
        // hi → think → type → goit → success → (repeat)
        const AVATAR_STORY = [
            { key: 'hi', src: '/ui/assets/library_hi.mp4' },
            { key: 'think', src: '/ui/assets/library_think.mp4' },
            { key: 'type', src: '/ui/assets/library_type.mp4' },
            { key: 'goit', src: '/ui/assets/library_goit.mp4' },
            { key: 'success', src: '/ui/assets/library_sucess%20(1).mp4' },
        ];

        const AVATAR_THINK_KEY = 'think';

        // Back-compat aliases for any remaining references
        const AVATAR_HI_SRC = AVATAR_STORY[0].src;

        const AVATAR_THINK_SRC = AVATAR_STORY[1].src;

        function buildAvatarClipsHtml(activeKey) {
            const start = activeKey || 'hi';
            return AVATAR_STORY.map((clip) => {
                const hidden = clip.key === start ? '' : ' is-hidden';
                return `<video data-avatar-clip="${clip.key}" class="avatar-clip${hidden}" src="${clip.src}" muted playsinline webkit-playsinline preload="auto"></video>`;
            }).join('\n');
        }

const CHAT_RESPONSE_TIMEOUT_MS = 45000;

        // Stream watchdogs: idle gap between chunks vs absolute wall-clock cap.
        const STREAM_IDLE_TIMEOUT_MS = 25000;

        const STREAM_HARD_TIMEOUT_MS = 120000;

        // Cap history sent to the API so long chats stay under request size limits.
        const MAX_HISTORY_TURNS_SENT = 12;

        function primeAvatarVideo(vid, src) {
            if (!vid) return;
            if (src) {
                const leaf = decodeURIComponent(src.split('/').pop() || '');
                const currentLeaf = decodeURIComponent((vid.getAttribute('src') || vid.currentSrc || '').split('/').pop() || '');
                if (!currentLeaf || currentLeaf !== leaf) {
                    vid.src = src;
                }
            }
            vid.muted = true;
            vid.defaultMuted = true;
            vid.playsInline = true;
            vid.autoplay = false;
            vid.loop = false;
            vid.preload = 'auto';
            vid.removeAttribute('autoplay');
            vid.removeAttribute('loop');
            vid.setAttribute('muted', '');
            vid.setAttribute('playsinline', '');
            vid.setAttribute('webkit-playsinline', '');
            try { if (!vid.src && src) vid.load(); } catch (_) {}
        }

        function playAvatarVideo(vid) {
            if (!vid) return;
            const go = () => {
                try { if (vid.currentTime > 0.05) vid.currentTime = 0; } catch (_) {}
                const p = vid.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            };
            if (vid.readyState >= 2) go();
            else vid.addEventListener('loadeddata', go, { once: true });
        }

        function pauseAvatarVideo(vid) {
            if (!vid) return;
            try {
                vid.pause();
                const setFrame = () => {
                    try { vid.currentTime = 0.1; } catch (_) {}
                };
                if (vid.readyState >= 1) {
                    setFrame();
                } else {
                    vid.addEventListener('loadedmetadata', setFrame, { once: true });
                }
            } catch (_) {}
        }

        function _avatarClipEls(root) {
            return AVATAR_STORY.map((clip) => root.querySelector(`video[data-avatar-clip="${clip.key}"]`)).filter(Boolean);
        }

        function _avatarIndexForKey(key) {
            const i = AVATAR_STORY.findIndex((c) => c.key === key);
            return i >= 0 ? i : 0;
        }

        function _showAvatarClipAt(root, index) {
            if (!root) return;
            const clips = _avatarClipEls(root);
            if (!clips.length) return;
            const n = clips.length;
            const idx = ((index % n) + n) % n;
            root.dataset.avatarIndex = String(idx);
            clips.forEach((vid, i) => {
                if (i === idx) {
                    vid.classList.remove('is-hidden');
                    vid.loop = root.dataset.avatarMode === 'think';
                    playAvatarVideo(vid);
                } else {
                    vid.classList.add('is-hidden');
                    vid.loop = false;
                    try { vid.pause(); } catch (_) {}
                }
            });
        }

        function _onAvatarClipEnded(root) {
            return function handleEnded() {
                if (!root || root.dataset.avatarWired !== '1') return;
                const mode = root.dataset.avatarMode || 'story';
                if (mode === 'paused') return;
                if (mode === 'think') {
                    // Stay on think while generating (loop handles it; safety restart)
                    const thinkIdx = _avatarIndexForKey(AVATAR_THINK_KEY);
                    _showAvatarClipAt(root, thinkIdx);
                    return;
                }
                const cur = parseInt(root.dataset.avatarIndex || '0', 10) || 0;
                const next = (cur + 1) % AVATAR_STORY.length;
                _showAvatarClipAt(root, next);
            };
        }

        function wireAvatarVideos(root, preferThink = false) {
            if (!root) return;

            // Ensure all 5 story clips exist (upgrade legacy 2-clip shells)
            AVATAR_STORY.forEach((clip) => {
                let vid = root.querySelector(`video[data-avatar-clip="${clip.key}"]`);
                if (!vid) {
                    // Legacy class fallback
                    if (clip.key === 'hi') vid = root.querySelector('video.avatar-hi');
                    if (clip.key === 'think') vid = root.querySelector('video.avatar-think');
                }
                if (!vid) {
                    vid = document.createElement('video');
                    vid.className = 'avatar-clip is-hidden';
                    vid.setAttribute('data-avatar-clip', clip.key);
                    root.appendChild(vid);
                }
                vid.setAttribute('data-avatar-clip', clip.key);
                vid.classList.add('avatar-clip');
                primeAvatarVideo(vid, clip.src);
                if (!vid._avatarErrorBound) {
                    vid._avatarErrorBound = true;
                    vid.addEventListener('error', () => {
                        console.warn('Avatar video failed to load:', vid.currentSrc || vid.src);
                    });
                }
                // Story advances on ended (one full play per beat)
                if (vid._avatarEndedHandler) {
                    vid.removeEventListener('ended', vid._avatarEndedHandler);
                }
                vid._avatarEndedHandler = _onAvatarClipEnded(root);
                vid.addEventListener('ended', vid._avatarEndedHandler);
            });

            root.dataset.avatarWired = '1';
            setAvatarThinking(root, preferThink);
        }

        function setAvatarThinking(root, thinking) {
            if (!root) return;
            if (root.dataset.avatarWired !== '1') {
                wireAvatarVideos(root, !!thinking);
                return;
            }
            root.classList.toggle('is-thinking', !!thinking);

            if (thinking) {
                // Processing: lock on think clip and loop it
                root.dataset.avatarMode = 'think';
                _showAvatarClipAt(root, _avatarIndexForKey(AVATAR_THINK_KEY));
            } else {
                // Idle: full story sequence looping forever
                root.dataset.avatarMode = 'story';
                const cur = parseInt(root.dataset.avatarIndex || '0', 10);
                const start = Number.isFinite(cur) ? cur : 0;
                _showAvatarClipAt(root, start);
            }
        }

        function buildAvatarHtml(thinking = false) {
            const active = thinking ? AVATAR_THINK_KEY : 'hi';
            return `
                <div class="avatar-shell${thinking ? ' is-thinking' : ''}" data-avatar data-avatar-index="${thinking ? 1 : 0}">
                    ${buildAvatarClipsHtml(active)}
                </div>
            `;
        }

        function pauseAvatarRoot(root) {
            if (!root) return;
            root.dataset.avatarMode = 'paused';
            root.querySelectorAll('video').forEach((vid) => {
                pauseAvatarVideo(vid);
            });
        }

        function getStickyAvatar() {
            return document.getElementById('sticky-avatar');
        }

        /** One librarian on the left — no per-message duplicates */
        function showStickyAvatar(thinking = false) {
            const dock = document.getElementById('sticky-avatar-dock');
            const sticky = getStickyAvatar();
            if (!dock || !sticky) return sticky;
            pauseAvatarRoot(document.getElementById('welcome-avatar'));
            dock.classList.add('is-visible');
            dock.setAttribute('aria-hidden', 'false');
            wireAvatarVideos(sticky, !!thinking);
            setAvatarThinking(sticky, !!thinking);
            return sticky;
        }

        function hideStickyAvatar() {
            const dock = document.getElementById('sticky-avatar-dock');
            const sticky = getStickyAvatar();
            if (sticky) pauseAvatarRoot(sticky);
            if (dock) {
                dock.classList.remove('is-visible');
                dock.setAttribute('aria-hidden', 'true');
            }
        }

        function setLibrarianThinking(thinking) {
            const sticky = getStickyAvatar();
            const dock = document.getElementById('sticky-avatar-dock');
            if (dock && dock.classList.contains('is-visible') && sticky) {
                setAvatarThinking(sticky, !!thinking);
                return;
            }
            const welcome = document.getElementById('welcome-avatar');
            if (welcome) setAvatarThinking(welcome, !!thinking);
        }

        // Wire welcome avatar as soon as script runs — full story loop idle
        wireAvatarVideos(document.getElementById('welcome-avatar'), false);

        hideStickyAvatar();

        // Wire graph browse link (students may browse; only librarians upload there)
        // ═══════════════════════════════════════════════════════════════
        // PREMIUM UI — SmoothUI / OriginKit component initializers
        // ═══════════════════════════════════════════════════════════════

        // ── 0. Hero video — final_archi only (never archi_main.mp4 / intro_archi) ─
        (function initHeroVideo() {
            const HERO_SRC = (CURRENT_ORIGIN || '') + '/ui/assets/final_archi.mp4';
            const HERO_POSTER = '/ui/assets/final_archi_poster.jpg';
            // wireLoopVideo: shared play/unlock helper for looping muted clips.
            function wireLoopVideo(vid, src) {
                if (!vid) return null;
                if (src) {
                    vid.src = src;
                    vid.setAttribute('src', src);
                }
                vid.muted = true;
                vid.defaultMuted = true;
                vid.loop = true;
                vid.autoplay = true;
                vid.playsInline = true;
                try { vid.load(); } catch (_) {}
                const tryPlay = () => {
                    const p = vid.play();
                    if (p && typeof p.catch === 'function') p.catch(() => {});
                };
                vid.addEventListener('canplay', tryPlay, { once: true });
                tryPlay();
                return tryPlay;
            }
            function wireHeroVideo(vid) {
                if (!vid) return;
                // Force final_archi only — strip any stale archi_main.mp4 / intro paths
                vid.src = HERO_SRC;
                vid.setAttribute('src', HERO_SRC);
                vid.poster = HERO_POSTER;
                vid.setAttribute('poster', HERO_POSTER);
                vid.muted = true;
                vid.defaultMuted = true;
                vid.loop = true;
                vid.autoplay = true;
                vid.playsInline = true;
                vid.preload = 'auto';
                vid.setAttribute('muted', '');
                vid.setAttribute('playsinline', '');
                vid.setAttribute('webkit-playsinline', '');
                vid.setAttribute('autoplay', '');
                vid.setAttribute('loop', '');
                try { vid.load(); } catch (_) {}
                const tryPlay = () => {
                    // Guard: never play a non-final_archi source
                    if (!String(vid.currentSrc || vid.src || '').includes('final_archi')) {
                        vid.src = HERO_SRC;
                        try { vid.load(); } catch (_) {}
                    }
                    const p = vid.play();
                    if (p && typeof p.catch === 'function') p.catch(() => {});
                };
                vid.addEventListener('canplay', tryPlay, { once: true });
                vid.addEventListener('loadeddata', tryPlay, { once: true });
                vid.addEventListener('pause', () => {
                    if (document.visibilityState === 'visible' && !vid.ended) {
                        setTimeout(tryPlay, 120);
                    }
                });
                document.addEventListener('visibilitychange', () => {
                    if (document.visibilityState === 'visible') tryPlay();
                });
                tryPlay();
                return tryPlay;
            }
            // Header bg video is decorative/disabled — do NOT load archi_main.mp4 into it
            const headerVid = document.getElementById('header-bg-video');
            if (headerVid) {
                try { headerVid.removeAttribute('src'); headerVid.removeAttribute('poster'); headerVid.load(); } catch (_) {}
            }
            const tryHero = wireHeroVideo(document.getElementById('hero-video'));
            const unlock = () => {
                if (tryHero) tryHero();
                window.removeEventListener('pointerdown', unlock);
            };
            window.addEventListener('pointerdown', unlock, { once: true, passive: true });
        })();

export { API_CONTRACT, API_HOST, AVATAR_HI_SRC, AVATAR_STORY, AVATAR_THINK_KEY, AVATAR_THINK_SRC, CHAT_RESPONSE_TIMEOUT_MS, CURRENT_ORIGIN, GRAPH_HOST, MAX_HISTORY_TURNS_SENT, STREAM_HARD_TIMEOUT_MS, STREAM_IDLE_TIMEOUT_MS, _avatarClipEls, _avatarIndexForKey, _graphPort, _onAvatarClipEnded, _pageHost, _pagePort, _showAvatarClipAt, buildAvatarClipsHtml, buildAvatarHtml, getStickyAvatar, hideStickyAvatar, pauseAvatarRoot, pauseAvatarVideo, playAvatarVideo, primeAvatarVideo, setAvatarThinking, setLibrarianThinking, showStickyAvatar, wireAvatarVideos };
