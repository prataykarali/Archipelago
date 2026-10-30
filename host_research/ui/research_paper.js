const paperEl = id => document.getElementById(id);
const PAPER_GROUPS = [
  ['Identity', 'identity', 'paper_identity', '▣'],
  ['Authors', 'authors', null, '♙'],
  ['Author metrics', 'author_bibliometrics', 'author_metrics', '▥'],
  ['Venue', 'venue_metrics', null, '⌂'],
  ['Citations', 'citation_metrics', 'citation_metrics', '❞'],
  ['Relevance', 'semantic_relevance', 'relevance', '◎'],
  ['Graph', 'graph_metrics', 'graph_metrics', '◇'],
  ['Novelty', 'novelty_metrics', 'novelty', '✧'],
  ['Methodology', 'methodology', 'methodology', '⚙'],
  ['Datasets & design', 'datasets', null, '▤'],
  ['Experiments', 'experiments', 'experiments', '⚗'],
  ['Performance', 'performance', 'performance', '▥'],
  ['Efficiency', 'efficiency', 'efficiency', '◷'],
  ['Claims', 'claims', null, '❞'],
  ['Evidence & claims', 'evidence', 'evidence', '✦'],
  ['Reproducibility', 'reproducibility', 'reproducibility', '♧'],
  ['Relationships', 'relations', 'research_relationships', '⌁'],
  ['Integrity', 'integrity', 'integrity', '♢'],
  ['Provenance', 'provenance', 'provenance', '⧉']
];
const MAX_DISPLAY_ITEMS = 8;
const MAX_ABSTRACT_PREVIEW = 420;
const MAX_FIELD_TEXT = 360;

function hasReportedValue(field) {
  const value = field?.value;
  if (value === null || value === undefined) return false;
  if (typeof value === 'string' && (!value.trim() || ['unknown', 'null', 'none', 'not reported', 'not available', 'n/a'].includes(value.trim().toLowerCase()))) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
}

function paperField(okf, section, parameter, name) {
  const direct = okf?.[section]?.[name];
  const contract = parameter ? okf?.parameters?.[parameter]?.[name] : null;
  return hasReportedValue(direct) ? direct : hasReportedValue(contract) ? contract : null;
}

function groupFields(okf, section, parameter) {
  const fields = new Map();
  for (const group of [parameter ? okf?.parameters?.[parameter] : null, okf?.[section]]) {
    if (!group || typeof group !== 'object') continue;
    for (const [name, field] of Object.entries(group)) {
      if (hasReportedValue(field)) fields.set(name, field);
    }
  }
  return [...fields.entries()];
}

