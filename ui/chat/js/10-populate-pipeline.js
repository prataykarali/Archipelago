// Auto-split from ui/chat/index.html — 10-populate-pipeline.js
// Feature module 11 of 22.
import { citationPageUrl } from './02--kw-highlights.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { autoPrompt } from './07-open-page-viewer-modal.js';

        // Populate Pipeline panel logs & citations
        function populatePipeline(data) {
            const citationsList = document.getElementById('citations-list');
            const citationsPlac = document.getElementById('citations-placeholder');
            const logsList = document.getElementById('logs-list');
            const logsPlac = document.getElementById('logs-placeholder');

            // 1. Citations
            if (data.citations && data.citations.length > 0) {
                citationsPlac.classList.add('hidden');
                citationsList.classList.remove('hidden');
                citationsList.innerHTML = '';
                
        data.citations.forEach(cit => {
            const docId = String(cit.doc_id || 'Unspecified source');
            const cleanDoc = docId.replace(/^.*[\\\/]/, '');
            const pageNum = cit.page_number || 1;
            const section = cit.section_title || '';
            const topic = cit.topic || '';
            const viewUrl = citationPageUrl(cit);
            const citationEl = document.createElement('a');
            citationEl.href = viewUrl || '#';
            citationEl.target = '_blank';
            citationEl.rel = 'noopener noreferrer';
            citationEl.className = "flex flex-col p-3 rounded-lg bg-white/5 border border-white/5 hover:glass-glow hover:scale-[1.02] text-left transition-all duration-300 group";
                    
                    if (window._newlyIngestedDocId && window._newlyIngestedDocId === cit.doc_id) {
                        citationEl.classList.add('new-evidence');
                    }
                    
                    const row = document.createElement('div'); row.className = 'flex items-center justify-between mb-1 gap-2';
                    
                    const nameWrapper = document.createElement('div');
                    nameWrapper.className = 'flex items-center truncate min-w-0';
                    nameWrapper.innerHTML = `<span class="mr-1.5 px-1.5 py-0.5 rounded bg-accentPink/20 text-accentPink font-mono text-[10px] font-bold">${cit.evidence_id || 'S?'}</span>`;
                    
                    const name = document.createElement('span'); name.className = 'text-[13px] font-bold text-gray-300 truncate max-w-[200px] group-hover:text-accentPink transition-colors'; name.textContent = cleanDoc;
                    nameWrapper.appendChild(name);
                    
                    const page = document.createElement('span'); page.className = 'px-2 py-0.5 rounded bg-accentPink/15 text-accentPink text-[10px] font-bold whitespace-nowrap';
                    page.textContent = cit.printed_page ? cit.printed_page : (cit.page_number ? `PDF page ${cit.page_number}` : 'Page not reported');
                    
                    const sectionEl = document.createElement('span'); sectionEl.className = 'text-xs text-gray-400 truncate'; sectionEl.textContent = cit.section_title || 'General Reference';
                    
                    row.append(nameWrapper, page); citationEl.append(row, sectionEl);
                    citationsList.appendChild(citationEl);
                });
            } else {
                citationsList.classList.add('hidden');
                citationsPlac.classList.remove('hidden');
            }

            // 2. Step logs
            if (data.logs && data.logs.length > 0) {
                logsPlac.classList.add('hidden');
                logsList.classList.remove('hidden');
                logsList.innerHTML = '';

                data.logs.forEach(log => {
                    const logEl = document.createElement('div');
                    logEl.className = "flex gap-2.5 p-3 rounded-lg bg-white/5 border border-white/5 relative overflow-hidden";
                    
                    const status = String(log.status || 'Unknown');
                    const isSuccess = status.toLowerCase().includes('success') || status.toLowerCase().includes('executed');
                    const dotClass = isSuccess ? 'bg-emerald-500' : 'bg-rose-500';
                    const dot = document.createElement('span'); dot.className = `w-1.5 h-1.5 rounded-full ${dotClass} mt-1.5 shrink-0`;
                    const content = document.createElement('div'); content.className = 'flex flex-col gap-1 w-full';
                    const row = document.createElement('div'); row.className = 'flex items-center justify-between gap-2';
                    const step = document.createElement('span'); step.className = 'text-[11px] font-bold text-gray-300'; step.textContent = log.step || 'Pipeline step';
                    const label = document.createElement('span'); label.className = 'text-[9px] font-semibold text-gray-400 uppercase tracking-widest'; label.textContent = status;
                    const details = document.createElement('p'); details.className = 'text-[11px] text-gray-400 leading-relaxed'; details.textContent = log.details || '';
                    row.append(step, label); content.append(row, details); logEl.append(dot, content);
                    logsList.appendChild(logEl);
                });
            } else {
                logsList.classList.add('hidden');
                logsPlac.classList.remove('hidden');
            }
        }

        // ── Neon concept graph (sidebar + bottom) + OKF inspector ──────────
        function _nodeLabel(n) {
            if (!n) return '';
            if (typeof n === 'string') return n;
            return n.label || n.name || n.id || '';
        }

        function _nodeId(n, fallback) {
            if (!n) return fallback || '';
            if (typeof n === 'string') return n;
            return String(n.id || n.name || n.label || fallback || '');
        }

        function _nodeSummary(n) {
            if (!n || typeof n === 'string') return '';
            return (n.summary || n.description || '').trim();
        }

        function selectGraphNode(nodeId, type) {
            const nb = window._graphNeighborhood || { anchor: null, prereqs: [], unlocks: [], related: [] };
            const anchor = nb.anchor;
            const prereqs = nb.prereqs || [];
            const unlocks = nb.unlocks || [];
            const related = nb.related || [];

            const findIn = (arr) => (arr || []).find(x => _nodeId(x) === String(nodeId) || _nodeLabel(x) === String(nodeId));

            let node = null;
            let nodeType = type || 'concept';
            if (anchor && (_nodeId(anchor) === String(nodeId) || _nodeLabel(anchor) === String(nodeId))) {
                node = anchor; nodeType = 'anchor';
            } else if ((node = findIn(prereqs))) {
                nodeType = 'prereq';
            } else if ((node = findIn(unlocks))) {
                nodeType = 'unlock';
            } else if ((node = findIn(related))) {
                nodeType = 'related';
            } else {
                node = { id: nodeId, name: nodeId, label: nodeId };
            }

            const typeLabels = {
                anchor: 'Target Concept',
                prereq: 'Prerequisite (Requires)',
                unlock: 'Unlocks (Enables)',
                related: 'Related Concept',
                concept: 'Concept Node'
            };
            const titleEl = document.getElementById('graph-node-title');
            const typeEl = document.getElementById('graph-node-type');
            const diffEl = document.getElementById('graph-node-diff');
            const sumEl = document.getElementById('graph-node-summary');
            if (typeEl) typeEl.textContent = typeLabels[nodeType] || 'Concept Node';
            if (diffEl) diffEl.textContent = (node && node.difficulty) || (nodeType === 'anchor' ? 'Focus' : nodeType.toUpperCase());
            if (titleEl) titleEl.textContent = _nodeLabel(node) || String(nodeId);
            let summary = _nodeSummary(node);
            if (!summary) {
                if (nodeType === 'prereq') summary = `Required before learning ${_nodeLabel(anchor) || 'the target concept'}.`;
                else if (nodeType === 'unlock') summary = `Unlocked after mastering ${_nodeLabel(anchor) || 'the target concept'}.`;
                else if (nodeType === 'related') summary = `Related to ${_nodeLabel(anchor) || 'the target concept'} in the knowledge graph.`;
                else summary = 'No summary available for this concept yet.';
            }
            if (sumEl) sumEl.textContent = summary;

            // OKF relationships relative to neighborhood
            const reqDiv = document.getElementById('okf-rel-requires');
            const unlDiv = document.getElementById('okf-rel-unlocks');
            const conDiv = document.getElementById('okf-rel-connects');

            const makeChip = (item, colorClass) => {
                const span = document.createElement('span');
                span.className = `px-2 py-1 rounded border cursor-pointer hover:bg-white/10 transition-colors text-[10px] font-bold ${colorClass}`;
                span.textContent = _nodeLabel(item);
                span.title = _nodeSummary(item) || _nodeLabel(item);
                span.onclick = () => selectGraphNode(_nodeId(item), null);
                return span;
            };
            const empty = () => { const s = document.createElement('span'); s.className = 'text-[10px] text-gray-500 italic'; s.textContent = 'None indexed'; return s; };

            if (reqDiv) {
                reqDiv.innerHTML = '';
                if (nodeType === 'anchor') {
                    if (prereqs.length) prereqs.forEach(p => reqDiv.appendChild(makeChip(p, 'text-accentPurple border-accentPurple/30 bg-accentPurple/10')));
                    else reqDiv.appendChild(empty());
                } else if (nodeType === 'unlock' && anchor) {
                    reqDiv.appendChild(makeChip(anchor, 'text-accentPurple border-accentPurple/30 bg-accentPurple/10'));
                } else if (nodeType === 'prereq') {
                    const note = document.createElement('span');
                    note.className = 'text-[10px] text-gray-400 italic';
                    note.textContent = `Required by ${_nodeLabel(anchor) || 'target'}`;
                    reqDiv.appendChild(note);
                } else {
                    reqDiv.appendChild(empty());
                }
            }
            if (unlDiv) {
                unlDiv.innerHTML = '';
                if (nodeType === 'anchor') {
                    if (unlocks.length) unlocks.forEach(u => unlDiv.appendChild(makeChip(u, 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10')));
                    else unlDiv.appendChild(empty());
                } else if (nodeType === 'prereq' && anchor) {
                    unlDiv.appendChild(makeChip(anchor, 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10'));
                } else {
                    unlDiv.appendChild(empty());
                }
            }
            if (conDiv) {
                conDiv.innerHTML = '';
                const peers = related.length ? related : [];
                if (peers.length) peers.forEach(r => conDiv.appendChild(makeChip(r, 'text-accentCyan border-accentCyan/30 bg-accentCyan/10')));
                else conDiv.appendChild(empty());
            }

            // Explore button under summary card
            let explore = document.getElementById('graph-explore-btn');
            const card = titleEl && titleEl.closest('.glass-glow, .p-3');
            if (!explore && card) {
                explore = document.createElement('button');
                explore.id = 'graph-explore-btn';
                explore.className = 'w-full mt-2 py-1.5 px-2 rounded-lg bg-accentPurple/20 border border-accentPurple/40 text-accentPurple font-bold text-[10px] hover:bg-accentPurple/30 transition-all flex items-center justify-center gap-1.5';
                card.appendChild(explore);
            }
            if (explore) {
                const label = _nodeLabel(node) || String(nodeId);
                explore.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i><span>Explore ${escapeHTML(label)}</span>`;
                explore.onclick = () => {
                    if (typeof autoPrompt === 'function') autoPrompt('Tell me about ' + label);
                    else {
                        const input = document.getElementById('chat-input');
                        if (input) { input.value = 'Tell me about ' + label; document.getElementById('send-btn')?.click(); }
                    }
                };
            }

            // Glow selected node on both SVGs and toggle badges visibility
            document.querySelectorAll('.graph-node-group').forEach(g => {
                const sel = g.getAttribute('data-node-id') === String(nodeId);
                g.classList.toggle('graph-node-selected', sel);
                const core = g.querySelector('circle.graph-node-core');
                if (core) {
                    core.setAttribute('stroke-width', sel ? '3.5' : (g.getAttribute('data-node-type') === 'anchor' ? '2' : '1.5'));
                }
                const ring = g.querySelector('circle.graph-select-ring');
                if (ring) ring.style.opacity = sel ? '1' : '0';

                const badge = g.querySelector('.graph-node-badge');
                if (badge) {
                    badge.style.opacity = (sel || g.getAttribute('data-node-type') === 'anchor') ? '1' : '0';
                }
            });
        }

        window.selectGraphNode = selectGraphNode;

        // ── Default Featured Graph (when no query anchor is active) ──────
        const DEFAULT_FEATURED_GRAPH = {
            anchor: {
                id: "rag",
                name: "Retrieval-Augmented Generation (RAG)",
                label: "RAG Synthesis",
                summary: "Combines dense vector retrieval over indexed domain knowledge with LLM synthesis to produce grounded, citation-backed answers.",
                difficulty: "Foundational"
            },
            prereqs: [
                { id: "vector_embeddings", name: "Vector Embeddings & Search", label: "Vector Embeddings", summary: "High-dimensional semantic representations used for k-NN similarity lookup." },
                { id: "dense_retrieval", name: "Dense Passage Retrieval (DPR)", label: "Dense Retrieval", summary: "Bi-encoder retrieval architecture for finding top-k relevant document chunks." }
            ],
            unlocks: [
                { id: "graph_rag", name: "GraphRAG & Subgraphs", label: "GraphRAG", summary: "Combines knowledge graph subgraphs and community summaries with RAG generation." },
                { id: "agentic_rag", name: "Agentic RAG & Routing", label: "Agentic RAG", summary: "Autonomous LLM agents using multi-hop query planning and tool execution." }
            ],
            related: [
                { id: "lora", name: "Low-Rank Adaptation (LoRA)", label: "LoRA PEFT", summary: "Efficient parameter fine-tuning by decomposing weight update matrices." },
                { id: "transformers", name: "Transformer Architecture", label: "Transformers", summary: "Self-attention encoder-decoder backbone powering modern LLMs." }
            ]
        };

export { DEFAULT_FEATURED_GRAPH, _nodeId, _nodeLabel, _nodeSummary, populatePipeline, selectGraphNode };
