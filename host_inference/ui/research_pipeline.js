(async () => {
  if (!await window.archipelagoResearchReady) return;
  try {
    const response = await fetch('/api/research/intake/metrics', { cache: 'no-store' });
    if (!response.ok) throw new Error('Stored-source counts are unavailable.');
    const counts = await response.json();
    document.getElementById('campus-flow-count').textContent = Number(counts.college_pages || 0).toLocaleString();
    document.getElementById('research-flow-count').textContent = Number(counts.papers || 0).toLocaleString();
  } catch (error) {
    document.getElementById('pipeline').setAttribute('data-state', 'unavailable');
  }
})();