function displayValue(value) {
  if (Array.isArray(value)) {
    const parts = value.slice(0, MAX_DISPLAY_ITEMS).map(item =>
      typeof item === 'object' && item !== null ? item.name || item.title || item.author_name || JSON.stringify(item) : String(item));
    return parts.join(', ') + (value.length > MAX_DISPLAY_ITEMS ? ` · +${value.length - MAX_DISPLAY_ITEMS} more` : '');
  }
  if (typeof value === 'object' && value !== null) return value.name || value.title || JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function safeLink(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch (_) { return null; }
}

function addAction(parent, label, href, className = '') {
  const link = document.createElement('a');
  link.textContent = label;
  link.href = href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.className = className;
  parent.append(link);
}

function addStat(parent, label, value, icon) {
  if (value === null || value === undefined || value === '') return;
  const tile = document.createElement('div'); tile.className = 'paper-stat';
  const mark = document.createElement('span'); mark.className = 'paper-stat-icon'; mark.textContent = icon;
  const body = document.createElement('div');
  const title = document.createElement('small'); title.textContent = label;
  const number = document.createElement('strong'); number.textContent = displayValue(value);
  body.append(title, number); tile.append(mark, body); parent.append(tile);
}

function fieldRow(name, field) {
  const row = document.createElement('div'); row.className = 'paper-field';
  const label = document.createElement('dt'); label.textContent = name.replace(/_/g, ' ');
  const value = document.createElement('dd');
  const raw = field.value;
  const url = safeLink(raw);
  if (url) addAction(value, raw.length > 62 ? `${raw.slice(0, 59)}… ↗` : `${raw} ↗`, url);
  else {
    const text = displayValue(raw);
    value.textContent = text.length > MAX_FIELD_TEXT ? `${text.slice(0, MAX_FIELD_TEXT)}…` : text;
    if (text.length > MAX_FIELD_TEXT) value.title = text;
  }
  const status = document.createElement('span');
  status.className = `paper-field-status ${field.status || 'observed'}`;
  status.textContent = field.status === 'inferred' ? 'Quote checked' : field.status === 'derived' ? 'Calculated' : 'Source';
  value.append(status);
  if (field.evidence_text) {
    const quote = document.createElement('small'); quote.className = 'paper-field-evidence';
    quote.textContent = `“${field.evidence_text}”${field.page_number ? ` · PDF p. ${field.page_number}` : ''}`;
    value.append(quote);
  }
  row.append(label, value);
  return row;
}

function sectionCard(label, fields, icon) {
  const card = document.createElement('article'); card.className = 'paper-section-card';
  const id = `section-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`; card.id = id;
  const heading = document.createElement('h2');
  const mark = document.createElement('span'); mark.textContent = icon; mark.setAttribute('aria-hidden', 'true');
  heading.append(mark, document.createTextNode(label));
  const list = document.createElement('dl');
  fields.forEach(([name, field]) => list.append(fieldRow(name, field)));
  card.append(heading, list);
  return card;
}

function abstractCard(okf) {
  const field = paperField(okf, 'identity', 'paper_identity', 'abstract');
  if (!field) return null;
  const card = document.createElement('article'); card.className = 'paper-section-card paper-abstract-card'; card.id = 'section-abstract';
  const heading = document.createElement('h2'); heading.textContent = '▤  Abstract';
  const paragraph = document.createElement('p'); paragraph.textContent = String(field.value).slice(0, MAX_ABSTRACT_PREVIEW);
  card.append(heading, paragraph);
  if (String(field.value).length > MAX_ABSTRACT_PREVIEW) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Read full abstract ↓';
    button.onclick = () => { paragraph.textContent = String(field.value); button.remove(); };
    card.append(button);
  }
  return card;
}

function citationTrend(okf) {
  const rows = okf.raw_metadata?.counts_by_year;
  if (!Array.isArray(rows) || !rows.length) return null;
  const points = rows.filter(row => Number.isFinite(Number(row.year)) && Number.isFinite(Number(row.cited_by_count)))
    .sort((a, b) => Number(a.year) - Number(b.year)).slice(-8);
  if (!points.length) return null;
  const card = document.createElement('article'); card.className = 'paper-section-card paper-chart-card'; card.id = 'section-trend';
  const heading = document.createElement('h2'); heading.textContent = '▥  Citation trend';
  const chart = document.createElement('div'); chart.className = 'paper-chart'; chart.setAttribute('role', 'img');
  chart.setAttribute('aria-label', points.map(p => `${p.year}: ${p.cited_by_count} citations`).join(', '));
  const peak = Math.max(1, ...points.map(p => Number(p.cited_by_count)));
  points.forEach(point => {
    const column = document.createElement('div');
    const bar = document.createElement('span'); bar.style.height = `${Math.max(6, Number(point.cited_by_count) / peak * 100)}%`;
    bar.title = `${point.year}: ${point.cited_by_count}`;
    const year = document.createElement('small'); year.textContent = String(point.year);
    column.append(bar, year); chart.append(column);
  });
  card.append(heading, chart);
  return card;
}

