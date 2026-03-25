let itemsData = [];
let selectedItems = new Set();
let groupsData = [];
let selectedGroupId = '';

// === Profile editing state (Teacher only) ===
let teacherProfiles = [];
let selectedProfileId = '';
let selectedProfileData = null;
let isProfileEditMode = false;

// Type configurations
const typeConfigs = {
    domain: {
        title: 'Add Domain',
        label: 'Domain Name',
        placeholder: 'example.com',
        example: 'Examples: example.com, *.subdomain.com, *.example.*',
        icon: 'globe',
        help: 'Use wildcards (*) for subdomains and patterns'
    },
    ip: {
        title: 'Add IP Address',
        label: 'IP Address/Range',
        placeholder: '192.168.1.100',
        example: 'Examples: 192.168.1.100, 10.0.0.0/24, 172.16.0.1-172.16.0.254',
        icon: 'network-wired',
        help: 'Single IPs, CIDR notation, or IP ranges supported'
    },
    url: {
        title: 'Add URL Pattern',
        label: 'URL Pattern',
        placeholder: 'https://api.example.com/v1/*',
        example: 'Examples: https://api.com/v1/*, /webhooks/*, *.example.com/api/*',
        icon: 'link',
        help: 'Use wildcards (*) for URL patterns and paths'
    }
};



async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        if (!response.ok) throw new Error('Failed to load groups');
        const data = await response.json();
        groupsData = data.data || [];
        populateGroupSelects();
    } catch (error) {
        console.error('Error loading groups:', error);
        showError('Unable to load groups: ' + error.message);
    }
}

function populateGroupSelects() {
    const filterSelect = document.getElementById('group-filter');
    const modalSelect = document.getElementById('groupSelect');
    const bulkGroupSelect = document.getElementById('bulkGroupSelect'); 

    [filterSelect, modalSelect, bulkGroupSelect].forEach(select => {
        if (!select) return;
        const current = select.value;
        let placeholder = 'All Groups';
        
        if (select.id === 'groupSelect' || select.id === 'bulkGroupSelect') {
            placeholder = 'Select a group...';
        }
        
        select.innerHTML = `<option value="">${placeholder}</option>`;
        groupsData.forEach(group => {
            const option = document.createElement('option');
            option.value = group._id;
            option.textContent = group.name;
            select.appendChild(option);
        });
        if (current) {
            select.value = current;
        }
        
        // Update Custom UI if initialized
        if (window.updateCustomOptions) {
            window.updateCustomOptions(select.id);
        }
    });

    if (selectedGroupId && filterSelect) {
        filterSelect.value = selectedGroupId;
        if (window.updateCustomOptions) window.updateCustomOptions('group-filter');
    }
}

/**
 * Enhanced error handling for API responses
 */
function handleApiResponse(response) {
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json().then(data => {
        //  FIX: Handle different response formats
        if (data.error) {
            throw new Error(data.error);
        }
        return data;
    });
}

/**
 * Notify function for displaying messages
 */
function notify(type, message) {
    if (typeof showNotification === 'function') {
        showNotification(type, message);
    } else if (type === 'danger') {
        console.error(message);
    } else if (type === 'warning') {
        console.warn(message);
    } else {
        console.log(message);
    }
}

/**
 * Toggle bulk actions panel visibility
 */
function toggleBulkActionsPanel() {
    if (selectedItems.size === 0) {
        notify('warning', 'Select at least one item to use bulk actions.');
        return;
    }
    const bulkActions = document.getElementById('bulkActions');
    if (bulkActions) {
        bulkActions.classList.toggle('show');
    }
}

/**
 * Refresh bulk actions UI elements
 */
function refreshBulkActionsUI() {
    const countEl = document.getElementById('selectedCount');
    if (countEl) {
        countEl.textContent = selectedItems.size;
    }

    const hasSelection = selectedItems.size > 0;
    const bulkActions = document.getElementById('bulkActions');
    if (bulkActions) {
        if (hasSelection) {
            bulkActions.classList.add('show');
        } else {
            bulkActions.classList.remove('show');
        }
    }

    const deleteBtn = document.getElementById('bulkDeleteBtn');
    if (deleteBtn) {
        deleteBtn.disabled = !hasSelection;
    }
}

async function bulkDeleteItems() {
    if (selectedItems.size === 0) {
        notify('warning', 'Select items before deleting.');
        return;
    }

    if (!confirm(`Delete ${selectedItems.size} selected item(s)? This action cannot be undone.`)) {
        return;
    }

    const actionButtons = document.querySelectorAll('#bulkActions button');
    actionButtons.forEach(btn => btn.disabled = true);

    try {
        const response = await fetch('/api/whitelist/bulk-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                item_ids: Array.from(selectedItems)
            })
        });

        const result = await handleApiResponse(response);
        const deleted = result.deleted_count ?? selectedItems.size;

        showSuccess(`${deleted} item(s) removed successfully.`);
        selectedItems.clear();
        await loadItems();
    } catch (error) {
        showError('Failed to delete items: ' + error.message);
    } finally {
        actionButtons.forEach(btn => btn.disabled = false);
        refreshBulkActionsUI();
    }
}

