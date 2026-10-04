/** Optional browser-owned learning memory; no account history or automatic consent. */
export function renderLearningMemoryControls(container) {
    if (!container || container.querySelector('[data-learning-memory]')) return;
    const details = document.createElement('details');
    details.dataset.learningMemory = 'true';
    details.className = 'text-xs text-gray-300 my-3';
    const summary = document.createElement('summary');
    summary.textContent = 'Learning memory (optional)';
    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'mr-2';
    try { checkbox.checked = localStorage.getItem('archipelago_remember_learning') === '1'; } catch (_) {}
    label.append(checkbox, ' Remember mastery on this browser for 30 days');
    const note = document.createElement('p');
    note.textContent = 'Saves concept mastery and preference only—not answers. Normal mode does not save learning memory. Hosted memory can reset on a deployment or container replacement. Staff may see anonymous gap counts only when at least five consenting browser profiles share a gap.';
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    const forget = document.createElement('button');
    forget.type = 'button';
    forget.className = 'px-3 py-2 mt-2 rounded border border-white/20';
    forget.textContent = 'Forget saved learning';
    async function disable() {
        const response = await fetch('/api/chat/learning-memory', { method: 'DELETE' });
        if (!response.ok) throw new Error('Could not delete saved learning. Please retry.');
        localStorage.removeItem('archipelago_remember_learning');
        checkbox.checked = false;
        status.textContent = 'Saved learning deleted.';
    }
    checkbox.addEventListener('change', async () => {
        try {
            if (checkbox.checked) {
                localStorage.setItem('archipelago_remember_learning', '1');
                status.textContent = 'The next personalized diagnostic will remember mastery.';
            } else {
                await disable();
            }
        } catch (error) { status.textContent = error.message; }
    });
    forget.addEventListener('click', async () => {
        forget.disabled = true;
        try { await disable(); } catch (error) { status.textContent = error.message; }
        finally { forget.disabled = false; }
    });
    details.append(summary, label, note, forget, status);
    container.appendChild(details);
}

export function rememberParameter() {
    try { return localStorage.getItem('archipelago_remember_learning') === '1' ? '&remember=1' : ''; }
    catch (_) { return ''; }
}

export function renderGapResources(container, resources) {
    if (!container || !Array.isArray(resources) || !resources.length) return;
    const details = document.createElement('details');
    details.className = 'text-xs text-gray-300 p-3';
    const summary = document.createElement('summary');
    summary.textContent = 'Physical resources for assessed gaps';
    details.appendChild(summary);
    for (const resource of resources) {
        const article = document.createElement('article');
        const heading = document.createElement('strong');
        heading.textContent = resource.title;
        const why = document.createElement('p');
        why.textContent = resource.why;
        article.append(heading, why);
        for (const key of ['authors', 'call_number', 'location', 'rack', 'shelf']) {
            if (!resource[key]) continue;
            const line = document.createElement('p');
            line.textContent = `${key.replaceAll('_', ' ')}: ${resource[key]}`;
            article.appendChild(line);
        }
        if (Number.isInteger(resource.available_copies) && Number.isInteger(resource.total_copies)) {
            const copies = document.createElement('p');
            copies.textContent = `${resource.available_copies}/${resource.total_copies} available in imported snapshot—confirm in OPAC.`;
            article.appendChild(copies);
        }
        details.appendChild(article);
    }
    container.appendChild(details);
}