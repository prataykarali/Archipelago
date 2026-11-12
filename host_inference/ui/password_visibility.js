"use strict";

const style = document.createElement("style");
style.textContent = `
  .archipelago-password-field { position: relative; display: block; width: 100%; }
  .archipelago-password-field input { padding-right: 3.25rem !important; }
  .archipelago-password-toggle {
    position: absolute !important; right: 0.45rem; top: 50%;
    transform: translateY(-50%); display: grid !important; place-items: center;
    width: 2.5rem !important; height: 2.5rem !important;
    min-width: 2.5rem; margin: 0 !important; padding: 0 !important;
    border: 0 !important; border-radius: 0.5rem !important;
    background: transparent !important; box-shadow: none !important;
    color: #e9d5ff !important; cursor: pointer;
  }
  .archipelago-password-toggle:hover { background: #ffffff18 !important; }
  .archipelago-password-toggle:focus-visible { outline: 2px solid #f4c4ff; outline-offset: 2px; }
  .archipelago-password-toggle[aria-pressed="false"] .archipelago-eye-slash { display: none; }
`;
document.head.appendChild(style);

function enhancePasswordFields() {
  for (const input of document.querySelectorAll('input[type="password"]')) {
    if (input.dataset.visibilityToggle === "ready") continue;
    input.dataset.visibilityToggle = "ready";

    const wrapper = document.createElement("span");
    wrapper.className = "archipelago-password-field";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "archipelago-password-toggle";
    button.setAttribute("aria-label", "Show password");
    button.setAttribute("aria-pressed", "false");
    button.title = "Show password";
    button.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/><path class="archipelago-eye-slash" d="M3 21 21 3"/></svg>';
    button.addEventListener("click", () => {
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
      button.title = visible ? "Hide password" : "Show password";
    });
    wrapper.appendChild(button);
  }
}

enhancePasswordFields();
new MutationObserver(enhancePasswordFields).observe(document.body, { childList: true, subtree: true });
