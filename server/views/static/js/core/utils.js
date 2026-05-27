/**
 * SaintUtils — tiny shared helpers used by multiple admin pages.
 *
 * Why: ``escapeHtml`` / ``escHtml`` was reimplemented in at least three
 * page scripts (logs.js, admin_users.js, group_detail.js — and a partial
 * impl in whitelist.js as ``wlEscapeHtml``) with subtly different null
 * handling. A single canonical version avoids the next "missing escape"
 * XSS regression.
 *
 * Public surface (all under ``window.SaintUtils``):
 *   escapeHtml(value) -> string
 *     Coerces ``null``/``undefined`` to ``""`` and HTML-escapes by
 *     round-tripping through ``textContent``. Always returns a string.
 *
 * Page scripts keep their local ``escHtml`` / ``escapeHtml`` names as
 * thin wrappers around ``SaintUtils.escapeHtml`` so callers don't have to
 * change. New code should call ``SaintUtils.escapeHtml`` directly.
 */

(function (global) {
  'use strict';

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(value);
    return div.innerHTML;
  }

  global.SaintUtils = { escapeHtml };
})(window);
