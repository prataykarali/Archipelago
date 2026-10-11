/* Word and letter reveals matching the landing's staggered motion design. */
(() => {
  const targets = document.querySelectorAll('[data-text-animation]');
  if (!targets.length) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  targets.forEach(target => {
    const original = target.textContent.trim();
    const byLetter = target.dataset.divideBy === 'letter';
    const pieces = byLetter ? Array.from(original) : original.split(/\s+/);
    const stagger = byLetter ? 0.02 : 0.05;
    const start = Number.parseFloat(target.dataset.delay || '0') || 0;
    target.replaceChildren();
    const fragment = document.createDocumentFragment();
    const accessibleText = document.createElement('span');
    accessibleText.className = 'sr-only';
    accessibleText.textContent = original;
    fragment.appendChild(accessibleText);
    pieces.forEach((piece, index) => {
      const clip = document.createElement('span');
      const inner = document.createElement('span');
      clip.className = 'text-reveal-token';
      clip.setAttribute('aria-hidden', 'true');
      clip.style.setProperty('--reveal-delay', `${start + stagger * index}s`);
      inner.textContent = byLetter ? (piece === ' ' ? '\u00a0' : piece) : `${piece}\u00a0`;
      clip.appendChild(inner);
      fragment.appendChild(clip);
    });
    target.appendChild(fragment);
  });

  document.documentElement.classList.add('text-animation-ready');
  if (reducedMotion || !('IntersectionObserver' in window)) {
    targets.forEach(target => target.classList.add('text-animation-visible'));
    return;
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('text-animation-visible');
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.15 });
  targets.forEach(target => observer.observe(target));
})();
