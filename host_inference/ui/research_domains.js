const RESEARCH_DOMAINS = [
  { name: 'DBMS & Data Systems', terms: /database|sql|transaction|indexing|b-tree|lsm|query optim|data warehouse|distributed data|mvcc|relational/i },
  { name: 'Operating Systems', terms: /operating system|process schedul|kernel|memory manag|virtual memory|thread|deadlock|filesystem|file system/i },
  { name: 'Computer Networks', terms: /tcp|udp|routing|network protocol|congestion|packet|wireless|internet protocol|dns|ethernet/i },
  { name: 'Algorithms & Data Structures', terms: /algorithm|data structure|tree|graph traversal|dynamic programming|hash table|sorting|complexity|search method/i },
  { name: 'Mathematics & Statistics', terms: /theorem|probability|statistics|matrix|eigen|singular value|linear algebra|calculus|optimization|regression|distribution|gradient/i },
  { name: 'Architecture & Hardware', terms: /processor|cpu|gpu|cache|instruction|branch prediction|hardware|circuit|architecture|vlsi|microcontroller/i },
  { name: 'Software & Compilers', terms: /compiler|parser|programming language|software engineer|software design|testing|interpreter|program analysis/i },
  { name: 'Security & Privacy', terms: /cryptograph|encrypt|security|privacy|attack|authentication|malware|blockchain/i },
  { name: 'AI & Machine Learning', terms: /neural|learning|model|transformer|attention|embedding|rag|classification|generation|agent|llm|convolution|vision|recognition|reinforcement|diffusion|language/i },
  { name: 'Interdisciplinary', terms: /.*/ }
];

let domainNodes = [];
let researchTopics = [];

function renderTopicCards() {
  const root = document.getElementById('topic-cards');
  const filter = document.getElementById('topic-filter').value.trim().toLowerCase();
  root.replaceChildren();
  researchTopics.filter(item => item.topic.toLowerCase().includes(filter)).forEach(item => {
    const card = document.createElement('article');
    card.className = 'domain-card';
    const link = document.createElement('a');
    link.href = `/research/papers?topic=${encodeURIComponent(item.topic)}`;
    link.textContent = item.topic;
    const count = document.createElement('span');
    count.className = 'domain-count';
    count.textContent = `${item.paper_count} SAVED PAPERS`;
    card.append(count, link);
    root.append(card);
  });
  if (!root.childElementCount) root.textContent = 'No research topics match that search.';
}

function bucketFor(node) {
  const title = String(node.data.name || node.data.id || '');
  return RESEARCH_DOMAINS.find(domain => domain.terms.test(title))?.name || 'Interdisciplinary';
}

function renderDomainCards() {
  const root = document.getElementById('domain-cards');
  const filter = document.getElementById('domain-filter').value.trim().toLowerCase();
  root.replaceChildren();
  const buckets = new Map(RESEARCH_DOMAINS.map(domain => [domain.name, []]));
  domainNodes.forEach(node => buckets.get(bucketFor(node)).push(node));
  RESEARCH_DOMAINS.forEach(domain => {
    const all = buckets.get(domain.name);
    const visible = filter ? all.filter(node => node.data.name.toLowerCase().includes(filter)) : all;
    if (filter && !visible.length && !domain.name.toLowerCase().includes(filter)) return;
    const card = document.createElement('article');
    card.className = 'domain-card';
    const count = document.createElement('span');
    count.className = 'domain-count';
    count.textContent = `${all.length} INDEXED CONCEPTS`;
    const heading = document.createElement('h3');
    heading.textContent = domain.name;
    const list = document.createElement('ul');
    if (!visible.length) {
      const empty = document.createElement('li');
      empty.textContent = 'No matching concepts indexed yet.';
      list.append(empty);
    }
    visible.sort((a, b) => a.data.name.localeCompare(b.data.name)).forEach(node => {
      const li = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = node.data.name;
      button.addEventListener('click', () => window.archipelagoFocusConcept(node.data.id));
      li.append(button);
      list.append(li);
    });
    card.append(count, heading, list);
    root.append(card);
  });
  if (!root.childElementCount) root.textContent = 'No concepts match that search.';
}

window.archipelagoRenderDomains = data => {
  domainNodes = Array.isArray(data.nodes) ? data.nodes : [];
  renderDomainCards();
};
window.archipelagoFocusConcept = conceptId => {
  window.location.assign(`/research/graph?concept=${encodeURIComponent(conceptId)}`);
};
document.getElementById('domain-filter').addEventListener('input', renderDomainCards);
document.getElementById('topic-filter').addEventListener('input', renderTopicCards);

async function loadConceptIndex() {
  if (!await window.archipelagoResearchReady) return;
  try {
    const response = await fetch('/api/research/graph/full', { cache: 'no-store' });
    if (!response.ok) throw new Error('Concept index unavailable.');
    window.archipelagoRenderDomains(await response.json());
  } catch (error) {
    document.getElementById('domain-cards').textContent = error.message || 'Concept index unavailable.';
  }
}
loadConceptIndex();

async function loadResearchTopics() {
  if (!await window.archipelagoResearchReady) return;
  try {
    const response = await fetch('/api/research/intake/topics', { cache: 'no-store' });
    if (!response.ok) throw new Error('Research topics unavailable.');
    researchTopics = (await response.json()).topics || [];
    renderTopicCards();
  } catch (error) {
    document.getElementById('topic-cards').textContent = error.message || 'Research topics unavailable.';
  }
}
loadResearchTopics();
window.setInterval(loadResearchTopics, 60000);
