// D11-B-UX: Pure graph node deduplication by canonical concept ID
// and collision-free SVG label placement for topology rendering.

function canonicalConceptId(item, fallback = '') {
    if (!item) return String(fallback || '').toLowerCase();
    if (typeof item === 'string') {
        return item.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || String(fallback || '').toLowerCase();
    }
    const raw = item.canonical_id || item.concept_id || item.id || item.label || item.name || fallback || '';
    return String(raw).trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || String(fallback || '').toLowerCase();
}

function buildDeduplicatedTopology({
    anchor,
    prereqs = [],
    unlocks = [],
    related = [],
    getNodeId,
    getNodeLabel,
    getNodeSummary,
    width = 300,
    height = 160,
    large = false,
}) {
    const idOf = typeof getNodeId === 'function' ? getNodeId : (n, fb) => (typeof n === 'string' ? n : (n?.id || n?.label || fb));
    const labelOf = typeof getNodeLabel === 'function' ? getNodeLabel : (n) => (typeof n === 'string' ? n : (n?.label || n?.name || n?.id || ''));
    const summaryOf = typeof getNodeSummary === 'function' ? getNodeSummary : (n) => (typeof n === 'object' && n ? (n.summary || n.description || '') : '');

    const cx = width / 2;
    const cy = height / 2 + (large ? 4 : 0);

    const nodeMap = new Map();
    const edges = [];
    const seenEdgeKeys = new Set();

    const anchorCanon = canonicalConceptId(anchor, 'anchor');
    const anchorNode = {
        canonicalId: anchorCanon,
        id: idOf(anchor, 'anchor'),
        label: labelOf(anchor),
        summary: summaryOf(anchor),
        x: cx,
        y: cy,
        type: 'anchor',
        relations: ['anchor'],
        data: anchor,
    };
    nodeMap.set(anchorCanon, anchorNode);

    const buckets = { prereq: [], unlock: [], related: [] };

    const ingest = (items, relType, prefix) => {
        (items || []).forEach((item, idx) => {
            if (!item) return;
            const canon = canonicalConceptId(item, `${prefix}_${idx}`);
            if (!canon || canon === anchorCanon) return;

            let node = nodeMap.get(canon);
            if (!node) {
                node = {
                    canonicalId: canon,
                    id: idOf(item, `${prefix}${idx}`),
                    label: labelOf(item),
                    summary: summaryOf(item),
                    x: cx,
                    y: cy,
                    type: relType,
                    relations: [relType],
                    data: item,
                };
                nodeMap.set(canon, node);
                buckets[relType].push(node);
            } else if (!node.relations.includes(relType)) {
                node.relations.push(relType);
            }

            const edgeKey = `${canon}:${relType}`;
            if (!seenEdgeKeys.has(edgeKey)) {
                seenEdgeKeys.add(edgeKey);
                edges.push({
                    targetCanonicalId: canon,
                    type: relType,
                    relationIndex: node.relations.indexOf(relType),
                });
            }
        });
    };

    ingest(prereqs, 'prereq', 'p');
    ingest(unlocks, 'unlock', 'u');
    ingest(related, 'related', 'r');

    // Position each unique node cleanly by its primary role bucket
    const preX = Math.max(64, cx - Math.min(cx - 48, large ? 200 : 130));
    const unX = Math.min(width - 64, cx + Math.min(width - cx - 48, large ? 200 : 130));

    const pN = Math.max(buckets.prereq.length, 1);
    buckets.prereq.forEach((node, i) => {
        node.x = preX;
        node.y = (height / (pN + 1)) * (i + 1);
    });

    const uN = Math.max(buckets.unlock.length, 1);
    buckets.unlock.forEach((node, i) => {
        node.x = unX;
        node.y = (height / (uN + 1)) * (i + 1);
    });

    buckets.related.forEach((node, i) => {
        const top = i % 2 === 0;
        const slot = Math.floor(i / 2);
        const xOff = (slot - 0.25) * (large ? 76 : 54);
        node.x = Math.max(48, Math.min(width - 48, cx + xOff + (top ? -22 : 22)));
        node.y = top
            ? Math.max(22, cy - (large ? 64 : 50))
            : Math.min(height - 22, cy + (large ? 64 : 50));
    });

    const nodes = Array.from(nodeMap.values());
    const resolvedEdges = edges.map((edge) => ({
        ...edge,
        node: nodeMap.get(edge.targetCanonicalId),
    })).filter((edge) => Boolean(edge.node));

    return { nodes, edges: resolvedEdges, cx, cy };
}

