/**
 * SaintToast — single ephemeral notification implementation for the SAINT admin UI.
 *
 * Why this module exists: ``showToast`` was duplicated across at least four
 * places (api_keys.html, profile.html, admin_users.js, and inline scripts in
 * several other templates). Every copy diverged slightly — different default
 * timeout, different colour-class names, some leaked timer handles. Now there
 * is one definition.
 *
 * Public surface:
 *   SaintToast.show(message, type = 'info', timeout = 3000)
 *   SaintToast.success(msg)  // sugar
 *   SaintToast.error(msg)
 *   SaintToast.warning(msg)
 *
 * Type maps to a Bootstrap-flavoured class:
 *   info     → bg-info text-white
 *   success  → bg-success text-white
 *   warning  → bg-warning text-dark
 *   error    → bg-danger text-white
 *
 * The toast container is created lazily on first call so pages don't need to
 * include a static placeholder. Multiple toasts stack vertically.
 */

(function (global) {
  'use strict';

  // The container is fixed-position in the top-right. Re-use across calls so
  // toasts stack instead of overlapping. Bootstrap utility classes assumed.
  function ensureContainer() {
    let container = document.getElementById('saint-toast-container');
    if (container) return container;
    container = document.createElement('div');
    container.id = 'saint-toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1080';
    document.body.appendChild(container);
    return container;
  }

  const TYPE_CLASS = {
    info: 'bg-info text-white',
    success: 'bg-success text-white',
    warning: 'bg-warning text-dark',
    error: 'bg-danger text-white',
    danger: 'bg-danger text-white', // legacy alias
  };

  function show(message, type = 'info', timeout = 3000) {
    const container = ensureContainer();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center border-0 mb-2 show ${TYPE_CLASS[type] || TYPE_CLASS.info}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${escapeHTML(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close"></button>
      </div>
    `;
    toast.querySelector('.btn-close').addEventListener('click', () => toast.remove());
    container.appendChild(toast);
    if (timeout > 0) {
      setTimeout(() => toast.remove(), timeout);
    }
    return toast;
  }

  function escapeHTML(s) {
    // Toasts often carry server-supplied error text. Escape so a malicious
    // error message can't smuggle script tags into the DOM.
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  const SaintToast = {
    show,
    success: (msg, t) => show(msg, 'success', t),
    error: (msg, t) => show(msg, 'error', t),
    warning: (msg, t) => show(msg, 'warning', t),
    info: (msg, t) => show(msg, 'info', t),
  };

  global.SaintToast = SaintToast;

  // Backwards-compat: every page used to define its own ``showToast``. Expose
  // a global of the same name pointing at the canonical impl so existing
  // inline scripts keep working until they're migrated.
  if (typeof global.showToast !== 'function') {
    global.showToast = show;
  }
})(window);
