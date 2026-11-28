import "./user_management_modal.js";
import "./password_visibility.js";

const API_PREFIX = "/api/";
const LOGIN_PATH = "/login";
// Pages anyone may read without signing in.
const OPEN_PATHS = new Set(["/", "/landing", "/library", "/chat", "/research"]);
const CHAT_DRAFT_KEY = "archipelago_pending_chat_draft";
const STUDENT_ROUTES = new Set(["/chat", "/library"]);
const STAFF_ROUTES = new Set(["/chat", "/library", "/graph", "/research"]);
const AUTH_CHANNEL_NAME = "archipelago_auth_channel";
const LOGOUT_STORAGE_KEY = "archipelago_logout_broadcast";
const ACTIVE_PRINCIPAL_KEY = "archipelago_active_principal_id";
const AUTH_CONFIG_CACHE_KEY = "archipelago_auth_config_v1";
const AUTH_ME_CACHE_KEY = "archipelago_me_cache_v1";
const AUTH_CONFIG_TTL_MS = 600000;
const PASSIVE_RECHECK_INTERVAL_MS = 60000;
const PASSIVE_RECHECK_MIN_GAP_MS = 15000;
const PASSIVE_CHECK_TIMEOUT_MS = 12000;
const VERIFY_SESSION_TIMEOUT_MS = 15000;
const RECENT_SESSION_GRACE_MS = 300000;
const USER_KEEPALIVE_MIN_GAP_MS = 120000;
const SUPABASE_CDN_TIMEOUT_MS = 3500;
const LOGOUT_REQUEST_TIMEOUT_MS = 4000;
const SUPABASE_LOCAL_SIGNOUT_TIMEOUT_MS = 1000;
const POST_LOGIN_ME_CACHE_MS = 15000;
let cachedAccessToken = "";
let loadedSupabaseClient = null;
let inFlightMePromise = null;
let lastPassiveCheckAt = 0;
let passiveCheckInFlight = false;
let lastKeepaliveAt = 0;
let keepaliveInFlight = false;
let lastVerifiedSessionAt = 0;
let lastVerifiedPrincipal = null;

async function loadSupabaseCreateClient() {
  try {
    const mod = await Promise.race([
      import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.2/+esm"),
      new Promise((_, reject) => setTimeout(() => reject(new Error("supabase-cdn-timeout")), SUPABASE_CDN_TIMEOUT_MS)),
    ]);
    return mod?.createClient || null;
  } catch (_) {
    return null;
  }
}

function readCachedMe(maxAgeMs = POST_LOGIN_ME_CACHE_MS) {
  try {
    const raw = sessionStorage.getItem(AUTH_ME_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.ts && (Date.now() - parsed.ts) < maxAgeMs && parsed.principal?.authenticated) {
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

function clearVisibleAuthenticatedUi() {
  window.archipelagoUserId = null;
  lastVerifiedSessionAt = 0;
  lastVerifiedPrincipal = null;
  writeCachedMe(null);
  document.querySelector("#archipelago-role-navigation")?.remove();
  window.updateHeaderAuthProfile?.();
}

window.archipelagoClearChatSignInPrompt = () => {
  document.getElementById("archipelago-chat-sign-in-prompt")?.remove();
};

function recordVerifiedSession(principal) {
  if (principal && principal.authenticated) {
    lastVerifiedSessionAt = Date.now();
    lastVerifiedPrincipal = principal;
    writeCachedMe(principal);
  }
}

async function passiveSessionRecheck({ force = false } = {}) {
  if (isHandlingLogout || isPageUnloading || document.visibilityState === "hidden") return;
  if (passiveCheckInFlight) return;
  const now = Date.now();
  if (!force && now - lastPassiveCheckAt < PASSIVE_RECHECK_MIN_GAP_MS) return;
  lastPassiveCheckAt = now;
  passiveCheckInFlight = true;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PASSIVE_CHECK_TIMEOUT_MS);
  try {
    const { config } = await window.archipelagoAuthReady;
    if (!config || config.required === false) return;
    const hasVisibleAuthUi = Boolean(
      window.archipelagoUserId ||
      document.querySelector("#archipelago-role-navigation") ||
      document.querySelector("#user-profile-badge") ||
      sessionStorage.getItem(AUTH_ME_CACHE_KEY)
    );
    if (!hasVisibleAuthUi) return;
    const response = await fetch("/api/auth/me", {
      cache: "no-store",
      credentials: "same-origin",
      headers: { "X-Session-Passive": "1" },
      signal: controller.signal,
    });
    if (response.status === 401) {
      clearVisibleAuthenticatedUi();
    } else if (response.ok) {
      const result = await response.json().catch(() => null);
      if (result && result.authenticated === false && result.open !== true) {
        clearVisibleAuthenticatedUi();
      } else if (result && result.authenticated === true) {
        recordVerifiedSession(result);
        window.archipelagoClearChatSignInPrompt?.();
      }
    }
  } catch (_) {
  } finally {
    window.clearTimeout(timer);
    passiveCheckInFlight = false;
  }
}

async function sendUserInteractionKeepalive() {
  if (isHandlingLogout || isPageUnloading || document.visibilityState === "hidden") return;
  if (keepaliveInFlight) return;
  const now = Date.now();
  if (now - lastKeepaliveAt < USER_KEEPALIVE_MIN_GAP_MS) return;
  const hasSession = Boolean(
    window.archipelagoUserId ||
    document.querySelector("#user-profile-badge") ||
    sessionStorage.getItem(AUTH_ME_CACHE_KEY)
  );
  if (!hasSession) return;
  lastKeepaliveAt = now;
  keepaliveInFlight = true;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PASSIVE_CHECK_TIMEOUT_MS);
  try {
    await window.archipelagoAuthReady;
    const response = await fetch("/api/auth/keepalive", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: { "X-User-Interaction": "1" },
      signal: controller.signal,
    });
    if (response.status === 401) {
      clearVisibleAuthenticatedUi();
    }
  } catch (_) {
  } finally {
    window.clearTimeout(timer);
    keepaliveInFlight = false;
  }
}

