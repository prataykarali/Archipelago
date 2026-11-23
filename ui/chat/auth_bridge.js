import "./user_management_modal.js";
import "./password_visibility.js";

const API_PREFIX = "/api/";
const LOGIN_PATH = "/login";
// Pages anyone may read without signing in.
const OPEN_PATHS = new Set(["/", "/landing", "/library"]);
const IDLE_TIMEOUT_MS = 3600000;
const STUDENT_ROUTES = new Set(["/chat", "/library"]);
const STAFF_ROUTES = new Set(["/chat", "/library", "/graph", "/research"]);
const AUTH_CHANNEL_NAME = "archipelago_auth_channel";
const LOGOUT_STORAGE_KEY = "archipelago_logout_broadcast";
const ACTIVE_PRINCIPAL_KEY = "archipelago_active_principal_id";
const AUTH_CONFIG_CACHE_KEY = "archipelago_auth_config_v1";
const AUTH_ME_CACHE_KEY = "archipelago_me_cache_v1";
const AUTH_CONFIG_TTL_MS = 600000;
const AUTH_ME_TTL_MS = 120000;
const SUPABASE_CDN_TIMEOUT_MS = 3500;
let cachedAccessToken = "";

async function loadSupabaseCreateClient() {
  try {
    const mod = await Promise.race([
      import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm"),
      new Promise((_, reject) => setTimeout(() => reject(new Error("supabase-cdn-timeout")), SUPABASE_CDN_TIMEOUT_MS)),
    ]);
    return mod?.createClient || null;
  } catch (_) {
    return null;
  }
}

function readCachedMe() {
  try {
    const raw = sessionStorage.getItem(AUTH_ME_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.ts && (Date.now() - parsed.ts) < AUTH_ME_TTL_MS && parsed.principal?.authenticated) {
      return parsed.principal;
    }
  } catch (_) {}
  return null;
}

function writeCachedMe(principal) {
  try {
    if (principal && principal.authenticated) {
      sessionStorage.setItem(AUTH_ME_CACHE_KEY, JSON.stringify({ ts: Date.now(), principal }));
    } else {
      sessionStorage.removeItem(AUTH_ME_CACHE_KEY);
    }
  } catch (_) {}
}

const authChannel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel(AUTH_CHANNEL_NAME) : null;
const inFlightPageControllers = new Set();
let isHandlingLogout = false;
let isPageUnloading = false;

function handleGracefulPageShutdown(event) {
  const persisted = Boolean(event?.persisted);
  if (isPageUnloading && !persisted) return;
  if (!persisted) isPageUnloading = true;
  for (const controller of Array.from(inFlightPageControllers)) {
    try { controller.abort(); } catch (_) {}
  }
  inFlightPageControllers.clear();
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
    const sessionKeys = [
      "archipelago_local_user",
      AUTH_ME_CACHE_KEY,
      "archipelago_research_state_v1",
      "archipelago_research_state_v2",
      "archipelago_research_pending_v2",
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
  window.archipelagoUserId = null;
  window.archipelagoClearClientStorage({ includeHistory: false });
  try {
    const { supabase } = await window.archipelagoAuthReady;
    if (supabase) await supabase.auth.signOut({ scope: "global" });
  } catch (_) {}
  if (window.location.pathname !== LOGIN_PATH) {
    window.location.replace(LOGIN_PATH);
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
    await fetch("/api/chat/history", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  } catch (_) {}
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

window.archipelagoLogout = async ({ redirectUrl = LOGIN_PATH, clearHistory = false } = {}) => {
  if (isHandlingLogout) return;
  isHandlingLogout = true;
  window.archipelagoUserId = null;
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
    if (supabase) await supabase.auth.signOut({ scope: "global" });
  } catch (_) {}
  // Append ?logout=1 to the redirect so the login page knows not to auto-redirect
  // back (which would cause a loop when the session is fully cleared).
  const finalUrl = redirectUrl === LOGIN_PATH
    ? `${LOGIN_PATH}?logout=1`
    : redirectUrl;
  window.location.replace(finalUrl);
};

async function loadConfig() {
  try {
    const raw = sessionStorage.getItem(AUTH_CONFIG_CACHE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.ts && (Date.now() - parsed.ts) < AUTH_CONFIG_TTL_MS && parsed.config) {
        return parsed.config;
      }
    }
  } catch (_) {}
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    const response = await fetch("/api/auth/config", { cache: "no-store", signal: controller.signal });
    clearTimeout(timer);
    if (response.ok) {
      const cfg = await response.json();
      try {
        sessionStorage.setItem(AUTH_CONFIG_CACHE_KEY, JSON.stringify({ ts: Date.now(), config: cfg }));
      } catch (_) {}
      return cfg;
    }
  } catch (err) {
    console.warn("Auth config fetch failed, using fallback:", err);
  }
  return { configured: false, required: true };
}

