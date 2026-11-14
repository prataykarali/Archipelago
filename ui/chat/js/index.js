// Auto-split from ui/chat/index.html — module entry point.
// Import order preserves the original top-level evaluation order.
import './00-current-origin.js';
import './01--hide-welcome-with-transitio.js';
import './02--kw-highlights.js';
import './03-wrap-library-inventory-secti.js';
import './04-start-new-chat.js';
import './05-display-books.js';
import './06-open-book-or-unavailable.js';
import './07-open-page-viewer-modal.js';
import './08-send-message.js';
import './09-patterns.js';
import './10-populate-pipeline.js';
import './11-populate-topology.js';
import './12-choose-graph-experience.js';
import './13-render-horizontal-graph-card.js';
import './14-render-adaptive-mcqcard.js';
import './15-submit-adaptive-answer.js';
import './16-render-personalized-graph-ca.js';
import './17-draw-personalized-svg.js';
import './18--init-graph-ripple.js';
import './19-draw-horizontal-svg.js';
import './20--compact-history.js';
import './21-generate-roadmap.js';
import './expose.js';
await window.archipelagoAuthReady;
await window.archipelagoRequireSession();
if (window.matchMedia('(max-width: 768px)').matches) {
  window.closeAllSidePanels?.();
}
if (window.archipelagoUserId) {
  const { storageKey } = await import('./storage-key.js');
  window.showGraphCards = localStorage.getItem(storageKey('showGraphCards')) !== 'false';
  window.updateGraphToggleUI?.();
}
import { applyQuotaCooldown, formatQuotaResetTime } from './08-send-request.js';

try {
  const response = await fetch('/api/chat/quota');
  if (response.ok) {
    const quota = await response.json();
    const label = document.getElementById('query-limit-status');
    if (label) {
      if (quota.unrestricted) {
        label.textContent = `${(quota.role || 'Staff').replace(/^./, letter => letter.toUpperCase())}: no app AI query quota · provider limits may apply`;
      } else if (quota.limited || Number(quota.retry_after || 0) > 0) {
        const resetText = formatQuotaResetTime(quota.reset_at, quota.retry_after);
        label.textContent = `Hourly chat limit reached (${quota.used ?? 10}/10). You can ask another question after ${resetText}.`;
        applyQuotaCooldown(quota.reset_at, quota.retry_after);
      } else {
        label.textContent = `Student chat queries: ${quota.used ?? 0} / 10 this hour`;
      }
    }
  }
} catch (_) {}
