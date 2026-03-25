/**
 * Admin Users Management - SAINT RBAC
 * CRUD Teacher accounts (Admin only)
 */
(function () {
    'use strict';

    const API_BASE = '/api/admin/users';
    const PAGE_SIZE = 20;

    let currentPage = 0;
    let totalUsers = 0;

    document.addEventListener('DOMContentLoaded', function () {
        loadUsers();
        loadStats();
        bindEvents();
        
        // Initialize custom selects
        if (typeof window.initCustomSelect === 'function') {
            window.initCustomSelect('filterRole');
            window.initCustomSelect('filterStatus');
            window.initCustomSelect('createRole');
        }
    });

    // ========================================================================
    // LOAD DATA
    // ========================================================================

    async function loadUsers() {
        const search = document.getElementById('searchInput').value.trim();
        const role = document.getElementById('filterRole').value;
        const isActive = document.getElementById('filterStatus').value;

        const params = new URLSearchParams();
        if (search) params.set('search', search);
        if (role) params.set('role', role);
        if (isActive) params.set('is_active', isActive);
        params.set('limit', PAGE_SIZE);
        params.set('skip', currentPage * PAGE_SIZE);

        try {
            const resp = await fetch(`${API_BASE}?${params}`, { credentials: 'same-origin' });
            const data = await resp.json();

            if (data.success) {
                totalUsers = data.data.total || 0;
                renderTable(data.data.users || []);
                renderPagination();
            } else {
                showNotification('danger', data.error || 'Error loading data');
            }
        } catch (err) {
            console.error('Load users error:', err);
            showNotification('danger', 'Cannot load account list');
        }
    }

    async function loadStats() {
        try {
            const resp = await fetch(`${API_BASE}/statistics`, { credentials: 'same-origin' });
            const data = await resp.json();
            if (data.success) {
                const s = data.data;
                document.getElementById('statTotal').textContent = s.total || 0;
                document.getElementById('statAdmin').textContent = (s.by_role && s.by_role.admin) || 0;
                document.getElementById('statTeacher').textContent = (s.by_role && s.by_role.teacher) || 0;
                document.getElementById('statInactive').textContent = s.inactive || 0;
            }
        } catch (err) {
            console.error('Load stats error:', err);
        }
    }

    // ========================================================================
    // RENDER TABLE
    // ========================================================================

    function renderTable(users) {
        const tbody = document.getElementById('usersTableBody');

        if (!users.length) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">
                <i class="fas fa-users me-2"></i>No accounts found
            </td></tr>`;
            return;
        }

        tbody.innerHTML = users.map(u => `
            <tr class="user-row">
                <td class="text-nowrap">
                    <i class="fas fa-user-circle me-2 text-${u.role === 'admin' ? 'danger' : 'success'}"></i>
                    <strong>${escHtml(u.username)}</strong>
                </td>
                <td class="text-nowrap">${u.email ? escHtml(u.email) : '<span class="text-muted">-</span>'}</td>
                <td class="text-nowrap">
                    <span class="badge badge-${u.role}">${u.role}</span>
                </td>
                <td class="text-nowrap">
                    ${u.is_active
                        ? '<span class="badge bg-success"><i class="fas fa-check me-1"></i>Active</span>'
                        : '<span class="badge bg-secondary"><i class="fas fa-ban me-1"></i>Inactive</span>'}
                </td>
                <td class="d-none d-lg-table-cell text-nowrap"><small>${u.last_login ? formatDate(u.last_login) : '<span class="text-muted">Never logged in</span>'}</small></td>
                <td class="d-none d-lg-table-cell text-nowrap"><small>${formatDate(u.created_at)}</small></td>
                <td class="text-end text-nowrap">
                    <button class="btn btn-sm btn-outline-warning action-btn me-1"
                            onclick="userActions.toggleActive('${u._id}', ${!u.is_active})"
                            title="${u.is_active ? 'Deactivate' : 'Activate'}">
                        <i class="fas fa-${u.is_active ? 'ban' : 'check'}"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-info action-btn me-1"
                            onclick="userActions.openResetPassword('${u._id}', '${escHtml(u.username)}')"
                            title="Reset password">
                        <i class="fas fa-key"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger action-btn"
                            onclick="userActions.deleteUser('${u._id}', '${escHtml(u.username)}')"
                            title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    function renderPagination() {
        const totalPages = Math.ceil(totalUsers / PAGE_SIZE);
        const info = document.getElementById('paginationInfo');
        const nav = document.getElementById('paginationNav');

        const start = currentPage * PAGE_SIZE + 1;
        const end = Math.min((currentPage + 1) * PAGE_SIZE, totalUsers);
        info.textContent = totalUsers > 0
            ? `Showing ${start}-${end} of ${totalUsers} accounts`
            : 'No accounts found';

        if (totalPages <= 1) { nav.innerHTML = ''; return; }

        let html = '';
        html += `<li class="page-item ${currentPage === 0 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage - 1}">&laquo;</a></li>`;
        for (let i = 0; i < totalPages; i++) {
            html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i + 1}</a></li>`;
        }
        html += `<li class="page-item ${currentPage >= totalPages - 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage + 1}">&raquo;</a></li>`;
        nav.innerHTML = html;

        nav.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                const page = parseInt(this.dataset.page);
                if (page >= 0 && page < totalPages) {
                    currentPage = page;
                    loadUsers();
                }
            });
        });
    }

    // ========================================================================
    // ACTIONS
    // ========================================================================

    window.userActions = {
        async toggleActive(userId, newState) {
            const action = newState ? 'activate' : 'deactivate';
            if (!confirm(`Are you sure you want to ${action} this account?`)) return;

            try {
                const resp = await fetch(`${API_BASE}/${userId}/toggle-active`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ is_active: newState }),
                });
                const data = await resp.json();
                if (data.success) {
                    showNotification('success', data.message);
                    loadUsers();
                    loadStats();
                } else {
                    showNotification('danger', data.error);
                }
            } catch (err) {
                showNotification('danger', 'Operation failed');
            }
        },

        openResetPassword(userId, username) {
            document.getElementById('resetUserId').value = userId;
            document.getElementById('resetUsername').textContent = username;
            document.getElementById('resetNewPassword').value = '';
            document.getElementById('resetAlert').classList.add('d-none');
            new bootstrap.Modal(document.getElementById('resetPasswordModal')).show();
        },

        async deleteUser(userId, username) {
            if (!confirm(`Are you sure you want to DELETE account "${username}"? This action cannot be undone!`)) return;

            try {
                const resp = await fetch(`${API_BASE}/${userId}`, {
                    method: 'DELETE',
                    credentials: 'same-origin',
                });
                const data = await resp.json();
                if (data.success) {
                    showNotification('success', data.message);
                    loadUsers();
                    loadStats();
                } else {
                    showNotification('danger', data.error);
                }
            } catch (err) {
                showNotification('danger', 'Delete failed');
            }
        },
    };

    // ========================================================================
    // BIND EVENTS
    // ========================================================================

    function bindEvents() {
        // Search (debounced)
        let searchTimer;
        document.getElementById('searchInput').addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => { currentPage = 0; loadUsers(); }, 400);
        });

        // Filters
        document.getElementById('filterRole').addEventListener('change', () => { currentPage = 0; loadUsers(); });
        document.getElementById('filterStatus').addEventListener('change', () => { currentPage = 0; loadUsers(); });

        // Refresh
        document.getElementById('refreshBtn').addEventListener('click', () => { loadUsers(); loadStats(); });

        // Create user
        document.getElementById('createUserBtn').addEventListener('click', createUser);

        // Reset password
        document.getElementById('resetPasswordBtn').addEventListener('click', resetPassword);
    }

    async function createUser() {
        const alertEl = document.getElementById('createAlert');
        alertEl.classList.add('d-none');

        const username = document.getElementById('createUsername').value.trim();
        const password = document.getElementById('createPassword').value;
        const email = document.getElementById('createEmail').value.trim();
        const role = document.getElementById('createRole').value;

        if (!username || !password) {
            alertEl.textContent = 'Username and password are required';
            alertEl.classList.remove('d-none');
            return;
        }

        const btn = document.getElementById('createUserBtn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Creating...';

        try {
            const resp = await fetch(API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ username, password, email: email || undefined, role }),
            });
            const data = await resp.json();

            if (data.success) {
                showNotification('success', 'Account created successfully!');
                bootstrap.Modal.getInstance(document.getElementById('createUserModal')).hide();
                document.getElementById('createUserForm').reset();
                loadUsers();
                loadStats();
            } else {
                alertEl.textContent = data.error || 'Creation failed';
                alertEl.classList.remove('d-none');
            }
        } catch (err) {
            alertEl.textContent = 'Server connection error';
            alertEl.classList.remove('d-none');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-plus me-1"></i>Create account';
        }
    }

    async function resetPassword() {
        const alertEl = document.getElementById('resetAlert');
        alertEl.classList.add('d-none');

        const userId = document.getElementById('resetUserId').value;
        const newPassword = document.getElementById('resetNewPassword').value;

        if (!newPassword || newPassword.length < 8) {
            alertEl.textContent = 'Password must be at least 8 characters';
            alertEl.classList.remove('d-none');
            return;
        }

        try {
            const resp = await fetch(`${API_BASE}/${userId}/reset-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ new_password: newPassword }),
            });
            const data = await resp.json();

            if (data.success) {
                showNotification('success', 'Password reset successfully!');
                bootstrap.Modal.getInstance(document.getElementById('resetPasswordModal')).hide();
            } else {
                alertEl.textContent = data.error;
                alertEl.classList.remove('d-none');
            }
        } catch (err) {
            alertEl.textContent = 'Server connection error';
            alertEl.classList.remove('d-none');
        }
    }

    // ========================================================================
    // HELPERS
    // ========================================================================

    function escHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const d = new Date(dateStr);
            return d.toLocaleDateString('en-US') + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return dateStr;
        }
    }
})();