function verifiedEvidenceCard(facts) {
  if (!facts.length) return null;
  const card = document.createElement('article'); card.className = 'paper-section-card paper-evidence-log'; card.id = 'section-verified-evidence';
  const heading = document.createElement('h2'); heading.textContent = `✦  Verified evidence · ${facts.length}`;
  const list = document.createElement('ol');
  facts.forEach(fact => {
    const item = document.createElement('li');
    const label = document.createElement('strong'); label.textContent = `${String(fact.group || '').replace(/_/g, ' ')} / ${String(fact.field || '').replace(/_/g, ' ')}`;
    const source = document.createElement('small'); source.textContent = fact.pdf_page ? `PDF p. ${fact.pdf_page}` : 'Source abstract';
    const value = document.createElement('p'); value.textContent = String(fact.value ?? '');
    const quote = document.createElement('blockquote'); quote.textContent = String(fact.evidence_text || '');
    item.append(label, source, value, quote); list.append(item);
  });
  card.append(heading, list);
  return card;
}

function renderPaper(okf, key) {
  if (okf.search_topic) {
    const topicLink = paperEl('paper-topic-link');
    topicLink.textContent = String(okf.search_topic);
    topicLink.href = `/research/topic?name=${encodeURIComponent(okf.search_topic)}`;
  }
  const identity = okf.parameters?.paper_identity || {};
  const title = paperField(okf, 'identity', 'paper_identity', 'title')?.value || 'Research paper';
  paperEl('paper-title').textContent = String(title);
  const authors = identity.authors?.value || okf.authors?.author_name?.value || [];
  paperEl('paper-authors').textContent = Array.isArray(authors) ? displayValue(authors) : displayValue(authors);
  const venue = paperField(okf, 'identity', 'paper_identity', 'journal_or_conference')?.value || paperField(okf, 'identity', 'paper_identity', 'publisher')?.value;
  const year = paperField(okf, 'identity', 'paper_identity', 'publication_year')?.value;
  paperEl('paper-venue').textContent = [venue, year].filter(Boolean).join(' · ');
  const tags = paperEl('paper-tags');
  const keywords = paperField(okf, 'identity', 'paper_identity', 'keywords')?.value;
  if (Array.isArray(keywords)) keywords.slice(0, 4).forEach(value => {
    const tag = document.createElement('span'); tag.textContent = String(value); tags.append(tag);
  });
  const observed = (okf.feature_observations || []).filter(hasReportedValue);
  const observedQuoted = [...new Map(observed.filter(item => item.evidence_text).map(item => [
    `${item.value}|${item.evidence_text}|${item.page_number || ''}`,
    item
  ])).values()];
  const quoted = Array.isArray(okf.verified_evidence) ? okf.verified_evidence : observedQuoted;
  const access = okf.raw_metadata?.access_state;
  const accessLabel = access === 'FULLTEXT_EXTRACTED' ? 'Indra PDF with accepted page-linked evidence'
    : access === 'FULLTEXT_NO_VERIFIED_FIELDS' ? 'Indra PDF read · no accepted SLM facts'
      : 'Metadata and abstract record';
  paperEl('paper-subtitle').textContent = `${observed.length} observed or calculated fields · ${quoted.length} with quoted evidence · ${accessLabel}`;
  const doi = paperField(okf, 'identity', 'paper_identity', 'doi')?.value;
  const identityPanel = paperEl('paper-identity');
  if (access === 'FULLTEXT_EXTRACTED') { const badge = document.createElement('span'); badge.className = 'paper-access-badge'; badge.textContent = '✓ Indra OCR verified'; identityPanel.append(badge); }
  if (access === 'FULLTEXT_NO_VERIFIED_FIELDS') { const badge = document.createElement('span'); badge.className = 'paper-doi'; badge.textContent = 'Indra read · no verified PDF field'; identityPanel.append(badge); }
  if (doi) { const badge = document.createElement('span'); badge.className = 'paper-doi'; badge.textContent = `DOI: ${doi}`; identityPanel.append(badge); }
  const actions = paperEl('paper-actions');
  const source = safeLink(okf.identity?.landing_page_url?.value || identity.landing_page_url?.value || okf.raw_metadata?.source_url);
  const pdf = safeLink(identity.pdf_url?.value);
  if (source) addAction(actions, 'Open paper ↗', source, 'paper-action-secondary');
  if (pdf && okf.raw_metadata?.is_open_access === true) addAction(actions, 'Open access PDF ↗', pdf, 'paper-action-secondary');
  const exportButton = document.createElement('button'); exportButton.type = 'button'; exportButton.textContent = '↓ Export OKF JSON';
  exportButton.onclick = () => { const url = URL.createObjectURL(new Blob([JSON.stringify(okf, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = `${key}.okf.json`; a.click(); URL.revokeObjectURL(url); };
  actions.append(exportButton);
  const stats = paperEl('paper-stat-strip');
  addStat(stats, 'Citations', paperField(okf, 'citation_metrics', 'citation_metrics', 'citation_count')?.value, '❞');
  addStat(stats, 'References', paperField(okf, 'citation_metrics', 'citation_metrics', 'reference_count')?.value, '▧');
  addStat(stats, 'Research age', paperField(okf, 'integrity', 'integrity', 'research_age')?.value, '▣');
  addStat(stats, 'Topic relevance', paperField(okf, 'semantic_relevance', 'relevance', 'topic_relevance_score')?.value, '◎');
  addStat(stats, 'Quote-backed facts', quoted.length, '✦');
  addStat(stats, 'Reported fields', observed.length, '◈');
  const dashboard = paperEl('paper-dashboard');
  const abstract = abstractCard(okf); if (abstract) dashboard.append(abstract);
  const trend = citationTrend(okf); if (trend) dashboard.append(trend);
  const tabs = paperEl('paper-tabs');
  const overview = document.createElement('a'); overview.href = '#paper-overview'; overview.textContent = 'Overview'; overview.className = 'active'; tabs.append(overview);
  for (const [label, group, parameter, icon] of PAPER_GROUPS) {
    const fields = groupFields(okf, group, parameter).filter(([name]) => !(group === 'identity' && ['abstract', 'title'].includes(name)));
    if (!fields.length) continue;
    const card = sectionCard(label, fields, icon); dashboard.append(card);
    const tab = document.createElement('a'); tab.href = `#${card.id}`; tab.textContent = label; tabs.append(tab);
  }
  const evidenceLog = verifiedEvidenceCard(quoted);
  if (evidenceLog) {
    dashboard.append(evidenceLog);
    const tab = document.createElement('a'); tab.href = '#section-verified-evidence'; tab.textContent = 'Verified evidence'; tabs.append(tab);
  }
  const audit = document.createElement('details'); audit.className = 'paper-raw-json';
  const summary = document.createElement('summary'); summary.textContent = 'Inspect full OKF JSON (including unreported fields)';
  const pre = document.createElement('pre'); pre.textContent = JSON.stringify(okf, null, 2);
  audit.append(summary, pre); paperEl('paper-audit-actions').append(exportButton.cloneNode(true), audit);
  paperEl('paper-audit-actions').querySelector('button').onclick = exportButton.onclick;
}

window.addEventListener('load', async () => {
  if (!await window.archipelagoResearchReady) return;
  const key = new URLSearchParams(location.search).get('key') || '';
  if (!/^[a-f0-9]{64}$/.test(key)) { paperEl('paper-subtitle').textContent = 'Invalid paper link.'; return; }
  try {
    const response = await fetch(`/api/research/intake/paper-okf/${key}`, { cache: 'no-store' });
    if (!response.ok) throw new Error('This saved paper is unavailable.');
    renderPaper(await response.json(), key);
  } catch (error) { paperEl('paper-subtitle').textContent = error.message; }
});