/**
 * Load items from API with better error handling
 */
async function loadItems() {
    try {
        console.log(' Loading whitelist items...');
        const query = selectedGroupId ? `?group_id=${selectedGroupId}` : '';
        const response = await fetch(`/api/whitelist${query}`).catch(err => ({ ok: false, statusText: err.message }));
        if (response.ok) {
            const data = await handleApiResponse(response);
            
            //  FIX: Handle different response formats
            if (selectedGroupId && data.merged && Array.isArray(data.merged)) {
                itemsData = data.merged;
            } else if (data.domains && Array.isArray(data.domains)) {
                itemsData = data.domains;
            } else if (data.items && Array.isArray(data.items)) {
                itemsData = data.items;
            } else if (data.whitelist && Array.isArray(data.whitelist)) {
                itemsData = data.whitelist;
            } else if (Array.isArray(data)) {
                itemsData = data;
            } else {
                console.warn(' Unexpected data format:', data);
                itemsData = [];
            }
            
            console.log(' Loaded items:', itemsData.length);
            renderItems(itemsData);
            updateStatistics();
            selectedItems.clear();
            refreshBulkActionsUI();
        } else {
            console.error(' Failed to load items:', response.statusText);
            showError('Failed to load whitelist items');
            renderItems([]);
            updateStatistics();
            selectedItems.clear();
            refreshBulkActionsUI();
        }
        
    } catch (error) {
        console.error(' Error loading items:', error);
        showError('Error loading whitelist items: ' + error.message);
        renderItems([]);
        updateStatistics();
        selectedItems.clear();
        refreshBulkActionsUI();
    }
}

/**
 * Update statistics display
 */
function updateStatistics() {
    const total = itemsData.length;
    const active = itemsData.filter(item => item.active !== false).length;
    const domains = itemsData.filter(item => (item.type || 'domain') === 'domain').length;
    const ips = itemsData.filter(item => item.type === 'ip').length;
    
    document.getElementById('totalItemsCount').textContent = total;
    document.getElementById('activeItemsCount').textContent = active;
    document.getElementById('domainsCount').textContent = domains;
    document.getElementById('ipsCount').textContent = ips;
    document.getElementById('itemCount').textContent = total;
}

/**
 * Render items list - FIX: Handle all key formats
 */
