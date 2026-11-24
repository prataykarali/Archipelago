import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.2/+esm";

const AUTH_CHANNEL_NAME = "archipelago_auth_channel";
const LOGOUT_STORAGE_KEY = "archipelago_logout_broadcast";
const ACTIVE_PRINCIPAL_KEY = "archipelago_active_principal_id";
const authChannel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(AUTH_CHANNEL_NAME) : null;
const inFlightPageControllers = new Set();
let isHandlingLogout = false;
let isPageUnloading = false;

function handleGracefulPageShutdown() {
  if (isPageUnloading) return;
  isPageUnloading = true;
  for (const controller of Array.from(inFlightPageControllers)) {
    try { controller.abort(); } catch (_) {}
  }
  inFlightPageControllers.clear();
  try { authChannel?.close(); } catch (_) {}
}

window.addEventListener("pagehide", handleGracefulPageShutdown);
window.addEventListener("beforeunload", handleGracefulPageShutdown);

function readCookie(name) {
  const match = document.cookie.match(new RegExp("(?:^|;\\s*)" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : "";
}

function syncActivePrincipal(principal) {
  const nextId = String(principal?.id || principal?.user_id || principal?.username || "");
  if (!nextId) return;
  try {
    const prevId = sessionStorage.getItem(ACTIVE_PRINCIPAL_KEY);
    if (prevId && prevId !== nextId) {
      sessionStorage.removeItem("archipelago_research_state_v1");
      sessionStorage.removeItem("archipelago_academic_graph_state_v1");
    }
    sessionStorage.setItem(ACTIVE_PRINCIPAL_KEY, nextId);
  } catch (_) {}
}

window.archipelagoClearClientStorage = ({ includeHistory = false } = {}) => {
  try {
    const sessionKeys = [
      "archipelago_local_user",
      "archipelago_research_state_v1",
      "archipelago_academic_graph_state_v1",
      "archipelago_handoff_state",
      ACTIVE_PRINCIPAL_KEY,
    ];
    for (const k of sessionKeys) sessionStorage.removeItem(k);
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const k = sessionStorage.key(i);
      if (k && (k.startsWith("sb-") || (includeHistory && k.startsWith("archipelago_")))) {
        sessionStorage.removeItem(k);
      }
    }
  } catch (_) {}
  try {
    localStorage.removeItem("archipelago_local_user");
    localStorage.removeItem("archipelago_access_token");
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const k = localStorage.key(i);
      if (!k || k === LOGOUT_STORAGE_KEY) continue;
      if (k.startsWith("sb-") || (includeHistory && k.startsWith("archipelago_"))) {
        localStorage.removeItem(k);
      }
    }
  } catch (_) {}
};

function broadcastLogout() {
  try {
    authChannel?.postMessage({ type: "logout", ts: Date.now() });
  } catch (_) {}
  try {
    localStorage.setItem(LOGOUT_STORAGE_KEY, String(Date.now()));
  } catch (_) {}
}

async function handleRemoteLogout() {
  if (isHandlingLogout) return;
  isHandlingLogout = true;
  window.archipelagoClearClientStorage({ includeHistory: false });
  try {
    const { supabase } = await window.archipelagoAuthReady;
    if (supabase) await supabase.auth.signOut({ scope: "local" });
  } catch (_) {}
  if (location.pathname !== "/login") {
    location.replace("/login");
  }
}

if (authChannel) {
  authChannel.addEventListener("message", (event) => {
    if (event.data?.type === "logout") handleRemoteLogout();
  });
}
window.addEventListener("storage", (event) => {
  if (event.key === LOGOUT_STORAGE_KEY && event.newValue) handleRemoteLogout();
});

window.archipelagoPurgeMyData = async () => {
  window.archipelagoClearClientStorage({ includeHistory: true });
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
  try {
    await fetch("/api/auth/session", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
};

window.archipelagoLogout = async ({ redirectUrl = "/login", clearHistory = false } = {}) => {
  if (isHandlingLogout) return;
  isHandlingLogout = true;
  window.archipelagoClearClientStorage({ includeHistory: clearHistory });
  broadcastLogout();
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
  try {
    await fetch("/api/auth/session", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
  try {
    const { supabase } = await window.archipelagoAuthReady;
    if (supabase) await supabase.auth.signOut();
  } catch (_) {}
  location.replace(redirectUrl);
};

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
    const parsed = new URL(target, location.origin);
    if (parsed.origin !== location.origin || !parsed.pathname.startsWith("/api/")) return nativeFetch(input, init);
    const { data } = await supabase.auth.getSession();
    const headers = new Headers(init.headers || (typeof input === "string" ? undefined : input.headers));
    headers.set("X-Requested-With", "XMLHttpRequest");
    const csrfCookie = readCookie("archipelago_csrf") || readCookie("csrf_token");
    if (csrfCookie && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", csrfCookie);
    }
    if (data.session?.access_token) headers.set("Authorization", `Bearer ${data.session.access_token}`);
    return nativeFetch(input, { ...init, headers });
  };
  return { config, supabase };
})();

window.archipelagoAuthorizePage = async (roles) => {
  const { supabase } = await window.archipelagoAuthReady;
  const response = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) {
    window.archipelagoClearClientStorage({ includeHistory: false });
    if (supabase) await supabase.auth.signOut().catch(() => {});
    location.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
    return null;
  }
  const principal = await response.json();
  syncActivePrincipal(principal);
  if (!roles.includes(principal.role)) {
    location.replace("/library");
    return null;
  }
  return principal;
};

const IDLE_TIMEOUT_MS = 3600000;
let idleTimer;
const expire = async () => {
  const next = encodeURIComponent(location.pathname + location.search);
  await window.archipelagoLogout({ redirectUrl: `/login?timeout=1&next=${next}` });
};
const resetIdle = () => {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(expire, IDLE_TIMEOUT_MS);
};
window.archipelagoTouchSession = resetIdle;
for (const eventName of ["pointerdown", "keydown", "touchstart", "scroll", "wheel"]) {
  window.addEventListener(eventName, resetIdle, { passive: true });
}
resetIdle();
