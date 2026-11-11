(async function showResearchEntry() {
  try {
    await window.archipelagoAuthReady;
    const response = await fetch('/api/auth/me', { cache: 'no-store' });
    if (!response.ok) return;
    const principal = await response.json();
    if (principal.authenticated && ['faculty', 'librarian', 'administrator'].includes(principal.role)) {
      document.getElementById('research-cta').style.display = 'block';
    }
  } catch (error) {
    console.warn('Research entry could not verify the session.', error);
  }
})();