function renderItems(items) {
    const container = document.getElementById('itemsContainer');

    if (items.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-list"></i>
                <h5 class="fw-bold">No Items in Whitelist</h5>
                <p>Start by adding trusted domains, IPs, URLs, or other resources.</p>
                <div class="d-flex justify-content-center gap-2 flex-wrap">
                    <button class="btn btn-success btn-sm" data-type="domain">
                        <i class="fas fa-globe me-1"></i>Add Domain
                    </button>
                    <button class="btn btn-info btn-sm" data-type="ip">
                        <i class="fas fa-network-wired me-1"></i>Add IP
                    </button>
                    <button class="btn btn-warning btn-sm" data-type="url">
                        <i class="fas fa-link me-1"></i>Add URL
                    </button>
                </div>
            </div>
        `;

        container.querySelectorAll('[data-type]').forEach(btn => {
            btn.addEventListener('click', () => showAddItemModal(btn.dataset.type));
        });
        return;
    }

    container.innerHTML = '';

    items.forEach((item, index) => {
        const isActive = item.active !== false && item.is_active !== false;
        const itemType = item.type || 'domain';
        
        // FIX: Handle all possible value keys
        const value = item.value || item.domain || item.ip || item.url || item.port || item.process || '';
        
        // FIX: Handle all possible ID keys
        const itemId = item._id || item.id || '';
        
        // FIX: Check if item is from group (scope = 'group')
        const scope = item.scope || 'global';
        const groupId = item.group_id || '';
        const groupName = item.group_name || (groupId && groupsData.find(g => g._id === groupId)?.name) || '';
        
        if (!value) {
            console.warn('Item has no value:', item);
            return; // Skip items without value
        }
        
        const statusInfo = isActive ?
            { class: 'active', text: 'Active', icon: 'check-circle' } :
            { class: 'inactive', text: 'Inactive', icon: 'times-circle' };
        const typeConfig = typeConfigs[itemType] || typeConfigs.domain;
        
        // FIX: Better date handling - check multiple date fields
        let created = '';
        const dateValue = item.added_date || item.added_at || item.created_at;
        if (dateValue) {
            try {
                const dateObj = new Date(dateValue);
                if (!isNaN(dateObj.getTime())) {
                    created = dateObj.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                    });
                }
            } catch (e) {
                console.warn('Invalid date:', dateValue);
            }
        }
        
        // FIX: Show "Recently added" if no date available
        const dateDisplay = created || 'Recently added';

        const itemElement = document.createElement('div');
        itemElement.className = 'p-4 border-bottom item-row';
        itemElement.dataset.value = value.toLowerCase();
        itemElement.dataset.status = isActive ? 'active' : 'inactive';
        itemElement.dataset.type = itemType;
        itemElement.dataset.scope = scope.toLowerCase();
        itemElement.dataset.group = groupId;

        itemElement.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-1">
                    <div class="form-check">
                        <input class="form-check-input item-checkbox" type="checkbox" 
                               value="${itemId}" ${!itemId ? 'disabled' : ''}>
                    </div>
                </div>
                <div class="col-md-7">
                    <div class="d-flex align-items-center">
                        <div class="me-3">
                            <i class="fas fa-${typeConfig.icon} fa-2x text-success"></i>
                        </div>
                        <div>
                            <h6 class="mb-2 fw-bold">
                                <i class="fas fa-shield-alt me-2"></i>
                                ${escapeHtml(value)}
                            </h6>
                            <div class="d-flex align-items-center mb-2 flex-wrap gap-1">
                                <span class="domain-status ${statusInfo.class}">
                                    <span class="pulse-indicator ${statusInfo.class}"></span>
                                    ${statusInfo.text}
                                </span>
                                <span class="type-badge ${itemType}">
                                    ${itemType.toUpperCase()}
                                </span>
                                <span class="domain-type-badge ${scope}">
                                    ${scope === 'group' ? `Group: ${escapeHtml(groupName) || 'Unknown'}` : 'Global'}
                                </span>
                            </div>
                            <div class="row text-muted small">
                                <div class="col-auto">
                                    <i class="fas fa-calendar me-1"></i>
                                    Added: ${dateDisplay}
                                </div>
                                ${item.category && item.category !== 'uncategorized' ? `
                                    <div class="col-auto">
                                        <i class="fas fa-tag me-1"></i>
                                        ${escapeHtml(item.category)}
                                    </div>
                                ` : ''}
                            </div>
                            ${item.notes ? `
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <i class="fas fa-sticky-note me-1"></i>
                                        ${escapeHtml(item.notes)}
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                <div class="col-md-4 text-end">
                    ${(() => {
                        // Teacher in read-only mode (no profile selected): hide remove buttons
                        const isTeacher = window.SAINT_AUTH && window.SAINT_AUTH.isTeacher;
                        if (isTeacher && !isProfileEditMode) return '';
                        return `
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-danger btn-action"
                                    data-action="remove"
                                    data-item-id="${itemId}"
                                    data-group-id="${groupId}"
                                    data-scope="${scope}"
                                    data-item-type="${itemType}"
                                    data-item-value="${escapeHtml(value)}"
                                    title="Remove this item"
                                    ${!itemId && scope === 'global' ? 'disabled' : ''}>
                                <i class="fas fa-trash-alt me-1"></i>
                                <span>Remove</span>
                            </button>
                        </div>`;
                    })()}
                </div>
            </div>
        `;
        
        container.appendChild(itemElement);
    });
    
    // Add event listeners
    container.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', handleItemAction);
    });
    
    container.querySelectorAll('.item-checkbox').forEach(cb => {
        cb.addEventListener('change', updateSelectedItems);
    });
}

// ADD: escapeHtml function if not exists
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Handle item actions - FIX: Properly handle scope
 */
async function handleItemAction(event) {
    const btn = event.currentTarget;
    const action = btn.dataset.action;
    const itemId = btn.dataset.itemId;
    const groupId = btn.dataset.groupId;
    const scope = btn.dataset.scope;
    const itemType = btn.dataset.itemType;
    const itemValue = btn.dataset.itemValue;
    
    console.log('Item action:', { action, itemId, groupId, scope, itemType, itemValue });

    if (action === 'remove') {
        await removeItem(itemId, groupId, scope, itemType, itemValue);
    }
}

/**
 * Remove item - FIX: Handle both global and group items
 */
async function removeItem(itemId, groupId = '', scope = 'global', itemType = '', itemValue = '') {
    if (!confirm('Are you sure you want to remove this item?')) return;
    
    // FIX: If scope is 'group', remove from group whitelist
    if (scope === 'group' && groupId) {
        try {
            console.log('Removing group item:', { groupId, itemType, itemValue });
            await removeGroupItem(groupId, itemType, itemValue);
            showSuccess('Item removed from group whitelist');
            await Promise.all([loadGroups(), loadItems()]);
        } catch (error) {
            console.error('Error removing group item:', error);
            showError('Failed to remove group item: ' + error.message);
        }
        return;
    }

    // FIX: For global items, must have valid ID
    if (!itemId) {
        showError('Cannot remove item: Missing ID');
        return;
    }

    try {
        console.log('Removing global item:', itemId);
        
        const response = await fetch(`/api/whitelist/${itemId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Remove result:', result);
        
        if (result.success) {
            showSuccess(result.message || 'Item removed successfully');
            await loadItems();
        } else {
            throw new Error(result.error || 'Failed to remove item');
        }
        
    } catch (error) {
        console.error('Error removing item:', error);
        showError('Failed to remove item: ' + error.message);
    }
}

async function addItemToGroup(groupId, itemData) {
    const group = groupsData.find(g => g._id === groupId);
    if (!group) {
        await loadGroups();
    }

    const currentGroup = groupsData.find(g => g._id === groupId);
    const whitelist = currentGroup?.whitelist ? [...currentGroup.whitelist] : [];
    whitelist.push({
        value: itemData.value,
        type: itemData.type,
        category: itemData.description || 'uncategorized',
        notes: itemData.notes || ''
    });

    await updateGroupWhitelist(groupId, whitelist);
}

async function removeGroupItem(groupId, itemType, itemValue) {
    const group = groupsData.find(g => g._id === groupId);
    if (!group) {
        await loadGroups();
    }

    const currentGroup = groupsData.find(g => g._id === groupId);
    const whitelist = (currentGroup?.whitelist || []).filter(entry => {
        const entryValue = typeof entry === 'string' ? entry : entry.value;
        const entryType = typeof entry === 'string' ? 'domain' : entry.type || 'domain';
        return !(entryValue === itemValue && entryType === itemType);
    });

    await updateGroupWhitelist(groupId, whitelist);
}

async function updateGroupWhitelist(groupId, whitelist) {
    const response = await fetch(`/api/groups/${groupId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ whitelist })
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to update group whitelist');
    }
}

/**
 * Add new item -  FIXED to actually call API
 */
async function addItem() {
    const form = document.getElementById('addItemForm');
    const formData = new FormData(form);
    
    const button = document.getElementById('addItemSubmitBtn');
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Adding...';
    button.disabled = true;
    
    try {
        const itemData = {
            type: formData.get('item_type'),
            value: formData.get('value'),
            scope: formData.get('scope') || 'global',
            description: formData.get('description'),
            notes: formData.get('notes') || '',
            active: formData.get('active') === 'on'
        };

        console.log('Sending item data:', itemData);

        // === PROFILE EDIT MODE: save to profile instead ===
        if (isProfileEditMode && selectedProfileData) {
            await addItemToProfile(itemData);
            showSuccess(`${itemData.value} added to profile "${selectedProfileData.name}"`);

            form.reset();
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('addItemModal'));
            if (modalInstance) modalInstance.hide();
            return; // renderProfileDomains() already called by saveProfileDomains
        }

        if (itemData.scope === 'group') {
            const targetGroupId = formData.get('group_id') || selectedGroupId;
            if (!targetGroupId) {
                throw new Error('Please choose a target group');
            }

            await addItemToGroup(targetGroupId, itemData);
            showSuccess(`${itemData.value} added to group whitelist`);

            // Reset form and close modal
            form.reset();
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('addItemModal'));
            if (modalInstance) {
                modalInstance.hide();
            }

            await Promise.all([loadGroups(), loadItems()]);
        } else {
            const response = await fetch('/api/whitelist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(itemData)
            });

            const result = await handleApiResponse(response);
            console.log('API response:', result);

            showSuccess(result.message || `${itemData.type.toUpperCase()} ${itemData.value} added successfully!`);

            // Reset form and close modal
            form.reset();
            bootstrap.Modal.getInstance(document.getElementById('addItemModal')).hide();

            await loadItems();
        }
        
    } catch (error) {
        console.error('Error adding item:', error);
        showError('Failed to add item: ' + error.message);
    } finally {
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

/**
 * Show error message
 */
function showError(message) {
    // Create error notification
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed';
    errorDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-triangle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(errorDiv);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

/**
 * Show success message
 */
function showSuccess(message) {
    // Create success notification
    const successDiv = document.createElement('div');
    successDiv.className = 'alert alert-success alert-dismissible fade show position-fixed';
    successDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    successDiv.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(successDiv);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (successDiv.parentNode) {
            successDiv.remove();
        }
    }, 3000);
}

/**
 * Other functions (simplified for demo)
 */
async function loadAgentsForSelect() {
    // Placeholder for loading agents
    console.log('Loading agents for selection...');
}

function refreshItems() {
    loadItems();
}

function showBulkActions() {
    const bulkActions = document.getElementById('bulkActions');
    bulkActions.classList.toggle('show');
}

function updateSelectedItems() {
    const checkboxes = document.querySelectorAll('.item-checkbox:checked');
    selectedItems.clear();

    checkboxes.forEach(cb => selectedItems.add(cb.value));
    refreshBulkActionsUI();
}

function filterItems() {
    const searchTerm = document.getElementById('item-search').value.toLowerCase();
    const typeFilter = document.getElementById('type-filter').value;
    const statusFilter = document.getElementById('status-filter').value;
    const groupFilter = document.getElementById('group-filter').value;
    const itemRows = document.querySelectorAll('.item-row');
    
    itemRows.forEach(row => {
        const value = row.dataset.value;
        const type = row.dataset.type;
        const status = row.dataset.status;
        const group = row.dataset.group || '';

        const matchesSearch = value.includes(searchTerm);
        const matchesType = !typeFilter || type === typeFilter;
        const matchesStatus = !statusFilter || status === statusFilter;
        const matchesGroup = !groupFilter || group === groupFilter;

        if (matchesSearch && matchesType && matchesStatus && matchesGroup) {
            row.style.display = 'block';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * Show Add Item Modal with pre-selected type
 */
function showAddItemModal(type = 'domain') {
    const config = typeConfigs[type] || typeConfigs.domain;
    
    // FIX: Use correct element IDs from HTML
    const modalTitleEl = document.getElementById('modalTitle');
    const valueLabelEl = document.getElementById('valueLabel');
    const valueInputEl = document.getElementById('valueInput');
    const valueExampleEl = document.getElementById('valueExample');
    const itemTypeEl = document.getElementById('itemType');
    const formEl = document.getElementById('addItemForm');
    
    // Update modal title and labels
    if (modalTitleEl) {
        modalTitleEl.innerHTML = `<i class="fas fa-${config.icon} me-2"></i>${config.title}`;
    }
    if (valueLabelEl) {
        valueLabelEl.textContent = config.label;
    }
    if (valueInputEl) {
        valueInputEl.placeholder = config.placeholder;
    }
    if (valueExampleEl) {
        valueExampleEl.textContent = config.example;
    }
    
    // Set hidden type field
    if (itemTypeEl) {
        itemTypeEl.value = type;
    }
    
    // Reset form
    if (formEl) {
        formEl.reset();
    }
    
    // Set type again after reset
    if (itemTypeEl) {
        itemTypeEl.value = type;
    }
    
    // Hide scope/group selectors when in profile edit mode
    const scopeEl = document.getElementById('scopeSelect');
    const groupSelectGroup = document.getElementById('groupSelectGroup');
    // Find the mb-3 container wrapping scope select (may be wrapped by custom-select-wrapper)
    const scopeContainer = scopeEl ? scopeEl.closest('.mb-3') : null;
    if (isProfileEditMode) {
        if (scopeContainer) scopeContainer.style.display = 'none';
        if (groupSelectGroup) groupSelectGroup.style.display = 'none';
    } else {
        if (scopeContainer) scopeContainer.style.display = '';
    }

    // Show modal
    const modalEl = document.getElementById('addItemModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

/**
 * Show Bulk Import Modal
 */
function showBulkImportModal() {
    const modalEl = document.getElementById('bulkImportModal');
    if (modalEl) {
        // Hide scope/group selectors when in profile edit mode
        const bulkScopeEl = document.getElementById('bulkScope');
        const bulkGroupEl = document.getElementById('bulkGroupSelectGroup');
        if (isProfileEditMode) {
            if (bulkScopeEl && bulkScopeEl.closest('.col-md-4')) bulkScopeEl.closest('.col-md-4').style.display = 'none';
            if (bulkGroupEl) bulkGroupEl.style.display = 'none';
        } else {
            if (bulkScopeEl && bulkScopeEl.closest('.col-md-4')) bulkScopeEl.closest('.col-md-4').style.display = '';
        }

        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

/**
 * Bulk Import Items
 */
async function bulkImportItems() {
    const method = document.querySelector('input[name="importMethod"]:checked').value;
    const items = [];
    const defaultType = document.getElementById('bulkType').value;
    const scope = document.getElementById('bulkScope').value;
    const groupId = document.getElementById('bulkGroupSelect').value;
    
    if (scope === 'group' && !groupId) {
        showError('Please select a target group for import');
        return;
    }

    let rawText = '';

    if (method === 'text') {
        rawText = document.getElementById('bulkTextarea').value;
        if (!rawText.trim()) {
            showError('Please enter items to import');
            return;
        }
    } else {
        const fileInput = document.getElementById('bulkFile');
        if (fileInput.files.length === 0) {
            showError('Please select a file to upload');
            return;
        }
        
        try {
            rawText = await readFileContent(fileInput.files[0]);
        } catch (error) {
            console.error('File read error:', error);
            showError('Failed to read file');
            return;
        }
    }
    
    // Process text content
    const lines = rawText.split(/[\r\n]+/).map(line => line.trim()).filter(line => line);
    
    if (lines.length === 0) {
        showError('No valid items found to import');
        return;
    }
    
    // Detect type helper
    const detectType = (value) => {
        if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(value)) return 'ip';
        if (value.startsWith('http://') || value.startsWith('https://')) return 'url';
        return 'domain';
    };

    lines.forEach(line => {
        // Skip comments or empty lines
        if (line.startsWith('#') || !line) return;
        
        let type = defaultType;
        let value = line;
        
        // Handle CSV-like format: type,value or value,type
        if (line.includes(',')) {
            const parts = line.split(',').map(p => p.trim());
            if (['domain', 'ip', 'url'].includes(parts[0].toLowerCase())) {
                 type = parts[0].toLowerCase();
                 value = parts[1];
            } else if (['domain', 'ip', 'url'].includes(parts[1].toLowerCase())) {
                 value = parts[0];
                 type = parts[1].toLowerCase();
            }
        }
        
        if (type === 'auto') {
            type = detectType(value);
        }
        
        items.push({
            type: type,
            value: value,
            scope: scope,
            group_id: groupId,
            notes: 'Bulk import',
            active: true
        });
    });

    if (items.length === 0) {
        showError('No valid items to import');
        return;
    }

    const btn = document.getElementById('bulkImportBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Importing...';
    btn.disabled = true;

    try {
        // === PROFILE EDIT MODE: merge into profile domains ===
        if (isProfileEditMode && selectedProfileData) {
            const currentDomains = [...(selectedProfileData.domains || [])];
            let addedCount = 0;
            for (const item of items) {
                const exists = currentDomains.some(d => {
                    const dVal = typeof d === 'string' ? d : d.value;
                    return dVal === item.value;
                });
                if (!exists) {
                    currentDomains.push({
                        value: item.value,
                        type: item.type || 'domain',
                        notes: item.notes || '',
                    });
                    addedCount++;
                }
            }

            await saveProfileDomains(currentDomains);
            showSuccess(`Import complete: ${addedCount} domain(s) added to profile "${selectedProfileData.name}"`);

            document.getElementById('bulkTextarea').value = '';
            const modal = bootstrap.Modal.getInstance(document.getElementById('bulkImportModal'));
            if (modal) modal.hide();

            btn.innerHTML = originalText;
            btn.disabled = false;
            return;
        }

        // Split into chunks of 100 to avoid timeouts
        const chunkSize = 100;
        let successCount = 0;
        let errorCount = 0;

        for (let i = 0; i < items.length; i += chunkSize) {
            const chunk = items.slice(i, i + chunkSize);

            const response = await fetch('/api/whitelist/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: chunk })
            });
            
            const result = await response.json();
            if (result.success) {
                successCount += (result.inserted_count || 0);
            } else {
                errorCount += chunk.length; // Approximate
            }
        }
        
        showSuccess(`Import completed: ${successCount} added, ${errorCount} failed`);
        
        document.getElementById('bulkTextarea').value = '';
        document.getElementById('bulkFile').value = '';
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('bulkImportModal'));
        if (modal) modal.hide();
        
        await loadItems();
        
    } catch (error) {
        console.error('Bulk import error:', error);
        showError('Bulk import failed: ' + error.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

/**
 * Read file content helper
 */
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsText(file);
    });
}

// =====================================================================
// PROFILE EDITING MODE (Teacher only)
// =====================================================================

/**
 * Load teacher's profiles across all groups
 */
async function loadTeacherProfiles() {
    try {
        const response = await fetch('/api/my-profiles');
        if (!response.ok) throw new Error('Failed to load profiles');
        const data = await response.json();
        teacherProfiles = data.data || [];
        populateProfileSelect();
    } catch (error) {
        console.error('Error loading teacher profiles:', error);
    }
}

/**
 * Populate the profile selector dropdown
 */
function populateProfileSelect() {
    const select = document.getElementById('profileSelect');
    if (!select) return;

    const current = select.value;
    select.innerHTML = '<option value="">-- View mode (Read-only) --</option>';

    teacherProfiles.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p._id;
        opt.textContent = `${p.name} - ${p.group_name || 'Unknown Group'}`;
        if (p.is_active) {
            opt.textContent += ' ⚡ Active';
        }
        select.appendChild(opt);
    });

    if (current) select.value = current;

    // Update Custom UI if initialized
    if (window.updateCustomOptions) {
        window.updateCustomOptions('profileSelect');
    }
}

/**
 * Handle profile selection change
 */
function onProfileSelected(profileId) {
    selectedProfileId = profileId;

    if (!profileId) {
        // Switch to read-only mode
        isProfileEditMode = false;
        selectedProfileData = null;
        updateProfileUI();
        loadItems(); // Reload normal whitelist
        return;
    }

    // Find profile data
    selectedProfileData = teacherProfiles.find(p => p._id === profileId);
    if (!selectedProfileData) {
        showError('Profile not found');
        return;
    }

    isProfileEditMode = true;
    updateProfileUI();
    renderProfileDomains();
}

/**
 * Update UI elements based on profile edit mode
 */
function updateProfileUI() {
    const addSection = document.getElementById('addItemsSection');
    const infoBadge = document.getElementById('profileInfoBadge');
    const readonlyHint = document.getElementById('profileReadonlyHint');
    const searchCard = document.querySelector('.search-card');
    const bulkActions = document.getElementById('bulkActions');

    if (isProfileEditMode && selectedProfileData) {
        // Show editing state
        if (infoBadge) {
            infoBadge.style.display = 'block';
            document.getElementById('profileEditingName').textContent = selectedProfileData.name;
            document.getElementById('profileEditingGroup').textContent = selectedProfileData.group_name || '';
            document.getElementById('profileDomainCount').textContent = (selectedProfileData.domains || []).length;
        }
        if (readonlyHint) readonlyHint.style.display = 'none';
        if (addSection) addSection.style.display = '';
        // Hide group filter & scope when editing profile (not relevant)
        if (searchCard) searchCard.style.display = 'none';
        if (bulkActions) bulkActions.classList.remove('show');
    } else {
        // Read-only mode for teacher
        if (infoBadge) infoBadge.style.display = 'none';
        if (readonlyHint) readonlyHint.style.display = '';

        // For teacher without profile selected: hide add section
        const isTeacher = window.SAINT_AUTH && window.SAINT_AUTH.isTeacher;
        if (isTeacher) {
            if (addSection) addSection.style.display = 'none';
        } else {
            if (addSection) addSection.style.display = '';
        }
        if (searchCard) searchCard.style.display = '';
    }
}

/**
 * Render profile domains in the items container (replacing normal whitelist view)
 */
function renderProfileDomains() {
    if (!selectedProfileData) return;

    const domains = selectedProfileData.domains || [];
    const container = document.getElementById('itemsContainer');

    // Update stats for profile
    document.getElementById('totalItemsCount').textContent = domains.length;
    document.getElementById('activeItemsCount').textContent = domains.length;
    document.getElementById('domainsCount').textContent = domains.filter(d => (d.type || 'domain') === 'domain').length;
    document.getElementById('ipsCount').textContent = domains.filter(d => d.type === 'ip').length;
    document.getElementById('itemCount').textContent = domains.length;
    document.getElementById('profileDomainCount').textContent = domains.length;

    if (domains.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-list"></i>
                <h5 class="fw-bold">Profile has no domains yet</h5>
                <p>Add domains/IPs/URLs using the buttons above.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = '';

    domains.forEach((domain, index) => {
        const value = typeof domain === 'string' ? domain : (domain.value || domain.domain || '');
        const itemType = typeof domain === 'string' ? 'domain' : (domain.type || 'domain');
        const notes = typeof domain === 'string' ? '' : (domain.notes || '');
        const typeConfig = typeConfigs[itemType] || typeConfigs.domain;

        if (!value) return;

        const el = document.createElement('div');
        el.className = 'p-4 border-bottom item-row';
        el.dataset.value = value.toLowerCase();
        el.dataset.type = itemType;

        el.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-1">
                    <span class="text-muted fw-bold">#${index + 1}</span>
                </div>
                <div class="col-md-7">
                    <div class="d-flex align-items-center">
                        <div class="me-3">
                            <i class="fas fa-${typeConfig.icon} fa-2x text-success"></i>
                        </div>
                        <div>
                            <h6 class="mb-1 fw-bold">
                                <i class="fas fa-shield-alt me-2"></i>
                                ${escapeHtml(value)}
                            </h6>
                            <div class="d-flex align-items-center gap-1">
                                <span class="domain-status active">
                                    <span class="pulse-indicator active"></span>Active
                                </span>
                                <span class="type-badge ${itemType}">${itemType.toUpperCase()}</span>
                                <span class="domain-type-badge" style="background:rgba(var(--bs-success-rgb),0.1);color:var(--bs-success);">
                                    Profile: ${escapeHtml(selectedProfileData.name)}
                                </span>
                            </div>
                            ${notes ? `<small class="text-muted mt-1 d-block"><i class="fas fa-sticky-note me-1"></i>${escapeHtml(notes)}</small>` : ''}
                        </div>
                    </div>
                </div>
                <div class="col-md-4 text-end">
                    <button class="btn btn-outline-danger btn-sm btn-action"
                            onclick="removeProfileDomain(${index})"
                            title="Remove from profile">
                        <i class="fas fa-trash-alt me-1"></i>Remove
                    </button>
                </div>
            </div>
        `;

        container.appendChild(el);
    });
}

