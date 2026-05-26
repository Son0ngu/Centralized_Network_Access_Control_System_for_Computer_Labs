/**
 * SaintDate — consistent Vietnam-locale formatting for timestamps from the server.
 *
 * Why this module exists: ``formatDate`` was reimplemented at least five times
 * (admin_users.js, admin_audit.html, api_keys.html, profile.html, group_detail
 * had its own ``formatDates`` plural variant). They returned subtly different
 * shapes — some HH:mm, some HH:mm:ss; some with year, some without.
 *
 * Server contract: every timestamp shipped over the API is ISO 8601 with a
 * timezone offset (Vietnam time, +07:00). Don't try to interpret naive strings
 * here; if the server forgets to attach a tz, fix it at the source, not here.
 *
 * Public surface:
 *   SaintDate.formatVN(iso, options?)  // "12/05/2026 14:30"
 *   SaintDate.formatVNFull(iso)        // "12/05/2026 14:30:25"
 *   SaintDate.formatDateOnly(iso)      // "12/05/2026"
 *   SaintDate.relativeTime(iso)        // "5 phút trước"
 */

(function (global) {
  'use strict';

  const TZ = 'Asia/Ho_Chi_Minh';

  function _toDate(input) {
    if (!input) return null;
    if (input instanceof Date) return input;
    // Numeric epoch (ms or s) — accept both, sniff by magnitude.
    if (typeof input === 'number') {
      return new Date(input > 1e12 ? input : input * 1000);
    }
    const d = new Date(input);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // ``options`` mirrors Intl.DateTimeFormat. We default to Vietnam time and
  // the dd/MM/yyyy ordering the UI uses everywhere.
  const DEFAULT_DT = {
    timeZone: TZ,
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    hour12: false,
  };

  function formatVN(input, override = {}) {
    const d = _toDate(input);
    if (!d) return '';
    try {
      return new Intl.DateTimeFormat('vi-VN', { ...DEFAULT_DT, ...override }).format(d);
    } catch (_) {
      // Locale not supported in this engine — fall back to a stable ISO slice.
      return d.toISOString().replace('T', ' ').slice(0, 16);
    }
  }

  function formatVNFull(input) {
    return formatVN(input, { second: '2-digit' });
  }

  function formatDateOnly(input) {
    return formatVN(input, { hour: undefined, minute: undefined });
  }

  // Relative time in Vietnamese — useful for "last heartbeat 5 phút trước"
  // style chips. Falls back to absolute date for anything older than a week.
  function relativeTime(input) {
    const d = _toDate(input);
    if (!d) return '';
    const diffMs = Date.now() - d.getTime();
    const seconds = Math.floor(diffMs / 1000);
    if (seconds < 30) return 'vừa xong';
    if (seconds < 60) return `${seconds} giây trước`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} phút trước`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} giờ trước`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days} ngày trước`;
    return formatDateOnly(d);
  }

  global.SaintDate = { formatVN, formatVNFull, formatDateOnly, relativeTime };

  // Backwards-compat: legacy pages call a bare ``formatDate(iso)``. Route it
  // through the canonical impl so a future "remove duplicates" pass can grep
  // for old definitions and delete them safely.
  if (typeof global.formatDate !== 'function') {
    global.formatDate = formatVN;
  }
})(window);
