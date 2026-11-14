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
                // A source citation is not a physical holding. Build the physical
                // inventory table ONLY from records verified against the Koha export;
                // render cited PDFs and research papers in a compact Sources & Resources block.
                const citations = getResponseCitations(metadata) || [];
                const verifiedHoldings = citations.filter(c => Boolean(c && c.koha_record_verified)).slice(0, 8);
                const otherSources = citations.filter(c => !(c && c.koha_record_verified)).slice(0, 8);
                if (verifiedHoldings.length || otherSources.length) {
                    container = document.createElement('section');
                    container.className = 'library-inventory-section';
                    let html = '';
                    if (verifiedHoldings.length) {
                        html += `
                            <div class="library-inventory-header flex items-center justify-between gap-2 mb-2.5 pb-2 border-b border-sky-500/20">
                                <span class="text-xs font-bold uppercase tracking-wider text-sky-400 flex items-center gap-2">
                                    <i class="fa-solid fa-book-bookmark text-sky-400"></i> Library holdings
                                </span>
                                <span class="text-[11px] text-gray-400 bg-sky-950/40 px-2.5 py-0.5 rounded-full border border-sky-500/30 flex items-center gap-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Koha verified
                                </span>
                            </div>
                            <div class="inventory-table-wrap overflow-x-auto w-full mb-3">
                                <table class="w-full text-left text-xs">
                                    <thead>
                                        <tr class="border-b border-sky-500/30 text-sky-400">
                                            <th class="py-2 px-3">Book / Resource</th>
                                            <th class="py-2 px-3 whitespace-nowrap">Accession</th>
                                            <th class="py-2 px-3 text-right whitespace-nowrap">Copies</th>
                                            <th class="py-2 px-3 text-right whitespace-nowrap">Avail</th>
                                            <th class="py-2 px-3 text-center whitespace-nowrap">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${verifiedHoldings.map((c, i) => {
                                            const title = citationTitle(c, 'Resource');
                                            const pageNum = c.page_number || c.page;
                                            const badgeStr = c.evidence_id || `S${i+1}`;
                                            const pageUrl = citationPageUrl(c);
                                            return `
                                                <tr class="border-b border-white/10 hover:bg-white/5 transition-colors">
                                                    <td class="py-2.5 px-3 font-semibold text-gray-200">
                                                        <span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30 mr-1.5">${escapeHTML(badgeStr)}</span>
                                                        ${escapeHTML(title)}
                                                    </td>
                                                    <td class="py-2.5 px-3 font-mono text-[11px] text-sky-300 whitespace-nowrap">${escapeHTML(c.accession || '—')}</td>
                                                    <td class="py-2.5 px-3 text-right text-gray-400 whitespace-nowrap">${c.total_copies ?? '—'}</td>
                                                    <td class="py-2.5 px-3 text-right font-bold text-emerald-400 whitespace-nowrap">${c.available_copies ?? '—'}</td>
                                                    <td class="py-2.5 px-3 text-center whitespace-nowrap">
                                                        <a class="view-page-link inline-block whitespace-nowrap text-indigo-200 text-xs font-bold underline" href="${escapeHTML(pageUrl)}" target="_blank" rel="noopener noreferrer">${pageNum ? `Open page ${pageNum}` : 'Open source'}</a>
                                                    </td>
                                                </tr>
                                            `;
                                        }).join('')}
                                    </tbody>
                                </table>
                            </div>
                        `;
                    }
                    if (otherSources.length) {
                        const openAttr = otherSources.length <= 3 ? 'open' : '';
                        html += `
                            <details class="sources-resources-details rounded-xl border border-sky-500/20 bg-sky-950/20 px-3 py-2" ${openAttr}>
                                <summary class="cursor-pointer list-none flex items-center justify-between gap-2 text-xs font-bold uppercase tracking-wider text-sky-400 select-none">
                                    <span class="flex items-center gap-2">
                                        <i class="fa-solid fa-layer-group text-sky-400"></i> Sources &amp; Resources (${otherSources.length})
                                    </span>
                                    <span class="text-[11px] font-normal normal-case text-gray-400">${otherSources.length > 3 ? 'Click to expand' : 'Verified links'}</span>
                                </summary>
                                <div class="mt-2.5 space-y-1.5">
                                    ${otherSources.map((c, i) => {
                                        const title = citationTitle(c, 'Resource');
                                        const pageNum = c.page_number || c.page;
                                        const badgeStr = c.evidence_id || `S${i+1}`;
                                        const pageUrl = citationPageUrl(c);
                                        return `
                                            <div class="flex items-center justify-between gap-3 py-1.5 px-2.5 rounded-lg border border-white/10 bg-white/5 text-xs">
                                                <div class="min-w-0 font-semibold text-gray-200 truncate">
                                                    <span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30 mr-1.5">${escapeHTML(badgeStr)}</span>
                                                    ${escapeHTML(title)}
                                                </div>
                                                <a class="view-page-link shrink-0 whitespace-nowrap text-indigo-200 text-xs font-bold underline" href="${escapeHTML(pageUrl)}" target="_blank" rel="noopener noreferrer">${pageNum ? `Open page ${pageNum}` : 'Open source'}</a>
                                            </div>
                                        `;
                                    }).join('')}
                                </div>
                            </details>
                        `;
                    }
                    container.innerHTML = html;
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
