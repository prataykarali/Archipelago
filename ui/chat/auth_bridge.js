import "./user_management_modal.js";
import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const API_PREFIX = "/api/";
const LOGIN_PATH = "/login";
// Pages anyone may read without signing in.
const OPEN_PATHS = new Set(["/", "/landing"]);
const IDLE_TIMEOUT_MS = 300000;
const STUDENT_ROUTES = new Set(["/chat", "/library"]);
const STAFF_ROUTES = new Set(["/chat", "/library", "/graph"]);

async function loadConfig() {
  try {
    const response = await fetch("/api/auth/config", { cache: "no-store" });
    if (response.ok) return await response.json();
  } catch (err) {
    console.warn("Auth config fetch failed, using fallback:", err);
  }
  return { configured: false, required: true };
}

function isApiRequest(input) {
  const target = typeof input === "string" ? input : input.url;
  return new URL(target, window.location.origin).pathname.startsWith(API_PREFIX);
}

async function addAccessToken(supabase, input, init = {}) {
  if (!isApiRequest(input)) return init;
  const { data } = await supabase.auth.getSession();
  if (!data.session?.access_token) return init;
  const headers = new Headers(init.headers || (typeof input === "string" ? undefined : input.headers));
  headers.set("Authorization", `Bearer ${data.session.access_token}`);
  return { ...init, headers };
}

window.archipelagoAuthReady = (async () => {
  const config = await loadConfig();
  if (!config.configured) return { config, supabase: null };

  const supabase = createClient(config.url, config.publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => originalFetch(input, await addAccessToken(supabase, input, init));
  return { config, supabase };
})();

window.archipelagoRequireSession = async () => {
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!config?.required) return null;
  try {
    const { data } = await supabase?.auth.getSession();
    if (data?.session?.access_token) {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      if (response.ok) {
        const principal = await response.json();
        window.archipelagoUserId = principal.id || principal.user_id;
        return data.session;
      }
    }
  } catch (_) {}
  sessionStorage.removeItem("archipelago_local_user");
  localStorage.removeItem("archipelago_local_user");
  if (OPEN_PATHS.has(window.location.pathname.replace(/\/$/, "") || "/")) return null;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`${LOGIN_PATH}?next=${next}`);
  return null;
};

if (["/chat", "/library", "/graph"].includes(window.location.pathname.replace(/\/$/, ""))) {
  let idleTimer;
  const expire = async () => {
    try {
      const { supabase } = await window.archipelagoAuthReady;
      await fetch('/api/auth/session', { method: 'DELETE', credentials: 'same-origin' });
      if (supabase) await supabase.auth.signOut();
    } finally {
      window.archipelagoUserId = null;
      window.location.replace('/login?timeout=1');
    }
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
  const { config, supabase } = await window.archipelagoAuthReady;
  if (!config.required) return null;

  if (!supabase) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`${LOGIN_PATH}?next=${next}`);
    return null;
  }
  const { data } = await supabase.auth.getSession();
  if (!data.session) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`${LOGIN_PATH}?next=${next}`);
    return null;
  }

  const response = await fetch("/api/auth/me");
  if (!response.ok) {
    await supabase.auth.signOut();
    window.location.replace(LOGIN_PATH);
    return null;
  }
  const principal = await response.json();
  if (!allowedRoles.includes(principal.role)) {
    window.location.replace("/chat");
    return null;
  }
  return principal;
};

window.archipelagoRouteForRole = (role, requestedPath) => {
  const allowed = role === "student" ? STUDENT_ROUTES : STAFF_ROUTES;
  return allowed.has(requestedPath) ? requestedPath : "/chat";
};

window.archipelagoMountNavigation = async () => {
  const { config, supabase } = await window.archipelagoAuthReady;
  let principal = null;
  try {
    const response = await fetch("/api/auth/me");
    if (response.ok) {
      principal = await response.json();
    }
  } catch (err) {
    console.warn("Could not fetch user identity:", err);
  }

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
    : [["Chat", "/chat"], ["Library", "/library"], ["Graph", "/graph"]];
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
    sessionStorage.removeItem("archipelago_local_user");
    localStorage.removeItem("archipelago_local_user");
    try { await fetch("/api/auth/session", { method: "DELETE", credentials: "same-origin" }); } catch (_) {}
    if (supabase) {
      try { await supabase.auth.signOut(); } catch (_) {}
    }
    window.location.assign(LOGIN_PATH);
  });
  nav.appendChild(signOut);
  document.body.appendChild(nav);
};
