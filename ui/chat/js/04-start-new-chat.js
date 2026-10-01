// Auto-split from ui/chat/index.html — 04-start-new-chat.js
// Feature module 5 of 22.
import { state } from './00-state.js';
import { API_HOST, buildAvatarClipsHtml, hideStickyAvatar, wireAvatarVideos } from './00-current-origin.js';
import { _updateGlowState } from './01--hide-welcome-with-transitio.js';
import { setPanelOpen, syncPanelToggleUI } from './03-wrap-library-inventory-secti.js';
import { populateTopology } from './11-populate-topology.js';
import { renderChatHistory } from './20--compact-history.js';
import { displayBooks } from './05-display-books.js';

// New Chat — reset conversation and welcome screen (hero video stays mounted)
function startNewChat() {
    if (state.conversationSessionId) {
        fetch(API_HOST + '/api/context-status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.conversationSessionId, action: 'reset' })
        }).catch(err => console.warn('Failed to reset server session context:', err));
    }
    state.chatHistory = [];
    state.conversationSessionId = null;
    state.isGenerating = false;
    try { window.isGenerating = false; } catch (_) {}
    if (typeof _updateGlowState === 'function') _updateGlowState(false);

    // Hide sticky librarian; welcome screen owns the only avatar again
    if (typeof hideStickyAvatar === 'function') hideStickyAvatar();

    // Ensure hero keeps playing after reset
    const heroVid = document.getElementById('hero-video');
    if (heroVid) {
        try {
            heroVid.muted = true;
            heroVid.loop = true;
            if (heroVid.paused) {
                const p = heroVid.play();
                if (p && p.catch) p.catch(() => {});
            }
        } catch (_) {}
    }

    const chatMsgs = document.getElementById('chat-messages');
    chatMsgs.innerHTML = '';

    // Chromatic waves are stage-level — keep them; only drop legacy ripples
    const oldRipple = document.getElementById('line-ripple-bg');
    if (oldRipple) oldRipple.remove();

    const welcome = document.createElement('div');
    welcome.id = 'welcome-container';
    welcome.className = 'w-full max-w-4xl mx-auto flex flex-col items-center justify-center text-center py-3 md:py-5 gap-4';
    welcome.removeAttribute('aria-hidden');
    welcome.dataset.exiting = '0';
    welcome.innerHTML = `
        <!-- Avatar (5-clip story loop: hi → think → type → goit → success) -->
        <div class="avatar-shell welcome-avatar" id="welcome-avatar" data-avatar>
            ${buildAvatarClipsHtml('hi')}
        </div>
        <!-- ShineText + TypewriterText -->
        <div>
            <h2 class="welcome-title shine-text font-extrabold tracking-tight">Welcome to Archipelago</h2>
            <p id="welcome-subtitle" class="typewriter-cursor mt-2.5 mx-auto leading-relaxed"></p>
        </div>
        <!-- Suggestion cards — DepthParallaxWords + Hover-3D -->
            <button onclick="autoPrompt('What is Low-Rank Adaptation (LoRA)?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-accentPurple/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/brain_btn2.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Brain"><span class="depth-word-target">What is Low-Rank Adaptation (LoRA)?</span></button>
            <button onclick="autoPrompt('Explain the main components of retrieval augmented generation (RAG)')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-accentPink/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/search_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Search"><span class="depth-word-target">Explain the main components of RAG</span></button>
            <button onclick="autoPrompt('What are the prerequisites for BERT model training?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-accentCyan/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/network_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Network"><span class="depth-word-target">What are the prerequisites for BERT?</span></button>
            <button onclick="autoPrompt('How does the Attention mechanism handle sequence alignment?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-purple-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/brain_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Attention"><span class="depth-word-target">How does the Attention mechanism work?</span></button>
            <button onclick="autoPrompt('How do DBMS buffer pools optimize query retrieval in Silberschatz?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-amber-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/book_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Book"><span class="depth-word-target">DBMS buffer pools in Silberschatz</span></button>
            <button onclick="autoPrompt('Explain virtual memory paging vs segmentation in OSTEP.')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-emerald-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/note_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Note"><span class="depth-word-target">Virtual memory paging vs segmentation</span></button>
            <button onclick="autoPrompt('How does GraphRAG combine graph databases with RAG synthesis?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-indigo-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/graph_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Graph"><span class="depth-word-target">GraphRAG: graph + RAG synthesis</span></button>
            <button onclick="autoPrompt('Rank the most critical PEFT and RAG papers in the corpus by contribution.')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-rose-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/flash_card_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Flashcard"><span class="depth-word-target">Rank top PEFT &amp; RAG papers</span></button>
<button onclick="autoPrompt('What are the library hours and weekend issue rules?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-emerald-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/library_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Hours"><span class="depth-word-target">Library hours &amp; weekend rules</span></button><button onclick="autoPrompt('What e-resource portals does the central library provide?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-sky-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/search_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="E-resources"><span class="depth-word-target">E-resource portals (IEEE, Pearson…)</span></button><button onclick="autoPrompt('How do I access Pearson eLibrary textbooks?')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-amber-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/book_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Pearson"><span class="depth-word-target">Pearson eLibrary — read from library</span></button><button onclick="autoPrompt('Suggest books on operating systems')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-rose-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/note_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Books"><span class="depth-word-target">Suggest books on operating systems</span></button>            <button onclick="autoPrompt('RAG + DBMS')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-fuchsia-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/library_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Library"><span class="depth-word-target">Multi-topic: RAG + DBMS</span></button>
            <button onclick="autoPrompt('LoRA vs BERT')" class="hover-3d-card p-4 rounded-xl bg-white/5 border border-white/10 hover:border-sky-400/40 hover:bg-white/10 text-xs text-gray-300 font-medium transition-all duration-200 flex items-start gap-3 group"><img src="/ui/assets/settings_btn.png" class="w-10 h-10 object-contain group-hover:scale-110 transition-transform flex-shrink-0" alt="Compare"><span class="depth-word-target">Compare LoRA vs BERT</span></button>
        </div>
    `;
    chatMsgs.appendChild(welcome);

    // Re-init welcome-only premium components (hero/switchboard stay mounted)
    (function reinitPremiumWelcome() {
        // Welcome character — loop constantly
        const wa = document.getElementById('welcome-avatar');
        if (wa) wireAvatarVideos(wa, false);

        // Typewriter (looping)
        if (typeof window.startWelcomeTypewriter === 'function') {
            window.startWelcomeTypewriter(document.getElementById('welcome-subtitle'));
        }
        // Depth words
        const red = window.matchMedia('(prefers-reduced-motion:reduce)').matches;
        document.querySelectorAll('#welcome-container .depth-word-target').forEach((span, ci) => {
            const words = span.textContent.trim().split(' ');
            span.innerHTML = '';
            words.forEach((w, wi) => {
                const s = document.createElement('span');
                s.className = 'depth-word';
                s.textContent = w;
                if (red) s.classList.add('visible');
                else s.style.transitionDelay = `${ci * 45 + wi * 55}ms`;
                span.appendChild(s);
                if (wi < words.length - 1) span.appendChild(document.createTextNode(' '));
            });
        });
        if (!red) setTimeout(() => {
            document.querySelectorAll('#welcome-container .depth-word').forEach(w => w.classList.add('visible'));
        }, 150);
        // Hover 3d (suggestion cards only — never on chat message text)
        document.querySelectorAll('#welcome-container .hover-3d-card').forEach(card => {
            card.addEventListener('mousemove', e => {
                const r = card.getBoundingClientRect();
                const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
                const dx = (e.clientX - cx) / (r.width / 2), dy = (e.clientY - cy) / (r.height / 2);
                card.style.transform = `perspective(800px) rotateY(${dx * 8}deg) rotateX(${-dy * 6}deg) scale(1.03)`;
                card.style.transition = 'transform 0.08s ease-out';
            });
            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
                card.style.transition = 'transform 0.35s cubic-bezier(0.22,1,0.36,1)';
            });
        });
        // Ensure full-stage Chromatic Waves still running after reset
        if (typeof window._remountChromaticWaves === 'function') {
            window._remountChromaticWaves();
        } else if (typeof window.mountChromaticWavesOnChat === 'function') {
            window.mountChromaticWavesOnChat();
        }
    })();

    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) { sendBtn.disabled = false; sendBtn.classList.remove('opacity-50'); }
    const input = document.getElementById('chat-input');
    if (input) { input.disabled = false; input.classList.remove('opacity-40'); input.placeholder = 'Ask AIML, books, library hours, e-resources…'; input.value = ''; input.style.height = 'auto'; input.style.overflowY = 'hidden'; }
    window._lastChatMetadata = null;
    const citationsPlac = document.getElementById('citations-placeholder');
    const citationsList = document.getElementById('citations-list');
    const logsPlac = document.getElementById('logs-placeholder');
    const logsList = document.getElementById('logs-list');
    if (citationsPlac) { citationsPlac.classList.remove('hidden'); citationsPlac.textContent = 'No citations retrieved yet.'; }
    if (citationsList) { citationsList.classList.add('hidden'); citationsList.innerHTML = ''; }
    if (logsPlac) { logsPlac.classList.remove('hidden'); logsPlac.textContent = 'No logs captured yet.'; }
    if (logsList) { logsList.classList.add('hidden'); logsList.innerHTML = ''; }
    
    const topologyView = document.getElementById('topology-view');
    const topologyPlaceholder = document.getElementById('topology-placeholder');
    if (topologyView) topologyView.classList.add('hidden');
    if (topologyPlaceholder) topologyPlaceholder.classList.remove('hidden');

    // Keep left panel open; close right so chat isn't squeezed
    if (typeof setPanelOpen === 'function') {
        setPanelOpen(document.getElementById('left-sidebar'), true);
        setPanelOpen(document.getElementById('pipeline-panel'), false);
        if (typeof syncPanelToggleUI === 'function') syncPanelToggleUI();
    } else {
        const left = document.getElementById('left-sidebar');
        const right = document.getElementById('pipeline-panel');
        if (left) left.classList.remove('panel-closed');
        if (right) {
            right.style.transform = '';
            right.classList.add('panel-closed');
        }
    }
    const welcomeAvatar = document.getElementById('welcome-avatar');
    if (welcomeAvatar && typeof wireAvatarVideos === 'function') {
        // Fresh DOM node after New Chat — wire alternating hi ↔ think loop
        delete welcomeAvatar.dataset.avatarWired;
        wireAvatarVideos(welcomeAvatar, false);
    }
    if (typeof hideStickyAvatar === 'function') hideStickyAvatar();
    const bottomMap = document.getElementById('bottom-svg-map-container');
    if (bottomMap) {
        bottomMap.classList.add('hidden');
        bottomMap.classList.remove('is-visible', 'flex');
    }
    if (typeof populateTopology === 'function') populateTopology(null, null, null, null, true);
    if (typeof renderChatHistory === 'function') renderChatHistory();
}