function getApiUrl(input) {
  const target = typeof input === "string" ? input : input.url;
  const parsed = new URL(target, window.location.origin);
  return parsed.origin === window.location.origin && parsed.pathname.startsWith(API_PREFIX) ? parsed : null;
}

async function addAccessToken(supabase, input, init = {}) {
  const apiUrl = getApiUrl(input);
  if (!apiUrl) return init;
  const headers = new Headers(init.headers || (typeof input === "string" ? undefined : input.headers));
  headers.set("X-Requested-With", "XMLHttpRequest");
  const csrfCookie = readCookie("archipelago_csrf") || readCookie("csrf_token");
  if (csrfCookie && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", csrfCookie);
  }
  if (apiUrl.pathname === "/api/readiness" && !headers.has("X-Background-Poll")) {
    headers.set("X-Background-Poll", "1");
  }
  if (!headers.has("Authorization") && cachedAccessToken) {
    headers.set("Authorization", `Bearer ${cachedAccessToken}`);
  } else if (!headers.has("Authorization") && supabase) {
    try {
      const { data } = await supabase.auth.getSession();
      if (data.session?.access_token) {
        cachedAccessToken = data.session.access_token;
        headers.set("Authorization", `Bearer ${cachedAccessToken}`);
      }
    } catch (_) {}
  }
  return { ...init, headers };
}

window.archipelagoAuthReady = (async () => {
  const config = await loadConfig();
  const originalFetch = window.fetch.bind(window);
  let supabase = null;
  if (config.configured) {
    const createClient = await loadSupabaseCreateClient();
    if (createClient) {
      supabase = createClient(config.url, config.publishableKey, {
        auth: { persistSession: true, autoRefreshToken: true },
      });
      supabase.auth.onAuthStateChange((_event, session) => {
        cachedAccessToken = session?.access_token || "";
      });
      supabase.auth.getSession().then(({ data }) => {
        cachedAccessToken = data?.session?.access_token || "";
      }).catch(() => {});
    }
  }
  window.fetch = async (input, init) => {
    const apiUrl = getApiUrl(input);
    if (apiUrl?.pathname === "/api/readiness" && document.hidden) {
      return new Response(JSON.stringify({ ready: true, paused: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return originalFetch(input, await addAccessToken(supabase, input, init));
  };
  return { config, supabase };
})();

window.archipelagoRequireSession = async () => {
  const cached = readCachedMe();
  if (cached) {
    window.archipelagoUserId = cached.id || cached.user_id;
    syncActivePrincipal(cached);
    // Revalidate in background without blocking page switch
    fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" })
      .then(r => (r.ok ? r.json() : null))
      .then(p => { if (p?.authenticated) writeCachedMe(p); })
      .catch(() => {});
    return { user: cached };
  }
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!config?.required) return null;
  try {
    let session = null;
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      session = data?.session || null;
      if (session?.access_token) cachedAccessToken = session.access_token;
    }
    const response = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
    if (response.ok) {
      const principal = await response.json();
      if (principal?.authenticated) {
        writeCachedMe(principal);
        window.archipelagoUserId = principal.id || principal.user_id;
        syncActivePrincipal(principal);
        return session || { user: principal };
      }
    }
  } catch (_) {}
  window.archipelagoClearClientStorage({ includeHistory: false });
  if (OPEN_PATHS.has(window.location.pathname.replace(/\/$/, "") || "/")) return null;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`${LOGIN_PATH}?next=${next}`);
  return null;
};

if (["/chat", "/graph"].includes(window.location.pathname.replace(/\/$/, "")) || window.location.pathname.startsWith('/research')) {
  let idleTimer;
  const expire = async () => {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    await window.archipelagoLogout({ redirectUrl: `/login?timeout=1&next=${next}` });
  };
  const resetIdle = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(expire, IDLE_TIMEOUT_MS);
  };
  for (const eventName of ['pointerdown', 'keydown', 'touchstart', 'scroll', 'wheel']) {
    window.addEventListener(eventName, resetIdle, { passive: true });
  }
  resetIdle();
}

window.archipelagoAuthorizePage = async (allowedRoles) => {
  const cached = readCachedMe();
  if (cached) {
    syncActivePrincipal(cached);
    if (!allowedRoles.includes(cached.role)) {
      window.location.replace("/chat");
      return null;
    }
    return cached;
  }
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!config.required) return null;

  const response = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) {
    window.archipelagoClearClientStorage({ includeHistory: false });
    try { if (supabase) await supabase.auth.signOut(); } catch (_) {}
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`${LOGIN_PATH}?next=${next}`);
    return null;
  }
  const principal = await response.json();
  if (!principal?.authenticated) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`${LOGIN_PATH}?next=${next}`);
    return null;
  }
  writeCachedMe(principal);
  syncActivePrincipal(principal);
  if (!allowedRoles.includes(principal.role)) {
    window.location.replace("/chat");
    return null;
  }
  return principal;
};