function resolveLabelPositions(labelSpecs, width, height) {
    const padX = 8;
    const minY = 12;
    const maxY = Math.max(minY + 12, height - 6);
    const labelH = 14;
    const placed = [];

    const overlaps = (a, b) => !(
        a.x2 + 4 < b.x1
        || a.x1 - 4 > b.x2
        || a.y2 + 2 < b.y1
        || a.y1 - 2 > b.y2
    );

    return (labelSpecs || []).map((spec) => {
        const halfW = Math.max(12, spec.textWidth / 2);
        let x = spec.x;
        if (x - halfW < padX) x = padX + halfW;
        if (x + halfW > width - padX) x = width - padX - halfW;

        const baseBelow = spec.y + spec.radius + 14;
        const baseAbove = spec.y - spec.radius - 6;
        const candidates = [
            baseBelow <= maxY ? baseBelow : baseAbove,
            baseAbove >= minY ? baseAbove : baseBelow,
            baseBelow + labelH,
            baseAbove - labelH,
            baseBelow + labelH * 2,
            baseAbove - labelH * 2,
        ].map((cy) => Math.max(minY, Math.min(maxY, cy)));

        let chosenY = candidates[0];
        for (const candY of candidates) {
            const box = {
                x1: x - halfW,
                x2: x + halfW,
                y1: candY - labelH + 3,
                y2: candY + 3,
            };
            if (!placed.some((p) => overlaps(box, p))) {
                chosenY = candY;
                placed.push(box);
                return { ...spec, labelX: x, labelY: chosenY };
            }
        }

        // Fallback: keep clamped candidate and record box
        placed.push({
            x1: x - halfW,
            x2: x + halfW,
            y1: chosenY - labelH + 3,
            y2: chosenY + 3,
        });
        return { ...spec, labelX: x, labelY: chosenY };
    });
}

function computeEdgeEndpoints(x1, y1, x2, y2, r1 = 10, r2 = 14, pad = 4) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy);
    if (!Number.isFinite(dist) || dist <= 1e-3) {
        return { sx: x1, sy: y1, ex: x2, ey: y2 };
    }
    const ux = dx / dist;
    const uy = dy / dist;
    const maxTrim = Math.max(0, dist - 6);
    const startTrim = Math.min(r1 + 2, maxTrim * 0.45);
    const endTrim = Math.min(r2 + pad, maxTrim * 0.55);
    return {
        sx: Number((x1 + ux * startTrim).toFixed(2)),
        sy: Number((y1 + uy * startTrim).toFixed(2)),
        ex: Number((x2 - ux * endTrim).toFixed(2)),
        ey: Number((y2 - uy * endTrim).toFixed(2)),
    };
}

function buildArrowMarkerDefs(
    sid,
    {
        size = 8,
        prereqColor = '#c084fc',
        unlockColor = '#22d3ee',
        relatedColor = '#fbbf24',
    } = {},
) {
    const mk = (id, color) => (
        `<marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" `
        + `markerWidth="${size}" markerHeight="${size}" markerUnits="userSpaceOnUse" `
        + `orient="auto" overflow="visible">`
        + `<path d="M 0 1.2 L 9.5 5 L 0 8.8 L 2.2 5 Z" fill="${color}" stroke="${color}" stroke-width="0.6" stroke-linejoin="round"/>`
        + `</marker>`
    );
    return [
        mk(`arr-pre-${sid}`, prereqColor),
        mk(`arr-unl-${sid}`, unlockColor),
        mk(`arr-rel-${sid}`, relatedColor),
    ].join('\n');
}