/**
 * Remove a domain from the selected profile by index
 */
async function removeProfileDomain(index) {
    if (!selectedProfileData) return;
    if (!confirm('Remove this domain from profile?')) return;

    const domains = [...(selectedProfileData.domains || [])];
    const removed = domains.splice(index, 1);

    try {
        await saveProfileDomains(domains);
        showSuccess(`Removed "${removed[0]?.value || removed[0]}" from profile`);
    } catch (error) {
        showError('Error removing domain: ' + error.message);
    }
}

/**
 * Save domains array to the selected profile via PATCH API
 */
async function saveProfileDomains(domains) {
    if (!selectedProfileData) throw new Error('No profile selected');

    const groupId = selectedProfileData.group_id;
    const profileId = selectedProfileData._id;

    const response = await fetch(`/api/groups/${groupId}/profiles/${profileId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domains: domains })
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to update profile');
    }

    // Update local state
    selectedProfileData.domains = domains;
    // Also update in teacherProfiles array
    const idx = teacherProfiles.findIndex(p => p._id === profileId);
    if (idx !== -1) {
        teacherProfiles[idx].domains = domains;
    }

    renderProfileDomains();
}

/**
 * Add a domain to the selected profile
 */
async function addItemToProfile(itemData) {
    if (!selectedProfileData) throw new Error('No profile selected');

    const domains = [...(selectedProfileData.domains || [])];

    // Check duplicate
    const exists = domains.some(d => {
        const dVal = typeof d === 'string' ? d : d.value;
        return dVal === itemData.value;
    });
    if (exists) {
        throw new Error(`"${itemData.value}" already exists in profile`);
    }

    domains.push({
        value: itemData.value,
        type: itemData.type || 'domain',
        notes: itemData.notes || '',
    });

    await saveProfileDomains(domains);
}

/**
 * Initialize page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add item type cards
    document.querySelectorAll('.add-item-card').forEach(card => {
        card.addEventListener('click', function() {
            const type = this.dataset.type;
            if (type === 'bulk') {
                showBulkImportModal();
            } else {
                showAddItemModal(type);
            }
        });
    });
    
    // Modal submit button
    document.getElementById('addItemSubmitBtn').addEventListener('click', addItem);
    
    // Bulk Import submit button
    const bulkImportBtn = document.getElementById('bulkImportBtn');
    if (bulkImportBtn) {
        bulkImportBtn.addEventListener('click', bulkImportItems);
    }
    
    // Filter and search
    document.getElementById('item-search').addEventListener('input', filterItems);
    document.getElementById('type-filter').addEventListener('change', filterItems);
    document.getElementById('status-filter').addEventListener('change', filterItems);
    document.getElementById('group-filter').addEventListener('change', function() {
        selectedGroupId = this.value;
        loadItems();
    });

    // Control buttons
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadGroups();
        refreshItems();
    });
    // document.getElementById('bulkActionsBtn').addEventListener('click', toggleBulkActionsPanel); // Removed
    document.getElementById('bulkDeleteBtn').addEventListener('click', bulkDeleteItems);
    
    // REMOVED: Agent-specific handling, only keep Global and Group
    document.getElementById('scopeSelect').addEventListener('change', function() {
        const groupSelect = document.getElementById('groupSelectGroup');
        groupSelect.style.display = this.value === 'group' ? 'block' : 'none';
    });
    
    // NEW: Bulk scope selection handler
    document.getElementById('bulkScope').addEventListener('change', function() {
        const bulkGroupSelect = document.getElementById('bulkGroupSelectGroup');
        bulkGroupSelect.style.display = this.value === 'group' ? 'block' : 'none';
    });
    
    // Bulk import method toggle
    document.querySelectorAll('[name="importMethod"]').forEach(radio => {
        radio.addEventListener('change', function() {
            const textSection = document.getElementById('textImportSection');
            const fileSection = document.getElementById('fileImportSection');
            
            if (this.value === 'text') {
                textSection.style.display = 'block';
                fileSection.style.display = 'none';
            } else {
                textSection.style.display = 'none';
                fileSection.style.display = 'block';
            }
        });
    });
    
    // Load initial data
    loadGroups().then(() => {
        const filter = document.getElementById('group-filter');
        if (filter) {
            selectedGroupId = filter.value;
        }
        loadItems();
    });

    // === TEACHER PROFILE INTEGRATION ===
    const profileSelect = document.getElementById('profileSelect');
    if (profileSelect) {
        profileSelect.addEventListener('change', function () {
            onProfileSelected(this.value);
        });
    }

    // Wait for auth to be ready, then init profile selector for teachers
    function initProfileSelector() {
        const isTeacher = window.SAINT_AUTH && window.SAINT_AUTH.isTeacher;
        const profileBar = document.getElementById('profileSelectorBar');
        const addSection = document.getElementById('addItemsSection');

        if (isTeacher && profileBar) {
            profileBar.style.display = '';
            // Teacher starts in read-only mode: hide add section
            if (addSection) addSection.style.display = 'none';
            loadTeacherProfiles();
        }
    }

    // SAINT_AUTH may be set after DOMContentLoaded by auth.js applyUserUI()
    if (window.SAINT_AUTH) {
        initProfileSelector();
    } else {
        // Retry after short delay for auth.js to finish
        setTimeout(initProfileSelector, 500);
        setTimeout(initProfileSelector, 1500);
    }

    // Initialize Custom Selects
    ['profileSelect', 'type-filter', 'status-filter', 'group-filter', 'scopeSelect', 'groupSelect', 'bulkScope', 'bulkGroupSelect', 'bulkType'].forEach(id => {
        if (window.initCustomSelect) window.initCustomSelect(id);
    });

    // Auto-refresh every 60 seconds (only when NOT in profile edit mode)
    setInterval(() => {
        if (!isProfileEditMode) loadItems();
    }, 60000);

    console.log('Enhanced whitelist management initialized');
});