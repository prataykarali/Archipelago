/* Show dated discovery data without treating links as fetched records. */
(async () => {
  const status = document.getElementById('scholarly-status');
  const sources = document.getElementById('scholarly-sources');
  const items = document.getElementById('scholarly-items');
  const links = document.getElementById('scholarly-links');
  if (!status || !sources || !items || !links) return;

  function safeLink(url, label) {
    if (typeof url !== 'string') return null;
    let parsed;
    try { parsed = new URL(url); } catch { return null; }
    if (!['https:', 'http:'].includes(parsed.protocol)) return null;
    const anchor = document.createElement('a');
    anchor.href = parsed.href;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.className = 'text-blue-300 hover:underline';
    anchor.textContent = label;
    return anchor;
  }

  try {
    const response = await fetch('/api/scholarly/snapshot', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Snapshot unavailable');
    const data = await response.json();
    document.getElementById('sec-scholarly')?.removeAttribute('hidden');
    const timestamp = typeof data.last_updated === 'string' ? data.last_updated : 'unknown time';
    status.textContent = `Discovery snapshot: ${timestamp}. Delivery: ${data.delivery || 'unknown'}. Live counts describe the recorded fetch, not current holdings.`;

    for (const [name, detail] of Object.entries(data.source_status || {})) {
      const badge = document.createElement('span');
      badge.className = 'px-2 py-1 rounded border border-white/20 text-white/80';
      badge.textContent = `${name}: ${detail.mode || 'unavailable'} · ${detail.live_records || 0} live`;
      sources.appendChild(badge);
    }

    for (const item of (data.items || []).slice(0, 8)) {
      const row = document.createElement('li');
      row.className = 'border-b border-white/10 pb-2';
      const anchor = safeLink(item.source_url || item.oa_url, item.title || 'Untitled record');
      if (anchor) row.appendChild(anchor);
      const detail = document.createElement('span');
      detail.className = 'block text-xs text-white/50';
      detail.textContent = `${item.source || 'unknown'} · fetched ${item.fetched_at || timestamp}`;
      row.appendChild(detail);
      items.appendChild(row);
    }

    const linkHeading = document.createElement('p');
    linkHeading.className = 'text-xs text-white/60';
    linkHeading.textContent = 'Catalog and portal fallbacks are navigation links; their holdings are unverified.';
    links.appendChild(linkHeading);
    for (const item of (data.resources || []).slice(0, 8)) {
      const row = document.createElement('p');
      const anchor = safeLink(item.source_url || item.oa_url, `${item.title || 'Resource'} (${item.source || 'fallback'})`);
      if (anchor) row.appendChild(anchor);
      links.appendChild(row);
    }
    const scholar = safeLink(data.scholar_verification_url, 'Verify this topic in Google Scholar');
    if (scholar) links.appendChild(scholar);
  } catch {
    document.getElementById('sec-scholarly')?.setAttribute('hidden', '');
  }
})();
