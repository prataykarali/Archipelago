// Auto-split from ui/chat/index.html — 03-wrap-library-inventory-secti.js
// Feature module 4 of 22.
import { state } from './00-state.js';
import { citationPageUrl, citationTitle, getResponseCitations } from './02--kw-highlights.js';
import { escapeHTML } from './01--hide-welcome-with-transitio.js';
import { API_CONTRACT } from './00-current-origin.js';

        function wrapLibraryInventorySection(messageBody, metadata) {
            if (!messageBody) return;

            // 1. Identify any table already generated via markdown
            const tables = Array.from(messageBody.querySelectorAll('table'));
            let inventoryTable = null;
            for (const tbl of tables) {
                if (tbl.closest('.library-inventory-section')) {
                    inventoryTable = tbl;
                    break;
                }
                const text = (tbl.textContent || '').toLowerCase();
                const contextText = [tbl.previousElementSibling, tbl.previousElementSibling && tbl.previousElementSibling.previousElementSibling]
                    .filter(Boolean).map(el => (el.textContent || '').toLowerCase()).join(' ');
                if (contextText.includes('koha catalogue matches') && text.includes('copies')) {
                    inventoryTable = tbl;
                    break;
                }
            }

            // Find heading if present
            const headings = Array.from(messageBody.querySelectorAll('h3, h4'));
            let holdingsHeading = null;
            for (const h of headings) {
                if (/Koha catalogue matches/i.test(h.textContent)) {
                    holdingsHeading = h;
                    break;
                }
            }

            let container = messageBody.querySelector('.library-inventory-section');

            if (inventoryTable && !container) {
                container = document.createElement('section');
                container.className = 'library-inventory-section';

                const prevDisclaimer = holdingsHeading && holdingsHeading.nextElementSibling && holdingsHeading.nextElementSibling.tagName === 'P' ? holdingsHeading.nextElementSibling : null;
                
                const insertBeforeTarget = holdingsHeading || inventoryTable;
                if (insertBeforeTarget && insertBeforeTarget.parentNode) {
                    insertBeforeTarget.parentNode.insertBefore(container, insertBeforeTarget);
                } else {
                    messageBody.appendChild(container);
                }

                container.innerHTML = `
                    <div class="library-inventory-header flex items-center justify-between gap-2 mb-2.5 pb-2 border-b border-sky-500/20">
                        <span class="text-xs font-bold uppercase tracking-wider text-sky-400 flex items-center gap-2">
                            <i class="fa-solid fa-book-bookmark text-sky-400"></i> Koha Catalogue Matches
                        </span>
                        <span class="text-[11px] text-gray-400 bg-sky-950/40 px-2.5 py-0.5 rounded-full border border-sky-500/30 flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full bg-sky-400"></span> Export snapshot
                        </span>
                    </div>
                `;

                if (holdingsHeading) container.appendChild(holdingsHeading);
                if (prevDisclaimer) container.appendChild(prevDisclaimer);
                
                const scrollWrap = document.createElement('div');
                scrollWrap.className = 'inventory-table-wrap overflow-x-auto w-full';
                scrollWrap.appendChild(inventoryTable);
                container.appendChild(scrollWrap);
            } else if (!inventoryTable && !container && metadata) {
                // Synthesize inventory table from metadata citations/books if not present in markdown prose
                const citations = getResponseCitations(metadata);
                const sourceRows = (citations || []).slice(0, 6);
                if (sourceRows.length) {
                    container = document.createElement('section');
                    container.className = 'library-inventory-section';
                    container.innerHTML = `
                        <div class="library-inventory-header flex items-center justify-between gap-2 mb-2.5 pb-2 border-b border-sky-500/20">
                            <span class="text-xs font-bold uppercase tracking-wider text-sky-400 flex items-center gap-2">
                            <i class="fa-solid fa-book-bookmark text-sky-400"></i> Source inventory
                            </span>
                            <span class="text-[11px] text-gray-400 bg-sky-950/40 px-2.5 py-0.5 rounded-full border border-sky-500/30 flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full bg-sky-400"></span> Cited sources
                        </span>
                    </div>
                        <h4 class="text-xs text-gray-400 mb-2 font-medium italic">Copy counts appear only for titles verified in the Koha export.</h4>
                    `;
                    const scrollWrap = document.createElement('div');
                    scrollWrap.className = 'inventory-table-wrap overflow-x-auto w-full';
                    const tbl = document.createElement('table');
                    tbl.className = 'w-full text-left text-xs';
                    tbl.innerHTML = `
                        <thead>
                            <tr class="border-b border-sky-500/30 text-sky-400">
                                <th class="py-2 px-3">Book / Resource</th>
                                <th class="py-2 px-3">Accession</th>
                                <th class="py-2 px-3 text-right">Copies</th>
                                <th class="py-2 px-3 text-right">Avail</th>
                                <th class="py-2 px-3 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${sourceRows.map((c, i) => {
                                const title = citationTitle(c, 'Resource');
                                const accession = c.accession || '—';
                                const total = c.koha_record_verified ? c.total_copies : '—';
                                const avail = c.koha_record_verified ? c.available_copies : '—';
                                const pageNum = Math.max(1, Math.floor(Number(c.page_number || c.page) || 1));
                                const badgeStr = c.evidence_id || `S${i+1}`;
                                const route = citationPageUrl(c);
                                const action = route && route.startsWith('/')
                                    ? `<a href="${escapeHTML(route)}" target="_blank" rel="noopener noreferrer" class="text-amber-200 underline underline-offset-2 hover:text-amber-100">Open page ${pageNum}</a>`
                                    : `Page ${pageNum}`;
                                return `
                                    <tr class="glass-card hover:border-sky-400/50 hover:scale-[1.01] transition-all duration-200 border border-white/10 rounded-xl my-1.5 p-3 flex flex-col md:table-row gap-2">
                                        <td class="py-2.5 px-3 font-semibold text-gray-200">
                                            <span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30 mr-1.5">${escapeHTML(badgeStr)}</span>
                                            ${escapeHTML(title)}
                                        </td>
                                        <td class="py-2.5 px-3 font-mono text-[11px] text-sky-300">${escapeHTML(accession)}</td>
                                        <td class="py-2.5 px-3 text-right text-gray-400">${total}</td>
                                        <td class="py-2.5 px-3 text-right font-bold text-emerald-400">${avail}</td>
                                        <td class="py-2.5 px-3 text-center">
                                            <span class="text-indigo-200 text-xs font-bold">${action}</span>
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody></table>

                    `;
                    scrollWrap.appendChild(tbl);
                    container.appendChild(scrollWrap);
                    const zone = messageBody.querySelector('[id^="interactive-zone-"]');
                    if (zone) {
                        messageBody.insertBefore(container, zone);
                    } else {
                        messageBody.appendChild(container);
                    }
                }
            }

            // If a quiz is active on this message card, ensure container is hidden
            const matchMsg = messageBody.id && messageBody.id.match(/^msg-body-(.+)$/);
            if (matchMsg && matchMsg[1] && container) {
                const id = matchMsg[1];
                const state = window._adaptiveState && window._adaptiveState[id];
                if (state && state.current_mcq && !state.completed) {
                    container.classList.add('hidden');
                }
            }
            const evidenceRail = messageBody.querySelector('.evidence-rail');
            if (container && evidenceRail && container.parentNode === evidenceRail.parentNode) {
                container.parentNode.insertBefore(evidenceRail, container);
            }
        }

        window.wrapLibraryInventorySection = wrapLibraryInventorySection;

        function renderCurriculumPaths(paths) {
            // Learning roadmaps are available only when explicitly requested;
            // ordinary answers should stay focused on the question and graph.
            return '';
        }

        function setChatAvailability(available, reason) {
            // Student chat is never locked for upload jobs (students cannot upload).
            const input = document.getElementById('chat-input');
            const send = document.getElementById('send-btn');
            const note = document.getElementById('chat-availability');
            if (input) {
                input.disabled = false;
                input.classList.remove('opacity-40');
                input.placeholder = 'Ask AIML, books, library hours, e-resources…';
            }
            if (send) {
                send.disabled = state.isGenerating;
                send.classList.toggle('opacity-40', state.isGenerating);
            }
            if (note) {
                note.textContent = reason || 'Student mode: query only. Librarians manage PDFs in the Graph UI.';
                note.className = 'max-w-3xl mx-auto mt-2 text-[11px] text-gray-500';
            }
        }

        // Auto-resize textarea
        const textarea = document.getElementById('chat-input');

        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
            if (this.scrollHeight > 150) {
                this.style.overflowY = 'scroll';
                this.style.height = '150px';
            } else {
                this.style.overflowY = 'hidden';
            }
        });

        // Connection Check
        async function checkConnection() {
            const statusContainer = document.getElementById('connection-status');
            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');
            try {
                const response = await fetch(API_CONTRACT.health);
                if (response.ok) {
                    if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-md shadow-emerald-500/50";
                    if (statusText) statusText.textContent = "Online";
                    if (statusContainer) {
                        statusContainer.className = "flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/5 border border-emerald-500/30 text-xs status-glow-online transition-all duration-300";
                    }
                } else {
                    throw new Error('readiness not ok');
                }
            } catch (e) {
                if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-rose-500 shadow-md shadow-rose-500/50 animate-pulse";
                if (statusText) statusText.textContent = "Offline (Inference Server)";
                if (statusContainer) {
                    statusContainer.className = "flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/5 border border-rose-500/30 text-xs status-glow-offline transition-all duration-300";
                }
            }
        }

        setInterval(checkConnection, 10000);

        checkConnection();

        // No upload capability checks — student chat never calls /api/ingest.

        // Toggle Left / Right panels — accordion slider: opening one closes the other
        function isPanelOpen(el) {
            return el && !el.classList.contains('panel-closed');
        }

        function setPanelOpen(panel, open) {
            if (!panel) return;
            panel.classList.toggle('panel-closed', !open);
            panel.setAttribute('aria-hidden', open ? 'false' : 'true');
        }

        function syncPanelToggleUI() {
            const leftOpen = isPanelOpen(document.getElementById('left-sidebar'));
            const rightOpen = isPanelOpen(document.getElementById('pipeline-panel'));
            const leftBtn = document.getElementById('toggle-left-sidebar-btn');
            const rightBtn = document.getElementById('toggle-pipeline-btn');
            const edgeLeft = document.getElementById('edge-toggle-left');
            const edgeRight = document.getElementById('edge-toggle-right');
            const leftIcon = document.getElementById('edge-toggle-left-icon');
            const rightIcon = document.getElementById('edge-toggle-right-icon');

            if (leftBtn) {
                leftBtn.classList.toggle('bg-amber-400/30', leftOpen);
                leftBtn.classList.toggle('text-amber-200', leftOpen);
                leftBtn.classList.toggle('border-amber-400/60', leftOpen);
            }
            if (rightBtn) {
                rightBtn.classList.toggle('bg-accentPurple/40', rightOpen);
                rightBtn.classList.toggle('text-white', rightOpen);
                rightBtn.classList.toggle('border-accentPurple/60', rightOpen);
            }
            if (edgeLeft) {
                edgeLeft.classList.toggle('is-active', leftOpen);
                edgeLeft.title = leftOpen ? 'Close library menu' : 'Open library menu';
            }
            if (edgeRight) {
                edgeRight.classList.toggle('is-active', rightOpen);
                edgeRight.title = rightOpen ? 'Close pipeline' : 'Open pipeline';
            }
            if (leftIcon) leftIcon.className = `fa-solid ${leftOpen ? 'fa-chevron-left' : 'fa-chevron-right'} text-sm`;
            if (rightIcon) rightIcon.className = `fa-solid ${rightOpen ? 'fa-chevron-right' : 'fa-chevron-left'} text-sm`;
        }

        function toggleLeftSidebar() {
            const leftSidebar = document.getElementById('left-sidebar');
            const pipelinePanel = document.getElementById('pipeline-panel');
            if (!leftSidebar) return;
            const willOpen = !isPanelOpen(leftSidebar);
            if (willOpen) setPanelOpen(pipelinePanel, false); // slide: close right
            setPanelOpen(leftSidebar, willOpen);
            syncPanelToggleUI();
        }

        function togglePipeline() {
            const leftSidebar = document.getElementById('left-sidebar');
            const pipelinePanel = document.getElementById('pipeline-panel');
            if (!pipelinePanel) return;
            const willOpen = !isPanelOpen(pipelinePanel);
            if (willOpen) setPanelOpen(leftSidebar, false); // slide: close left
            setPanelOpen(pipelinePanel, willOpen);
            syncPanelToggleUI();
        }

        function closeAllSidePanels() {
            setPanelOpen(document.getElementById('left-sidebar'), false);
            setPanelOpen(document.getElementById('pipeline-panel'), false);
            syncPanelToggleUI();
        }

        window.toggleLeftSidebar = toggleLeftSidebar;

        window.togglePipeline = togglePipeline;

        window.closeAllSidePanels = closeAllSidePanels;

        window.setPanelOpen = setPanelOpen;

        window.syncPanelToggleUI = syncPanelToggleUI;

        // Left starts open; right starts closed
        syncPanelToggleUI();

export { checkConnection, closeAllSidePanels, isPanelOpen, renderCurriculumPaths, setChatAvailability, setPanelOpen, syncPanelToggleUI, textarea, toggleLeftSidebar, togglePipeline, wrapLibraryInventorySection };
