/**
 * Auth Module - SAINT RBAC
 * Handles: role-based UI, token refresh, auto-logout, AJAX interceptor
 * Loaded in base.html on every page (except login.html)
 */
(function () {
    'use strict';

    const AUTH_ME_API = '/api/admin/auth/me';
    const AUTH_REFRESH_API = '/api/admin/auth/refresh';
    const AUTH_LOGOUT_API = '/api/admin/auth/logout';
    const LOGIN_URL = '/login';

    // Token refresh interval (20 minutes)
    const REFRESH_INTERVAL_MS = 20 * 60 * 1000;

    // ========================================================================
    // GLOBAL AUTH STATE
    // ========================================================================

    window.SAINT_AUTH = {
        user: null,
        role: null,
        isAdmin: false,
        isTeacher: false,
        isLoggedIn: false,
    };

    // ========================================================================
    // INITIALIZATION
    // ========================================================================

    document.addEventListener('DOMContentLoaded', async function () {
        // Skip auth on login page
        if (window.location.pathname === '/login') return;

        await initAuth();
    });

    async function initAuth() {
        // Try to get user from sessionStorage first (fast UI)
        const cached = sessionStorage.getItem('saint_user');
        if (cached) {
            try {
                const user = JSON.parse(cached);
                applyUserUI(user);
            } catch (e) { /* ignore parse errors */ }
        }

        // Verify with server (authoritative)
        try {
            const resp = await fetch(AUTH_ME_API, { credentials: 'same-origin' });

            if (resp.status === 401) {
                // Not authenticated
                handleNotAuthenticated();
                return;
            }

            if (!resp.ok) return;

            const data = await resp.json();
            if (data.success && data.data) {
                const user = data.data;
                sessionStorage.setItem('saint_user', JSON.stringify({
                    username: user.username,
                    role: user.role,
                    _id: user._id,
                }));
                applyUserUI(user);
                startTokenRefreshTimer();
            }
        } catch (err) {
            console.warn('Auth check failed:', err);
            // If server unreachable, use cached data
        }
    }

    // ========================================================================
    // ROLE-BASED UI
    // ========================================================================

    function applyUserUI(user) {
        if (!user) return;

        // Update global state
        window.SAINT_AUTH.user = user;
        window.SAINT_AUTH.role = user.role;
        window.SAINT_AUTH.isAdmin = user.role === 'admin';
        window.SAINT_AUTH.isTeacher = user.role === 'teacher';
        window.SAINT_AUTH.isLoggedIn = true;

        // Update navbar username & role badge
        const navUsername = document.getElementById('navUsername');
        const navRoleBadge = document.getElementById('navRoleBadge');
        const navUserFull = document.getElementById('navUserFull');
        const userMenuDropdown = document.getElementById('userMenuDropdown');

        if (navUsername) navUsername.textContent = user.username;
        if (navUserFull) navUserFull.textContent = user.username + ' (' + user.role + ')';
        if (navRoleBadge) {
            navRoleBadge.textContent = user.role;
            if (user.role === 'admin') {
                navRoleBadge.className = 'badge rounded-pill ms-1 bg-danger';
            } else {
                navRoleBadge.className = 'badge rounded-pill ms-1 bg-success';
            }
        }
        if (userMenuDropdown) userMenuDropdown.style.display = '';

        // Show admin-only nav items
        if (user.role === 'admin') {
            document.querySelectorAll('.rbac-admin-only').forEach(el => {
                el.style.display = '';
            });
        }

        // Hide admin-only content from teachers
        if (user.role === 'teacher') {
            document.querySelectorAll('.rbac-admin-only').forEach(el => {
                el.style.display = 'none';
            });
            document.querySelectorAll('.rbac-teacher-hide').forEach(el => {
                el.style.display = 'none';
            });
        }

        // Show teacher-specific content
        document.querySelectorAll('.rbac-teacher-only').forEach(el => {
            el.style.display = user.role === 'teacher' ? '' : 'none';
        });

        // Setup logout button
        const logoutBtn = document.getElementById('navLogoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', function (e) {
                e.preventDefault();
                doLogout();
            });
        }
    }

    // ========================================================================
    // NOT AUTHENTICATED HANDLER
    // ========================================================================

    function handleNotAuthenticated() {
        window.SAINT_AUTH.isLoggedIn = false;
        window.SAINT_AUTH.user = null;
        sessionStorage.removeItem('saint_user');

        // Redirect to login (except if already on login page)
        if (window.location.pathname !== LOGIN_URL) {
            window.location.href = LOGIN_URL;
        }
    }

    // ========================================================================
    // TOKEN REFRESH
    // ========================================================================

    let refreshTimer = null;

    function startTokenRefreshTimer() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(refreshToken, REFRESH_INTERVAL_MS);
    }

    async function refreshToken() {
        try {
            const resp = await fetch(AUTH_REFRESH_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({}),
            });

            if (resp.status === 401) {
                // Refresh failed, session expired
                console.warn('Token refresh failed, session expired');
                handleNotAuthenticated();
                return false;
            }

            if (resp.ok) {
                console.debug('Token refreshed successfully');
                return true;
            }
        } catch (err) {
            console.warn('Token refresh error:', err);
        }
        return false;
    }

    // ========================================================================
    // LOGOUT
    // ========================================================================

    async function doLogout() {
        try {
            await fetch(AUTH_LOGOUT_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({}),
            });
        } catch (err) {
            console.warn('Logout request failed:', err);
        }

        // Always clear client state and redirect
        sessionStorage.removeItem('saint_user');
        window.SAINT_AUTH.isLoggedIn = false;
        window.SAINT_AUTH.user = null;
        window.location.href = LOGIN_URL;
    }

    // ========================================================================
    // FETCH INTERCEPTOR - Auto-handle 401 responses
    // ========================================================================

    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        const response = await originalFetch.apply(this, args);

        // If any API returns 401 (except auth endpoints), try refresh then retry
        if (response.status === 401) {
            const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';

            // Don't intercept login/refresh/me endpoints to avoid loops
            if (!url.includes('/admin/auth/')) {
                // Try to refresh token
                const refreshed = await refreshToken();
                if (refreshed) {
                    // Retry original request
                    return originalFetch.apply(this, args);
                } else {
                    // Refresh failed, redirect to login
                    handleNotAuthenticated();
                }
            }
        }

        return response;
    };

    // ========================================================================
    // HELPER: Check permission (for JS-side UI logic)
    // ========================================================================

    window.SAINT_AUTH.hasPermission = function (permission) {
        // Simplified client-side check (server always validates too)
        if (!window.SAINT_AUTH.isLoggedIn) return false;
        if (window.SAINT_AUTH.isAdmin) return true;

        // Teacher permissions (same as config/rbac_config.py TEACHER_PERMISSIONS)
        const teacherPermissions = [
            'profile:read', 'profile:change_password', 'dashboard:read',
            'groups:read', 'groups:create', 'groups:update', 'groups:delete', 'groups:manage_agents',
            'agents:read', 'agents:detail',
            'whitelist:read', 'whitelist:create', 'whitelist:update', 'whitelist:delete', 'whitelist:sync',
            'logs:read',
        ];

        return teacherPermissions.includes(permission);
    };

    // Expose logout for external use
    window.SAINT_AUTH.logout = doLogout;
    window.SAINT_AUTH.refresh = refreshToken;

})();
