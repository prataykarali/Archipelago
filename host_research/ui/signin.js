import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";

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
  location.replace(next);
});

document.querySelector('#continue-session').addEventListener('click', () => {
  status.textContent = 'Checking your main Archipelago session…';
  const popup = window.open('https://archipelago-blond.vercel.app/session-bridge.html', 'archipelago-session', 'width=560,height=360');
  if (!popup) status.textContent = 'Allow the Archipelago session window, then try again.';
});

window.addEventListener('message', async event => {
  if (event.origin !== 'https://archipelago-blond.vercel.app' || event.data?.type !== 'archipelago-session-v1' || !supabase) return;
  const { access_token, refresh_token } = event.data;
  if (typeof access_token !== 'string' || typeof refresh_token !== 'string') return;
  const { error } = await supabase.auth.setSession({ access_token, refresh_token });
  if (error) { status.textContent = 'Session handoff failed. Please sign in here.'; return; }
  const response = await fetch('/api/auth/me', { cache: 'no-store' });
  if (!response.ok) { status.textContent = 'This account cannot access the staff space.'; return; }
  location.replace(next);
});