window.archipelagoRouteForRole = (role, requestedPath) => {
  const allowed = role === "student" ? STUDENT_ROUTES : STAFF_ROUTES;
  return allowed.has(requestedPath) || (role !== 'student' && requestedPath.startsWith('/research/')) ? requestedPath : "/chat";
};

window.archipelagoMountNavigation = async () => {
  let principal = readCachedMe();
  if (!principal) {
    await window.archipelagoAuthReady;
    try {
      const response = await fetch("/api/auth/me", { credentials: "same-origin" });
      if (response.ok) {
        principal = await response.json();
        if (principal?.authenticated) writeCachedMe(principal);
      }
    } catch (err) {
      principal = null;
    }
  }
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!principal || !principal.authenticated || !principal.role) return;

  const existing = document.querySelector("#archipelago-role-navigation");
  if (existing) existing.remove();

  const nav = document.createElement("nav");
  nav.id = "archipelago-role-navigation";
  nav.setAttribute("aria-label", "Archipelago navigation");
  nav.style.cssText = "position:fixed;right:16px;top:16px;z-index:99999;display:flex;gap:8px;align-items:center;padding:6px 12px;border:1px solid rgba(255,255,255,.18);border-radius:999px;background:rgba(9,5,20,.88);backdrop-filter:blur(16px);font:500 12px 'Inter',system-ui;box-shadow:0 10px 30px rgba(0,0,0,0.5);";

  // Role badge
  const roleBadge = document.createElement("span");
  const roleColors = { administrator: "#ec4899", librarian: "#10b981", faculty: "#f59e0b", student: "#a78bfa" };
  roleBadge.style.cssText = `padding:3px 8px;border-radius:999px;background:${roleColors[principal.role] || "#a78bfa"}22;border:1px solid ${roleColors[principal.role] || "#a78bfa"}55;color:${roleColors[principal.role] || "#a78bfa"};font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:0.05em;`;
  roleBadge.textContent = `${principal.role}: ${principal.username || ""}`;
  nav.appendChild(roleBadge);

  const routes = principal.role === "student"
    ? [["Chat", "/chat"], ["Library", "/library"]]
    : [["Chat", "/chat"], ["Library", "/library"], ["Research", "/research"]];
  for (const [label, href] of routes) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    link.style.cssText = "color:rgba(255,255,255,0.85);text-decoration:none;padding:5px 8px;border-radius:6px;transition:all 0.2s;";
    link.onmouseenter = () => { link.style.color = "#ffffff"; link.style.background = "rgba(255,255,255,0.1)"; };
    link.onmouseleave = () => { link.style.color = "rgba(255,255,255,0.85)"; link.style.background = "transparent"; };
    nav.appendChild(link);
  }

  // If Librarian or Administrator, add User Management button
  if (principal.role === "librarian" || principal.role === "administrator") {
    const userMgmtBtn = document.createElement("button");
    userMgmtBtn.type = "button";
    userMgmtBtn.innerHTML = `<span>👥 Manage Users</span>`;
    userMgmtBtn.style.cssText = "border:1px solid rgba(139,92,246,0.5);border-radius:999px;background:rgba(139,92,246,0.15);color:#c4b5fd;cursor:pointer;padding:4px 10px;font:inherit;font-size:11px;font-weight:600;display:flex;align-items:center;gap:4px;transition:all 0.2s;";
    userMgmtBtn.onmouseenter = () => { userMgmtBtn.style.background = "rgba(139,92,246,0.3)"; userMgmtBtn.style.color = "#ffffff"; };
    userMgmtBtn.onmouseleave = () => { userMgmtBtn.style.background = "rgba(139,92,246,0.15)"; userMgmtBtn.style.color = "#c4b5fd"; };
    userMgmtBtn.addEventListener("click", () => {
      window.archipelagoOpenUserManagementModal(principal);
    });
    nav.appendChild(userMgmtBtn);
  }

  const signOut = document.createElement("button");
  signOut.type = "button";
  signOut.textContent = "Sign out";
  signOut.style.cssText = "border:0;border-radius:999px;background:rgba(255,255,255,0.9);color:#0f0a19;cursor:pointer;padding:5px 10px;font:inherit;font-weight:600;transition:all 0.2s;";
  signOut.onmouseenter = () => { signOut.style.background = "#ffffff"; };
  signOut.onmouseleave = () => { signOut.style.background = "rgba(255,255,255,0.9)"; };
  signOut.addEventListener("click", async () => {
    await window.archipelagoLogout({ redirectUrl: LOGIN_PATH });
  });
  nav.appendChild(signOut);
  document.body.appendChild(nav);
};