for (const evtName of ["pointerdown", "keydown", "wheel"]) {
  window.addEventListener(evtName, () => {
    sendUserInteractionKeepalive();
  }, { passive: true });
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
window.addEventListener("pageshow", () => {
  isPageUnloading = false;
  passiveSessionRecheck({ force: true });
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    passiveSessionRecheck({ force: true });
  }
});
window.addEventListener("focus", () => {
  passiveSessionRecheck();
});
window.setInterval(() => {
  if (document.visibilityState === "visible") {
    passiveSessionRecheck();
  }
}, PASSIVE_RECHECK_INTERVAL_MS);

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
  // Clear in-memory bearer token immediately so no subsequent fetch re-attaches it.
  cachedAccessToken = "";
  lastVerifiedSessionAt = 0;
  lastVerifiedPrincipal = null;
  inFlightMePromise = null;
  window.archipelagoUserId = null;
  window.archipelagoClearClientStorage({ includeHistory: clearHistory });
  broadcastLogout();
  // Single server-side logout call (revokes durable session + clears HttpOnly cookie).
  const logoutController = new AbortController();
  const logoutTimer = window.setTimeout(() => logoutController.abort(), LOGOUT_REQUEST_TIMEOUT_MS);
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      signal: logoutController.signal,
    });
  } catch (_) {
  } finally {
    window.clearTimeout(logoutTimer);
  }
  // Never block logout waiting on external CDN import or unbounded global signOut;
  // only clear local Supabase client state if already loaded, bounded to 1s.
  if (loadedSupabaseClient) {
    try {
      await Promise.race([
        loadedSupabaseClient.auth.signOut({ scope: "local" }),
        new Promise((resolve) => window.setTimeout(resolve, SUPABASE_LOCAL_SIGNOUT_TIMEOUT_MS)),
      ]);
    } catch (_) {}
  }
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
  if (window._archipelagoConfigPromise) {
    return window._archipelagoConfigPromise;
  }
  window._archipelagoConfigPromise = (async () => {
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
    } finally {
      window._archipelagoConfigPromise = null;
    }
    return { configured: false, required: true };
  })();
  return window._archipelagoConfigPromise;
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
      loadedSupabaseClient = supabase;
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
    const method = (init?.method || (typeof input !== "string" ? input?.method : "GET") || "GET").toUpperCase();
    if (apiUrl?.pathname === "/api/auth/me" && method === "GET") {
      const reqHeaders = new Headers(init?.headers || (typeof input === "string" ? undefined : input?.headers));
      const isPassive = reqHeaders.get("X-Session-Passive") === "1";
      if (!isPassive && !init?.signal) {
        const freshCached = readCachedMe(POST_LOGIN_ME_CACHE_MS);
        if (freshCached) {
          return new Response(JSON.stringify(freshCached), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (inFlightMePromise) {
          const shared = await inFlightMePromise;
          return shared.clone();
        }
        inFlightMePromise = originalFetch(input, await addAccessToken(supabase, input, init))
          .finally(() => { inFlightMePromise = null; });
        const shared = await inFlightMePromise;
        return shared.clone();
      }
    }
    return originalFetch(input, await addAccessToken(supabase, input, init));
  };
  return { config, supabase };
})();

