/**
 * Tenants Management JavaScript
 */

let tenantsData = [];
let currentPage = 1;
const pageSize = 20;

document.addEventListener('DOMContentLoaded', function() {
    loadTenants();
    setupEventListeners();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Search
    const searchInput = document.getElementById('searchTenant');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentPage = 1;
                loadTenants();
            }, 300);
        });
    }

    // Filters
    ['filterStatus', 'filterPlan'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', () => {
                currentPage = 1;
                loadTenants();
            });
        }
    });

    // Create tenant form
    const createForm = document.getElementById('createTenantForm');
    if (createForm) {
        createForm.addEventListener('submit', handleCreateTenant);
    }

    // Edit tenant form
    const editForm = document.getElementById('editTenantForm');
    if (editForm) {
        editForm.addEventListener('submit', handleEditTenant);
    }

    // Delete confirmation input
    const deleteInput = document.getElementById('deleteConfirmInput');
    if (deleteInput) {
        deleteInput.addEventListener('input', function() {
            const btn = document.getElementById('confirmDeleteBtn');
            btn.disabled = this.value !== 'DELETE';
        });
    }
}

/**
 * Load tenants from API
 */
async function loadTenants() {
    const search = document.getElementById('searchTenant')?.value || '';
    const status = document.getElementById('filterStatus')?.value || '';
    const plan = document.getElementById('filterPlan')?.value || '';

    let url = `/api/super/tenants?page=${currentPage}&limit=${pageSize}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (status) url += `&status=${status}`;
    if (plan) url += `&plan=${plan}`;

    try {
        const response = await fetch(url, {
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });
        const data = await response.json();

        if (data.success) {
            tenantsData = data.data.tenants;
            renderTenants(tenantsData);
            renderPagination(data.data.pagination);
        }
    } catch (error) {
        console.error('Error loading tenants:', error);
        showToast('error', 'Failed to load tenants');
    }
}

/**
 * Render tenants table
 */
function renderTenants(tenants) {
    const tbody = document.getElementById('tenantsTableBody');
    if (!tbody) return;

    if (!tenants || tenants.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5 text-muted">
                    <i class="fas fa-building fa-3x mb-3"></i>
                    <p class="mb-0">No tenants found</p>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = tenants.map(tenant => {
        const statusClass = tenant.status === 'active' ? 'success' : 
                           tenant.status === 'suspended' ? 'danger' : 'warning';
        
        const healthClass = tenant.health_status === 'healthy' ? 'success' :
                           tenant.health_status === 'warning' ? 'warning' : 'danger';

        const healthIcon = tenant.health_status === 'healthy' ? 'check-circle' :
                          tenant.health_status === 'warning' ? 'exclamation-triangle' : 'times-circle';

        return `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="avatar-sm bg-primary text-white rounded-circle d-flex align-items-center justify-content-center me-2">
                            ${tenant.company_name?.charAt(0)?.toUpperCase() || 'T'}
                        </div>
                        <div>
                            <strong>${escapeHtml(tenant.company_name)}</strong>
                            <br><small class="text-muted">${escapeHtml(tenant.subdomain)}.firewall.local</small>
                        </div>
                    </div>
                </td>
                <td><span class="badge bg-info">${tenant.plan || 'Free'}</span></td>
                <td>${tenant.admin_count || 0}</td>
                <td>
                    <span class="text-success">${tenant.online_agents || 0}</span>
                    <span class="text-muted">/</span>
                    <span>${tenant.total_agents || 0}</span>
                </td>
                <td>
                    <span class="badge bg-${statusClass}">${tenant.status}</span>
                </td>
                <td>
                    <span class="badge bg-${healthClass}">
                        <i class="fas fa-${healthIcon} me-1"></i>
                        ${tenant.health_status || 'unknown'}
                    </span>
                </td>
                <td>${formatDate(tenant.created_at)}</td>
                <td>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li>
                                <a class="dropdown-item" href="#" onclick="viewTenantDetails('${tenant.tenant_id}'); return false;">
                                    <i class="fas fa-eye me-2"></i>View Details
                                </a>
                            </li>
                            <li>
                                <a class="dropdown-item" href="#" onclick="editTenant('${tenant.tenant_id}'); return false;">
                                    <i class="fas fa-edit me-2"></i>Edit
                                </a>
                            </li>
                            <li>
                                <a class="dropdown-item text-warning" href="#" onclick="openImpersonateModal('${tenant.tenant_id}', '${escapeHtml(tenant.company_name)}'); return false;">
                                    <i class="fas fa-user-secret me-2"></i>Impersonate
                                </a>
                            </li>
                            <li><hr class="dropdown-divider"></li>
                            ${tenant.status === 'active' ? `
                                <li>
                                    <a class="dropdown-item text-warning" href="#" onclick="suspendTenant('${tenant.tenant_id}'); return false;">
                                        <i class="fas fa-pause me-2"></i>Suspend
                                    </a>
                                </li>
                            ` : `
                                <li>
                                    <a class="dropdown-item text-success" href="#" onclick="activateTenant('${tenant.tenant_id}'); return false;">
                                        <i class="fas fa-play me-2"></i>Activate
                                    </a>
                                </li>
                            `}
                            <li>
                                <a class="dropdown-item text-danger" href="#" onclick="openDeleteModal('${tenant.tenant_id}', '${escapeHtml(tenant.company_name)}'); return false;">
                                    <i class="fas fa-trash me-2"></i>Delete
                                </a>
                            </li>
                        </ul>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Render pagination
 */
function renderPagination(pagination) {
    if (!pagination) return;

    const info = document.getElementById('paginationInfo');
    if (info) {
        const start = ((pagination.page - 1) * pagination.limit) + 1;
        const end = Math.min(pagination.page * pagination.limit, pagination.total);
        info.textContent = `Showing ${start}-${end} of ${pagination.total} tenants`;
    }

    const paginationEl = document.getElementById('pagination');
    if (!paginationEl) return;

    const totalPages = Math.ceil(pagination.total / pagination.limit);
    
    if (totalPages <= 1) {
        paginationEl.innerHTML = '';
        return;
    }

    let html = `
        <li class="page-item ${pagination.page === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="goToPage(${pagination.page - 1}); return false;">Previous</a>
        </li>
    `;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= pagination.page - 2 && i <= pagination.page + 2)) {
            html += `
                <li class="page-item ${pagination.page === i ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="goToPage(${i}); return false;">${i}</a>
                </li>
            `;
        } else if (i === pagination.page - 3 || i === pagination.page + 3) {
            html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }

    html += `
        <li class="page-item ${pagination.page === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" onclick="goToPage(${pagination.page + 1}); return false;">Next</a>
        </li>
    `;

    paginationEl.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadTenants();
}

