import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
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

const HANDOFF_STATE_KEY = 'archipelago_handoff_state';
let activeHandoffPopup = null;

function generateHandoffState() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

document.querySelector('#continue-session').addEventListener('click', () => {
  status.textContent = 'Checking your main Archipelago session…';
  const state = generateHandoffState();
  sessionStorage.setItem(HANDOFF_STATE_KEY, state);
  const bridge = new URL('https://archipelago-blond.vercel.app/session-bridge.html');
  bridge.searchParams.set('target', location.origin);
  bridge.searchParams.set('state', state);
  activeHandoffPopup = window.open(bridge.href, 'archipelago-session', 'width=560,height=360');
  if (!activeHandoffPopup) {
    sessionStorage.removeItem(HANDOFF_STATE_KEY);
    status.textContent = 'Allow the Archipelago session window, then try again.';
  }
});

window.addEventListener('message', async (event) => {
  if (event.origin !== 'https://archipelago-blond.vercel.app') return;
  if (activeHandoffPopup && event.source !== activeHandoffPopup) return;
  const msgType = event.data?.type;
  if (msgType !== 'archipelago-session-v2' && msgType !== 'archipelago-session-v1') return;

  const expectedState = sessionStorage.getItem(HANDOFF_STATE_KEY);
  sessionStorage.removeItem(HANDOFF_STATE_KEY);
  activeHandoffPopup = null;

  if (!expectedState || typeof event.data?.state !== 'string' || event.data.state !== expectedState) {
    status.textContent = 'Session handoff state verification failed. Please try again.';
    return;
  }

  let accessToken = null;
  if (typeof event.data.ticket === 'string' && event.data.ticket.length >= 16) {
    try {
      const redeemResp = await fetch('/api/auth/handoff-redeem', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ ticket: event.data.ticket, state: expectedState, nonce: expectedState }),
        cache: 'no-store',
      });
      if (redeemResp.ok) {
        const redeemed = await redeemResp.json();
        accessToken = typeof redeemed?.access_token === 'string' ? redeemed.access_token : null;
        if (redeemed?.authenticated && !accessToken) {
          location.replace(next);
          return;
        }
      }
    } catch (_) {}
  }

  if (!accessToken && typeof event.data.access_token === 'string') {
    accessToken = event.data.access_token;
  }
  if (!accessToken) {
    status.textContent = 'Session handoff failed. Please sign in here.';
    return;
  }

  const response = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: 'no-store',
  });
  if (!response.ok) {
    if (supabase) await supabase.auth.signOut();
    status.textContent = 'This account cannot access the staff space.';
    return;
  }
  try {
    await fetch('/api/auth/session', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ access_token: accessToken }),
    });
  } catch (_) {}
  location.replace(next);
});
