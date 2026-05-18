let groupsData = [];
let agentsData = [];
let quickDomains = [];
let quickDomainEntries = [];  // Full entry objects for edit mode
let selectedColor = 'primary';
let currentView = 'grid';

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Groups page initialized');
    
    loadGroups();
    loadAgents();
    setupEventListeners();

    if (window.initCustomSelect) {
        window.initCustomSelect('sortFilter');
    }
});

function setupEventListeners() {
    // Search
    document.getElementById('groupSearch')?.addEventListener('input', filterGroups);
    
    // Sort
    document.getElementById('sortFilter')?.addEventListener('change', sortGroups);
    
    // View toggle
    document.getElementById('viewGrid')?.addEventListener('click', () => setView('grid'));
    document.getElementById('viewList')?.addEventListener('click', () => setView('list'));
    
    // Quick domain input - Enter key
    document.getElementById('quickDomainInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addQuickDomain();
        }
    });
}

function setView(view) {
    currentView = view;
    const container = document.getElementById('groupsContainer');
    
    if (view === 'grid') {
        container.classList.remove('groups-list');
        container.classList.add('groups-grid');
        document.getElementById('viewGrid').classList.add('active');
        document.getElementById('viewList').classList.remove('active');
    } else {
        container.classList.remove('groups-grid');
        container.classList.add('groups-list');
        document.getElementById('viewList').classList.add('active');
        document.getElementById('viewGrid').classList.remove('active');
    }
    
    renderGroups();
}

// ========================================
// DATA LOADING
// ========================================

async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        if (!response.ok) throw new Error('Failed to load groups');
        
        const data = await response.json();
        groupsData = data.data || [];
        
        document.getElementById('totalGroupsCount').textContent = groupsData.length;
        
        renderGroups();
    } catch (error) {
        console.error('Error loading groups:', error);
        showError('Failed to load groups');
    }
}

async function loadAgents() {
    try {
        const response = await fetch('/api/agents');
        if (!response.ok) throw new Error('Failed to load agents');
        
        const data = await response.json();
        agentsData = data.agents || [];
        
        document.getElementById('totalAgentsCount').textContent = agentsData.length;
        
        // Re-render to update agent counts
        renderGroups();
    } catch (error) {
        console.error('Error loading agents:', error);
    }
}

async function refreshGroups() {
    const btn = event?.target;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
    }
    
    await Promise.all([loadGroups(), loadAgents()]);
    
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Refresh';
    }
    
    showSuccess('Groups refreshed');
}

// ========================================
// RENDERING
// ========================================

function renderGroups() {
    const container = document.getElementById('groupsContainer');
    
    if (!groupsData.length) {
        container.innerHTML = `
            <div class="empty-groups">
                <i class="fas fa-layer-group"></i>
                <h4 class="fw-bold">No Groups Yet</h4>
                <p>Create your first group to organize agents and manage whitelists.</p>
                <button class="btn btn-primary" onclick="openCreateGroupModal()">
                    <i class="fas fa-plus me-2"></i>Create First Group
                </button>
            </div>
        `;
        return;
    }
    
    container.innerHTML = groupsData.map(group => renderGroupCard(group)).join('');
}