/**
 * Reset filters
 */
function resetFilters() {
    document.getElementById('searchTenant').value = '';
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterPlan').value = '';
    currentPage = 1;
    loadTenants();
}

/**
 * Handle create tenant form
 */
async function handleCreateTenant(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const data = Object.fromEntries(formData.entries());

    // Validate passwords match
    if (data.admin_password !== data.confirm_password) {
        showToast('error', 'Passwords do not match');
        return;
    }

    try {
        const response = await fetch('/api/super/tenants', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + getToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showToast('success', 'Tenant created successfully');
            bootstrap.Modal.getInstance(document.getElementById('createTenantModal')).hide();
            this.reset();
            loadTenants();
        } else {
            showToast('error', result.error || 'Failed to create tenant');
        }
    } catch (error) {
        console.error('Error creating tenant:', error);
        showToast('error', 'Failed to create tenant');
    }
}

/**
 * View tenant details
 */
async function viewTenantDetails(tenantId) {
    const tenant = tenantsData.find(t => t.tenant_id === tenantId);
    if (!tenant) return;

    const content = document.getElementById('tenantDetailsContent');
    content.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6 class="border-bottom pb-2 mb-3">Company Information</h6>
                <table class="table table-sm">
                    <tr><td width="40%">Company Name:</td><td><strong>${escapeHtml(tenant.company_name)}</strong></td></tr>
                    <tr><td>Subdomain:</td><td>${escapeHtml(tenant.subdomain)}</td></tr>
                    <tr><td>Industry:</td><td>${tenant.industry || 'N/A'}</td></tr>
                    <tr><td>Plan:</td><td><span class="badge bg-info">${tenant.plan || 'Free'}</span></td></tr>
                    <tr><td>Status:</td><td><span class="badge bg-${tenant.status === 'active' ? 'success' : 'danger'}">${tenant.status}</span></td></tr>
                    <tr><td>Created:</td><td>${formatDate(tenant.created_at)}</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <h6 class="border-bottom pb-2 mb-3">Statistics</h6>
                <table class="table table-sm">
                    <tr><td width="40%">Total Agents:</td><td>${tenant.total_agents || 0}</td></tr>
                    <tr><td>Online Agents:</td><td class="text-success">${tenant.online_agents || 0}</td></tr>
                    <tr><td>Admins:</td><td>${tenant.admin_count || 0}</td></tr>
                    <tr><td>Max Agents:</td><td>${tenant.max_agents || 'Unlimited'}</td></tr>
                    <tr><td>Health:</td><td><span class="badge bg-${tenant.health_status === 'healthy' ? 'success' : tenant.health_status === 'warning' ? 'warning' : 'danger'}">${tenant.health_status || 'unknown'}</span></td></tr>
                </table>
            </div>
        </div>
        ${tenant.contact_name || tenant.contact_phone ? `
            <div class="mt-3">
                <h6 class="border-bottom pb-2 mb-3">Contact Information</h6>
                <table class="table table-sm">
                    ${tenant.contact_name ? `<tr><td width="20%">Name:</td><td>${escapeHtml(tenant.contact_name)}</td></tr>` : ''}
                    ${tenant.contact_phone ? `<tr><td>Phone:</td><td>${escapeHtml(tenant.contact_phone)}</td></tr>` : ''}
                </table>
            </div>
        ` : ''}
        ${tenant.notes ? `
            <div class="mt-3">
                <h6 class="border-bottom pb-2 mb-3">Notes</h6>
                <p class="text-muted">${escapeHtml(tenant.notes)}</p>
            </div>
        ` : ''}
    `;

    new bootstrap.Modal(document.getElementById('tenantDetailsModal')).show();
}

/**
 * Edit tenant
 */
function editTenant(tenantId) {
    const tenant = tenantsData.find(t => t.tenant_id === tenantId);
    if (!tenant) return;

    document.getElementById('editTenantId').value = tenant.tenant_id;
    document.getElementById('editCompanyName').value = tenant.company_name || '';
    document.getElementById('editPlan').value = tenant.plan || 'free';
    document.getElementById('editIndustry').value = tenant.industry || '';
    document.getElementById('editMaxAgents').value = tenant.max_agents || '';
    document.getElementById('editContactName').value = tenant.contact_name || '';
    document.getElementById('editContactPhone').value = tenant.contact_phone || '';
    document.getElementById('editNotes').value = tenant.notes || '';

    new bootstrap.Modal(document.getElementById('editTenantModal')).show();
}

/**
 * Handle edit tenant form
 */
async function handleEditTenant(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const tenantId = formData.get('tenant_id');
    const data = Object.fromEntries(formData.entries());
    delete data.tenant_id;

    try {
        const response = await fetch(`/api/super/tenants/${tenantId}`, {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + getToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showToast('success', 'Tenant updated successfully');
            bootstrap.Modal.getInstance(document.getElementById('editTenantModal')).hide();
            loadTenants();
        } else {
            showToast('error', result.error || 'Failed to update tenant');
        }
    } catch (error) {
        console.error('Error updating tenant:', error);
        showToast('error', 'Failed to update tenant');
    }
}

/**
 * Suspend tenant
 */
async function suspendTenant(tenantId) {
    if (!confirm('Are you sure you want to suspend this tenant?')) return;

    try {
        const response = await fetch(`/api/super/tenants/${tenantId}/suspend`, {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });

        const result = await response.json();

        if (result.success) {
            showToast('success', 'Tenant suspended');
            loadTenants();
        } else {
            showToast('error', result.error || 'Failed to suspend tenant');
        }
    } catch (error) {
        console.error('Error suspending tenant:', error);
        showToast('error', 'Failed to suspend tenant');
    }
}

/**
 * Activate tenant
 */
async function activateTenant(tenantId) {
    try {
        const response = await fetch(`/api/super/tenants/${tenantId}/activate`, {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });

        const result = await response.json();

        if (result.success) {
            showToast('success', 'Tenant activated');
            loadTenants();
        } else {
            showToast('error', result.error || 'Failed to activate tenant');
        }
    } catch (error) {
        console.error('Error activating tenant:', error);
        showToast('error', 'Failed to activate tenant');
    }
}

/**
 * Open delete modal
 */
function openDeleteModal(tenantId, tenantName) {
    document.getElementById('deleteTenantId').value = tenantId;
    document.getElementById('deleteTenantName').textContent = tenantName;
    document.getElementById('deleteConfirmInput').value = '';
    document.getElementById('confirmDeleteBtn').disabled = true;

    new bootstrap.Modal(document.getElementById('deleteTenantModal')).show();
}

/**
 * Confirm delete tenant
 */
async function confirmDeleteTenant() {
    const tenantId = document.getElementById('deleteTenantId').value;

    try {
        const response = await fetch(`/api/super/tenants/${tenantId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + getToken() }
        });

        const result = await response.json();

        if (result.success) {
            showToast('success', 'Tenant deleted');
            bootstrap.Modal.getInstance(document.getElementById('deleteTenantModal')).hide();
            loadTenants();
        } else {
            showToast('error', result.error || 'Failed to delete tenant');
        }
    } catch (error) {
        console.error('Error deleting tenant:', error);
        showToast('error', 'Failed to delete tenant');
    }
}
