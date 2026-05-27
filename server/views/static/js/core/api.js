/**
 * SaintAPI — single fetch wrapper for SAINT admin pages.
 *
 * Why this module exists: every page hand-rolled its own ``fetch`` call with
 * subtly different defaults (some included credentials, some didn't; some
 * parsed errors, some didn't; some attached the auth token via cookie, some
 * via header). Inconsistencies surfaced as "works in one page, 401 in
 * another" reports.
 *
 * Contract:
 *   - Always send cookies (``credentials: 'include'``). The admin web UI uses
 *     httpOnly cookies via WebAuthController.
 *   - Always set ``Accept: application/json`` so the server returns JSON
 *     error bodies instead of HTML error pages.
 *   - For state-changing methods (POST/PUT/PATCH/DELETE), attach the CSRF
 *     token from the non-httpOnly ``csrf_token`` cookie as an
 *     ``X-CSRF-Token`` header. The server middleware (see
 *     ``server/middleware/csrf.py``) validates the header against the cookie
 *     in a double-submit pattern. A cross-origin attacker cannot read the
 *     cookie (Same-Origin Policy) and therefore cannot forge the header.
 *   - Parse JSON on the way back. On non-2xx, throw a ``SaintAPIError``
 *     carrying the status code, the parsed body (if any), and the failed URL
 *     so call sites have something to log.
 *
 * Public surface:
 *   SaintAPI.get(url)
 *   SaintAPI.post(url, body)
 *   SaintAPI.put(url, body)
 *   SaintAPI.patch(url, body)
 *   SaintAPI.del(url)
 *   SaintAPI.raw(url, init)       // escape hatch for blobs/streams
 *   SaintAPI.getCsrfToken()       // read current token (e.g. for raw fetch)
 */

(function (global) {
  'use strict';

  const CSRF_COOKIE_NAME = 'csrf_token';
  const CSRF_HEADER_NAME = 'X-CSRF-Token';
  const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

  function _readCookie(name) {
    // document.cookie is "k1=v1; k2=v2"; we don't bother with a regex so
    // there's nothing for a malicious cookie value to break.
    const target = name + '=';
    const parts = (document.cookie || '').split(';');
    for (let i = 0; i < parts.length; i++) {
      const trimmed = parts[i].trim();
      if (trimmed.indexOf(target) === 0) {
        return decodeURIComponent(trimmed.substring(target.length));
      }
    }
    return null;
  }

  class SaintAPIError extends Error {
    constructor(message, { status, body, url } = {}) {
      super(message);
      this.name = 'SaintAPIError';
      this.status = status;
      this.body = body;
      this.url = url;
    }
  }

  async function _send(method, url, body) {
    const init = {
      method,
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
      },
    };
    if (body !== undefined && body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = typeof body === 'string' ? body : JSON.stringify(body);
    }
    if (UNSAFE_METHODS.has(method)) {
      const csrf = _readCookie(CSRF_COOKIE_NAME);
      if (csrf) {
        init.headers[CSRF_HEADER_NAME] = csrf;
      }
      // If the cookie is missing we still send the request; the server will
      // respond 403 with code=CSRF_FAIL and the caller can prompt re-login.
    }

    let response;
    try {
      response = await fetch(url, init);
    } catch (err) {
      // Network-level failure (DNS, CORS preflight, offline). Wrap so call
      // sites only have to ``catch (SaintAPIError)``.
      throw new SaintAPIError(`Network error: ${err.message}`, { url });
    }

    // 204 No Content / 205 Reset Content carry no body — return null instead
    // of trying to parse.
    if (response.status === 204 || response.status === 205) {
      if (!response.ok) {
        throw new SaintAPIError(`HTTP ${response.status}`, { status: response.status, url });
      }
      return null;
    }

    let parsed = null;
    const ct = response.headers.get('Content-Type') || '';
    if (ct.includes('application/json')) {
      try { parsed = await response.json(); } catch (_) { parsed = null; }
    } else {
      // Non-JSON response. Read as text so callers can still inspect a 5xx
      // HTML error page in the error.body.
      try { parsed = await response.text(); } catch (_) { parsed = null; }
    }

    if (!response.ok) {
      const message = (parsed && parsed.error) || (parsed && parsed.message)
        || `HTTP ${response.status}`;
      throw new SaintAPIError(message, {
        status: response.status,
        body: parsed,
        url,
      });
    }
    return parsed;
  }

  const SaintAPI = {
    get: (url) => _send('GET', url),
    post: (url, body) => _send('POST', url, body),
    put: (url, body) => _send('PUT', url, body),
    patch: (url, body) => _send('PATCH', url, body),
    del: (url) => _send('DELETE', url),
    raw: (url, init = {}) => {
      // Mirror the CSRF behaviour of the structured helpers so blob/stream
      // call sites stay safe without each one re-implementing the cookie
      // dance. The method header in `init` (if any) decides whether we
      // attach the token.
      const method = (init.method || 'GET').toUpperCase();
      const headers = Object.assign({}, init.headers || {});
      if (UNSAFE_METHODS.has(method)) {
        const csrf = _readCookie(CSRF_COOKIE_NAME);
        if (csrf && !headers[CSRF_HEADER_NAME]) {
          headers[CSRF_HEADER_NAME] = csrf;
        }
      }
      return fetch(url, { credentials: 'include', ...init, headers });
    },
    getCsrfToken: () => _readCookie(CSRF_COOKIE_NAME),
    Error: SaintAPIError,
  };

  global.SaintAPI = SaintAPI;
  global.SaintAPIError = SaintAPIError;
})(window);
