// D11-B-UX: Dynamic Welcome Card, Shuffled Suggestions & Corpus Profile Awareness.
// Clean, restrained dark-purple welcome card backed by GET /api/chat/suggestions
// with graceful client-side fallback when the endpoint is unavailable.

const VISIBLE_SUGGESTION_COUNT = 5;
const MIN_SUGGESTION_COUNT = 4;

const DEFAULT_KNOWLEDGE_AREAS = [
    'Operating Systems & Virtual Memory',
    'Databases & Storage Engines',
    'Algorithms & Data Structures',
    'Computer Networks & Congestion Control',
    'Machine Learning & Retrieval-Augmented Generation',
    'Computer Architecture & Compilers',
];

const FALLBACK_SUGGESTED_QUESTIONS = [
    'Explain virtual memory paging vs segmentation in OSTEP.',
    'Compare B-Trees and LSM-Trees in database storage engines.',
    'Explain the main components of retrieval augmented generation (RAG).',
    'Compare TCP Reno and BBR congestion control in high-throughput networks.',
    'How does the Linux Completely Fair Scheduler choose processes to run?',
    'How do compilers transform source code into machine instructions?',
    'Explain singular value decomposition and its relation to eigenvalues.',
    'What are the risks of branch prediction and speculative execution?',
    'How does base-and-bounds address translation protect process memory?',
    'How do multi-level page tables reduce page table memory overhead?',
];

const _welcomeState = {
    areas: DEFAULT_KNOWLEDGE_AREAS.slice(),
    pool: FALLBACK_SUGGESTED_QUESTIONS.slice(),
    shown: [],
    shuffleCount: 0,
    loadedFromServer: false,
};

