import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const API_PREFIX = "/api/";
const LOGIN_PATH = "/login";
// Pages anyone may read without signing in.
const OPEN_PATHS = new Set(["/", "/landing", "/chat", "/library"]);
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
        if (principal.must_change_password && window.location.pathname !== "/change-password") {
          window.location.replace("/change-password");
          return null;
        }
        return data.session;
      }
    }
  } catch (_) {}
  sessionStorage.removeItem("archipelago_local_user");
  localStorage.removeItem("archipelago_local_user");
  // Open pages (landing, chat, library) stay readable without a session; only
  // staff surfaces redirect. Staff routes opt in via
  // `archipelagoAuthorizePage`, which always requires a role.
  if (OPEN_PATHS.has(window.location.pathname.replace(/\/$/, "") || "/")) return null;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`${LOGIN_PATH}?next=${next}`);
  return null;
};

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
  if (principal.must_change_password) {
    window.location.replace("/change-password");
    return null;
  }
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
  if (principal.must_change_password) {
    window.location.replace("/change-password");
    return;
  }

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
    userMgmtBtn.textContent = "Import students";
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

// A verified librarian grant or administrator role is checked again by the API.
window.archipelagoOpenUserManagementModal = async (principal) => {
  const existing = document.querySelector("#archipelago-user-mgmt-modal");
  if (existing) existing.remove();

  const modal = document.createElement("div");
  modal.id = "archipelago-user-mgmt-modal";
  modal.style.cssText = "position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;padding:16px;font-family:system-ui,sans-serif";
  const panel = document.createElement("section");
  panel.style.cssText = "background:#171126;border:1px solid #67518b;border-radius:20px;max-width:480px;width:100%;padding:28px;color:#fff";
  panel.setAttribute("aria-label", "Import student accounts");
  const heading = document.createElement("h2");
  heading.textContent = "Import student enrollments";
  panel.appendChild(heading);
  const help = document.createElement("p");
  help.textContent = "Upload a UTF-8 CSV exported from a spreadsheet with enrollment and optional display_name columns. Up to 100 rows per import. Existing accounts are skipped. Students must choose a new password on first sign-in.";
  panel.appendChild(help);
  const form = document.createElement("form");
  form.style.cssText = "display:grid;gap:12px";
  const sourceLabel = document.createElement("label");
  sourceLabel.textContent = "Approved source label";
  const sourceInput = document.createElement("input");
  sourceInput.name = "source_label";
  sourceInput.maxLength = 160;
  sourceInput.required = principal.role === "librarian";
  sourceInput.style.cssText = "display:block;width:100%;padding:10px;background:#0d0a16;border:1px solid #67518b;color:#fff;border-radius:8px;box-sizing:border-box";
  sourceLabel.appendChild(sourceInput);
  form.appendChild(sourceLabel);
  const fileLabel = document.createElement("label");
  fileLabel.textContent = "Student CSV file";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.name = "file";
  fileInput.accept = ".csv,text/csv";
  fileInput.required = true;
  fileLabel.appendChild(fileInput);
  form.appendChild(fileLabel);
  const message = document.createElement("p");
  message.setAttribute("role", "status");
  message.setAttribute("aria-live", "polite");
  form.appendChild(message);
  const preview = document.createElement("button");
  preview.type = "submit";
  preview.textContent = "Preview import";
  preview.style.cssText = "background:#8b5cf6;color:#fff;border:0;border-radius:8px;padding:10px;cursor:pointer";
  form.appendChild(preview);
  const apply = document.createElement("button");
  apply.type = "button";
  apply.textContent = "Create accounts";
  apply.disabled = true;
  apply.style.cssText = preview.style.cssText;
  form.appendChild(apply);
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close";
  close.style.cssText = "background:transparent;color:#fff;border:1px solid #67518b;border-radius:8px;padding:10px;cursor:pointer";
  close.onclick = () => modal.remove();
  form.appendChild(close);
  panel.appendChild(form);
  modal.appendChild(panel);
  document.body.appendChild(modal);
  modal.addEventListener("click", event => { if (event.target === modal) modal.remove(); });

  let previewedFile = null;
  async function sendImport(path) {
    const body = new FormData();
    body.set("source_label", sourceInput.value.trim());
    body.set("file", fileInput.files[0]);
    const response = await fetch(path, { method: "POST", body });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || "Import could not be completed.");
    return result;
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    apply.disabled = true;
    preview.disabled = true;
    message.textContent = "Checking enrollment records…";
    try {
      const result = await sendImport("/api/users/import/preview");
      previewedFile = fileInput.files[0];
      message.textContent = `${result.received} records: ${result.to_create} new, ${result.existing} already present.`;
      apply.disabled = result.to_create === 0;
    } catch (error) {
      message.textContent = error.message;
    } finally {
      preview.disabled = false;
    }
  });
  apply.addEventListener("click", async () => {
    if (fileInput.files[0] !== previewedFile) {
      message.textContent = "Preview this file before creating accounts.";
      apply.disabled = true;
      return;
    }
    apply.disabled = true;
    preview.disabled = true;
    message.textContent = "Creating accounts…";
    try {
      const result = await sendImport("/api/users/import");
      message.textContent = `${result.created} created, ${result.existing} already present, ${result.failed} failed.`;
    } catch (error) {
      message.textContent = error.message;
    } finally {
      preview.disabled = false;
    }
  });
  fileInput.addEventListener("change", () => { previewedFile = null; apply.disabled = true; });
};
