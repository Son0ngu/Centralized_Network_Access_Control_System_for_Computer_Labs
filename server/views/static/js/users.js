// ========================================
// USER MANAGEMENT PAGE
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    loadStats();
});

// ------------------------------------------------------------------
// LOAD USERS
// ------------------------------------------------------------------
async function loadUsers() {
    const search = document.getElementById('userSearch')?.value || '';
    const role = document.getElementById('roleFilter')?.value || '';

    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (role) params.set('role', role);

    try {
        const res = await fetch(`/api/users?${params}`);
        const data = await res.json();

        if (!data.success) {
            document.getElementById('usersTbody').innerHTML =
                '<tr><td colspan="6" class="text-center py-4 text-danger">Lỗi tải dữ liệu</td></tr>';
            return;
        }

        const users = data.users || [];
        if (users.length === 0) {
            document.getElementById('usersTbody').innerHTML =
                '<tr><td colspan="6" class="text-center py-4 text-muted">Không có tài khoản nào</td></tr>';
            return;
        }

        document.getElementById('usersTbody').innerHTML = users.map(u => {
            const roleClass = u.role === 'admin' ? 'role-admin' : 'role-teacher';
            const roleLabel = u.role === 'admin' ? 'Admin' : 'Teacher';
            const statusBadge = u.is_active
                ? '<span class="badge bg-success">Active</span>'
                : '<span class="badge bg-secondary">Inactive</span>';
            const lastLogin = u.last_login ? formatDate(u.last_login) : '<span class="text-muted">—</span>';

            return `
                <tr>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="user-avatar">
                                <i class="fas ${u.role === 'admin' ? 'fa-user-shield' : 'fa-chalkboard-teacher'}"></i>
                            </div>
                            <strong>${esc(u.username)}</strong>
                        </div>
                    </td>
                    <td>${esc(u.email || '—')}</td>
                    <td><span class="role-badge ${roleClass}">${roleLabel}</span></td>
                    <td>${statusBadge}</td>
                    <td class="small">${lastLogin}</td>
                    <td class="text-end user-actions">
                        <button class="btn btn-outline-primary btn-sm" onclick="openEditModal('${u._id}')" title="Sửa">
                            <i class="fas fa-pen"></i>
                        </button>
                        <button class="btn btn-outline-warning btn-sm" onclick="openResetPw('${u._id}', '${esc(u.username)}')" title="Đặt lại mật khẩu">
                            <i class="fas fa-key"></i>
                        </button>
                        <button class="btn btn-outline-${u.is_active ? 'secondary' : 'success'} btn-sm" onclick="toggleActive('${u._id}', ${!u.is_active})" title="${u.is_active ? 'Vô hiệu hoá' : 'Kích hoạt'}">
                            <i class="fas fa-${u.is_active ? 'ban' : 'check'}"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="deleteUser('${u._id}', '${esc(u.username)}')" title="Xoá">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                </tr>`;
        }).join('');

    } catch (err) {
        console.error('loadUsers error:', err);
        document.getElementById('usersTbody').innerHTML =
            '<tr><td colspan="6" class="text-center py-4 text-danger">Lỗi kết nối server</td></tr>';
    }
}

// ------------------------------------------------------------------
// LOAD STATS
// ------------------------------------------------------------------
async function loadStats() {
    try {
        const res = await fetch('/api/users/statistics');
        const data = await res.json();
        if (!data.success) return;

        document.getElementById('statTotal').textContent = data.total || 0;
        document.getElementById('statAdmin').textContent = (data.by_role || {}).admin || 0;
        document.getElementById('statTeacher').textContent = (data.by_role || {}).teacher || 0;
        document.getElementById('statInactive').textContent = data.inactive || 0;
    } catch (err) {
        console.error('loadStats error:', err);
    }
}

// ------------------------------------------------------------------
// CREATE
// ------------------------------------------------------------------
function openCreateModal() {
    document.getElementById('userModalTitle').innerHTML = '<i class="fas fa-user-plus me-2"></i>Tạo tài khoản';
    document.getElementById('editUserId').value = '';
    document.getElementById('inputUsername').value = '';
    document.getElementById('inputUsername').disabled = false;
    document.getElementById('inputPassword').value = '';
    document.getElementById('passwordGroup').style.display = '';
    document.getElementById('inputEmail').value = '';
    document.getElementById('inputRole').value = 'teacher';
    new bootstrap.Modal(document.getElementById('userModal')).show();
}

