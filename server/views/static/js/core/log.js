/**
 * SaintLog — opt-in debug console for SAINT admin pages.
 *
 * Why: the page scripts grew dozens of ``console.log("Loading agents...")``
 * style breadcrumbs that ship to production unconditionally. They pollute
 * the browser console for operators and leak structure (endpoints, agent
 * ids) to anyone with DevTools open.
 *
 * Contract:
 *   - ``SaintLog.debug(...)`` / ``SaintLog.info(...)`` write only when the
 *     global flag ``window.__SAINT_DEBUG__ === true`` is set. Operators
 *     can enable it from DevTools when triaging without a rebuild:
 *
 *         window.__SAINT_DEBUG__ = true
 *
 *   - ``SaintLog.warn`` / ``SaintLog.error`` always write — they signal
 *     real bugs that on-call wants to see in default consoles.
 *
 *   - The shim is intentionally tiny (no log levels, no formatters) so
 *     page scripts don't need to learn a new API; just s/console.log/SaintLog.debug.
 */

(function (global) {
  'use strict';

  function _enabled() {
    return global.__SAINT_DEBUG__ === true;
  }

  const SaintLog = {
    debug: function (...args) {
      if (_enabled()) console.log(...args);
    },
    info: function (...args) {
      if (_enabled()) console.info(...args);
    },
    warn: function (...args) {
      // Warnings always reach the console — they are signals, not noise.
      console.warn(...args);
    },
    error: function (...args) {
      console.error(...args);
    },
    isEnabled: _enabled,
  };

  global.SaintLog = SaintLog;
})(window);
