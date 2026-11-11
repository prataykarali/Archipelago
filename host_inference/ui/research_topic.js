const topicEl = id => document.getElementById(id);
const TOPIC_PREVIEW_CHARS = 260;
const TOPIC_SHOW_SECTIONS = 5;

function topicLink(label, href, className = '') {
  const link = document.createElement('a');
  link.textContent = label;
  link.href = href;
  link.className = className;
  return link;
}

function topicStat(label, value, icon) {
  const card = document.createElement('div'); card.className = 'topic-stat';
  const symbol = document.createElement('span'); symbol.textContent = icon;
  const copy = document.createElement('div');
  const name = document.createElement('small'); name.textContent = label;
  const count = document.createElement('strong'); count.textContent = String(value);
  copy.append(name, count); card.append(symbol, copy); return card;
}

function topicBars(target, entries) {
  const max = Math.max(1, ...entries.map(([, count]) => count));
  for (const [label, count] of entries) {
    const row = document.createElement('div'); row.className = 'topic-bar-row';
    const name = document.createElement('span'); name.textContent = label.replaceAll('_', ' ');
    const track = document.createElement('div'); track.className = 'topic-bar-track';
    const fill = document.createElement('i'); fill.style.width = `${Math.round(100 * count / max)}%`;
    track.append(fill);
    const number = document.createElement('strong'); number.textContent = String(count);
    row.append(name, track, number); target.append(row);
  }
  if (!entries.length) target.textContent = 'No source data reported yet.';
}

function paperCard(paper, index) {
  const card = document.createElement('article'); card.className = 'topic-paper-card';
  const head = document.createElement('div'); head.className = 'topic-paper-head';
  const number = document.createElement('span'); number.className = 'topic-paper-number'; number.textContent = String(index + 1).padStart(2, '0');
  const title = topicLink(paper.title, `/research/paper?key=${encodeURIComponent(paper.key)}`, 'topic-paper-title');
  head.append(number, title); card.append(head);
  const authors = document.createElement('p'); authors.className = 'topic-paper-authors';
  authors.textContent = [paper.authors.join(', '), paper.venue, paper.year].filter(Boolean).join(' · ') || paper.provider;
  card.append(authors);
  const badges = document.createElement('div'); badges.className = 'topic-paper-badges';
  const status = paper.access_state === 'FULLTEXT_EXTRACTED' ? '✓ Indra OCR · quote checked' : paper.access_state === 'FULLTEXT_NO_VERIFIED_FIELDS' ? 'Indra read · no verified PDF field' : 'Metadata + abstract';
  for (const label of [status, `${paper.observed_fields} reported fields`, `${paper.quoted_facts} quoted facts`, paper.citation_count === null ? '' : `${paper.citation_count} citations`]) {
    if (!label) continue;
    const badge = document.createElement('span'); badge.textContent = label; badges.append(badge);
  }
  card.append(badges);
  if (paper.abstract) { const abstract = document.createElement('p'); abstract.className = 'topic-paper-abstract'; abstract.textContent = paper.abstract.slice(0, TOPIC_PREVIEW_CHARS) + (paper.abstract.length > TOPIC_PREVIEW_CHARS ? '…' : ''); card.append(abstract); }
  const foot = document.createElement('div'); foot.className = 'topic-paper-foot';
  for (const section of paper.sections.slice(0, TOPIC_SHOW_SECTIONS)) { const tag = document.createElement('span'); tag.textContent = section.replaceAll('_', ' '); foot.append(tag); }
  foot.append(topicLink('Open complete paper OKF →', `/research/paper?key=${encodeURIComponent(paper.key)}`));
  card.append(foot); return card;
}

function renderTopic(data) {
  topicEl('topic-title').textContent = data.topic;
  topicEl('topic-breadcrumb').textContent = data.topic;
  topicEl('topic-status').textContent = `${data.paper_count} active papers from the local ingestion pipeline. Select a paper for its full evidence-aware OKF.`;
  // The graph resolves topic IDs from its own index; link to the full atlas.
  topicEl('topic-actions').append(topicLink('Explore full graph ↗', '/research/topics', 'topic-action'), topicLink('Search another topic', '/research', 'topic-action secondary'));
  const states = data.access_states;
  topicEl('topic-stats').append(
    topicStat('Saved papers', data.paper_count, '▤'),
    topicStat('Indra read + verified', states.FULLTEXT_EXTRACTED || 0, '✦'),
    topicStat('Indra read, no verified PDF field', states.FULLTEXT_NO_VERIFIED_FIELDS || 0, '◌'),
    topicStat('Metadata only', states.METADATA_ONLY || 0, '▣')
  );
  topicBars(topicEl('topic-coverage'), Object.entries(data.section_coverage).sort((a, b) => b[1] - a[1]));
  topicBars(topicEl('topic-years'), Object.entries(data.publication_years));
  topicBars(topicEl('topic-providers'), Object.entries(data.providers).sort((a, b) => b[1] - a[1]));
  topicEl('topic-paper-count').textContent = `${data.paper_count} papers`;
  const list = topicEl('topic-paper-list');
  if (!data.paper_count) { const empty = document.createElement('p'); empty.className = 'topic-empty'; empty.textContent = 'No completed local ingestion has saved papers for this topic yet.'; list.append(empty); }
  data.papers.forEach((paper, index) => list.append(paperCard(paper, index)));
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  const topic = new URLSearchParams(location.search).get('name')?.trim() || '';
  if (topic.length < 3) { topicEl('topic-status').textContent = 'Choose a topic from the research graph.'; return; }
  try {
    const response = await fetch(`/api/research/intake/topic-overview?topic=${encodeURIComponent(topic)}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('The saved topic could not be loaded.');
    renderTopic(await response.json());
  } catch (error) { topicEl('topic-status').textContent = error.message; }
});