// ------------------------------------------------------------------
// EDIT
// ------------------------------------------------------------------
async function openEditModal(userId) {
    try {
        const res = await fetch(`/api/users/${userId}`);
        const data = await res.json();
        if (!data.success) { showError(data.error); return; }

        const u = data.user;
        document.getElementById('userModalTitle').innerHTML = '<i class="fas fa-pen me-2"></i>Chỉnh sửa tài khoản';
        document.getElementById('editUserId').value = u._id;
        document.getElementById('inputUsername').value = u.username;
        document.getElementById('inputUsername').disabled = true;
        document.getElementById('passwordGroup').style.display = 'none';
        document.getElementById('inputEmail').value = u.email || '';
        document.getElementById('inputRole').value = u.role;
        new bootstrap.Modal(document.getElementById('userModal')).show();
    } catch (err) {
        showError('Lỗi kết nối');
    }
}

// ------------------------------------------------------------------
// SAVE (create or update)
// ------------------------------------------------------------------
async function saveUser() {
    const userId = document.getElementById('editUserId').value;
    const isEdit = !!userId;

    const username = document.getElementById('inputUsername').value.trim();
    const password = document.getElementById('inputPassword').value.trim();
    const email = document.getElementById('inputEmail').value.trim();
    const role = document.getElementById('inputRole').value;

    if (!isEdit && (!username || username.length < 3)) {
        showError('Username tối thiểu 3 ký tự'); return;
    }
    if (!isEdit && (!password || password.length < 6)) {
        showError('Password tối thiểu 6 ký tự'); return;
    }

    const btn = document.getElementById('btnSaveUser');
    btn.disabled = true;

    try {
        let res;
        if (isEdit) {
            res = await fetch(`/api/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, role }),
            });
        } else {
            res = await fetch('/api/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, email, role }),
            });
        }

        const data = await res.json();
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('userModal'))?.hide();
            showSuccess(data.message || 'Thành công');
            loadUsers();
            loadStats();
        } else {
            showError(data.error || 'Lỗi');
        }
    } catch (err) {
        showError('Lỗi kết nối');
    } finally {
        btn.disabled = false;
    }
}

// ------------------------------------------------------------------
// TOGGLE ACTIVE
// ------------------------------------------------------------------
async function toggleActive(userId, newActive) {
    try {
        const res = await fetch(`/api/users/${userId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: newActive }),
        });
        const data = await res.json();
        if (data.success) {
            showSuccess(newActive ? 'Đã kích hoạt' : 'Đã vô hiệu hoá');
            loadUsers();
            loadStats();
        } else {
            showError(data.error);
        }
    } catch (err) {
        showError('Lỗi kết nối');
    }
}

// ------------------------------------------------------------------
// DELETE
// ------------------------------------------------------------------
async function deleteUser(userId, username) {
    if (!confirm(`Xoá tài khoản "${username}"? Hành động này không thể hoàn tác.`)) return;

    try {
        const res = await fetch(`/api/users/${userId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showSuccess(data.message || 'Đã xoá');
            loadUsers();
            loadStats();
        } else {
            showError(data.error);
        }
    } catch (err) {
        showError('Lỗi kết nối');
    }
}

// ------------------------------------------------------------------
// RESET PASSWORD
// ------------------------------------------------------------------
function openResetPw(userId, username) {
    document.getElementById('resetPwUserId').value = userId;
    document.getElementById('resetPwUsername').textContent = username;
    document.getElementById('resetPwInput').value = '';
    new bootstrap.Modal(document.getElementById('resetPwModal')).show();
}

async function doResetPassword() {
    const userId = document.getElementById('resetPwUserId').value;
    const newPw = document.getElementById('resetPwInput').value.trim();

    if (!newPw || newPw.length < 6) {
        showError('Mật khẩu tối thiểu 6 ký tự'); return;
    }

    try {
        const res = await fetch(`/api/users/${userId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPw }),
        });
        const data = await res.json();
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('resetPwModal'))?.hide();
            showSuccess(data.message || 'Đã đặt lại mật khẩu');
        } else {
            showError(data.error);
        }
    } catch (err) {
        showError('Lỗi kết nối');
    }
}

// ------------------------------------------------------------------
// HELPERS
// ------------------------------------------------------------------
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(str) {
    if (!str || str === 'None') return '—';
    try {
        const d = new Date(str);
        if (isNaN(d.getTime())) return str;
        return d.toLocaleDateString('vi-VN') + ' ' + d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    } catch { return str; }
}
