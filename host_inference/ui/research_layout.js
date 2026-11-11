const workspaceTabs = [...document.querySelectorAll('[data-tab]')];
const workspacePanes = [...document.querySelectorAll('[data-pane]')];

function showResearchTab(name, focus = false) {
  workspaceTabs.forEach(tab => {
    const active = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
    if (active && focus) tab.focus();
  });
  workspacePanes.forEach(pane => { pane.hidden = pane.dataset.pane !== name; });
  if (name === 'graph') window.dispatchEvent(new Event('archipelago:graph-visible'));
}

window.archipelagoShowResearchTab = showResearchTab;
workspaceTabs.forEach(tab => tab.addEventListener('click', () => showResearchTab(tab.dataset.tab)));
document.querySelector('.workspace-tabs').addEventListener('keydown', event => {
  if (!['ArrowRight', 'ArrowLeft'].includes(event.key)) return;
  event.preventDefault();
  const current = workspaceTabs.findIndex(tab => tab.getAttribute('aria-selected') === 'true');
  const next = (current + (event.key === 'ArrowRight' ? 1 : -1) + workspaceTabs.length) % workspaceTabs.length;
  showResearchTab(workspaceTabs[next].dataset.tab, true);
});

document.querySelectorAll('[data-open-tab]').forEach(link => link.addEventListener('click', () => {
  showResearchTab(link.dataset.openTab);
}));
document.querySelectorAll('[data-tab-jump]').forEach(button => button.addEventListener('click', () => {
  showResearchTab(button.dataset.tabJump, true);
}));

function setMetric(id, value) {
  const target = document.getElementById(id);
  if (target) target.textContent = Number(value || 0).toLocaleString();
}

window.archipelagoUpdateGraphMetrics = counts => {
  setMetric('metric-concepts', counts.concepts);
  setMetric('metric-relationships', counts.relationships);
  setMetric('metric-documents', counts.documents);
};
window.archipelagoUpdatePipelineMetrics = counts => {
  const papers = counts.papers;
  const college = counts.college_pages;
  setMetric('metric-papers', papers);
  setMetric('metric-college', college);
  setMetric('research-flow-count', papers);
  setMetric('campus-flow-count', college);
  document.getElementById('pipeline-status').textContent = `${papers} paper records and ${college} campus pages are currently saved.`;
};