function _escapeText(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function isOpenAccessProfile(payload) {
    if (!payload || typeof payload !== 'object') return false;
    if (payload.open_access_only === true || payload.openAccessOnly === true) return true;
    if (payload.pearson_enabled === false || payload.pearsonEnabled === false) return true;
    const rawProfile = String(
        payload.access_profile
        || payload.corpus_profile
        || payload.corpusProfile
        || payload.profile
        || payload.deployment_profile
        || ''
    ).toLowerCase().trim();
    if (rawProfile && (rawProfile.includes('open_access') || rawProfile.includes('open-access') || rawProfile === 'sigir')) {
        return true;
    }
    return false;
}

function applyCorpusProfileUi(payload) {
    if (typeof document === 'undefined' || !payload || typeof payload !== 'object') return false;
    const hasExplicitFlag = (
        'access_profile' in payload
        || 'open_access_only' in payload
        || 'openAccessOnly' in payload
        || 'pearson_enabled' in payload
        || 'pearsonEnabled' in payload
        || 'corpus_profile' in payload
        || 'corpusProfile' in payload
        || 'profile' in payload
        || 'deployment_profile' in payload
    );
    if (!hasExplicitFlag) return Boolean(typeof window !== 'undefined' && window.ARCHIPELAGO_OPEN_ACCESS_ONLY);

    const openAccess = isOpenAccessProfile(payload);
    if (typeof window !== 'undefined') {
        window.ARCHIPELAGO_OPEN_ACCESS_ONLY = openAccess;
    }
    document.documentElement.dataset.corpusProfile = openAccess ? 'open_access' : 'institutional';

    const pearsonFilterBtns = document.querySelectorAll('[data-type-filter="library_pearson"], .pearson-only-ui');
    pearsonFilterBtns.forEach((el) => {
        el.classList.toggle('hidden', openAccess);
        if (openAccess) {
            el.setAttribute('aria-hidden', 'true');
        } else {
            el.removeAttribute('aria-hidden');
        }
    });

    if (openAccess && typeof window !== 'undefined') {
        const allTypeBtn = document.querySelector('#type-filter [data-type-filter="all"]');
        const pearsonBtn = document.querySelector('#type-filter [data-type-filter="library_pearson"]');
        if (pearsonBtn && pearsonBtn.classList.contains('bg-accentCyan/30') && allTypeBtn) {
            allTypeBtn.click();
        }
        if (typeof window.displayBooks === 'function') {
            try { window.displayBooks(); } catch (_) {}
        }
    }
    return openAccess;
}

function normalizeSuggestionsPayload(payload) {
    const rawAreas = Array.isArray(payload?.knowledge_areas)
        ? payload.knowledge_areas
        : Array.isArray(payload?.areas)
            ? payload.areas
            : Array.isArray(payload?.domains)
                ? payload.domains
                : [];

    const areas = [];
    const seenArea = new Set();
    for (const item of rawAreas) {
        const label = typeof item === 'string'
            ? item.trim()
            : String(item?.label || item?.name || item?.title || '').trim();
        if (!label) continue;
        const key = label.toLowerCase();
        if (seenArea.has(key)) continue;
        seenArea.add(key);
        const count = typeof item === 'object' && item !== null
            ? (item.concept_count ?? item.count ?? item.documents ?? null)
            : null;
        areas.push(count != null && Number.isFinite(Number(count)) && Number(count) > 0
            ? `${label} (${Number(count)})`
            : label);
    }

    const rawQuestions = Array.isArray(payload?.suggested_questions)
        ? payload.suggested_questions
        : Array.isArray(payload?.questions)
            ? payload.questions
            : Array.isArray(payload?.suggestions)
                ? payload.suggestions
                : [];

    const questions = [];
    const seenQ = new Set();
    const openAccess = isOpenAccessProfile(payload);
    for (const item of rawQuestions) {
        const text = typeof item === 'string'
            ? item.trim()
            : String(item?.query || item?.question || item?.text || item?.prompt || item?.label || '').trim();
        if (!text) continue;
        if (openAccess && /\bpearson\b/i.test(text)) continue;
        const key = text.toLowerCase();
        if (seenQ.has(key)) continue;
        seenQ.add(key);
        questions.push(text);
    }

    return {
        areas: areas.length ? areas : DEFAULT_KNOWLEDGE_AREAS.slice(),
        questions: questions.length ? questions : FALLBACK_SUGGESTED_QUESTIONS.slice(),
        openAccess,
    };
}

function pickShuffledQuestions(pool, count = VISIBLE_SUGGESTION_COUNT, previous = []) {
    const cleanPool = Array.isArray(pool) ? pool.filter((q) => typeof q === 'string' && q.trim()) : [];
    const targetCount = Math.max(MIN_SUGGESTION_COUNT, Math.min(VISIBLE_SUGGESTION_COUNT, cleanPool.length));
    if (cleanPool.length <= targetCount) return cleanPool.slice();

    const prevSet = new Set((previous || []).map((q) => String(q).toLowerCase()));
    const fresh = cleanPool.filter((q) => !prevSet.has(q.toLowerCase()));
    const rest = cleanPool.filter((q) => prevSet.has(q.toLowerCase()));

    const shuffleArr = (arr) => {
        const copy = arr.slice();
        for (let i = copy.length - 1; i > 0; i -= 1) {
            const j = Math.floor(Math.random() * (i + 1));
            [copy[i], copy[j]] = [copy[j], copy[i]];
        }
        return copy;
    };

    const ordered = [...shuffleArr(fresh), ...shuffleArr(rest)];
    return ordered.slice(0, targetCount);
}

function renderWelcomeSuggestionsCard(areas, questions) {
    if (typeof document === 'undefined') return null;
    const host = document.getElementById('welcome-suggestions-card');
    if (!host) return null;

    const visibleAreas = (areas && areas.length ? areas : DEFAULT_KNOWLEDGE_AREAS).slice(0, 12);
    const visibleQuestions = (questions && questions.length ? questions : FALLBACK_SUGGESTED_QUESTIONS)
        .slice(0, VISIBLE_SUGGESTION_COUNT);

    _welcomeState.shown = visibleQuestions.slice();

    const areasHtml = visibleAreas
        .map((area, idx) => `
            <li class="welcome-area-item">
                <span class="welcome-area-index">${idx + 1}.</span>
                <span class="welcome-area-label">${_escapeText(area)}</span>
            </li>
        `)
        .join('');

    const pillsHtml = visibleQuestions
        .map((q) => `
            <button type="button" class="welcome-question-pill" data-suggested-question="${_escapeText(q)}">
                <span class="welcome-question-text">${_escapeText(q)}</span>
                <i class="fa-solid fa-arrow-right welcome-question-arrow" aria-hidden="true"></i>
            </button>
        `)
        .join('');

    host.innerHTML = `
        <div class="welcome-card-section">
            <div class="welcome-card-eyebrow">Available knowledge areas</div>
            <ol class="welcome-areas-list" aria-label="Available knowledge areas">
                ${areasHtml}
            </ol>
        </div>
        <hr class="welcome-card-divider" aria-hidden="true">
        <div class="welcome-card-section">
            <div class="welcome-suggestions-header">
                <span class="welcome-suggestions-title">Suggested questions</span>
                <button type="button" id="shuffle-suggestions-btn" class="welcome-shuffle-btn"
                        aria-label="Shuffle suggested questions" title="Shuffle suggested questions">
                    <i class="fa-solid fa-shuffle" aria-hidden="true"></i>
                    <span>Shuffle</span>
                </button>
            </div>
            <div class="welcome-questions-stack" id="suggest-grid" role="list">
                ${pillsHtml}
            </div>
        </div>
    `;

    host.querySelectorAll('.welcome-question-pill').forEach((btn) => {
        btn.addEventListener('click', () => {
            const q = btn.getAttribute('data-suggested-question') || '';
            if (q && typeof window !== 'undefined' && typeof window.autoPrompt === 'function') {
                window.autoPrompt(q);
            }
        });
    });

    const shuffleBtn = host.querySelector('#shuffle-suggestions-btn');
    if (shuffleBtn) {
        shuffleBtn.addEventListener('click', () => {
            shuffleWelcomeSuggestions();
        });
    }
    return host;
}

async function shuffleWelcomeSuggestions() {
    _welcomeState.shuffleCount += 1;
    const shuffleBtn = typeof document !== 'undefined' ? document.getElementById('shuffle-suggestions-btn') : null;
    if (shuffleBtn) shuffleBtn.disabled = true;

    try {
        if (_welcomeState.loadedFromServer && typeof fetch === 'function') {
            const seed = Date.now() + _welcomeState.shuffleCount;
            const res = await fetch(`/api/chat/suggestions?seed=${seed}&count=${VISIBLE_SUGGESTION_COUNT}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (res.ok) {
                const payload = await res.json();
                applyCorpusProfileUi(payload);
                const norm = normalizeSuggestionsPayload(payload);
                _welcomeState.areas = norm.areas;
                _welcomeState.pool = norm.questions;
                const picked = pickShuffledQuestions(norm.questions, VISIBLE_SUGGESTION_COUNT, _welcomeState.shown);
                renderWelcomeSuggestionsCard(_welcomeState.areas, picked);
                return;
            }
        }
    } catch (_) {
        // Fall through to client-side shuffle
    } finally {
        if (shuffleBtn) shuffleBtn.disabled = false;
    }

    const picked = pickShuffledQuestions(_welcomeState.pool, VISIBLE_SUGGESTION_COUNT, _welcomeState.shown);
    renderWelcomeSuggestionsCard(_welcomeState.areas, picked);
}

async function loadWelcomeSuggestions() {
    if (typeof document === 'undefined') return;
    // Render immediate fallback so welcome screen is never blank while loading
    const initial = pickShuffledQuestions(_welcomeState.pool, VISIBLE_SUGGESTION_COUNT, []);
    renderWelcomeSuggestionsCard(_welcomeState.areas, initial);

    if (typeof fetch !== 'function') return;
    try {
        const res = await fetch('/api/chat/suggestions', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!res.ok) return;
        const payload = await res.json();
        _welcomeState.loadedFromServer = true;
        applyCorpusProfileUi(payload);
        const norm = normalizeSuggestionsPayload(payload);
        _welcomeState.areas = norm.areas;
        _welcomeState.pool = norm.questions;
        const picked = norm.questions.slice(0, VISIBLE_SUGGESTION_COUNT);
        renderWelcomeSuggestionsCard(_welcomeState.areas, picked);
    } catch (_) {
        // Graceful client fallback already rendered
    }
}

export {
    DEFAULT_KNOWLEDGE_AREAS,
    FALLBACK_SUGGESTED_QUESTIONS,
    VISIBLE_SUGGESTION_COUNT,
    applyCorpusProfileUi,
    isOpenAccessProfile,
    loadWelcomeSuggestions,
    normalizeSuggestionsPayload,
    pickShuffledQuestions,
    renderWelcomeSuggestionsCard,
    shuffleWelcomeSuggestions,
};