window.archipelagoVerifyChatSession = async ({ force = false, signal = null } = {}) => {
  if (signal?.aborted) {
    const err = new Error("USER_CANCELLED");
    err.name = "AbortError";
    throw err;
  }
  await window.archipelagoAuthReady;
  if (signal?.aborted) {
    const err = new Error("USER_CANCELLED");
    err.name = "AbortError";
    throw err;
  }
  if (
    !force &&
    lastVerifiedPrincipal &&
    lastVerifiedPrincipal.authenticated &&
    (Date.now() - lastVerifiedSessionAt) < RECENT_SESSION_GRACE_MS
  ) {
    window.archipelagoClearChatSignInPrompt?.();
    return lastVerifiedPrincipal;
  }
  if (
    !force &&
    (window.archipelagoUserId || document.querySelector("#user-profile-badge") || readCachedMe(RECENT_SESSION_GRACE_MS))
  ) {
    // Active UI session present: let POST /api/chat enforce server-side auth & revocation directly
    // (08-send-message.js handles 401 cleanly while preserving the unsent question).
    window.archipelagoClearChatSignInPrompt?.();
    return { authenticated: true, deferredToServer: true };
  }
  const controller = new AbortController();
  const onExternalAbort = () => controller.abort("USER_CANCELLED");
  if (signal) signal.addEventListener("abort", onExternalAbort, { once: true });
  const timer = window.setTimeout(() => controller.abort("timeout"), VERIFY_SESSION_TIMEOUT_MS);
  try {
    const response = await fetch("/api/auth/me", {
      cache: "no-store",
      credentials: "same-origin",
      headers: { "X-Session-Passive": "1" },
      signal: controller.signal,
    });
    const result = await response.json().catch(() => ({}));
    if (response.ok && result.open === true) {
      window.archipelagoClearChatSignInPrompt?.();
      return { authenticated: true };
    }
    if (response.ok && result.authenticated === true) {
      recordVerifiedSession(result);
      syncActivePrincipal(result);
      window.archipelagoClearChatSignInPrompt?.();
      return result;
    }
    if (response.status === 401) {
      clearVisibleAuthenticatedUi();
      return { authenticated: false, reason: result.reason || "unauthorized" };
    }
    const error = new Error("Session verification is unavailable. Please try again.");
    error.reason = "upstream_unavailable";
    throw error;
  } catch (err) {
    if (signal?.aborted || controller.signal.reason === "USER_CANCELLED") {
      const cancelErr = new Error("USER_CANCELLED");
      cancelErr.name = "AbortError";
      throw cancelErr;
    }
    if (err && err.reason) throw err;
    const error = new Error("Session verification timed out. Please try again.");
    error.reason = "upstream_unavailable";
    throw error;
  } finally {
    if (signal) signal.removeEventListener("abort", onExternalAbort);
    window.clearTimeout(timer);
  }
};

window.archipelagoPromptChatSignIn = (draft, reason = "unauthorized") => {
  if (draft) sessionStorage.setItem(CHAT_DRAFT_KEY, draft);
  const input = document.getElementById("chat-input");
  if (input && draft && !input.value.trim()) input.value = draft;
  let prompt = document.getElementById("archipelago-chat-sign-in-prompt");
  if (!prompt) {
    prompt = document.createElement("div");
    prompt.id = "archipelago-chat-sign-in-prompt";
    prompt.setAttribute("role", "alert");
    input?.parentElement?.insertAdjacentElement("beforebegin", prompt);
  }
  const messages = {
    idle_expired: "Your session expired after inactivity. Sign in to send your question.",
    absolute_expired: "Your session reached its maximum lifetime. Sign in to send your question.",
    jwt_expired: "Your sign-in token expired. Sign in to send your question.",
    revoked_credentials: "Your session was revoked. Sign in to send your question.",
    upstream_unavailable: "Session verification is unavailable. Your question is saved; please try again.",
  };
  prompt.textContent = messages[reason] || "Sign in to send your question.";
  if (reason !== "upstream_unavailable") {
    const link = document.createElement("a");
    link.href = "/login?next=%2Fchat";
    link.textContent = " Sign in";
    prompt.appendChild(link);
  }
};

if (window.location.pathname === "/chat") {
  window.archipelagoAuthReady.then(async () => {
    const draft = sessionStorage.getItem(CHAT_DRAFT_KEY);
    if (!draft) return;
    try {
      const verified = await window.archipelagoVerifyChatSession();
      if (!verified.authenticated) return;
      const input = document.getElementById("chat-input");
      if (input && !input.value.trim()) input.value = draft;
      sessionStorage.removeItem(CHAT_DRAFT_KEY);
    } catch (_) {}
  });
}

window.archipelagoRequireSession = async () => {
  const { config, supabase } = await window.archipelagoAuthReady;
  if (config?.required === false) return null;
  let verificationUnavailable = false;
  try {
    let session = null;
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      session = data?.session || null;
      if (session?.access_token) cachedAccessToken = session.access_token;
    }
    const response = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
    if (response.status >= 500) verificationUnavailable = true;
    if (response.ok) {
      const principal = await response.json();
      if (principal?.authenticated) {
        writeCachedMe(principal);
        window.archipelagoUserId = principal.id || principal.user_id;
        syncActivePrincipal(principal);
        return session || { user: principal };
      }
    }
  } catch (_) { verificationUnavailable = true; }
  if (verificationUnavailable) return null;
  window.archipelagoClearClientStorage({ includeHistory: false });
  if (OPEN_PATHS.has(window.location.pathname.replace(/\/$/, "") || "/") || window.location.pathname.startsWith("/research")) return null;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`${LOGIN_PATH}?next=${next}`);
  return null;
};

window.archipelagoAuthorizePage = async (allowedRoles) => {
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!config.required) return null;

  let response;
  try {
    response = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" });
  } catch (_) {
    return null;
  }
  if (response.status >= 500) return null;
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
  let principal = null;
  {
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
