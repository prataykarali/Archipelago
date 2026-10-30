window.archipelagoResearchReady = new Promise(resolve => {
  window.addEventListener('load', async () => {
    await window.archipelagoAuthReady;
    resolve(await window.archipelagoAuthorizePage(['faculty', 'librarian', 'administrator']));
  });
});

window.archipelagoResearchCounts = async () => {
  const [graphResponse, intakeResponse] = await Promise.all([
    fetch('/api/research/graph/papers', { cache: 'no-store' }),
    fetch('/api/research/intake/metrics', { cache: 'no-store' })
  ]);
  if (!graphResponse.ok || !intakeResponse.ok) throw new Error('Research counts are unavailable.');
  const graph = await graphResponse.json();
  const intake = await intakeResponse.json();
  return { graph, intake };
};
