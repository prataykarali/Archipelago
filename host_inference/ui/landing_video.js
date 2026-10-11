/* Seamless landing video loop with requestAnimationFrame opacity fades. */
(() => {
  const video = document.getElementById('bg-hero-video');
  if (!video) return;

  const FADE_MS = 500;
  const FADE_BEFORE_END_SECONDS = 0.55;
  const RESTART_PAUSE_MS = 100;
  const VISIBLE_OPACITY = 1;
  let animationFrame = 0;
  let fadingOut = false;

  function fadeTo(targetOpacity, onComplete) {
    if (animationFrame) cancelAnimationFrame(animationFrame);
    const startingOpacity = Number.parseFloat(video.style.opacity || '0');
    const startedAt = performance.now();
    function frame(now) {
      const progress = Math.min((now - startedAt) / FADE_MS, 1);
      video.style.opacity = String(startingOpacity + (targetOpacity - startingOpacity) * progress);
      if (progress < 1) {
        animationFrame = requestAnimationFrame(frame);
      } else {
        animationFrame = 0;
        if (onComplete) onComplete();
      }
    }
    animationFrame = requestAnimationFrame(frame);
  }

  function fadeIn() {
    if (!fadingOut) fadeTo(VISIBLE_OPACITY);
  }

  video.addEventListener('loadeddata', fadeIn);
  video.addEventListener('play', fadeIn);
  video.addEventListener('timeupdate', () => {
    if (!fadingOut && Number.isFinite(video.duration) && video.duration - video.currentTime <= FADE_BEFORE_END_SECONDS) {
      fadingOut = true;
      fadeTo(0);
    }
  });
  video.addEventListener('ended', () => {
    if (animationFrame) cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    video.style.opacity = '0';
    window.setTimeout(() => {
      video.currentTime = 0;
      fadingOut = false;
      video.play().then(fadeIn).catch(() => { video.style.opacity = '0'; });
    }, RESTART_PAUSE_MS);
  });

  video.play().then(fadeIn).catch(() => { video.style.opacity = '0'; });
})();
