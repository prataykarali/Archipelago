window.archipelagoResearchReady = new Promise(resolve => {
  window.addEventListener('load', async () => {
    const page = document.body.dataset.researchPage;
    if (page === 'rankings' || (['paper', 'topic'].includes(page) && new URLSearchParams(location.search).has('example'))) {
      resolve({ publicPreview: true }); return;
    }
    await window.archipelagoAuthReady;
    resolve(await window.archipelagoAuthorizePage(['faculty', 'librarian', 'administrator']));
  });
});

window.archipelagoResearchCounts = async ({ background = false, signal } = {}) => {
  const headers = background ? { 'X-Background-Poll': '1' } : undefined;
  const [graphResponse, intakeResponse] = await Promise.all([
    fetch('/api/research/graph/papers', { cache: 'no-store', headers, signal }),
    fetch('/api/research/intake/metrics', { cache: 'no-store', headers, signal })
  ]);
  if (!graphResponse.ok || !intakeResponse.ok) throw new Error('Research counts are unavailable.');
  const graph = await graphResponse.json();
  const intake = await intakeResponse.json();
  return { graph, intake };
};
