/* Source-backed OKF presentation for the Research page. */
function statusBadgeClass(status) {
  const map = {
    verified: 'okf-badge-verified',
    inferred: 'okf-badge-verified',
    abstract_quote_matched: 'okf-badge-verified',
    observed: 'okf-badge-source',
    source_reported: 'okf-badge-source',
    derived: 'okf-badge-computed',
    computed: 'okf-badge-computed',
    deterministic: 'okf-badge-computed',
    unknown: 'okf-badge-unknown',
    not_reported: 'okf-badge-unknown',
    not_applicable: 'okf-badge-na'
  };
  return map[status] || 'okf-badge-unknown';
}

function hasReportedValue(field) {
  const value = field?.value;
  if (value === null || value === undefined) return false;
  if (typeof value === 'string' && (!value.trim() || ['unknown', 'not reported', 'not available', 'n/a', 'null', 'none'].includes(value.trim().toLowerCase()))) return false;
  if ((Array.isArray(value) || typeof value === 'object') && !Object.keys(value).length) return false;
  return true;
}

function makeTile(label, value, status) {
  const tile = document.createElement('div');
  tile.className = 'okf-tile';
  const dt = document.createElement('dt');
  dt.textContent = label;
  const badge = document.createElement('span');
  badge.className = `okf-badge ${statusBadgeClass(status)}`;
  badge.textContent = status;
  dt.append(badge);
  const dd = document.createElement('dd');
  if (typeof value === 'object' && value !== null) {
    dd.textContent = Array.isArray(value) ? value.join(', ') || '—' : JSON.stringify(value);
  } else {
    dd.textContent = value ?? '—';
  }
  tile.append(dt, dd);
  return tile;
}

function makeSection(title, okf, groupKey) {
  const group = okf?.[groupKey] || okf?.parameters?.[groupKey];
  if (!group || !Object.keys(group).length) return null;
  const section = document.createElement('div');
  section.className = 'okf-section';
  const heading = document.createElement('h4');
  heading.className = 'okf-section-title';
  heading.textContent = title;
  const grid = document.createElement('dl');
  grid.className = 'okf-grid';
  for (const [key, field] of Object.entries(group)) {
    if (!hasReportedValue(field)) continue;
    const displayLabel = key.replace(/_/g, ' ');
    const val = field?.value;
    grid.append(makeTile(displayLabel, val, field?.status || 'observed'));
  }
  if (!grid.childElementCount) {
    const empty = document.createElement('p');
    empty.textContent = 'No source-backed values reported. The complete contract remains available in the JSON audit.';
    section.append(heading, empty);
    return section;
  }
  section.append(heading, grid);
  return section;
}

function decorateOkf(okf, title) {
  const wrapper = document.createElement('div');
  wrapper.className = 'okf-card';

  /* ── Header ── */
  const header = document.createElement('div');
  header.className = 'okf-header';
  const h3 = document.createElement('h3');
  h3.textContent = title;
  header.append(h3);

  const metaRow = document.createElement('div');
  metaRow.className = 'okf-meta-row';
  const identity = okf?.parameters?.paper_identity || {};
  const metaParts = [
    identity.authors?.value, identity.publication_year?.value,
    identity.journal_or_conference?.value, identity.doi?.value && `DOI: ${identity.doi.value}`
  ].filter(Boolean);
  metaParts.forEach(text => {
    const tag = document.createElement('span');
    tag.className = 'okf-meta-tag';
    tag.textContent = Array.isArray(text) ? text.slice(0, 4).map(item => typeof item === 'object' ? item.name || item.author_name || '' : item).filter(Boolean).join(', ') : (typeof text === 'object' ? '' : String(text));
    metaRow.append(tag);
  });
  if (identity.is_open_access?.value === true || identity.is_open_access?.value === 'true') {
    const oa = document.createElement('span');
    oa.className = 'okf-badge okf-badge-verified';
    oa.textContent = 'Open Access';
    metaRow.append(oa);
  }
  header.append(metaRow);
  const reported = Object.values(okf?.feature_observations || {}).filter(hasReportedValue).length;
  const coverage = document.createElement('p');
  coverage.className = 'okf-coverage';
  coverage.textContent = `${reported} source-backed values available. Unreported fields stay in the JSON audit, without guessed values.`;
  header.append(coverage);
  wrapper.append(header);

  /* ── Tab bar ── */
  const SECTIONS = [
    ['Identity', 'identity'], ['Authors', 'authors'],
    ['Author metrics', 'author_bibliometrics'], ['Venue', 'venue_metrics'],
    ['Citations', 'citation_metrics'], ['Relevance', 'semantic_relevance'],
    ['Graph', 'graph_metrics'], ['Novelty', 'novelty_metrics'],
    ['Methodology', 'methodology'], ['Datasets', 'datasets'],
    ['Experiments', 'experiments'], ['Performance', 'performance'],
    ['Efficiency', 'efficiency'], ['Claims', 'claims'],
    ['Evidence', 'evidence'], ['Reproducibility', 'reproducibility'],
    ['Relations', 'relations'], ['Integrity', 'integrity'], ['Provenance', 'provenance']
  ];

  const available = SECTIONS.filter(([, key]) => {
    const g = okf?.[key] || okf?.parameters?.[key];
    return g && Object.values(g).some(hasReportedValue);
  });

  const tabBar = document.createElement('div');
  tabBar.className = 'okf-tabs';
  const body = document.createElement('div');
  body.className = 'okf-body';

  const panels = [];
  available.forEach(([label, key], idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'okf-tab' + (idx === 0 ? ' active' : '');
    btn.textContent = label;
    const panel = makeSection(label, okf, key);
    if (!panel) return;
    panel.hidden = idx !== 0;
    panels.push({ btn, panel });
    btn.addEventListener('click', () => {
      panels.forEach(p => { p.btn.classList.remove('active'); p.panel.hidden = true; });
      btn.classList.add('active');
      panel.hidden = false;
    });
    tabBar.append(btn);
    body.append(panel);
  });
  if (!available.length) {
    const empty = document.createElement('p');
    empty.className = 'okf-empty';
    empty.textContent = 'This record has no reported OKF values yet. A permitted full-text ingestion can add page-linked evidence.';
    body.append(empty);
  }
  wrapper.append(tabBar, body);

  /* ── Collapsible raw JSON audit drawer ── */
  const details = document.createElement('details');
  details.className = 'okf-json-audit';
  const summary = document.createElement('summary');
  summary.textContent = '🔍 Raw OKF JSON · values, status, confidence and provenance';
  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(okf, null, 2);
  details.append(summary, pre);
  wrapper.append(details);
  return wrapper;
}
