    let targetReaderUrl = "";
    let targetPage = 1;
    let countdownInterval = null;
    let hasAttemptedLogin = false;

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => { t.classList.remove('show'); }, 3000);
    }

    function startLoginAutomation() {
      hasAttemptedLogin = true;
      sessionStorage.setItem('pearson_auto_launch_pending', '1');

      // Open Pearson login portal
      const ssoUrl = `https://admin.elibrary.in.pearson.com/sso/login?service=${encodeURIComponent('https://ebooks.elibrary.in.pearson.com/wr/index.html')}&eulogin=true`;
      window.open(ssoUrl, '_blank', 'noopener,noreferrer');

      // Show automation status banner with countdown
      const statusEl = document.getElementById('automation-status');
      statusEl.style.display = 'block';

      let seconds = 6;
      const countEl = document.getElementById('countdown-text');
      clearInterval(countdownInterval);
      countdownInterval = setInterval(() => {
        seconds--;
        if (seconds > 0) {
          countEl.textContent = `Auto-opening book in ${seconds}s…`;
        } else {
          clearInterval(countdownInterval);
          countEl.textContent = 'Launching book reader…';
          triggerBookLaunch();
        }
      }, 1000);
    }

    function triggerBookLaunch() {
      if (!targetReaderUrl) return;
      sessionStorage.removeItem('pearson_auto_launch_pending');
      window.open(targetReaderUrl, '_blank', 'noopener,noreferrer');
      showToast('Opening exact book page!');
    }

    // When the user logs in on Pearson tab and switches back to this tab, auto-open!
    window.addEventListener('focus', () => {
      if (hasAttemptedLogin && targetReaderUrl) {
        hasAttemptedLogin = false;
        clearInterval(countdownInterval);
        const statusEl = document.getElementById('automation-status');
        if (statusEl) statusEl.style.display = 'none';
        showToast('Welcome back! Launching exact book page…');
        setTimeout(triggerBookLaunch, 400);
      }
    });

    // Load book metadata and populate links
    (async () => {
      const path = decodeURIComponent(location.pathname);
      const bookId = path.split('/').filter(Boolean).pop();
      targetPage = Math.max(1, Number.parseInt(new URLSearchParams(location.search).get('page') || '1', 10) || 1);

      document.getElementById('page-badge').textContent = `Target: Page ${targetPage}`;
      document.getElementById('status-target-page').textContent = targetPage;

      try {
        const response = await fetch(`/api/reader/info/${encodeURIComponent(bookId)}?page=${targetPage}`, { cache: 'no-store' });
        if (!response.ok) {
          document.getElementById('book-title').textContent = 'Pearson Textbook Holding';
          targetReaderUrl = `https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?version=1.0.317.1#book/${bookId}/page/${targetPage}`;
          document.getElementById('btn-open-reader').href = targetReaderUrl;
          return;
        }

        const book = await response.json();
        document.getElementById('book-title').textContent = book.title || 'Pearson Digital Textbook';
        document.getElementById('book-author').textContent = (book.author || 'Pearson Education') + ` · Page ${targetPage}`;
        targetReaderUrl = book.reader_url || `https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?version=1.0.317.1#book/${bookId}/page/${targetPage}`;
        document.getElementById('btn-open-reader').href = targetReaderUrl;
      } catch (err) {
        document.getElementById('book-title').textContent = 'Pearson Textbook Holding';
        targetReaderUrl = `https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?version=1.0.317.1#book/${bookId}/page/${targetPage}`;
        document.getElementById('btn-open-reader').href = targetReaderUrl;
      }
    })();
