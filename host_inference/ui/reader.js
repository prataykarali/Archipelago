    // Configure PDF.js Worker
    if (typeof pdfjsLib !== 'undefined') {
      pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }

    let pdfDoc = null;
    let pageNum = 1;
    let pageRendering = false;
    let pageNumPending = null;
    let scale = 1.35;
    let rawPdfUrl = '';
    let currentDocId = '';

    const canvas = document.getElementById('pdf-canvas');
    const ctx = canvas.getContext('2d');
    const pageNumInput = document.getElementById('page-num-input');
    const pageCountSpan = document.getElementById('page-count');
    const zoomLabel = document.getElementById('zoom-label');
    const loadingEl = document.getElementById('loading-spinner');
    const loadingText = document.getElementById('loading-text');
    const errorEl = document.getElementById('error-message');
    const errorDetail = document.getElementById('error-detail');
    const errorFallbackLink = document.getElementById('error-fallback-link');

    // Parse URL parameters and route
    function parseRouteParams() {
      const path = window.location.pathname;
      const urlParams = new URLSearchParams(window.location.search);
      const hash = window.location.hash;

      // Extract resource ID from /read/<id> or ?id= or ?src=
      let resourceId = '';
      if (path.includes('/read/')) {
        resourceId = path.split('/read/')[1].replace(/^\/+/, '');
        if (resourceId.startsWith('book/')) {
          resourceId = resourceId.substring(5);
        }
      }
      if (!resourceId) {
        resourceId = urlParams.get('doc') || urlParams.get('id') || urlParams.get('doc_id') || urlParams.get('src') || urlParams.get('book') || '';
      }

      // Extract target page from ?page=N or #page=N
      let targetPage = 1;
      const qPage = urlParams.get('page');
      if (qPage) {
        targetPage = parseInt(qPage, 10) || 1;
      } else if (hash && hash.includes('page=')) {
        const match = hash.match(/page=(\d+)/);
        if (match) targetPage = parseInt(match[1], 10) || 1;
      }

      return { resourceId: decodeURIComponent(resourceId), targetPage };
    }

    async function loadDocument() {
      const { resourceId, targetPage } = parseRouteParams();
      currentDocId = resourceId;
      pageNum = Math.max(1, targetPage);

      if (!resourceId) {
        showError("No document specified in the URL route.");
        return;
      }

      loadingText.textContent = `Resolving ${resourceId}...`;

      try {
        // Fetch document metadata from backend reader info route
        const infoResp = await fetch(`/api/reader/info/${encodeURIComponent(resourceId)}?page=${pageNum}`);
        let docInfo = {};
        if (infoResp.ok) {
          docInfo = await infoResp.json();
        }

        // If backend indicated this is Pearson, redirect to Pearson reader
        if (docInfo.provider === 'pearson' && docInfo.reader_url) {
          window.location.replace(docInfo.reader_url);
          return;
        }

        const title = docInfo.title || resourceId.split('/').pop().replace(/\.pdf$/i, '').replace(/_/g, ' ');
        const author = docInfo.author || (docInfo.provider === 'huggingface' ? 'Hugging Face Dataset: Prataykarali/Library_books' : 'Archipelago Library Holding');
        const badge = docInfo.provider === 'huggingface' ? 'HF Dataset' : (docInfo.provider === 'pearson' ? 'Pearson eLibrary' : 'Local PDF');

        document.getElementById('doc-title').textContent = title;
        document.title = `${title} — Archipelago Reader`;
        document.getElementById('doc-author').textContent = author;
        document.getElementById('doc-badge').textContent = badge;

        // Build streaming URL for the PDF
        rawPdfUrl = docInfo.pdf_url || `/papers/${encodeURIComponent(resourceId)}`;
        const anchorUrl = rawPdfUrl + (rawPdfUrl.includes('#') ? '' : `#page=${pageNum}`);
        document.getElementById('btn-raw-pdf').href = anchorUrl;
        errorFallbackLink.href = anchorUrl;

        loadingText.textContent = `Rendering page ${pageNum}...`;

        // Load the PDF via PDF.js
        const loadingTask = pdfjsLib.getDocument({
          url: rawPdfUrl,
          withCredentials: true,
          cMapUrl: 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/cmaps/',
          cMapPacked: true,
        });

        pdfDoc = await loadingTask.promise;
        pageCountSpan.textContent = pdfDoc.numPages;
        pageNumInput.max = pdfDoc.numPages;

        if (pageNum > pdfDoc.numPages) {
          pageNum = 1;
        }

        loadingEl.classList.add('hidden');
        canvas.classList.remove('hidden');

        renderPage(pageNum);
      } catch (err) {
        console.error("PDF loading error:", err);
        showError(err.message || "Failed to load PDF bytes from server.");
      }
    }

    function renderPage(num) {
      pageRendering = true;
      pageNumInput.value = num;

      // Update URL query & hash silently so reload retains exact page
      const url = new URL(window.location);
      url.searchParams.set('page', num);
      window.history.replaceState({}, '', url.toString());

      pdfDoc.getPage(num).then(function(page) {
        const viewport = page.getViewport({ scale: scale });
        const outputScale = window.devicePixelRatio || 1;

        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = Math.floor(viewport.width) + "px";
        canvas.style.height = Math.floor(viewport.height) + "px";

        const transform = outputScale !== 1
          ? [outputScale, 0, 0, outputScale, 0, 0]
          : null;

        const renderContext = {
          canvasContext: ctx,
          transform: transform,
          viewport: viewport
        };

        const renderTask = page.render(renderContext);

        renderTask.promise.then(function() {
          pageRendering = false;
          if (pageNumPending !== null) {
            renderPage(pageNumPending);
            pageNumPending = null;
          }
        });
      }).catch(function(err) {
        console.error("Page render error:", err);
        pageRendering = false;
      });

      // Update button states
      document.getElementById('btn-prev').disabled = (num <= 1);
      document.getElementById('btn-next').disabled = (pdfDoc && num >= pdfDoc.numPages);
    }

    function queueRenderPage(num) {
      if (pageRendering) {
        pageNumPending = num;
      } else {
        renderPage(num);
      }
    }

    function goToPrevPage() {
      if (pageNum <= 1) return;
      pageNum--;
      queueRenderPage(pageNum);
    }

    function goToNextPage() {
      if (!pdfDoc || pageNum >= pdfDoc.numPages) return;
      pageNum++;
      queueRenderPage(pageNum);
    }

    function handlePageInputChange(e) {
      const val = parseInt(e.target.value, 10);
      if (pdfDoc && val >= 1 && val <= pdfDoc.numPages) {
        pageNum = val;
        queueRenderPage(pageNum);
      } else {
        e.target.value = pageNum;
      }
    }

    function zoomIn() {
      scale = Math.min(3.0, scale + 0.15);
      updateZoomLabel();
      queueRenderPage(pageNum);
    }

    function zoomOut() {
      scale = Math.max(0.5, scale - 0.15);
      updateZoomLabel();
      queueRenderPage(pageNum);
    }

    function fitWidth() {
      if (!pdfDoc) return;
      const containerWidth = document.getElementById('viewer-container').clientWidth - 48;
      pdfDoc.getPage(pageNum).then(function(page) {
        const unscaledViewport = page.getViewport({ scale: 1.0 });
        scale = Math.max(0.6, containerWidth / unscaledViewport.width);
        updateZoomLabel();
        queueRenderPage(pageNum);
      });
    }

    function updateZoomLabel() {
      zoomLabel.textContent = `${Math.round(scale * 100)}%`;
    }

    function handleBack() {
      if (window.history.length > 1 && document.referrer && document.referrer.includes(window.location.host)) {
        window.history.back();
      } else {
        window.location.assign('/library');
      }
    }

    function showError(msg) {
      loadingEl.classList.add('hidden');
      canvas.classList.add('hidden');
      errorEl.classList.remove('hidden');
      errorDetail.textContent = msg;
    }

    // Keyboard navigation
    window.addEventListener('keydown', function(e) {
      if (e.target.tagName === 'INPUT') return;
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        goToPrevPage();
      } else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        e.preventDefault();
        goToNextPage();
      } else if (e.key === '+' || e.key === '=') {
        zoomIn();
      } else if (e.key === '-') {
        zoomOut();
      } else if (e.key === 'Home') {
        if (pdfDoc) { pageNum = 1; queueRenderPage(pageNum); }
      } else if (e.key === 'End') {
        if (pdfDoc) { pageNum = pdfDoc.numPages; queueRenderPage(pageNum); }
      }
    });

    // Start loading on DOM ready
    window.addEventListener('DOMContentLoaded', loadDocument);