window._graphNeighborhood = state._graphNeighborhood;

const DOM_SECTIONS = [
    { key: 'dbms', label: 'DBMS & Data Systems', btn: '/ui/assets/book_btn.png', color: 'text-amber-400 border-amber-400/30 bg-amber-400/10' },
    { key: 'os', label: 'Operating Systems (OSTEP)', btn: '/ui/assets/note_btn.png', color: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10' },
    { key: 'dl', label: 'Deep Learning & LLMs', btn: '/ui/assets/brain_btn2.png', color: 'text-cyan-300 border-cyan-400/30 bg-cyan-400/10' },
    { key: 'math', label: 'Mathematics & Algorithms', btn: '/ui/assets/settings_btn.png', color: 'text-purple-300 border-purple-400/30 bg-purple-400/10' },
    { key: 'peft', label: 'Fine-Tuning, RAG & Agents', btn: '/ui/assets/flash_card_btn.png', color: 'text-pink-400 border-pink-400/30 bg-pink-400/10' },
    { key: 'gnn', label: 'Graph Neural Nets & GenAI', btn: '/ui/assets/graph_btn.png', color: 'text-indigo-400 border-indigo-400/30 bg-indigo-400/10' },
    { key: 'syllabi', label: 'Syllabi & Course Notes', btn: '/ui/assets/note_btn2.png', color: 'text-yellow-300 border-yellow-400/30 bg-yellow-400/10' }
];

const CATALOG_55 = [
    // 🗄️ DBMS & Data Systems
    { id: 'database_system_concepts_silberschatz', title: 'Database System Concepts', authors: 'Silberschatz, Korth, Sudarshan', year: 2020, cat: 'textbook', dom: 'dbms', topics: ['DBMS', 'Relational Algebra', 'ACID'] },
    { id: 'database_management_systems_ramakrishnan', title: 'Database Management Systems', authors: 'Ramakrishnan, Gehrke', year: 2003, cat: 'textbook', dom: 'dbms', topics: ['BCNF', '3NF', 'Buffer Pool'] },
    { id: 'papers/Edge2024_GraphRAG.pdf', title: 'From Local to Global: A Graph RAG Approach to Summarization', authors: 'Edge et al.', year: 2024, cat: 'paper', dom: 'peft', pdf: 'papers/Edge2024_GraphRAG.pdf', topics: ['GraphRAG', 'Leiden Summaries'] },

    // ⚙️ Operating Systems (OSTEP & Silberschatz)
    { id: 'operating_system_concepts_silberschatz', title: 'Operating System Concepts (Dinosaur Book)', authors: 'Silberschatz, Galvin, Gagne', year: 2018, cat: 'textbook', dom: 'os', topics: ['OS Concepts', 'Virtual Memory'] },
    { id: 'ostep_three_easy_pieces/00_Dialogue.pdf', title: 'OSTEP: Dialogue', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/00_Dialogue.pdf', topics: ['OS Intro'] },
    { id: 'ostep_three_easy_pieces/01_Introduction.pdf', title: 'OSTEP: Introduction to Operating Systems', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/01_Introduction.pdf', topics: ['Virtualization', 'Concurrency'] },
    { id: 'ostep_three_easy_pieces/02_CPU_Virtualization.pdf', title: 'OSTEP: CPU Virtualization', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/02_CPU_Virtualization.pdf', topics: ['CPU Virtualization', 'Processes'] },
    { id: 'ostep_three_easy_pieces/03_Process_API.pdf', title: 'OSTEP: Process API (fork/exec/wait)', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/03_Process_API.pdf', topics: ['Process API', 'System Calls'] },
    { id: 'ostep_three_easy_pieces/04_Limited_Direct_Execution.pdf', title: 'OSTEP: Limited Direct Execution', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/04_Limited_Direct_Execution.pdf', topics: ['LDE', 'Traps', 'Context Switch'] },
    { id: 'ostep_three_easy_pieces/05_CPU_Scheduling.pdf', title: 'OSTEP: CPU Scheduling Policies', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/05_CPU_Scheduling.pdf', topics: ['MLFQ', 'SJF', 'RR'] },
    { id: 'ostep_three_easy_pieces/06_Address_Spaces.pdf', title: 'OSTEP: Address Spaces', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/06_Address_Spaces.pdf', topics: ['Address Space', 'Stack/Heap'] },
    { id: 'ostep_three_easy_pieces/07_Address_Translation.pdf', title: 'OSTEP: Address Translation', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/07_Address_Translation.pdf', topics: ['Address Translation', 'Base/Bounds'] },
    { id: 'ostep_three_easy_pieces/08_Paging.pdf', title: 'OSTEP: Paging & Virtual Memory', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/08_Paging.pdf', topics: ['Paging', 'Page Tables'] },
    { id: 'ostep_three_easy_pieces/09_TLBs.pdf', title: 'OSTEP: Translation Lookaside Buffers (TLB)', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/09_TLBs.pdf', topics: ['TLB', 'Page Translation'] },
    { id: 'ostep_three_easy_pieces/10_Concurrency_Intro.pdf', title: 'OSTEP: Concurrency & Threads Intro', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/10_Concurrency_Intro.pdf', topics: ['Threads', 'Race Conditions'] },
    { id: 'ostep_three_easy_pieces/11_Locks.pdf', title: 'OSTEP: Locks & Synchronization', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/11_Locks.pdf', topics: ['Locks', 'Mutex', 'Spinlocks'] },
    { id: 'ostep_three_easy_pieces/12_Semaphores.pdf', title: 'OSTEP: Semaphores & Condition Vars', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/12_Semaphores.pdf', topics: ['Semaphores', 'Producer-Consumer'] },
    { id: 'ostep_three_easy_pieces/13_Common_Bugs.pdf', title: 'OSTEP: Common Concurrency Bugs', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/13_Common_Bugs.pdf', topics: ['Deadlock', 'Atomicity Bugs'] },
    { id: 'ostep_three_easy_pieces/14_IO_Devices.pdf', title: 'OSTEP: Hard Disks & I/O Devices', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/14_IO_Devices.pdf', topics: ['I/O Devices', 'DMA', 'Disks'] },
    { id: 'ostep_three_easy_pieces/15_RAID.pdf', title: 'OSTEP: RAID Systems', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/15_RAID.pdf', topics: ['RAID 0/1/5', 'Disk Redundancy'] },
    { id: 'ostep_three_easy_pieces/16_Log_Structured_FS.pdf', title: 'OSTEP: Log-Structured File System', authors: 'Arpaci-Dusseau', year: 2018, cat: 'textbook', dom: 'os', pdf: 'ostep_three_easy_pieces/16_Log_Structured_FS.pdf', topics: ['LFS', 'File Systems'] },

    // 🤖 Deep Learning & Transformers
    { id: 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf', title: 'Attention Is All You Need', authors: 'Vaswani et al.', year: 2017, cat: 'paper', dom: 'dl', pdf: 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf', topics: ['Transformer', 'Self-Attention'] },
    { id: 'papers/Devlin2018_BERT.pdf', title: 'BERT: Pre-training of Deep Bidirectional Transformers', authors: 'Devlin et al.', year: 2018, cat: 'paper', dom: 'dl', pdf: 'papers/Devlin2018_BERT.pdf', topics: ['BERT', 'Bidirectional', 'MLM'] },
    { id: 'papers/Brown2020_GPT3.pdf', title: 'Language Models are Few-Shot Learners', authors: 'Brown et al.', year: 2020, cat: 'paper', dom: 'dl', pdf: 'papers/Brown2020_GPT3.pdf', topics: ['GPT-3', 'Few-Shot'] },
    { id: 'papers/Rumelhart1986_Backpropagation.pdf', title: 'Learning Representations by Back-Propagating Errors', authors: 'Rumelhart, Hinton, Williams', year: 1986, cat: 'paper', dom: 'dl', pdf: 'papers/Rumelhart1986_Backpropagation.pdf', topics: ['Backpropagation', 'MLP'] },
    { id: 'papers/LeCun1998_ConvNets.pdf', title: 'Gradient-Based Learning Applied to Document Recognition', authors: 'LeCun et al.', year: 1998, cat: 'paper', dom: 'dl', pdf: 'papers/LeCun1998_ConvNets.pdf', topics: ['ConvNets', 'LeNet'] },
    { id: 'papers/Hochreiter1997_LSTM.pdf', title: 'Long Short-Term Memory', authors: 'Hochreiter, Schmidhuber', year: 1997, cat: 'paper', dom: 'dl', pdf: 'papers/Hochreiter1997_LSTM.pdf', topics: ['LSTM', 'RNN'] },
    { id: 'papers/Krizhevsky2012_AlexNet.pdf', title: 'ImageNet Classification with Deep Convolutional Neural Networks', authors: 'Krizhevsky et al.', year: 2012, cat: 'paper', dom: 'dl', pdf: 'papers/Krizhevsky2012_AlexNet.pdf', topics: ['AlexNet', 'CNN'] },
    { id: 'papers/Bahdanau2014_Attention.pdf', title: 'Neural Machine Translation by Jointly Learning to Align and Translate', authors: 'Bahdanau et al.', year: 2014, cat: 'paper', dom: 'dl', pdf: 'papers/Bahdanau2014_Attention.pdf', topics: ['Attention', 'Seq2Seq'] },

    // 🧮 Mathematics & Algorithms
    { id: 'textbooks/Deisenroth_Math_For_ML.pdf', title: 'Mathematics for Machine Learning', authors: 'Deisenroth, Faisal, Ong', year: 2020, cat: 'textbook', dom: 'math', pdf: 'textbooks/Deisenroth_Math_For_ML.pdf', topics: ['Linear Algebra', 'Calculus', 'Optim'] },
    { id: 'introduction_to_algorithms_clrs', title: 'Introduction to Algorithms (CLRS)', authors: 'Cormen, Leiserson, Rivest, Stein', year: 2022, cat: 'textbook', dom: 'math', topics: ['Algorithms', 'Dynamic Prog', 'Graphs'] },
    { id: 'data_structures_algorithm_analysis_weiss', title: 'Data Structures and Algorithm Analysis', authors: 'Mark Allen Weiss', year: 2014, cat: 'textbook', dom: 'math', topics: ['Data Structures', 'Heaps', 'Trees'] },
    { id: 'pattern_recognition_2009', title: 'Pattern Recognition & Machine Learning', authors: 'Bishop et al.', year: 2009, cat: 'textbook', dom: 'math', pdf: 'archipelago-books-cs/pattern_recognition_2009/Chapter-1---Introduction_2009_Pattern-Recognition.pdf', topics: ['Pattern Rec', 'Bayesian ML'] },
    { id: 'predictive_analytics_and_data_mining_2015', title: 'Predictive Analytics & Data Mining', authors: 'Kuhn et al.', year: 2015, cat: 'textbook', dom: 'math', pdf: 'archipelago-books-cs/predictive_analytics_and_data_mining_2015/Chapter-1---Introduction_2015_Predictive-Analytics-and-Data-Mining.pdf', topics: ['Data Mining', 'Classification'] },
    { id: 'data_science_2019', title: 'Data Science & Analytics Principles', authors: 'Kelleher et al.', year: 2019, cat: 'textbook', dom: 'math', pdf: 'archipelago-books-cs/data_science_2019/Chapter-1---Introduction_2019_Data-Science.pdf', topics: ['Data Science', 'Clustering'] },

    // ⚡ Fine-Tuning, RAG & Agents
    { id: 'papers/Hu2021_LoRA.pdf', title: 'LoRA: Low-Rank Adaptation of Large Language Models', authors: 'Hu et al.', year: 2021, cat: 'paper', dom: 'peft', pdf: 'papers/Hu2021_LoRA.pdf', topics: ['LoRA', 'PEFT'] },
    { id: 'papers/Dettmers2023_QLoRA.pdf', title: 'QLoRA: Efficient Finetuning of Quantized LLMs', authors: 'Dettmers et al.', year: 2023, cat: 'paper', dom: 'peft', pdf: 'papers/Dettmers2023_QLoRA.pdf', topics: ['QLoRA', 'NF4 Quantization'] },
    { id: 'papers/Lewis2020_RAG.pdf', title: 'Retrieval-Augmented Generation for Knowledge-Intensive Tasks', authors: 'Lewis et al.', year: 2020, cat: 'paper', dom: 'peft', pdf: 'papers/Lewis2020_RAG.pdf', topics: ['RAG', 'Dense Retrieval'] },
    { id: 'papers/Karpukhin2020_DPR.pdf', title: 'Dense Passage Retrieval for Open-Domain Question Answering', authors: 'Karpukhin et al.', year: 2020, cat: 'paper', dom: 'peft', pdf: 'papers/Karpukhin2020_DPR.pdf', topics: ['DPR', 'Bi-Encoder'] },
    { id: 'papers/Wei2022_ChainOfThought.pdf', title: 'Chain-of-Thought Prompting Elicits Reasoning in LLMs', authors: 'Wei et al.', year: 2022, cat: 'paper', dom: 'peft', pdf: 'papers/Wei2022_ChainOfThought.pdf', topics: ['Chain-of-Thought', 'Reasoning'] },
    { id: 'papers/Yao2022_ReAct.pdf', title: 'ReAct: Synergizing Reasoning and Acting in Language Models', authors: 'Yao et al.', year: 2022, cat: 'paper', dom: 'peft', pdf: 'papers/Yao2022_ReAct.pdf', topics: ['ReAct', 'Agents'] },
    { id: 'papers/Willard2023_Outlines.pdf', title: 'Efficient Guided Generation for Large Language Models', authors: 'Willard, Louf', year: 2023, cat: 'paper', dom: 'peft', pdf: 'papers/Willard2023_Outlines.pdf', topics: ['Guided Generation', 'FSM'] },
    { id: 'papers/Kwon2023_vLLM.pdf', title: 'Efficient Memory Management for LLM Serving with PagedAttention', authors: 'Kwon et al.', year: 2023, cat: 'paper', dom: 'peft', pdf: 'papers/Kwon2023_vLLM.pdf', topics: ['vLLM', 'PagedAttention'] },
    { id: 'papers/Ouyang2022_InstructGPT.pdf', title: 'Training Language Models to Follow Instructions with Human Feedback', authors: 'Ouyang et al.', year: 2022, cat: 'paper', dom: 'peft', pdf: 'papers/Ouyang2022_InstructGPT.pdf', topics: ['InstructGPT', 'RLHF'] },
    { id: 'papers/Rafailov2023_DPO.pdf', title: 'Direct Preference Optimization', authors: 'Rafailov et al.', year: 2023, cat: 'paper', dom: 'peft', pdf: 'papers/Rafailov2023_DPO.pdf', topics: ['DPO', 'Direct Fine-Tuning'] },
    { id: 'papers/Bai2022_ConstitutionalAI.pdf', title: 'Constitutional AI: Harmlessness from AI Feedback', authors: 'Bai et al.', year: 2022, cat: 'paper', dom: 'peft', pdf: 'papers/Bai2022_ConstitutionalAI.pdf', topics: ['Constitutional AI', 'RLAIF'] },

    // 🕸️ Graph Neural Nets & Generative Models
    { id: 'papers/Kipf2016_GCN.pdf', title: 'Semi-Supervised Classification with Graph Convolutional Networks', authors: 'Kipf, Welling', year: 2016, cat: 'paper', dom: 'gnn', pdf: 'papers/Kipf2016_GCN.pdf', topics: ['GCN', 'Graph Neural Nets'] },
    { id: 'papers/Velickovic2017_GAT.pdf', title: 'Graph Attention Networks', authors: 'Veličković et al.', year: 2017, cat: 'paper', dom: 'gnn', pdf: 'papers/Velickovic2017_GAT.pdf', topics: ['GAT', 'Graph Attention'] },
    { id: 'papers/Goodfellow2014_GAN.pdf', title: 'Generative Adversarial Nets', authors: 'Goodfellow et al.', year: 2014, cat: 'paper', dom: 'gnn', pdf: 'papers/Goodfellow2014_GAN.pdf', topics: ['GAN', 'Minimax'] },
    { id: 'papers/Kingma2013_VAE.pdf', title: 'Auto-Encoding Variational Bayes', authors: 'Kingma, Welling', year: 2013, cat: 'paper', dom: 'gnn', pdf: 'papers/Kingma2013_VAE.pdf', topics: ['VAE', 'Reparameterization'] },
    { id: 'papers/Ho2020_DDPM.pdf', title: 'Denoising Diffusion Probabilistic Models', authors: 'Ho, Jain, Abbeel', year: 2020, cat: 'paper', dom: 'gnn', pdf: 'papers/Ho2020_DDPM.pdf', topics: ['Diffusion', 'DDPM'] },
    { id: 'knowledge_representation_and_reasoning_2004', title: 'Knowledge Representation and Reasoning', authors: 'Brachman, Levesque', year: 2004, cat: 'textbook', dom: 'gnn', pdf: 'archipelago-books-cs/knowledge_representation_and_reasoning_2004/Chapter-1---Introduction_2004_Knowledge-Representation-and-Reasoning.pdf', topics: ['Knowledge Graphs', 'Ontologies'] },

    // 📋 Syllabi & Course Notes
    { id: 'AI_ML_Archipelago_Corpus_Seed.md', title: 'AI/ML Archipelago Corpus Seed Syllabus', authors: 'Archipelago Team', year: 2025, cat: 'syllabus', dom: 'syllabi', pdf: 'web_syllabi/AI_ML_Archipelago_Corpus_Seed.md', topics: ['Syllabus', 'Curriculum'] },
    { id: 'synthetic_concept_x_lora.pdf', title: 'Synthetic Concept X & LoRA Lab Notes', authors: 'Archipelago Lab', year: 2026, cat: 'syllabus', dom: 'syllabi', pdf: 'synthetic_concept_x_lora.pdf', topics: ['LoRA Lab', 'Notes'] },
    { id: 'artificial_intelligence_a_new_synthesis_1998', title: 'Artificial Intelligence: A New Synthesis', authors: 'Nils J. Nilsson', year: 1998, cat: 'textbook', dom: 'syllabi', pdf: 'archipelago-books-cs/artificial_intelligence_a_new_synthesis_1998/1---Introduction_1998_Artificial-Intelligence--A-New-Synthesis.pdf', topics: ['AI Search', 'Planning', 'Logic'] }
];

function getDocCollection(doc) {
    if (!doc) return 'open_source';
    if (doc.collection === 'library_pearson' || doc.tier === 'pearson' || doc.source_tier === 'pearson') return 'library_pearson';
    if (doc.collection === 'open_source' || doc.tier === 'open_source') return 'open_source';

    const id = (doc.id || '').toLowerCase();
    const pdf = (doc.pdf || '').toLowerCase();
    const title = (doc.title || '').toLowerCase();
    const authors = (doc.authors || '').toLowerCase();

    if (id.startsWith('textbooks/') || pdf.startsWith('textbooks/') || pdf.includes('archipelago-books-cs/')) {
        return 'library_pearson';
    }
    const libraryKeywords = [
        'pearson', 'silberschatz', 'ramakrishnan', 'deisenroth', 'cormen', 'clrs', 'weiss',
        'bishop', 'pattern_recognition', 'predictive_analytics', 'data_science',
        'knowledge_representation', 'artificial_intelligence_a_new_synthesis',
        'database_system_concepts', 'database_management_systems', 'operating_system_concepts'
    ];
    for (let i = 0; i < libraryKeywords.length; i++) {
        const kw = libraryKeywords[i];
        if (id.includes(kw) || pdf.includes(kw) || title.includes(kw) || authors.includes(kw)) {
            return 'library_pearson';
        }
    }
    return 'open_source';
}

function getCategory(docId) {
    for (let i = 0; i < CATALOG_55.length; i++) {
        if (CATALOG_55[i].id === docId || CATALOG_55[i].pdf === docId) return CATALOG_55[i].dom;
    }
    const lower = (docId || '').toLowerCase();
    if (lower.indexOf('dbms') !== -1 || lower.indexOf('database') !== -1) return 'dbms';
    if (lower.indexOf('ostep') !== -1 || lower.indexOf('operating') !== -1) return 'os';
    if (lower.indexOf('math') !== -1 || lower.indexOf('algorithm') !== -1) return 'math';
    if (lower.indexOf('lora') !== -1 || lower.indexOf('rag') !== -1 || lower.indexOf('peft') !== -1) return 'peft';
    if (lower.indexOf('graph') !== -1 || lower.indexOf('gan') !== -1 || lower.indexOf('vae') !== -1) return 'gnn';
    if (lower.indexOf('syllabus') !== -1 || lower.indexOf('notes') !== -1) return 'syllabi';
    return 'dl';
}

function setupFilterButtons() {
    const booksFilter = document.getElementById('books-filter');
    if (booksFilter) {
        const newFilter = booksFilter.cloneNode(true);
        booksFilter.parentNode.replaceChild(newFilter, booksFilter);
        newFilter.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            const f = btn.getAttribute('data-filter') || 'all';
            state.currentFilter = f;
            newFilter.querySelectorAll('button').forEach(b => {
                const active = b.getAttribute('data-filter') === f;
                b.className = active 
                    ? 'px-2.5 py-1 rounded bg-accentPurple/30 text-accentPurple border border-accentPurple/35 transition-all'
                    : 'px-2.5 py-1 rounded bg-white/5 text-gray-400 hover:text-gray-200 transition-all';
            });
            displayBooks();
        });
    }

    const typeFilter = document.getElementById('type-filter');
    if (typeFilter) {
        const newTypeFilter = typeFilter.cloneNode(true);
        typeFilter.parentNode.replaceChild(newTypeFilter, typeFilter);
        newTypeFilter.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            const f = btn.getAttribute('data-type-filter') || 'all';
            state.currentTypeFilter = f;
            newTypeFilter.querySelectorAll('button').forEach(b => {
                const active = b.getAttribute('data-type-filter') === f;
                b.className = active 
                    ? 'flex-1 px-2.5 py-1 rounded bg-accentCyan/30 text-accentCyan border border-accentCyan/35 transition-all'
                    : 'flex-1 px-2.5 py-1 rounded bg-white/5 text-gray-400 hover:text-gray-200 transition-all';
            });
            displayBooks();
        });
    }
}

export { CATALOG_55, DOM_SECTIONS, getCategory, getDocCollection, setupFilterButtons, startNewChat };
