/* Admin Management JavaScript */

let currentAdmin = null;
let currentTenant = null;
let accessToken = null;
let refreshToken = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Check if already logged in (from localStorage)
    const savedToken = localStorage.getItem('admin_access_token');
    const savedAdmin = localStorage.getItem('admin_data');
    
    if (savedToken && savedAdmin) {
        accessToken = savedToken;
        currentAdmin = JSON.parse(savedAdmin);
        showAuthenticatedSection();
        loadAdminList();
    }
    
    // Setup event listeners
    setupEventListeners();
});

function setupEventListeners() {
    // Login form
    document.getElementById('loginForm')?.addEventListener('submit', handleLogin);
    
    // Register form
    document.getElementById('registerForm')?.addEventListener('submit', handleRegister);
    
    // 2FA form
    document.getElementById('twoFAForm')?.addEventListener('submit', handle2FAVerify);
    
    // Change password form
    document.getElementById('changePasswordForm')?.addEventListener('submit', handleChangePassword);
    
    // Email validation on blur
    document.getElementById('loginEmail')?.addEventListener('blur', function() {
        const email = this.value;
        if (email && !validateEmail(email)) {
            showInlineError('loginEmail', 'Please enter a valid email address');
        } else {
            clearInlineError('loginEmail');
        }
    });
    
    document.getElementById('regEmail')?.addEventListener('blur', function() {
        const email = this.value;
        if (email && !validateEmail(email)) {
            showInlineError('regEmail', 'Please enter a valid email address');
        } else {
            clearInlineError('regEmail');
        }
    });
    
    // Password strength indicator for registration
    document.getElementById('regPassword')?.addEventListener('input', function() {
        checkPasswordStrength(this.value);
    });
    
    // Clear errors on input
    ['loginEmail', 'loginPassword', 'regEmail', 'regPassword', 'regFullName', 'regTenantName'].forEach(fieldId => {
        document.getElementById(fieldId)?.addEventListener('input', function() {
            if (this.classList.contains('is-invalid')) {
                clearInlineError(fieldId);
            }
        });
    });
}

// Login handler
async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Logging in...';
    
    try {
        const response = await fetch('/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const result = await response.json();
        
        if (result.success) {
            if (result.data.requires_2fa) {
                // Show 2FA section overlay
                document.getElementById('twoFAAdminId').value = result.data.admin_id;
                document.getElementById('twoFASection').style.display = 'flex';
                showNotification('info', result.data.message);
            } else {
                // Login successful
                handleLoginSuccess(result.data);
            }
        } else {
            showNotification('error', result.error || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('error', 'Network error during login');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 2FA verification
async function handle2FAVerify(e) {
    e.preventDefault();
    
    const admin_id = document.getElementById('twoFAAdminId').value;
    const code = document.getElementById('twoFACode').value;
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Verifying...';
    
    try {
        const response = await fetch('/api/admin/verify-2fa', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ admin_id, code })
        });
        
        const result = await response.json();
        
        if (result.success) {
            handleLoginSuccess(result.data);
        } else {
            showNotification('error', result.error || '2FA verification failed');
        }
    } catch (error) {
        console.error('2FA error:', error);
        showNotification('error', 'Network error during 2FA verification');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Cancel 2FA and go back to login
function cancelTwoFA() {
    document.getElementById('twoFASection').style.display = 'none';
    document.getElementById('twoFACode').value = '';
    document.getElementById('twoFAAdminId').value = '';
    // Show auth container again (it has the tabs)
    const authContainer = document.querySelector('.auth-container');
    if (authContainer) authContainer.style.display = 'flex';
}

// Handle successful login
function handleLoginSuccess(data) {
    currentAdmin = data.admin;
    currentTenant = data.tenant;
    accessToken = data.access_token;
    refreshToken = data.refresh_token;
    
    // Save to localStorage
    localStorage.setItem('admin_access_token', accessToken);
    localStorage.setItem('admin_refresh_token', refreshToken);
    localStorage.setItem('admin_data', JSON.stringify(currentAdmin));
    localStorage.setItem('tenant_data', JSON.stringify(currentTenant));
    
    // Also save as jwt_token for compatibility with other pages
    localStorage.setItem('jwt_token', accessToken);
    
    // Set session cookie by calling a backend endpoint
    fetch('/api/admin/set-session', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
            admin_id: currentAdmin._id
        })
    }).then(() => {
        showNotification('success', 'Login successful!');
        
        // Redirect based on role
        const role = currentAdmin.role;
        const params = new URLSearchParams(window.location.search);
        let redirect = params.get('redirect');
        
        if (!redirect) {
            // Default redirects based on role
            if (role === 'super_admin') {
                redirect = '/super-admin/';
            } else {
                redirect = '/dashboard';
            }
        } else {
            // Validate redirect for security
            // Super admin shouldn't be redirected to tenant pages and vice versa
            if (role === 'super_admin' && !redirect.startsWith('/super-admin')) {
                redirect = '/super-admin/';
            } else if (role !== 'super_admin' && redirect.startsWith('/super-admin')) {
                redirect = '/dashboard';
            }
        }
        
        window.location.href = redirect;
    }).catch(err => {
        console.error('Session setup error:', err);
        showAuthenticatedSection();
        loadAdminList();
    });
}

