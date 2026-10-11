// Personalized learning roadmaps: one visible, selectable step at a time.
const SVG_NS = 'http://www.w3.org/2000/svg';
const STEP_WIDTH = 210;
const GRAPH_HEIGHT = 230;

function svgElement(tag, attributes = {}) {
    const element = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    return element;
}

function drawPersonalizedSVG(svg, nodes, _edges, cardId, anchorLabel) {
    if (!svg) return;
    svg.replaceChildren();
    const steps = (nodes || []).filter(node => node && node.id);
    const width = Math.max(320, steps.length * STEP_WIDTH + 60);
    svg.setAttribute('viewBox', `0 0 ${width} ${GRAPH_HEIGHT}`);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', `Learning roadmap to ${anchorLabel}. Select a step for details.`);
    svg.style.width = `${width}px`;
    svg.style.height = `${GRAPH_HEIGHT}px`;

    const defs = svgElement('defs');
    const marker = svgElement('marker', {
        id: `roadmap-arrow-${cardId}`, viewBox: '0 0 10 10',
        refX: '9', refY: '5', markerWidth: '8', markerHeight: '8', orient: 'auto',
    });
    marker.appendChild(svgElement('path', { d: 'M0,0 L10,5 L0,10 Z', fill: '#67e8f9' }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    const points = steps.map((node, index) => ({
        node, x: 70 + index * STEP_WIDTH, y: index % 2 ? 145 : 80,
    }));
    points.slice(0, -1).forEach((point, index) => {
        const next = points[index + 1];
        svg.appendChild(svgElement('path', {
            d: `M ${point.x + 32} ${point.y} L ${next.x - 36} ${next.y}`,
            stroke: '#67e8f9', 'stroke-width': 3, fill: 'none',
            'marker-end': `url(#roadmap-arrow-${cardId})`,
        }));
    });

    points.forEach(({ node, x, y }, index) => {
        const color = node.role === 'target' ? '#fbbf24'
            : node.status === 'review_gap' ? '#fb923c' : '#34d399';
        const group = svgElement('g', { transform: `translate(${x}, ${y})`,
            role: 'button', tabindex: '0', 'aria-label': `Step ${index + 1}: ${node.label || node.id}` });
        group.style.cursor = 'pointer';
        group.appendChild(svgElement('circle', { r: 27, fill: '#101827', stroke: color,
            'stroke-width': 3 }));
        const number = svgElement('text', { 'text-anchor': 'middle',
            'dominant-baseline': 'central', fill: color, 'font-size': 16, 'font-weight': 'bold' });
        number.textContent = String(index + 1);
        group.appendChild(number);
        const words = String(node.label || node.id).trim().split(/\s+/);
        const lines = [];
        while (words.length && lines.length < 3) {
            let line = words.shift();
            while (words.length && `${line} ${words[0]}`.length <= 22) line += ` ${words.shift()}`;
            lines.push(line);
        }
        if (words.length) lines[lines.length - 1] += '…';
        lines.forEach((line, lineIndex) => {
            const text = svgElement('text', { x: 0, y: 43 + lineIndex * 16,
                'text-anchor': 'middle', fill: '#f8fafc', 'font-size': 12,
                'font-weight': 'bold' });
            text.textContent = line;
            group.appendChild(text);
        });
        group.addEventListener('click', () => selectPersonalizedNode(cardId, node, anchorLabel));
        group.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectPersonalizedNode(cardId, node, anchorLabel);
            }
        });
        svg.appendChild(group);
    });
    if (steps.length) selectPersonalizedNode(cardId, steps[0], anchorLabel);
}

function selectPersonalizedNode(cardId, node, anchorLabel) {
    const title = document.getElementById(`pers-insp-title-${cardId}`);
    const summary = document.getElementById(`pers-insp-summary-${cardId}`);
    const badge = document.getElementById(`pers-insp-badge-${cardId}`);
    const citation = document.getElementById(`pers-insp-citation-${cardId}`);
    const actions = document.getElementById(`pers-insp-actions-${cardId}`);
    if (title) title.textContent = node.label || node.id;
    if (summary) summary.textContent = node.summary ||
        `Study ${node.label || node.id} before moving toward ${anchorLabel}.`;
    if (badge) badge.textContent = node.role === 'target' ? 'Goal' :
        node.status === 'review_gap' ? 'Review this step' : 'Mastered step';
    if (citation) citation.textContent = node.citation || '';
    if (!actions) return;
    actions.replaceChildren();
    if (node.doc_id) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'px-3 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-200 font-bold text-xs';
        button.textContent = `Open source · p. ${node.printed_page || node.page_number || 1}`;
        button.addEventListener('click', () => window.openPrerequisiteRemediationReader(
            node.doc_id, node.page_number || 1, node.label || node.id, node.summary || ''));
        actions.appendChild(button);
    }
}

window.drawPersonalizedSVG = drawPersonalizedSVG;
window.selectPersonalizedNode = selectPersonalizedNode;
export { drawPersonalizedSVG, selectPersonalizedNode };
