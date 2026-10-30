import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

const status = document.querySelector("#login-status");
document.querySelector("#login-panel").hidden = false;
const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;
const EMAIL_DOMAIN = ".iem.archipelago.invalid";
let supabase;

try {
  const response = await fetch("/api/auth/config", { cache: "no-store" });
  const config = await response.json();
  if (!config.configured) throw new Error("Shared sign-in is not configured.");
  supabase = createClient(config.url, config.publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });
  const { data } = await supabase.auth.getSession();
  if (data.session) location.replace("/research");
} catch (error) {
  status.textContent = error.message;
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabase) return;
  const username = document.querySelector("#username").value.trim();
  const role = document.querySelector("#role").value;
  if (!USERNAME_PATTERN.test(username)) {
    status.textContent = "Enter a valid staff username.";
    return;
  }
  status.textContent = "Signing in…";
  const { error } = await supabase.auth.signInWithPassword({
    email: `${username.toLowerCase()}@${role}${EMAIL_DOMAIN}`,
    password: document.querySelector("#password").value,
  });
  if (error) {
    status.textContent = error.message;
    return;
  }
  const { data } = await supabase.auth.getSession();
  const identity = await fetch("/api/auth/me", {
    headers: { Authorization: `Bearer ${data.session.access_token}` },
    cache: "no-store",
  });
  if (!identity.ok) {
    await supabase.auth.signOut();
    status.textContent = "This account needs a research staff role.";
    return;
  }
  const next = new URLSearchParams(location.search).get("next") || "/research";
  location.replace(next.startsWith("/research") ? next : "/research");
});