// Register handler
async function handleRegister(e) {
    e.preventDefault();
    
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const full_name = document.getElementById('regFullName').value;
    const tenant_name = document.getElementById('regTenantName').value;
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Registering...';
    
    try {
        const response = await fetch('/api/admin/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password, full_name, tenant_name })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('success', 'Registration successful! You can now login.');
            document.getElementById('registerForm').reset();
            
            // Auto-fill login form
            document.getElementById('loginEmail').value = email;
        } else {
            showNotification('error', result.error || 'Registration failed');
        }
    } catch (error) {
        console.error('Register error:', error);
        showNotification('error', 'Network error during registration');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Show authenticated section
function showAuthenticatedSection() {
    // Hide login/register section (entire auth container)
    const authContainer = document.querySelector('.auth-container');
    if (authContainer) authContainer.style.display = 'none';
    
    // Hide 2FA overlay
    document.getElementById('twoFASection').style.display = 'none';
    
    // Show authenticated section
    document.getElementById('authenticatedSection').style.display = 'block';
    
    // Update profile display
    document.getElementById('profileEmail').textContent = currentAdmin.email;
    document.getElementById('profileName').textContent = currentAdmin.full_name || 'N/A';
    document.getElementById('profileRole').textContent = currentAdmin.role || 'admin';
    document.getElementById('profileTenant').textContent = currentTenant?.name || 'N/A';
    document.getElementById('profile2FA').textContent = currentAdmin['2fa_enabled'] ? 'Enabled' : 'Disabled';
    document.getElementById('profileStatus').textContent = currentAdmin.status;
    
    // Update 2FA button
    const btn = document.getElementById('toggle2FABtn');
    if (currentAdmin['2fa_enabled']) {
        btn.innerHTML = '<i class="fas fa-shield-alt me-1"></i>Disable 2FA';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-secondary');
    } else {
        btn.innerHTML = '<i class="fas fa-shield-alt me-1"></i>Enable 2FA';
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-warning');
    }
}

// Load admin list
async function loadAdminList() {
    if (!currentTenant || !accessToken) return;
    
    try {
        const response = await fetch(`/api/admin/list?tenant_id=${currentTenant._id}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayAdminList(result.data.admins);
            document.getElementById('totalAdmins').textContent = result.data.total;
        }
    } catch (error) {
        console.error('Load admin list error:', error);
    }
}

// Display admin list
function displayAdminList(admins) {
    const tbody = document.getElementById('adminListBody');
    
    if (!admins || admins.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No admins found</td></tr>';
        return;
    }
    
    tbody.innerHTML = admins.map(admin => `
        <tr>
            <td>${admin.email}</td>
            <td>${admin.full_name || 'N/A'}</td>
            <td><span class="badge bg-primary">${admin.role}</span></td>
            <td><span class="badge bg-${admin.status === 'active' ? 'success' : 'warning'}">${admin.status}</span></td>
            <td>${admin['2fa_enabled'] ? '<i class="fas fa-check text-success"></i>' : '<i class="fas fa-times text-muted"></i>'}</td>
            <td>${admin.last_login_at ? new Date(admin.last_login_at).toLocaleString() : 'Never'}</td>
            <td>
                ${admin._id !== currentAdmin._id ? `
                    <button class="btn btn-sm btn-warning" onclick="suspendAdmin('${admin._id}')">
                        <i class="fas fa-ban"></i>
                    </button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

// Change password
function showChangePassword() {
    document.getElementById('changePasswordSection').style.display = 'block';
}

function hideChangePassword() {
    document.getElementById('changePasswordSection').style.display = 'none';
    document.getElementById('changePasswordForm').reset();
}

async function handleChangePassword(e) {
    e.preventDefault();
    
    const old_password = document.getElementById('oldPassword').value;
    const new_password = document.getElementById('newPassword').value;
    
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Updating...';
    
    try {
        const response = await fetch('/api/admin/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                admin_id: currentAdmin._id,
                old_password,
                new_password
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('success', 'Password changed successfully!');
            hideChangePassword();
        } else {
            showNotification('error', result.error || 'Failed to change password');
        }
    } catch (error) {
        console.error('Change password error:', error);
        showNotification('error', 'Network error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// Toggle 2FA
async function toggle2FA() {
    const isEnabled = currentAdmin['2fa_enabled'];
    const endpoint = isEnabled ? '/api/admin/2fa/disable' : '/api/admin/2fa/enable';
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                admin_id: currentAdmin._id,
                method: 'email'
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentAdmin['2fa_enabled'] = !isEnabled;
            localStorage.setItem('admin_data', JSON.stringify(currentAdmin));
            showNotification('success', result.message);
            showAuthenticatedSection();
        } else {
            showNotification('error', result.error);
        }
    } catch (error) {
        console.error('Toggle 2FA error:', error);
        showNotification('error', 'Network error');
    }
}

// Suspend admin
async function suspendAdmin(adminId) {
    if (!confirm('Are you sure you want to suspend this admin?')) return;
    
    try {
        const response = await fetch(`/api/admin/${adminId}/suspend`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({
                reason: 'Suspended by administrator',
                suspended_by: currentAdmin._id
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('success', 'Admin suspended successfully');
            loadAdminList();
        } else {
            showNotification('error', result.error);
        }
    } catch (error) {
        console.error('Suspend admin error:', error);
        showNotification('error', 'Network error');
    }
}

// Logout
function logout() {
    // Call backend to clear session
    fetch('/api/admin/logout', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    }).finally(() => {
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_refresh_token');
        localStorage.removeItem('admin_data');
        localStorage.removeItem('tenant_data');
        
        currentAdmin = null;
        currentTenant = null;
        accessToken = null;
        refreshToken = null;
        
        showNotification('info', 'Logged out successfully');
        
        // Redirect to admin page (login)
        window.location.href = '/admin';
    });
}

/* ============================================
   UI/UX Enhancement Functions
   ============================================ */

// Toggle password visibility
function togglePassword(fieldId, buttonElement) {
    const field = document.getElementById(fieldId);
    const icon = buttonElement.querySelector('i');
    
    if (field.type === 'password') {
        field.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        field.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Validate email format
function validateEmail(email) {
    const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return re.test(String(email).toLowerCase());
}

// Check password strength
function checkPasswordStrength(password) {
    let strength = 0;
    const strengthIndicator = document.getElementById('passwordStrength');
    
    if (!password) {
        strengthIndicator.innerHTML = '';
        return;
    }
    
    // Length check
    if (password.length >= 8) strength += 25;
    if (password.length >= 12) strength += 15;
    
    // Complexity checks
    if (/[a-z]/.test(password)) strength += 15;
    if (/[A-Z]/.test(password)) strength += 15;
    if (/[0-9]/.test(password)) strength += 15;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 15;
    
    // Update indicator
    let color, text, barClass;
    if (strength < 40) {
        color = '#dc3545';
        text = 'Weak';
        barClass = 'strength-weak';
    } else if (strength < 70) {
        color = '#ffc107';
        text = 'Medium';
        barClass = 'strength-medium';
    } else {
        color = '#28a745';
        text = 'Strong';
        barClass = 'strength-strong';
    }
    
    strengthIndicator.innerHTML = `<div class="strength-bar ${barClass}"></div>`;
}

// Show inline validation error
function showInlineError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const feedback = document.getElementById(fieldId + 'Error');
    
    if (message) {
        field.classList.add('is-invalid');
        field.classList.remove('is-valid');
        if (feedback) {
            feedback.textContent = message;
            feedback.style.display = 'block';
        }
    } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
        if (feedback) {
            feedback.style.display = 'none';
        }
    }
}

// Clear inline errors
function clearInlineError(fieldId) {
    showInlineError(fieldId, null);
}
