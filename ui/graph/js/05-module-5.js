// Auto-split from ui/chat/index.html — 05-module-5.js
// Feature module 6 of 6.
import { state } from './00-state.js';
import { showBooks, showConcepts, showCrossBook } from './01-books-module.js';
import { bk, checkGraphStaffAccess, processData, urlParams } from './00-escape-html.js';

// ── TAB CLICK HANDLERS ──
document.getElementById('tab-books').onclick = () => showBooks();

document.getElementById('tab-concepts').onclick = () => showConcepts(null);

document.getElementById('tab-crossbook').onclick = () => showCrossBook();

document.getElementById('home-btn').onclick = () => showBooks();

document.getElementById('back-btn').onclick = () => showBooks();

// ── INITIAL FETCH & BOOTSTRAP ──
checkGraphStaffAccess().then((hasStaffAccess) => {
  if (!hasStaffAccess) return null;
  return fetch('/api/graph', { credentials: 'same-origin', cache: 'no-store' });
}).then(r => {
    if (!r) return null;
    if (!r.ok) throw new Error("API not active");
    return r.json();
  })
  .catch(() => {
    console.log("Flask API unavailable. Fetching static okf_graph.json...");
    return fetch('./okf_graph.json').then(r => r.json());
  })
  .then(data => {
    if (!data) return;
    document.getElementById('loader').classList.add('gone');
    setTimeout(() => document.getElementById('loader').style.display = 'none', 500);
    processData(data);

    if (window._highlightIds && window._highlightIds.length > 0) {
      const presentCount = state.allNodes.filter(n => window._highlightIds.includes(n.id)).length;
      if (presentCount > 0) {
        let docName = '';
        const docParam = urlParams.get('document');
        if (docParam) {
          docName = docParam.split('/').pop().replace(/\.pdf$/i, '').replace(/\.md$/i, '');
        }
        if (!docName) {
          for (const id of window._highlightIds) {
            const node = state.allNodes.find(n => n.id === id);
            if (node && node.sources && node.sources.length > 0) {
              const docId = node.sources[0].doc_id;
              if (docId) { docName = bk(docId).name; break; }
            }
          }
        }
        if (!docName) docName = 'Document';
        const banner = document.getElementById('highlight-banner');
        const bannerText = document.getElementById('highlight-banner-text');
        bannerText.textContent = `${presentCount} new concepts added from ${docName}`;
        banner.classList.remove('hidden');
        document.getElementById('highlight-banner-close').onclick = () => { banner.classList.add('hidden'); };
      }
      showConcepts(null);
    } else {
      const urlTab = new URLSearchParams(window.location.search).get('tab');
      if (urlTab === 'concepts') {
        showConcepts(null);
      } else if (urlTab === 'crossbook') {
        showCrossBook();
      } else {
        showBooks();
      }
    }
  })
  .catch(e => {
    document.querySelector('.ltxt').textContent = 'Error: ' + e.message;
    document.querySelector('.lsub').textContent = 'Ensure okf_graph.json exists in this directory.';
  });