function clearStaleInspectorState(isReset = false) {
    const sidebarSvg = document.getElementById('sidebar-svg-map');
    const bottomSvg = document.getElementById('bottom-svg-map');
    if (sidebarSvg) sidebarSvg.innerHTML = '';
    if (bottomSvg) bottomSvg.innerHTML = '';

    const nodeTitle = document.getElementById('graph-node-title');
    const nodeSummary = document.getElementById('graph-node-summary');
    const nodeType = document.getElementById('graph-node-type');
    const nodeDiff = document.getElementById('graph-node-diff');
    if (nodeTitle) nodeTitle.textContent = isReset ? 'Loading…' : 'No active concept';
    if (nodeSummary) nodeSummary.textContent = isReset ? '' : 'No indexed concept anchored for this response.';
    if (nodeType) nodeType.textContent = isReset ? 'Pending' : 'No Match';
    if (nodeDiff) nodeDiff.textContent = '—';

    const emptyBadgeHtml = '<span class="text-[10px] text-gray-500 italic">None indexed</span>';
    ['okf-rel-requires', 'okf-rel-unlocks', 'okf-rel-connects'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = emptyBadgeHtml;
    });

    if (isReset) {
        const citationsPlac = document.getElementById('citations-placeholder');
        const citationsList = document.getElementById('citations-list');
        const logsPlac = document.getElementById('logs-placeholder');
        const logsList = document.getElementById('logs-list');
        if (citationsPlac) {
            citationsPlac.classList.remove('hidden');
            citationsPlac.textContent = 'No citations retrieved yet.';
        }
        if (citationsList) {
            citationsList.classList.add('hidden');
            citationsList.innerHTML = '';
        }
        if (logsPlac) {
            logsPlac.classList.remove('hidden');
            logsPlac.textContent = 'No logs captured yet.';
        }
        if (logsList) {
            logsList.classList.add('hidden');
            logsList.innerHTML = '';
        }
        const evList = document.getElementById('evidence-list') || document.getElementById('inspector-evidence-list');
        if (evList) evList.innerHTML = '';
        const traceContent = document.getElementById('trace-content')
            || document.getElementById('inspector-trace-content')
            || document.getElementById('inspector-trace-list');
        if (traceContent) traceContent.innerHTML = '';
    }
}

function ensureSidebarEdgeLegend() {
    const container = document.getElementById('sidebar-svg-map-container');
    if (!container || !container.parentNode) return;
    let legend = document.getElementById('sidebar-graph-legend');
    if (!legend) {
        legend = document.createElement('div');
        legend.id = 'sidebar-graph-legend';
        legend.className = 'graph-edge-legend-bar';
        legend.setAttribute('aria-label', 'Graph edge legend');
        legend.innerHTML = `
            <span class="graph-legend-item" data-relation="REQUIRES"><span class="graph-legend-swatch swatch-requires" aria-hidden="true">→</span><span>REQUIRES</span></span>
            <span class="graph-legend-item" data-relation="UNLOCKS"><span class="graph-legend-swatch swatch-unlocks" aria-hidden="true">→</span><span>UNLOCKS</span></span>
            <span class="graph-legend-item" data-relation="RELATED_TO"><span class="graph-legend-swatch swatch-related" aria-hidden="true">⇢</span><span>RELATED_TO</span></span>
        `;
        container.parentNode.insertBefore(legend, container.nextSibling);
    }
}

function renderTopologyPlaceholder(placeholder, isReset = false) {
    if (!placeholder) return;
    placeholder.classList.remove('hidden');
    const heading = isReset ? 'Resolving Concept Graph…' : 'No Verified Graph Match';
    const sub = isReset
        ? 'Cleared previous turn state while checking indexed concepts.'
        : 'No indexed concept node is anchored for this response.';
    placeholder.innerHTML = `
        <div class="p-4 rounded-xl bg-white/5 border border-white/10 text-center flex flex-col items-center gap-2">
            <i class="fa-solid fa-circle-nodes text-gray-500 text-lg"></i>
            <p class="text-xs font-semibold text-gray-300">${heading}</p>
            <p class="text-[11px] text-gray-400">${sub}</p>
        </div>
    `;
}

export {
    buildArrowMarkerDefs,
    buildDeduplicatedTopology,
    canonicalConceptId,
    clearStaleInspectorState,
    computeEdgeEndpoints,
    ensureSidebarEdgeLegend,
    renderTopologyPlaceholder,
    resolveLabelPositions,
};
