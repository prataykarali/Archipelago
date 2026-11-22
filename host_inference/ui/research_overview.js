let overviewController = null;
let overviewTimer = null;

async function loadResearchOverview(isBackground = false) {
  if (!await window.archipelagoResearchReady) return;
  if (isBackground && document.hidden) return;
  if (overviewController) return;
  const controller = new AbortController();
  overviewController = controller;
  try {
    const { graph, intake } = await window.archipelagoResearchCounts({
      background: isBackground,
      signal: controller.signal,
    });
    const values = {
      'metric-concepts': graph.counts.concepts,
      'metric-relationships': graph.counts.relationships,
      'metric-documents': graph.counts.documents,
      'metric-papers': intake.papers,
      'metric-college': intake.college_pages
    };
    Object.entries(values).forEach(([id, value]) => {
      document.getElementById(id).textContent = Number(value || 0).toLocaleString();
    });
    const response = await fetch('/api/research/intake/topics', {
      cache: 'no-store',
      headers: isBackground ? { 'X-Background-Poll': '1' } : undefined,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('Research topic count unavailable.');
    document.getElementById('metric-topics').textContent = Number((await response.json()).count || 0).toLocaleString();
    document.getElementById('pipeline-status').textContent = 'Counts verified against the live institutional graph and research store.';
  } catch (error) {
    if (error?.name === 'AbortError') return;
    document.getElementById('pipeline-status').textContent = error.message || 'Counts unavailable.';
  } finally {
    if (overviewController === controller) overviewController = null;
  }
}

function stopOverviewPolling() {
  if (overviewTimer) {
    clearInterval(overviewTimer);
    overviewTimer = null;
  }
  if (overviewController) {
    try { overviewController.abort(); } catch (_) {}
    overviewController = null;
  }
}

loadResearchOverview(false);
overviewTimer = window.setInterval(() => loadResearchOverview(true), 60000);
window.addEventListener('pagehide', stopOverviewPolling);
window.addEventListener('beforeunload', stopOverviewPolling);
