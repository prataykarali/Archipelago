import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

window.archipelagoAuthReady = (async () => {
  const response = await fetch("/api/auth/config", { cache: "no-store" });
  const config = await response.json();
  if (!config.configured) return { config, supabase: null };
  const supabase = createClient(config.url, config.publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const target = typeof input === "string" ? input : input.url;
    if (!new URL(target, location.origin).pathname.startsWith("/api/")) return nativeFetch(input, init);
    const { data } = await supabase.auth.getSession();
    const headers = new Headers(init.headers || (typeof input === "string" ? undefined : input.headers));
    if (data.session) headers.set("Authorization", `Bearer ${data.session.access_token}`);
    return nativeFetch(input, { ...init, headers });
  };
  return { config, supabase };
})();

window.archipelagoAuthorizePage = async (roles) => {
  const { supabase } = await window.archipelagoAuthReady;
  const { data } = supabase ? await supabase.auth.getSession() : { data: {} };
  if (!data.session) {
    location.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
    return null;
  }
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  if (!response.ok) {
    await supabase.auth.signOut();
    location.replace("/login");
    return null;
  }
  const principal = await response.json();
  if (!roles.includes(principal.role)) {
    location.replace("https://archipelago-blond.vercel.app/library");
    return null;
  }
  return principal;
};

const IDLE_TIMEOUT_MS = 300000;
let idleTimer;
const expire = async () => {
  const { supabase } = await window.archipelagoAuthReady;
  if (supabase) await supabase.auth.signOut();
  location.replace(`/login?timeout=1&next=${encodeURIComponent(location.pathname + location.search)}`);
};
window.archipelagoTouchSession = () => {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(expire, IDLE_TIMEOUT_MS);
};
for (const eventName of ["pointerdown", "keydown", "touchstart", "scroll", "wheel"]) {
  window.addEventListener(eventName, window.archipelagoTouchSession, { passive: true });
}
window.archipelagoTouchSession();
