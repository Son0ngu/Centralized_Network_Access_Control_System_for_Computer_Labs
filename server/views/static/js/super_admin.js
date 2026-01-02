/**
 * Super Admin JavaScript
 * Common functionality for all Super Admin pages
 */

// Global variables
let currentTenantId = null;

/**
 * Get JWT token from storage
 */
function getToken() {
    return localStorage.getItem('jwt_token') || sessionStorage.getItem('jwt_token') || '';
}

/**
 * Show toast notification
 */
function showToast(type, message) {
    // Check if toast container exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }

    const toastId = 'toast-' + Date.now();
    const bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning text-dark',
        'info': 'bg-info'
    }[type] || 'bg-secondary';

    const icon = {
        'success': 'fa-check-circle',
        'error': 'fa-times-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';

    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass}" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas ${icon} me-2"></i>${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 3000 });
    toast.show();

    // Remove after hiding
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Format relative time
 */
function formatRelativeTime(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
}

/**
 * Toggle password visibility
 */
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

/**
 * API request helper
 */
async function apiRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Authorization': 'Bearer ' + getToken(),
            'Content-Type': 'application/json'
        }
    };

    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }

    return data;
}

// ============ Dashboard Functions ============

/**
 * Load dashboard data
 */
async function loadDashboard() {
    try {
        const response = await fetch('/api/super/dashboard', {
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });
        const data = await response.json();

        if (data.success) {
            renderDashboardStats(data.data);
            loadRecentTenants();
            loadActiveBroadcasts();
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showToast('error', 'Failed to load dashboard data');
    }
}

/**
 * Render dashboard statistics
 */
function renderDashboardStats(data) {
    // Tenant stats
    document.getElementById('totalTenants').textContent = data.tenants?.total || 0;
    document.getElementById('activeTenants').textContent = data.tenants?.active || 0;
    document.getElementById('suspendedTenants').textContent = data.tenants?.suspended || 0;

    // Agent stats
    document.getElementById('totalAgents').textContent = data.agents?.total || 0;
    document.getElementById('onlineAgents').textContent = data.agents?.online || 0;
    document.getElementById('offlineAgents').textContent = (data.agents?.total || 0) - (data.agents?.online || 0);

    // Admin stats
    document.getElementById('totalAdmins').textContent = data.admins?.total || 0;
    document.getElementById('activeAdmins').textContent = data.admins?.active || 0;

    // Log stats
    document.getElementById('todayLogs').textContent = data.logs?.today || 0;
    document.getElementById('blockedToday').textContent = data.logs?.blocked_today || 0;

    // Health stats
    const health = data.health || {};
    document.getElementById('healthyTenants').textContent = health.healthy || 0;
    document.getElementById('warningTenants').textContent = health.warning || 0;
    document.getElementById('criticalTenants').textContent = health.critical || 0;

    // Update health bar
    updateHealthBar(health);
}

/**
 * Update health progress bar
 */
function updateHealthBar(health) {
    const total = (health.healthy || 0) + (health.warning || 0) + (health.critical || 0);
    if (total === 0) return;

    const healthyPercent = ((health.healthy || 0) / total) * 100;
    const warningPercent = ((health.warning || 0) / total) * 100;
    const criticalPercent = ((health.critical || 0) / total) * 100;

    document.getElementById('healthySegment').style.width = healthyPercent + '%';
    document.getElementById('warningSegment').style.width = warningPercent + '%';
    document.getElementById('criticalSegment').style.width = criticalPercent + '%';
}

/**
 * Load recent tenants for dashboard
 */
async function loadRecentTenants() {
    try {
        const response = await fetch('/api/super/tenants?limit=5&sort=created_at&order=desc', {
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });
        const data = await response.json();

        if (data.success) {
            renderRecentTenants(data.data.tenants);
        }
    } catch (error) {
        console.error('Error loading recent tenants:', error);
    }
}

/**
 * Render recent tenants table
 */
function renderRecentTenants(tenants) {
    const tbody = document.getElementById('recentTenantsTable');
    if (!tbody) return;

    if (!tenants || tenants.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-3 text-muted">
                    No tenants found
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = tenants.map(tenant => `
        <tr>
            <td>
                <strong>${escapeHtml(tenant.company_name)}</strong>
                <br><small class="text-muted">${escapeHtml(tenant.subdomain)}</small>
            </td>
            <td><span class="badge bg-info">${tenant.plan || 'Free'}</span></td>
            <td>
                <span class="text-success">${tenant.online_agents || 0}</span>/${tenant.total_agents || 0}
            </td>
            <td>
                <span class="badge bg-${tenant.status === 'active' ? 'success' : 'danger'}">
                    ${tenant.status}
                </span>
            </td>
            <td>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-warning btn-sm" onclick="openImpersonateModal('${tenant.tenant_id}', '${escapeHtml(tenant.company_name)}')" title="Impersonate">
                        <i class="fas fa-user-secret"></i>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/**
 * Load active broadcasts for dashboard
 */
async function loadActiveBroadcasts() {
    try {
        const response = await fetch('/api/super/broadcasts?status=active&limit=3', {
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });
        const data = await response.json();

        if (data.success) {
            renderDashboardBroadcasts(data.data.broadcasts);
        }
    } catch (error) {
        console.error('Error loading broadcasts:', error);
    }
}

/**
 * Render broadcasts for dashboard
 */
function renderDashboardBroadcasts(broadcasts) {
    const container = document.getElementById('activeBroadcasts');
    if (!container) return;

    if (!broadcasts || broadcasts.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="fas fa-bullhorn fa-2x mb-2"></i>
                <p class="mb-0">No active broadcasts</p>
            </div>`;
        return;
    }

    container.innerHTML = broadcasts.map(b => {
        const typeClass = {
            'info': 'alert-info',
            'warning': 'alert-warning',
            'critical': 'alert-danger',
            'maintenance': 'alert-secondary'
        }[b.broadcast_type] || 'alert-info';

        return `
            <div class="alert ${typeClass} mb-2">
                <strong>${escapeHtml(b.title)}</strong>
                <p class="mb-0 small">${escapeHtml(b.message?.substring(0, 100))}...</p>
            </div>
        `;
    }).join('');
}

// ============ Impersonation Functions ============

// Impersonation config constants (synced with server config)
const IMPERSONATION_CONFIG = {
    maxDurationHours: 4,
    minReasonLength: 10,
    warningMinutes: 15  // Show warning when less than this time remains
};

/**
 * Open impersonate modal
 */
function openImpersonateModal(tenantId, tenantName) {
    currentTenantId = tenantId;
    document.getElementById('impersonateTenantId').value = tenantId;
    document.getElementById('impersonateTenantName').textContent = tenantName;
    document.getElementById('impersonateReason').value = '';
    
    // Clear any previous validation state
    const reasonInput = document.getElementById('impersonateReason');
    reasonInput.classList.remove('is-invalid');
    
    // Update help text with min length requirement
    const helpText = document.querySelector('#impersonateModal .form-text');
    if (helpText) {
        helpText.textContent = `Required. Minimum ${IMPERSONATION_CONFIG.minReasonLength} characters. Max session: ${IMPERSONATION_CONFIG.maxDurationHours}h`;
    }
    
    new bootstrap.Modal(document.getElementById('impersonateModal')).show();
}

/**
 * Validate impersonation reason
 */
function validateImpersonationReason(reason) {
    if (!reason || reason.length < IMPERSONATION_CONFIG.minReasonLength) {
        return {
            valid: false,
            message: `Reason must be at least ${IMPERSONATION_CONFIG.minReasonLength} characters`
        };
    }
    return { valid: true };
}

/**
 * Confirm and start impersonation
 */
async function confirmImpersonation() {
    const tenantId = document.getElementById('impersonateTenantId').value;
    const reason = document.getElementById('impersonateReason').value.trim();
    const reasonInput = document.getElementById('impersonateReason');

    // Validate reason
    const validation = validateImpersonationReason(reason);
    if (!validation.valid) {
        reasonInput.classList.add('is-invalid');
        showToast('error', validation.message);
        return;
    }
    reasonInput.classList.remove('is-invalid');

    try {
        const response = await fetch(`/api/super/impersonate/${tenantId}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + getToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ reason })
        });

        const data = await response.json();

        if (data.success) {
            // Use ImpersonationHandler if available
            if (typeof ImpersonationHandler !== 'undefined') {
                ImpersonationHandler.start(data.data);
            } else {
                // Fallback: manual token handling
                localStorage.setItem('impersonation_token', data.data.token);
                localStorage.setItem('original_token', getToken());
                localStorage.setItem('jwt_token', data.data.token);
                localStorage.setItem('impersonation_data', JSON.stringify(data.data));
            }
            
            showToast('success', 'Impersonation started. Redirecting...');
            
            // Redirect to tenant dashboard
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1000);
        } else {
            showToast('error', data.error || 'Failed to start impersonation');
        }
    } catch (error) {
        console.error('Error starting impersonation:', error);
        showToast('error', 'Failed to start impersonation');
    }
}

/**
 * End impersonation session
 */
async function endImpersonation() {
    try {
        // Use ImpersonationHandler if available
        if (typeof ImpersonationHandler !== 'undefined') {
            await ImpersonationHandler.exit();
            return;
        }
        
        // Fallback: manual handling
        const response = await fetch('/api/super/end-impersonation', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + getToken(),
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        // Restore original token
        const originalToken = localStorage.getItem('original_token');
        if (originalToken) {
            localStorage.setItem('jwt_token', originalToken);
            localStorage.removeItem('original_token');
            localStorage.removeItem('impersonation_token');
            localStorage.removeItem('impersonation_data');
        }

        showToast('success', 'Impersonation ended');
        
        // Redirect back to super admin dashboard
        setTimeout(() => {
            window.location.href = '/super-admin/';
        }, 500);
    } catch (error) {
        console.error('Error ending impersonation:', error);
        showToast('error', 'Failed to end impersonation');
    }
}

/**
 * Check if currently impersonating
 */
function isImpersonating() {
    if (typeof ImpersonationHandler !== 'undefined') {
        return ImpersonationHandler.isActive();
    }
    return !!localStorage.getItem('impersonation_token');
}

/**
 * Get remaining impersonation time
 */
function getImpersonationTimeRemaining() {
    if (typeof ImpersonationHandler !== 'undefined') {
        return ImpersonationHandler.getTimeRemaining();
    }
    
    const data = localStorage.getItem('impersonation_data');
    if (!data) return null;
    
    try {
        const parsed = JSON.parse(data);
        const expiresAt = new Date(parsed.expires_at).getTime();
        const now = Date.now();
        return Math.max(0, expiresAt - now);
    } catch {
        return null;
    }
}

// ============ Initialize ============

document.addEventListener('DOMContentLoaded', function() {
    // Load dashboard if on dashboard page
    if (document.getElementById('totalTenants')) {
        loadDashboard();
    }

    // Auto-refresh dashboard every 60 seconds
    if (window.location.pathname === '/super-admin/' || window.location.pathname === '/super-admin') {
        setInterval(loadDashboard, 60000);
    }

    // Check if currently impersonating
    const impersonationToken = localStorage.getItem('impersonation_token');
    if (impersonationToken && !window.location.pathname.startsWith('/super-admin')) {
        // Show impersonation banner
        showImpersonationBanner();
    }
});

/**
 * Show impersonation banner when impersonating
 */
function showImpersonationBanner() {
    if (document.getElementById('impersonation-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'impersonation-banner';
    banner.className = 'alert alert-warning fixed-bottom mb-0 rounded-0 d-flex justify-content-between align-items-center';
    banner.innerHTML = `
        <span>
            <i class="fas fa-user-secret me-2"></i>
            <strong>Impersonation Mode Active</strong> - All actions are being logged
        </span>
        <button class="btn btn-sm btn-warning" onclick="endImpersonation()">
            <i class="fas fa-times me-1"></i>End Impersonation
        </button>
    `;
    document.body.appendChild(banner);
}
