import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const AUTH_CHANNEL_NAME = "archipelago_auth_channel";
const LOGOUT_STORAGE_KEY = "archipelago_logout_broadcast";
const ACTIVE_PRINCIPAL_KEY = "archipelago_active_principal_id";
const authChannel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(AUTH_CHANNEL_NAME) : null;
const inFlightControllers = new Set();
let isHandlingLogout = false;
let isPageUnloading = false;

function handleGracefulPageShutdown(event) {
  const persisted = Boolean(event?.persisted);
  if (isPageUnloading && !persisted) return;
  if (!persisted) isPageUnloading = true;
  for (const controller of Array.from(inFlightControllers)) {
    try { controller.abort(); } catch (_) {}
  }
  inFlightControllers.clear();
  if (!persisted) {
    try { authChannel?.close(); } catch (_) {}
  }
}

window.addEventListener("pagehide", handleGracefulPageShutdown);
window.addEventListener("beforeunload", handleGracefulPageShutdown);
window.addEventListener("pageshow", () => { isPageUnloading = false; });

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
      sessionStorage.removeItem("archipelago_research_state_v2");
      sessionStorage.removeItem("archipelago_research_pending_v2");
      sessionStorage.removeItem("archipelago_academic_graph_state_v1");
    }
    sessionStorage.setItem(ACTIVE_PRINCIPAL_KEY, nextId);
  } catch (_) {}
}

window.archipelagoClearClientStorage = ({ includeHistory = false } = {}) => {
  try {
    const keys = [
      "archipelago_local_user",
      "archipelago_research_state_v1",
      "archipelago_research_state_v2",
      "archipelago_research_pending_v2",
      "archipelago_academic_graph_state_v1",
      "archipelago_handoff_state",
      ACTIVE_PRINCIPAL_KEY,
    ];
    for (const k of keys) sessionStorage.removeItem(k);
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
  try { authChannel?.postMessage({ type: "logout", ts: Date.now() }); } catch (_) {}
  try { localStorage.setItem(LOGOUT_STORAGE_KEY, String(Date.now())); } catch (_) {}
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
    if (event?.data?.type === "logout") void handleRemoteLogout();
  });
}
window.addEventListener("storage", (event) => {
  if (event.key === LOGOUT_STORAGE_KEY && event.newValue) void handleRemoteLogout();
});

window.archipelagoLogout = async ({ redirectUrl = "/login" } = {}) => {
  if (isHandlingLogout) return;
  isHandlingLogout = true;
  broadcastLogout();
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
  try {
    const { supabase } = await window.archipelagoAuthReady;
    if (supabase) await supabase.auth.signOut({ scope: "local" });
  } catch (_) {}
  window.archipelagoClearClientStorage({ includeHistory: true });
  const target = typeof redirectUrl === "string" && redirectUrl.startsWith("/") && !redirectUrl.startsWith("//")
    ? redirectUrl
    : "/login";
  location.replace(target);
};

window.archipelagoPurgeMyData = async () => {
  const response = await fetch("/api/chat/history", {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-Requested-With": "XMLHttpRequest" },
  });
  window.archipelagoClearClientStorage({ includeHistory: true });
  return response.ok;
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
    const targetUrl = new URL(target, location.origin);
    if (!targetUrl.pathname.startsWith("/api/")) return nativeFetch(input, init);
    const { data } = await supabase.auth.getSession();
    const headers = new Headers(init.headers || (typeof input === "string" ? undefined : input.headers));
    if (data.session && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${data.session.access_token}`);
    }
    const method = (init.method || "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers.set("X-Requested-With", "XMLHttpRequest");
      const csrf = readCookie("archipelago_csrf");
      if (csrf && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", csrf);
    }
    let controller = null;
    const reqInit = { ...init, headers, credentials: init.credentials || "same-origin" };
    if (!reqInit.signal) {
      controller = new AbortController();
      inFlightControllers.add(controller);
      reqInit.signal = controller.signal;
    }
    try {
      return await nativeFetch(input, reqInit);
    } finally {
      if (controller) inFlightControllers.delete(controller);
    }
  };
  return { config, supabase };
})();

window.archipelagoAuthorizePage = async (roles) => {
  const { supabase } = await window.archipelagoAuthReady;
  const { data } = supabase ? await supabase.auth.getSession() : { data: {} };
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  if (!response.ok) {
    if (supabase && data?.session) await supabase.auth.signOut({ scope: "local" });
    window.archipelagoClearClientStorage({ includeHistory: false });
    location.replace(`/login?next=${encodeURIComponent(location.pathname + location.search)}`);
    return null;
  }
  const principal = await response.json();
  syncActivePrincipal(principal);
  if (!roles.includes(principal.role)) {
    location.replace("https://archipelago-blond.vercel.app/library");
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
window.archipelagoTouchSession = () => {
  const page = document.body?.dataset.researchPage;
  const publicExample = new URLSearchParams(location.search).has("example");
  if (page === "rankings" || (publicExample && ["paper", "topic"].includes(page))) return;
  clearTimeout(idleTimer);
  idleTimer = setTimeout(expire, IDLE_TIMEOUT_MS);
};
for (const eventName of ["pointerdown", "keydown", "touchstart", "scroll", "wheel"]) {
  window.addEventListener(eventName, window.archipelagoTouchSession, { passive: true });
}
window.archipelagoTouchSession();
