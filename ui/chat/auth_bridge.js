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
      if (response.ok) return data.session;
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

// ── Interactive User Management Modal for Librarian and Administrator ────────
window.archipelagoOpenUserManagementModal = async (principal) => {
  let modal = document.querySelector("#archipelago-user-mgmt-modal");
  if (modal) modal.remove();

  modal = document.createElement("div");
  modal.id = "archipelago-user-mgmt-modal";
  modal.style.cssText = "position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,0.85);backdrop-filter:blur(20px);display:flex;align-items:center;justify-content:center;padding:16px;font-family:'Inter',system-ui,sans-serif;";

  const container = document.createElement("div");
  container.style.cssText = "background:#120d22;border:1px solid rgba(255,255,255,0.15);border-radius:20px;max-width:850px;width:100%;max-height:90vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,0.8);color:#fff;";

  // Header
  const header = document.createElement("div");
  header.style.cssText = "padding:20px 24px;border-bottom:1px solid rgba(255,255,255,0.1);display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,0.02);";
  header.innerHTML = `
    <div>
      <h2 style="margin:0;font-size:20px;font-weight:700;display:flex;align-items:center;gap:8px;">
        <span>User & Login Account Management</span>
        <span style="font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;background:rgba(139,92,246,0.2);color:#c4b5fd;border:1px solid rgba(139,92,246,0.3);text-transform:uppercase;">${principal.role}</span>
      </h2>
      <p style="margin:4px 0 0;font-size:12px;color:rgba(255,255,255,0.6);">
        ${principal.role === 'administrator' ? 'Full administrator permissions: add, update username/password, and delete any account.' : 'Librarian permissions: add/delete students, update student usernames, and update your own username.'}
      </p>
    </div>
    <button id="close-user-modal" style="background:rgba(255,255,255,0.1);border:0;color:#fff;font-size:18px;width:32px;height:32px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;">✕</button>
  `;
  container.appendChild(header);

  // Content Area
  const content = document.createElement("div");
  content.style.cssText = "padding:20px 24px;overflow-y:auto;flex:1;display:flex;flex-direction:column;gap:20px;";

  // Top action bar (Add user + Search)
  const actionBar = document.createElement("div");
  actionBar.style.cssText = "display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;";
  actionBar.innerHTML = `
    <div style="position:relative;flex:1;min-width:240px;">
      <input type="text" id="user-mgmt-search" placeholder="Search by username or display name..." style="width:100%;box-sizing:border-box;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);border-radius:10px;padding:10px 14px;color:#fff;font-size:13px;outline:none;" />
    </div>
    <button id="open-add-user-btn" style="background:#10b981;border:0;border-radius:10px;color:#000;font-weight:700;font-size:13px;padding:10px 16px;cursor:pointer;display:flex;align-items:center;gap:6px;">
      <span>+ Add New ${principal.role === 'administrator' ? 'Account' : 'Student'}</span>
    </button>
  `;
  content.appendChild(actionBar);

  // Alert banner
  const alertBox = document.createElement("div");
  alertBox.id = "user-mgmt-alert";
  alertBox.style.cssText = "display:none;padding:12px 16px;border-radius:10px;font-size:13px;";
  content.appendChild(alertBox);

  function showAlert(msg, isError = false) {
    alertBox.style.display = "block";
    alertBox.style.background = isError ? "rgba(239,68,68,0.15)" : "rgba(16,185,129,0.15)";
    alertBox.style.border = `1px solid ${isError ? "#ef4444" : "#10b981"}`;
    alertBox.style.color = isError ? "#fca5a5" : "#6ee7b7";
    alertBox.textContent = msg;
    setTimeout(() => { alertBox.style.display = "none"; }, 5000);
  }

  // Users Table Container
  const tableContainer = document.createElement("div");
  tableContainer.style.cssText = "border:1px solid rgba(255,255,255,0.1);border-radius:12px;overflow:hidden;background:rgba(0,0,0,0.3);";
  tableContainer.innerHTML = `
    <table style="width:100%;border-collapse:collapse;text-align:left;font-size:13px;">
      <thead style="background:rgba(255,255,255,0.05);font-size:11px;text-transform:uppercase;color:rgba(255,255,255,0.5);">
        <tr>
          <th style="padding:12px 16px;">Username</th>
          <th style="padding:12px 16px;">Role</th>
          <th style="padding:12px 16px;">Display Name</th>
          <th style="padding:12px 16px;text-align:right;">Actions</th>
        </tr>
      </thead>
      <tbody id="user-mgmt-tbody">
        <tr><td colspan="4" style="padding:24px;text-align:center;color:rgba(255,255,255,0.5);">Loading users...</td></tr>
      </tbody>
    </table>
  `;
  content.appendChild(tableContainer);
  container.appendChild(content);
  modal.appendChild(container);
  document.body.appendChild(modal);

  // Close handlers
  modal.querySelector("#close-user-modal").onclick = () => modal.remove();
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.remove(); });

  let allUsers = [];

  async function loadUsers() {
    try {
      const resp = await fetch("/api/users");
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        showAlert(err.detail || "Failed to load users.", true);
        return;
      }
      const data = await resp.json();
      allUsers = data.users || [];
      renderTable();
    } catch (err) {
      showAlert("Network error fetching user directory.", true);
    }
  }

  function renderTable(filter = "") {
    const tbody = tableContainer.querySelector("#user-mgmt-tbody");
    const q = filter.toLowerCase().trim();
    const filtered = allUsers.filter(u => 
      (u.username || "").toLowerCase().includes(q) || 
      (u.display_name || "").toLowerCase().includes(q) ||
      (u.role || "").toLowerCase().includes(q)
    );

    if (filtered.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="padding:24px;text-align:center;color:rgba(255,255,255,0.5);">No matching users found.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    filtered.forEach(u => {
      const isSelf = u.id === principal.user_id;
      const isStudent = u.role === "student";
      const canEdit = principal.role === "administrator" || isStudent || isSelf;
      const canDelete = !isSelf && (principal.role === "administrator" || (principal.role === "librarian" && isStudent));

      const roleBadgeBg = u.role === 'administrator' ? '#ec489922' : (u.role === 'librarian' ? '#10b98122' : '#8b5cf622');
      const roleBadgeColor = u.role === 'administrator' ? '#ec4899' : (u.role === 'librarian' ? '#10b981' : '#a78bfa');

      const tr = document.createElement("tr");
      tr.style.cssText = "border-top:1px solid rgba(255,255,255,0.06);transition:background 0.15s;";
      tr.onmouseenter = () => { tr.style.background = "rgba(255,255,255,0.03)"; };
      tr.onmouseleave = () => { tr.style.background = "transparent"; };

      tr.innerHTML = `
        <td style="padding:14px 16px;font-weight:600;color:#fff;">
          ${u.username}
          ${isSelf ? '<span style="margin-left:6px;font-size:10px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.1);color:#fff;">YOU</span>' : ''}
        </td>
        <td style="padding:14px 16px;">
          <span style="padding:3px 8px;border-radius:999px;background:${roleBadgeBg};color:${roleBadgeColor};font-size:11px;font-weight:600;text-transform:uppercase;">
            ${u.role}
          </span>
        </td>
        <td style="padding:14px 16px;color:rgba(255,255,255,0.7);">${u.display_name || u.username}</td>
        <td style="padding:14px 16px;text-align:right;">
          <div style="display:inline-flex;gap:8px;">
            ${canEdit ? `<button class="edit-user-btn" data-id="${u.id}" style="padding:6px 12px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.15);border-radius:6px;color:#fff;font-size:12px;cursor:pointer;font-weight:500;">Edit Username</button>` : ''}
            ${canDelete ? `<button class="del-user-btn" data-id="${u.id}" data-username="${u.username}" style="padding:6px 12px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);border-radius:6px;color:#fca5a5;font-size:12px;cursor:pointer;font-weight:500;">Delete</button>` : ''}
          </div>
        </td>
      `;

      // Wire edit button
      const editBtn = tr.querySelector(".edit-user-btn");
      if (editBtn) {
        editBtn.onclick = () => openEditUserDialog(u);
      }
      // Wire delete button
      const delBtn = tr.querySelector(".del-user-btn");
      if (delBtn) {
        delBtn.onclick = () => deleteUserConfirm(u.id, u.username);
      }

      tbody.appendChild(tr);
    });
  }

  // Filter input event
  content.querySelector("#user-mgmt-search").addEventListener("input", (e) => {
    renderTable(e.target.value);
  });

  // Open Add User Dialog
  content.querySelector("#open-add-user-btn").onclick = () => {
    openAddUserDialog();
  };

  // Add User Form Modal
  function openAddUserDialog() {
    const subModal = document.createElement("div");
    subModal.style.cssText = "position:fixed;inset:0;z-index:100010;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:16px;";
    subModal.innerHTML = `
      <div style="background:#171126;border:1px solid rgba(255,255,255,0.2);border-radius:16px;max-width:420px;width:100%;padding:24px;box-shadow:0 20px 40px rgba(0,0,0,0.8);color:#fff;">
        <h3 style="margin:0 0 16px;font-size:18px;font-weight:700;">Add New ${principal.role === 'administrator' ? 'Account' : 'Student'}</h3>
        <form id="add-user-form" style="display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Username ${principal.role === 'librarian' ? '(or 14-digit Enrollment No.)' : ''}</label>
            <input name="username" required placeholder="e.g. 12024002028099 or jdoe" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Initial Password (min 6 characters)</label>
            <input name="password" type="password" required placeholder="••••••••" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Display Name</label>
            <input name="display_name" placeholder="Full name (optional)" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          ${principal.role === 'administrator' ? `
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Role</label>
            <select name="role" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;">
              <option value="student">Student</option>
              <option value="librarian">Librarian</option>
              <option value="administrator">Administrator</option>
            </select>
          </div>
          ` : `<input type="hidden" name="role" value="student" />`}
          <div id="add-user-error" style="color:#f87171;font-size:12px;display:none;"></div>
          <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:8px;">
            <button type="button" id="cancel-add-user" style="background:transparent;border:1px solid rgba(255,255,255,0.2);color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;">Cancel</button>
            <button type="submit" style="background:#10b981;border:0;color:#000;font-weight:700;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">Create Account</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(subModal);
    subModal.querySelector("#cancel-add-user").onclick = () => subModal.remove();

    subModal.querySelector("#add-user-form").onsubmit = async (e) => {
      e.preventDefault();
      const form = e.target;
      const payload = {
        username: form.username.value.trim(),
        password: form.password.value.trim(),
        display_name: form.display_name.value.trim(),
        role: form.role ? form.role.value : "student",
      };

      const errDiv = subModal.querySelector("#add-user-error");
      try {
        const res = await fetch("/api/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
          errDiv.textContent = data.detail || "Failed to create user.";
          errDiv.style.display = "block";
          return;
        }
        subModal.remove();
        showAlert(`Account '${payload.username}' created successfully!`);
        await loadUsers();
      } catch (err) {
        errDiv.textContent = "Network error creating account.";
        errDiv.style.display = "block";
      }
    };
  }

  // Edit User Dialog
  function openEditUserDialog(user) {
    const isSelf = user.id === principal.user_id;
    const subModal = document.createElement("div");
    subModal.style.cssText = "position:fixed;inset:0;z-index:100010;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px);display:flex;align-items:center;justify-content:center;padding:16px;";
    subModal.innerHTML = `
      <div style="background:#171126;border:1px solid rgba(255,255,255,0.2);border-radius:16px;max-width:420px;width:100%;padding:24px;box-shadow:0 20px 40px rgba(0,0,0,0.8);color:#fff;">
        <h3 style="margin:0 0 4px;font-size:18px;font-weight:700;">Update ${isSelf ? 'Your Account' : `Student '${user.username}'`}</h3>
        <p style="margin:0 0 16px;font-size:12px;color:rgba(255,255,255,0.6);">Update login username, display name, or password.</p>
        <form id="edit-user-form" style="display:flex;flex-direction:column;gap:12px;">
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Username</label>
            <input name="username" required value="${user.username}" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Display Name</label>
            <input name="display_name" value="${user.display_name || ''}" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">New Password (leave blank to keep existing)</label>
            <input name="password" type="password" placeholder="New password (optional)" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;" />
          </div>
          ${principal.role === 'administrator' && !isSelf ? `
          <div>
            <label style="display:block;font-size:12px;color:rgba(255,255,255,0.6);margin-bottom:4px;">Role</label>
            <select name="role" style="width:100%;box-sizing:border-box;background:#0d0a16;border:1px solid #67518b;border-radius:8px;padding:10px;color:#fff;font-size:13px;outline:none;">
              <option value="student" ${user.role === 'student' ? 'selected' : ''}>Student</option>
              <option value="librarian" ${user.role === 'librarian' ? 'selected' : ''}>Librarian</option>
              <option value="administrator" ${user.role === 'administrator' ? 'selected' : ''}>Administrator</option>
            </select>
          </div>
          ` : ''}
          <div id="edit-user-error" style="color:#f87171;font-size:12px;display:none;"></div>
          <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:8px;">
            <button type="button" id="cancel-edit-user" style="background:transparent;border:1px solid rgba(255,255,255,0.2);color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;">Cancel</button>
            <button type="submit" style="background:#8b5cf6;border:0;color:#fff;font-weight:700;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">Save Changes</button>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(subModal);
    subModal.querySelector("#cancel-edit-user").onclick = () => subModal.remove();

    subModal.querySelector("#edit-user-form").onsubmit = async (e) => {
      e.preventDefault();
      const form = e.target;
      const payload = {
        username: form.username.value.trim(),
        display_name: form.display_name.value.trim(),
      };
      if (form.password.value.trim()) {
        payload.password = form.password.value.trim();
      }
      if (form.role) {
        payload.role = form.role.value;
      }

      const errDiv = subModal.querySelector("#edit-user-error");
      try {
        const res = await fetch(`/api/users/${user.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) {
          errDiv.textContent = data.detail || "Failed to update user.";
          errDiv.style.display = "block";
          return;
        }
        subModal.remove();
        showAlert(`Username updated to '${payload.username}' successfully!`);
        // If updating self, update local session
        if (isSelf) {
          principal.username = payload.username;
          window.archipelagoMountNavigation();
        }
        await loadUsers();
      } catch (err) {
        errDiv.textContent = "Network error updating user.";
        errDiv.style.display = "block";
      }
    };
  }

  // Delete User Confirmation
  async function deleteUserConfirm(userId, username) {
    if (!confirm(`Are you sure you want to permanently delete user '${username}'? This cannot be undone.`)) {
      return;
    }
    try {
      const res = await fetch(`/api/users/${userId}`, {
        method: "DELETE",
        headers: {}
      });
      const data = await res.json();
      if (!res.ok) {
        showAlert(data.detail || "Failed to delete user.", true);
        return;
      }
      showAlert(`User '${username}' has been deleted.`);
      await loadUsers();
    } catch (err) {
      showAlert("Network error deleting user.", true);
    }
  }

  await loadUsers();
};

