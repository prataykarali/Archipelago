import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.119.2/+esm";
import "./password_visibility.js";

const status = document.querySelector("#login-status");
document.querySelector("#login-panel").hidden = false;
const USERNAME_PATTERN = /^[A-Za-z0-9._-]{3,64}$/;
const EMAIL_DOMAIN = ".iem.archipelago.invalid";
let supabase;
const requestedNext = new URLSearchParams(location.search).get("next") || "/research";
const next = /^\/(research(?:\/[^?#]*)?|librarian(?:\/(?:catalog|circulation|orders|fines))?|academic\/graph)(?:[?#].*)?$/.test(requestedNext) ? requestedNext : "/research";

try {
  const response = await fetch("/api/auth/config", { cache: "no-store" });
  const config = await response.json();
  if (!config.configured) throw new Error("Shared sign-in is not configured.");
  supabase = createClient(config.url, config.publishableKey, {
    auth: { persistSession: true, autoRefreshToken: true },
  });
  const { data } = await supabase.auth.getSession();
  if (data.session) location.replace(next);
} catch (error) {
  status.textContent = error.message;
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabase) return;
  const username = document.querySelector("#username").value.trim();
  const role = document.querySelector("#role").value;
  const isEmail = username.includes("@");
  if (!isEmail && !USERNAME_PATTERN.test(username)) {
    status.textContent = "Enter a valid staff username.";
    return;
  }
  status.textContent = "Signing in…";
  const { error } = await supabase.auth.signInWithPassword({
    email: isEmail ? username.toLowerCase() : `${username.toLowerCase()}@${role}${EMAIL_DOMAIN}`,
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
  try {
    await fetch("/api/auth/session", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        Authorization: `Bearer ${data.session.access_token}`,
      },
      body: JSON.stringify({ access_token: data.session.access_token }),
    });
  } catch (_) {}
  location.replace(next);
});

document.querySelector('#continue-session').addEventListener('click', async () => {
  status.textContent = 'Checking this research site session…';
  const response = await fetch('/api/auth/me', { cache: 'no-store', credentials: 'same-origin' });
  if (response.ok) {
    location.replace(next);
  } else {
    status.textContent = 'Please sign in with your research account.';
  }
});