function renderGroupCard(group) {
    const agentsInGroup = agentsData.filter(a => a.group_id === group._id);
    const agentCount = agentsInGroup.length;
    const whitelistCount = (group.whitelist || []).length;
    const color = group.color || 'primary';
    const isSystem = group.is_system;
    
    // Agent avatars preview (max 5)
    const previewAgents = agentsInGroup.slice(0, 5);
    const moreCount = agentCount - 5;
    
    const agentAvatarsHtml = previewAgents.map(agent => {
        const initial = (agent.display_name || agent.hostname || 'A')[0].toUpperCase();
        return `<div class="agent-avatar" title="${agent.display_name || agent.hostname}">${initial}</div>`;
    }).join('');
    
    const moreAvatarHtml = moreCount > 0 
        ? `<div class="agent-avatar more">+${moreCount}</div>` 
        : '';
    
    return `
        <div class="group-card ${isSystem ? 'system' : ''}" data-group-id="${group._id}" 
             data-name="${(group.name || '').toLowerCase()}"
             data-description="${(group.description || '').toLowerCase()}"
             data-agents="${agentCount}"
             data-whitelist="${whitelistCount}"
             data-updated="${group.updated_at || ''}">
            
            <div class="group-card-stripe ${color}"></div>
            
            <div class="group-card-body">
                <div class="group-card-header">
                    <h5 class="group-card-title">
                        <i class="fas fa-layer-group"></i>
                        ${escapeHtml(group.name)}
                        ${isSystem ? '<span class="system-badge">System</span>' : ''}
                    </h5>
                    <div class="group-card-actions">
                        <button class="btn btn-sm btn-outline-info" onclick="viewGroupDetail('${group._id}')" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${!isSystem && window.SAINT_AUTH && window.SAINT_AUTH.isAdmin ? `
                            <button class="btn btn-sm btn-outline-primary" onclick="openEditGroupModal('${group._id}')" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteGroup('${group._id}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        ` : ''}
                    </div>
                </div>
                
                <p class="group-card-description">
                    ${escapeHtml(group.description) || 'No description'}
                </p>

                ${group.created_by_username ? `<div class="mb-2"><span class="badge bg-${group.created_by_role === 'admin' ? 'danger' : 'success'} bg-opacity-10 text-${group.created_by_role === 'admin' ? 'danger' : 'success'}" style="font-size:0.7rem;"><i class="fas fa-user me-1"></i>Owner: ${escapeHtml(group.created_by_username)}</span></div>` : ''}

                <div class="group-card-stats">
                    <div class="stat-item">
                        <i class="fas fa-laptop-code text-primary"></i>
                        <div>
                            <div class="stat-value">${agentCount}</div>
                            <div class="stat-label">Agents</div>
                        </div>
                    </div>
                    <div class="stat-item">
                        <i class="fas fa-shield-alt text-success"></i>
                        <div>
                            <div class="stat-value">${whitelistCount}</div>
                            <div class="stat-label">Whitelist</div>
                        </div>
                    </div>
                </div>
                
                ${agentCount > 0 ? `
                    <div class="agents-preview">
                        ${agentAvatarsHtml}
                        ${moreAvatarHtml}
                        <span class="agents-preview-text">
                            ${agentCount} agent${agentCount !== 1 ? 's' : ''} assigned
                        </span>
                    </div>
                ` : `
                    <div class="agents-preview">
                        <span class="text-muted"><i class="fas fa-info-circle me-1"></i>No agents assigned</span>
                    </div>
                `}
            </div>
            
            <div class="group-card-footer">
                <a href="/whitelist?group_id=${group._id}" class="btn btn-sm btn-outline-primary">
                    <i class="fas fa-shield-alt me-1"></i>Manage Whitelist
                </a>
                <span class="text-muted small">v${group.whitelist_version || 1}</span>
            </div>
        </div>
    `;
}

// ========================================
// FILTERING & SORTING
// ========================================

function filterGroups() {
    const searchTerm = document.getElementById('groupSearch').value.toLowerCase();
    const cards = document.querySelectorAll('.group-card');
    
    cards.forEach(card => {
        const name = card.dataset.name || '';
        const description = card.dataset.description || '';
        const matches = name.includes(searchTerm) || description.includes(searchTerm);
        card.style.display = matches ? '' : 'none';
    });
}

function sortGroups() {
    const sortBy = document.getElementById('sortFilter').value;
    
    groupsData.sort((a, b) => {
        switch (sortBy) {
            case 'name':
                return (a.name || '').localeCompare(b.name || '');
            case 'agents':
                const aAgents = agentsData.filter(ag => ag.group_id === a._id).length;
                const bAgents = agentsData.filter(ag => ag.group_id === b._id).length;
                return bAgents - aAgents;
            case 'whitelist':
                return (b.whitelist?.length || 0) - (a.whitelist?.length || 0);
            case 'updated':
                return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
            default:
                return 0;
        }
    });
    
    renderGroups();
}

// ========================================
// CRUD OPERATIONS
// ========================================

function openCreateGroupModal() {
    document.getElementById('groupModalTitle').textContent = 'Create Group';
    const subtitle = document.getElementById('groupModalSubtitle');
    if (subtitle) subtitle.textContent = 'Organize agents under one policy';
    document.getElementById('editGroupId').value = '';
    document.getElementById('groupName').value = '';
    document.getElementById('groupDescription').value = '';
    selectedColor = 'primary';

    // Clear quick domains
    quickDomains = [];
    quickDomainEntries = [];
    renderQuickDomains();

    const modal = new bootstrap.Modal(document.getElementById('groupModal'));
    modal.show();
}

function openEditGroupModal(groupId) {
    const group = groupsData.find(g => g._id === groupId);
    if (!group) return;

    document.getElementById('groupModalTitle').textContent = 'Edit Group';
    const subtitle = document.getElementById('groupModalSubtitle');
    if (subtitle) subtitle.textContent = `Update "${group.name || ''}" settings`;
    document.getElementById('editGroupId').value = groupId;
    document.getElementById('groupName').value = group.name || '';
    document.getElementById('groupDescription').value = group.description || '';
    selectedColor = group.color || 'primary';
    
    // FIX: Preserve full entry objects so we don't lose type/category/priority
    quickDomainEntries = (group.whitelist || []).map(item => {
        if (typeof item === 'string') return { value: item, type: 'domain', category: 'general' };
        return { ...item };
    }).filter(e => e.value);
    quickDomains = quickDomainEntries.map(e => e.value || e.domain || '').filter(Boolean);
    renderQuickDomains();
    
    const modal = new bootstrap.Modal(document.getElementById('groupModal'));
    modal.show();
}

async function saveGroup() {
    const groupId = document.getElementById('editGroupId').value;
    const name = document.getElementById('groupName').value.trim();
    const description = document.getElementById('groupDescription').value.trim();
    
    if (!name) {
        showError('Group name is required');
        return;
    }
    
    const payload = {
        name,
        description,
        color: selectedColor
    };
    
    // FIX: Always include whitelist, even if empty (for edit mode)
    const isEdit = Boolean(groupId);
    
    if (isEdit || quickDomains.length > 0) {
        const now = new Date().toISOString();
        // Build whitelist preserving existing entry fields
        const existingMap = {};
        quickDomainEntries.forEach(e => {
            const key = (e.value || e.domain || '').toLowerCase();
            if (key) existingMap[key] = e;
        });

        payload.whitelist = quickDomains.map(domain => {
            const existing = existingMap[domain.toLowerCase()];
            if (existing) {
                // Preserve original fields
                return { ...existing, value: domain };
            }
            // New domain added in this session
            return {
                value: domain,
                type: 'domain',
                category: 'general',
                added_at: now,
                added_date: now
            };
        });
    }
    
    const url = isEdit ? `/api/groups/${groupId}` : '/api/groups';
    const method = isEdit ? 'PATCH' : 'POST';
    
    try {
        console.log('Saving group:', { url, method, payload });
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        console.log('Save result:', result);
        
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to save group');
        }
        
        bootstrap.Modal.getInstance(document.getElementById('groupModal')).hide();
        showSuccess(isEdit ? 'Group updated successfully' : 'Group created successfully');
        
        await loadGroups();
        
    } catch (error) {
        console.error('Error saving group:', error);
        showError(error.message || 'Failed to save group');
    }
}

async function deleteGroup(groupId) {
    const group = groupsData.find(g => g._id === groupId);
    if (!group) return;
    
    const agentsInGroup = agentsData.filter(a => a.group_id === groupId);
    
    let confirmMsg = `Delete group "${group.name}"?`;
    if (agentsInGroup.length > 0) {
        confirmMsg += `\n\nThis group has ${agentsInGroup.length} agent(s) assigned. They will be moved to Pending.`;
    }
    
    if (!confirm(confirmMsg)) return;
    
    try {
        const response = await fetch(`/api/groups/${groupId}`, { method: 'DELETE' });
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to delete group');
        }
        
        showSuccess('Group deleted successfully');
        await loadGroups();
        await loadAgents();
        
    } catch (error) {
        console.error('Error deleting group:', error);
        showError(error.message || 'Failed to delete group');
    }
}

function viewGroupDetail(groupId) {
    window.location.href = `/groups/${groupId}`;
}

// ========================================
// QUICK DOMAINS
// ========================================

function addQuickDomain() {
    const input = document.getElementById('quickDomainInput');
    const domain = input.value.trim().toLowerCase();
    
    if (!domain) return;
    
    // Basic validation
    if (!domain.match(/^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,}$/)) {
        showError('Invalid domain format');
        return;
    }
    
    if (quickDomains.includes(domain)) {
        showError('Domain already added');
        return;
    }
    
    quickDomains.push(domain);
    input.value = '';
    renderQuickDomains();
}

function removeQuickDomain(domain) {
    quickDomains = quickDomains.filter(d => d !== domain);
    renderQuickDomains();
}

function renderQuickDomains() {
    const container = document.getElementById('quickDomainsList');
    const emptyHint = document.querySelector('.quick-whitelist-empty');

    if (quickDomains.length === 0) {
        container.innerHTML = '';
        if (emptyHint) emptyHint.style.display = '';
        return;
    }

    if (emptyHint) emptyHint.style.display = 'none';

    container.innerHTML = quickDomains.map(domain => `
        <span class="quick-domain-tag">
            <i class="fas fa-globe"></i>
            <span>${escapeHtml(domain)}</span>
            <button type="button" class="quick-domain-remove" onclick="removeQuickDomain('${domain}')" aria-label="Remove">
                <i class="fas fa-times"></i>
            </button>
        </span>
    `).join('');
}

// ========================================
// BULK ACTIONS
// ========================================

function bulkExportWhitelist() {
    // Combine all whitelists
    const allDomains = new Set();
    
    groupsData.forEach(group => {
        (group.whitelist || []).forEach(item => {
            const domain = typeof item === 'string' ? item : (item.value || item.domain);
            if (domain) {
                allDomains.add(domain);
            }
        });
    });
    
    if (allDomains.size === 0) {
        showError('No domains to export');
        return;
    }
    
    const content = Array.from(allDomains).join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'whitelist_export.txt';
    a.click();
    URL.revokeObjectURL(url);
    
    showSuccess(`Exported ${allDomains.size} domains`);
}

function bulkSyncWhitelist() {
    // TODO: Implement actual sync via SocketIO
    showSuccess('Sync request sent to all agents');
    bootstrap.Modal.getInstance(document.getElementById('bulkActionsModal'))?.hide();
}

function bulkCopyWhitelist() {
    bootstrap.Modal.getInstance(document.getElementById('bulkActionsModal'))?.hide();
    
    // Populate dropdowns
    const fromSelect = document.getElementById('copyFromGroup');
    const toSelect = document.getElementById('copyToGroup');
    
    const options = groupsData.map(g => 
        `<option value="${g._id}">${g.name} (${(g.whitelist || []).length} domains)</option>`
    ).join('');
    
    fromSelect.innerHTML = options;
    toSelect.innerHTML = options;
    
    const modal = new bootstrap.Modal(document.getElementById('copyWhitelistModal'));
    modal.show();
}

async function executeCopyWhitelist() {
    const fromId = document.getElementById('copyFromGroup').value;
    const toId = document.getElementById('copyToGroup').value;
    const merge = document.getElementById('mergeWhitelist').checked;
    
    if (fromId === toId) {
        showError('Source and destination must be different');
        return;
    }
    
    const fromGroup = groupsData.find(g => g._id === fromId);
    const toGroup = groupsData.find(g => g._id === toId);
    
    if (!fromGroup || !toGroup) return;
    
    let newWhitelist;
    if (merge) {
        // Merge: combine both whitelists, remove duplicates
        const existingDomains = new Set(
            (toGroup.whitelist || []).map(item => 
                typeof item === 'string' ? item : (item.value || item.domain)
            )
        );
        
        newWhitelist = [...(toGroup.whitelist || [])];
        (fromGroup.whitelist || []).forEach(item => {
            const domain = typeof item === 'string' ? item : (item.value || item.domain);
            if (!existingDomains.has(domain)) {
                newWhitelist.push(item);
            }
        });
    } else {
        // Replace: just copy from source
        newWhitelist = [...(fromGroup.whitelist || [])];
    }
    
    try {
        const response = await fetch(`/api/groups/${toId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ whitelist: newWhitelist })
        });
        
        if (!response.ok) throw new Error('Failed to copy whitelist');
        
        bootstrap.Modal.getInstance(document.getElementById('copyWhitelistModal')).hide();
        showSuccess(`Whitelist copied to ${toGroup.name}`);
        await loadGroups();
        
    } catch (error) {
        console.error('Error copying whitelist:', error);
        showError('Failed to copy whitelist');
    }
}

// ========================================
// UTILITIES
// ========================================

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(message) {
    // Try to use global notification if available
    if (typeof showNotification === 'function') {
        showNotification('success', message);
        return;
    }
    
    // Fallback: create toast notification
    const toast = document.createElement('div');
    toast.className = 'alert alert-success alert-dismissible fade show position-fixed';
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    toast.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function showError(message) {
    // Try to use global notification if available
    if (typeof showNotification === 'function') {
        showNotification('danger', message);
        return;
    }
    
    // Fallback: create toast notification
    const toast = document.createElement('div');
    toast.className = 'alert alert-danger alert-dismissible fade show position-fixed';
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    toast.innerHTML = `
        <i class="fas fa-exclamation-triangle me-2"></i>${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}