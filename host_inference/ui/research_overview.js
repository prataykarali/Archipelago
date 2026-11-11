async function loadResearchOverview() {
  if (!await window.archipelagoResearchReady) return;
  try {
    const { graph, intake } = await window.archipelagoResearchCounts();
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
    const response = await fetch('/api/research/intake/topics', { cache: 'no-store' });
    if (!response.ok) throw new Error('Research topic count unavailable.');
    document.getElementById('metric-topics').textContent = Number((await response.json()).count || 0).toLocaleString();
    document.getElementById('pipeline-status').textContent = 'Counts verified against the live institutional graph and research store.';
  } catch (error) {
    document.getElementById('pipeline-status').textContent = error.message || 'Counts unavailable.';
  }
}
loadResearchOverview();
window.setInterval(loadResearchOverview, 60000);
