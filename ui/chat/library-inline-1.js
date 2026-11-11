    if (window.lucide) lucide.createIcons();

    // Authenticate user session as student, faculty, librarian, or admin
    window.archipelagoAuthReady?.then(async ({ config, supabase }) => {
      if (config && config.required) {
        const session = await window.archipelagoRequireSession();
        if (!session) return;
      }
      if (window.archipelagoMountNavigation) {
        window.archipelagoMountNavigation();
      }
    });

    let allEbooks = [];
    let filteredEbooks = [];
    let currentBookIndex = 0;

    let holdingsData = [];
    let journalsData = [];
    let subjCountsData = [];
    let subjTitlesData = [];

    function openPearsonModal(book) {
      document.getElementById('pearson-modal').classList.remove('hidden');
      const directBtn = document.getElementById('modal-pearson-direct-btn');
      directBtn.onclick = () => {
        const bookId = book && (book.id || book.pearson_book_id || book.isbn);
        const page = Math.max(1, Number(book?.page || book?.page_number || 1));
        if (bookId) window.open(`/open/${encodeURIComponent(bookId)}?page=${page}`, '_blank', 'noopener,noreferrer');
        else window.open('https://elibrary.in.pearson.com/', '_blank', 'noopener,noreferrer');
      };
    }

    function closePearsonModal() {
      document.getElementById('pearson-modal').classList.add('hidden');
    }

    function openPearsonLoginPortal() {
      window.open('https://elibrary.in.pearson.com/', '_blank', 'noopener,noreferrer');
    }

    function showPearsonAccessHelp() {
      if (typeof showToast === 'function') {
        showToast('Use your authorized institutional Pearson account in the portal.');
      }
    }

    function handleBookAction(book) {
      if (!book) return;
      if (book.isCatalogOnly) {
        const search = document.getElementById('holdings-search-input');
        if (search) {
          search.value = book.title || '';
          search.dispatchEvent(new Event('input'));
        }
        document.getElementById('holdings')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      const isPearson = !!(book.isPearson || book.subscription_id || (book.pearsonUrl && book.pearsonUrl.includes('pearson.com')));
      if (isPearson) {
        showPearsonAccessHelp();
        const bookId = book.id || book.pearson_book_id || book.isbn || '';
        const page = Math.max(1, Number(book.page || book.page_number || 1));
        window.open(`/open/${encodeURIComponent(bookId)}?page=${page}`, '_blank', 'noopener,noreferrer');
      } else {
        const bookId = book.id || book.pdf || book.title || '';
        const page = Math.max(1, Number(book.page || book.page_number || 1));
        const readerUrl = `/read?doc=${encodeURIComponent(bookId)}&page=${page}`;
        window.open(readerUrl, '_blank', 'noopener,noreferrer');
      }
    }

    function openChapterPage(bookId, page, isPearson) {
      const n = Math.max(1, Number(page) || 1);
      const target = isPearson
        ? `/open/${encodeURIComponent(bookId)}?page=${n}`
        : `/read?doc=${encodeURIComponent(bookId)}&page=${n}`;
      window.open(target, '_blank', 'noopener,noreferrer');
    }



    function close3DView() {
      if (window.LibraryShowcase3D) {
        window.LibraryShowcase3D.closeBook();
      }
    }

    function renderBookDetails(index, isOpen = false) {
      if (!filteredEbooks || filteredEbooks.length === 0) return;
      const b = filteredEbooks[index];
      document.getElementById('book-title').innerText = b.title;
      document.getElementById('book-author').innerText = b.author || b.authors || 'Unknown';
      document.getElementById('book-desc').innerText = b.desc || 'Pearson / Institutional textbook holding.';
      document.getElementById('book-counter').innerText = `Book ${index + 1} of ${filteredEbooks.length}`;
      document.getElementById('book-domain-badge').innerText = b.domain || 'Computer Science';
      document.getElementById('book-isbn-txt').innerText = `ISBN: ${b.isbn || 'N/A'}`;

      const openBadge = document.getElementById('open-state-badge');
      const closeBtn = document.getElementById('close-3d-btn');

      if (isOpen) {
        openBadge.innerText = '📖 3D Cover Swung Open';
        openBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 font-bold';
        closeBtn.classList.remove('hidden');
      } else {
        openBadge.innerText = '3D Interactive Shelf';
        openBadge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-blue-500/20 text-blue-300';
        closeBtn.classList.add('hidden');
      }

      const badge = document.getElementById('book-type-badge');
      const actionBtn = document.getElementById('book-action-btn');
      const actionText = document.getElementById('book-action-text');
      const credsBtn = document.getElementById('copy-creds-btn');

      if (b.isCatalogOnly) {
        badge.innerText = 'Catalog Holding';
        badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-slate-500/20 text-slate-300 font-bold';
        badge.onclick = null;
        actionText.innerText = 'View Holding Details ↓';
        actionBtn.className = 'w-full py-2.5 px-4 rounded-lg bg-slate-700 text-white font-semibold text-xs hover:bg-slate-600 transition-colors flex items-center justify-center gap-2 shadow-lg cursor-pointer';
        if (credsBtn) credsBtn.classList.add('hidden');
      } else if (b.isPearson) {
        badge.innerText = 'Pearson eBook';
        badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/20 text-amber-300 font-bold cursor-pointer hover:bg-amber-500/30';
        badge.onclick = () => openPearsonModal(b);
        actionText.innerText = 'Open Pearson Reader ↗';
        actionBtn.className = 'w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-amber-400 to-amber-300 text-black font-extrabold text-xs hover:from-amber-300 hover:to-amber-200 transition-colors flex items-center justify-center gap-2 shadow-lg cursor-pointer';
        if (credsBtn) {
          credsBtn.classList.remove('hidden');
          credsBtn.innerText = '🔑 Pearson Sign In & Reader';
          credsBtn.onclick = () => openPearsonModal(b);
        }
      } else if (b.isPaper) {
        badge.innerText = 'Research Paper';
        badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/20 text-purple-300 font-bold';
        badge.onclick = null;
        actionText.innerText = 'Read Research Paper ↗';
        actionBtn.className = 'w-full py-2.5 px-4 rounded-lg bg-white text-black font-bold text-xs hover:bg-white/90 transition-colors flex items-center justify-center gap-2 shadow-lg cursor-pointer';
        if (credsBtn) credsBtn.classList.add('hidden');
      } else {
        badge.innerText = 'Textbook PDF';
        badge.className = 'px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-300 font-bold';
        badge.onclick = null;
        actionText.innerText = 'Open PDF Reader ↗';
        actionBtn.className = 'w-full py-2.5 px-4 rounded-lg bg-white text-black font-semibold text-xs hover:bg-white/90 transition-colors flex items-center justify-center gap-2 shadow-lg cursor-pointer';
        if (credsBtn) credsBtn.classList.add('hidden');
      }

      actionBtn.onclick = () => handleBookAction(b);


      const tocContainer = document.getElementById('book-toc-list');
      const tocItems = b.toc || [
        { title: 'Chapter 1: Overview & Theoretical Foundations', page: 1 },
        { title: 'Chapter 2: Methods & Analytical Formulation', page: 45 },
        { title: 'Chapter 3: Experimental Evaluation', page: 92 },
        { title: 'Chapter 4: Synthesis & Conclusions', page: 148 }
      ];
      tocContainer.innerHTML = tocItems.map(c => `
        <div onclick="openChapterPage('${encodeURIComponent(b.id || b.pdf || '')}', ${c.page}, ${b.isPearson ? 'true' : 'false'})" class="flex items-center justify-between p-2 rounded bg-white/5 border border-white/5 hover:border-purple-500/30 hover:bg-white/10 transition-colors text-xs text-white/80 cursor-pointer group" title="Open Chapter (Page ${c.page})">
          <span class="font-medium truncate pr-2 group-hover:text-purple-300 transition-colors">${c.title}</span>
          <span class="font-mono text-purple-400/80 text-[10px] shrink-0 font-semibold">p. ${c.page} ↗</span>
        </div>
      `).join('');
    }

    document.getElementById('book-prev-btn').onclick = () => {
      if (filteredEbooks.length === 0) return;
      currentBookIndex = (currentBookIndex - 1 + filteredEbooks.length) % filteredEbooks.length;
      if (window.LibraryShowcase3D) window.LibraryShowcase3D.selectBookIndex(currentBookIndex);
    };

    document.getElementById('book-next-btn').onclick = () => {
      if (filteredEbooks.length === 0) return;
      currentBookIndex = (currentBookIndex + 1) % filteredEbooks.length;
      if (window.LibraryShowcase3D) window.LibraryShowcase3D.selectBookIndex(currentBookIndex);
    };

    document.getElementById('ebook-search-input').oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        filteredEbooks = [...allEbooks];
      } else {
        filteredEbooks = allEbooks.filter(b =>
          (b.title && b.title.toLowerCase().includes(q)) ||
          (b.author && b.author.toLowerCase().includes(q)) ||
          (b.domain && b.domain.toLowerCase().includes(q))
        );
      }
      currentBookIndex = 0;
      if (window.LibraryShowcase3D) window.LibraryShowcase3D.setBooks(filteredEbooks);
      renderBookDetails(0, false);
    };

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') close3DView();
    });

    // Holdings Table Render & Search
    function renderHoldingsTable(items) {
      const tbody = document.getElementById('holdings-table-body');
      if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-white/40">No matching holdings records found.</td></tr>`;
        return;
      }
      tbody.innerHTML = items.map((h, i) => `
        <tr class="hover:bg-white/5 transition-colors">
          <td class="p-3.5 font-medium text-white max-w-xs truncate">${i + 1}. ${h.title}</td>
          <td class="p-3.5 text-white/70">${h.authors || h.author || 'Unknown'}</td>
          <td class="p-3.5 text-white/60">${h.publisher || 'Unknown'}</td>
          <td class="p-3.5 font-mono text-blue-300 text-[11px]">${h.accession || 'N/A'}</td>
          <td class="p-3.5 text-right font-bold ${h.available_copies > 0 ? 'text-emerald-400' : 'text-rose-400'}">${h.available_ratio || `${h.available_copies} / ${h.no_of_copies}`}</td>
        </tr>
      `).join('');
    }

    document.getElementById('holdings-search-input').oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = holdingsData.filter(h =>
        (h.title && h.title.toLowerCase().includes(q)) ||
        (h.author && h.author.toLowerCase().includes(q)) ||
        (h.publisher && h.publisher.toLowerCase().includes(q)) ||
        (h.accession && h.accession.toLowerCase().includes(q))
      );
      renderHoldingsTable(filtered);
    };

    // Supplementary Datasets Tabs
    function switchTab(tabKey) {
      ['journals', 'subj-counts', 'subj-titles'].forEach(k => {
        const btn = document.getElementById(`tab-btn-${k}`);
        const content = document.getElementById(`tab-content-${k}`);
        if (k === tabKey) {
          btn.className = 'px-3 py-1.5 rounded text-xs font-mono bg-blue-600 text-white font-semibold';
          content.classList.remove('hidden');
        } else {
          btn.className = 'px-3 py-1.5 rounded text-xs font-mono bg-white/10 text-white/70 hover:bg-white/20';
          content.classList.add('hidden');
        }
      });
    }

    function renderJournals(items) {
      const tbody = document.getElementById('journals-table-body');
      tbody.innerHTML = items.slice(0, 200).map(j => `
        <tr class="hover:bg-white/5 transition-colors">
          <td class="p-3 text-white font-medium">${j.title}</td>
          <td class="p-3 text-white/70">${j.vol}</td>
          <td class="p-3 text-white/50">${j.date || '—'}</td>
          <td class="p-3 text-right">
            <span class="px-2 py-0.5 rounded text-[10px] font-mono ${j.status === 'Arrived' ? 'bg-emerald-500/20 text-emerald-300' : j.status === 'Late' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300'}">${j.status || 'Expected'}</span>
          </td>
        </tr>
      `).join('');
    }

    document.getElementById('journals-search').oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = journalsData.filter(j => j.title.toLowerCase().includes(q) || j.vol.toLowerCase().includes(q));
      renderJournals(filtered);
    };

    function renderSubjCounts(items) {
      const container = document.getElementById('subj-summary-cards');
      container.innerHTML = items.slice(0, 120).map(sc => `
        <div class="p-3 rounded-lg bg-black/40 border border-white/10">
          <div class="text-xs text-white/80 font-medium truncate">${sc.subject}</div>
          <div class="text-lg font-black text-purple-400 mt-1">${sc.total_titles}</div>
        </div>
      `).join('');
    }

    document.getElementById('subj-summary-search').oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      renderSubjCounts(subjCountsData.filter(sc => sc.subject.toLowerCase().includes(q)));
    };

    function renderSubjTitles(items) {
      const tbody = document.getElementById('subj-detail-table-body');
      tbody.innerHTML = items.slice(0, 200).map(st => `
        <tr class="hover:bg-white/5 transition-colors">
          <td class="p-3 text-amber-300/80 font-mono text-[11px]">${st.subject}</td>
          <td class="p-3 text-white font-medium">${st.title}</td>
          <td class="p-3 text-white/60">${st.author || '—'}</td>
          <td class="p-3 text-right text-white/50">${st.year || '—'}</td>
        </tr>
      `).join('');
    }

    document.getElementById('subj-detail-search').oninput = (e) => {
      const q = e.target.value.toLowerCase().trim();
      renderSubjTitles(subjTitlesData.filter(st => st.title.toLowerCase().includes(q) || st.subject.toLowerCase().includes(q) || st.author.toLowerCase().includes(q)));
    };

    // Hydrate Page Data from API
    async function loadData() {
      try {
        const res = await fetch('/api/library/data');
        const d = await res.json();

        if (d.ebook_shelf && d.ebook_shelf.length > 0) {
          allEbooks = d.ebook_shelf;
        } else {
          allEbooks = [
            { id: '1', title: 'Artificial Intelligence: A New Synthesis', author: 'Nils J. Nilsson', year: '1998', primaryColor: '#2563eb', accentColor: '#93c5fd', domain: 'AI & ML', desc: 'Foundational text on agent architectures and state space search.' },
            { id: '2', title: 'Attention Is All You Need', author: 'Vaswani et al.', year: '2017', primaryColor: '#7c3aed', accentColor: '#c4b5fd', domain: 'Transformers', desc: 'Introduces self-attention mechanism for deep sequence models.' }
          ];
        }

        filteredEbooks = [...allEbooks];
        if (d.ebook_stats) {
          document.getElementById('ebook-stats-pill').innerText = d.ebook_stats;
        }

        // Init 3D Showcase Engine
        if (window.LibraryShowcase3D) {
          window.LibraryShowcase3D.init('library-3d-shelf', filteredEbooks, (book, idx, total, isOpen) => {
            currentBookIndex = idx;
            renderBookDetails(idx, isOpen);
          });
        }

        renderBookDetails(0, false);

        // Auto-open book and page from URL parameters (?book=...&pdf=...&page=...)
        const urlParams = new URLSearchParams(window.location.search);
        const targetBookKey = urlParams.get('book') || '';
        const targetPdf = urlParams.get('pdf') || '';
        const targetPage = parseInt(urlParams.get('page') || '1', 10);

        if ((targetBookKey || targetPdf) && filteredEbooks.length > 0) {
          const searchKey = (targetPdf || targetBookKey).toLowerCase().replace(/\.pdf$/i, '');
          const matchIdx = filteredEbooks.findIndex(b => {
            const bId = (b.id || '').toLowerCase();
            const bPdf = (b.pdfUrl || b.pdf || '').toLowerCase();
            const bTitle = (b.title || '').toLowerCase();
            return bId.includes(searchKey) || bPdf.includes(searchKey) || bTitle.includes(searchKey);
          });
          if (matchIdx >= 0) {
            currentBookIndex = matchIdx;
            if (window.LibraryShowcase3D) window.LibraryShowcase3D.openBook(matchIdx);
            renderBookDetails(matchIdx, true);
            const matchedBook = filteredEbooks[matchIdx];
            if (!matchedBook.isPearson && targetPdf) {
              let pdfSrc = targetPdf.startsWith('/') || targetPdf.startsWith('http') ? targetPdf : `/pdfs/${encodeURIComponent(targetPdf)}`;
              if (!pdfSrc.includes('#page=')) pdfSrc += `#page=${targetPage}`;
              document.getElementById('pdf-modal-title').innerText = `${matchedBook.title} — p.${targetPage}`;
              document.getElementById('pdf-iframe').src = pdfSrc;
              document.getElementById('pdf-modal').classList.remove('hidden');
            }
          }
        }

        // Holdings
        if (d.holdings && d.holdings.length > 0) {
          holdingsData = d.holdings;
        } else {
          holdingsData = [];
        }
        document.getElementById('holdings-source-label').textContent = d.holdings_status === 'sample'
          ? 'Sample spreadsheet values for preview only. These are not live holdings.'
          : 'Inventory values from the latest library import.';

        if (d.holdings_stats) {
          document.getElementById('stat-records-num').innerText = d.holdings_stats.total_records ?? '—';
          document.getElementById('stat-copies-num').innerText = d.holdings_stats.total_copies ?? '—';
          document.getElementById('stat-avail-num').innerText = d.holdings_stats.available_copies ?? '—';
        }

        renderHoldingsTable(holdingsData);

        // Supplementary
        if (d.journal_issues) {
          journalsData = d.journal_issues;
          renderJournals(journalsData);
        }
        if (d.subject_counts) {
          subjCountsData = d.subject_counts;
          renderSubjCounts(subjCountsData);
        }
        if (d.subject_titles) {
          subjTitlesData = d.subject_titles;
          renderSubjTitles(subjTitlesData);
        }

      } catch (err) {
        console.error('Failed to load library data payload:', err);
      }
    }

    window.addEventListener('DOMContentLoaded', loadData);
