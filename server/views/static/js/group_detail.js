let groupAgents = [];
let allAgents = [];
let selectedAgents = new Set();
let agentPolicies = {};        // { agent_id: { override_mode, reason, ... } }
let customWlDomains = [];      // Temp state for custom whitelist modal
let ctxTargetAgentId = null;   // Agent currently targeted by context menu
let wlEntries = [];            // Inline whitelist editor state
let wlAllEntries = [];         // Unfiltered copy for search
const groupId = document.getElementById('groupId').value;

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Group detail page initialized for:', groupId);
    
    loadGroupAgents();
    setupEventListeners();
    setupSocketIO();
    formatDates();
    wlLoadEntries();
    
    // Initialize custom select for status filter
    if (typeof initCustomSelect === 'function') {
        initCustomSelect('statusFilter');
    }
});

function setupEventListeners() {
    // Search and filter
    document.getElementById('agentSearch')?.addEventListener('input', filterGroupAgents);
    document.getElementById('statusFilter')?.addEventListener('change', filterGroupAgents);
    
    // Available agents search
    document.getElementById('availableAgentSearch')?.addEventListener('input', filterAvailableAgents);
    
    // Confirm add agents button
    document.getElementById('confirmAddAgents')?.addEventListener('click', addSelectedAgents);

    // Unassigned agents search in Assign Modal
    document.getElementById('unassignedAgentSearch')?.addEventListener('input', filterUnassignedAgentsList);
}

function setupSocketIO() {
    if (typeof io === 'undefined') {
        console.warn('Socket.IO not available');
        return;
    }
    
    const socket = io();
    
    socket.on('agent_heartbeat', (data) => {
        updateAgentStatus(data.agent_id, data.status, data);
    });
    
    socket.on('agent_group_updated', (data) => {
        if (data.group_id === groupId || groupAgents.some(a => a.agent_id === data.agent_id)) {
            loadGroupAgents();
        }
    });
    
    socket.on('agent_policy_changed', (data) => {
        if (groupAgents.some(a => a.agent_id === data.agent_id)) {
            // Update local policy cache + re-render
            agentPolicies[data.agent_id] = {
                override_mode: data.override_mode,
                reason: data.reason,
                applied_by_username: data.applied_by,
                expires_at: data.expires_at,
            };
            if (currentView === 'map') {
                renderGroupMap(groupAgents);
            } else {
                renderGroupAgents(groupAgents);
            }
        }
    });

    socket.on('connect', () => {
        console.log('Socket.IO connected');
    });
}

function formatDates() {
    const createdEl = document.getElementById('groupCreated');
    const updatedEl = document.getElementById('groupUpdated');
    
    if (createdEl && createdEl.textContent) {
        createdEl.textContent = formatTimestamp(createdEl.textContent);
    }
    if (updatedEl && updatedEl.textContent) {
        updatedEl.textContent = formatTimestamp(updatedEl.textContent);
    }
}

// ========================================
// DATA LOADING
// ========================================

async function loadGroupAgents() {
    try {
        const response = await fetch(`/api/agents?group_id=${groupId}`);
        if (!response.ok) throw new Error('Failed to load agents');

        const data = await response.json();
        groupAgents = data.agents || [];

        console.log(`Loaded ${groupAgents.length} agents for group`);

        // Load policies for all agents in parallel
        await loadAgentPolicies(groupAgents.map(a => a.agent_id));

        if (currentView === 'map') {
            renderGroupMap(groupAgents);
        } else {
            renderGroupAgents(groupAgents);
        }
        updateStatistics();

    } catch (error) {
        console.error('Error loading group agents:', error);
        showError('Failed to load agents');
    }
}

async function loadAgentPolicies(agentIds) {
    // Load policy for each agent (batch would be better but individual is fine for now)
    const promises = agentIds.map(async (id) => {
        try {
            const resp = await fetch(`/api/agents/${id}/policy`);
            if (resp.ok) {
                const result = await resp.json();
                if (result.success && result.data) {
                    agentPolicies[id] = result.data;
                }
            }
        } catch (e) {
            // Policy not found = none, which is fine
        }
    });
    await Promise.all(promises);
}

async function loadAllAgents() {
    try {
        // Ask server to exclude agents already in this group so the picker only shows available ones
        const response = await fetch(`/api/agents?exclude_group_id=${groupId}`);
        if (!response.ok) throw new Error('Failed to load agents');
        
        const data = await response.json();
        allAgents = data.agents || [];
        
        return allAgents;
    } catch (error) {
        console.error('Error loading all agents:', error);
        return [];
    }
}

function refreshGroupAgents() {
    const btn = event?.target;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
    }
    
    loadGroupAgents().finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Refresh';
        }
    });
}

// ========================================
// RENDERING
// ========================================

function renderGroupAgents(agents) {
    const container = document.getElementById('groupAgentsContainer');
    
    if (!agents || agents.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-users"></i>
                </div>
                <h5 class="fw-bold mt-3">No Agents in this Group</h5>
                <p class="text-muted mb-4">Add agents to this group to manage them together.</p>
                <button class="btn btn-primary" onclick="openAddAgentModal()">
                    <i class="fas fa-plus me-2"></i>Add Agent
                </button>
            </div>
        `;
        return;
    }
    
    container.innerHTML = agents.map(agent => renderAgentItem(agent)).join('');
    
    // Update count
    document.getElementById('agentCount').textContent = agents.length;
}

function renderAgentItem(agent) {
    const statusInfo = getStatusInfo(agent.status);
    const displayName = agent.display_name || agent.hostname || agent.agent_id;
    const lastSeen = formatTimestamp(agent.last_heartbeat);

    // Policy badge for list view
    const policy = agentPolicies[agent.agent_id];
    const policyMode = policy?.override_mode || 'none';
    let policyBadgeHtml = '';
    if (policyMode === 'isolate') {
        policyBadgeHtml = '<span class="badge bg-danger ms-2" title="Cắt mạng"><i class="fas fa-ban me-1"></i>Isolated</span>';
    } else if (policyMode === 'custom_whitelist') {
        policyBadgeHtml = '<span class="badge bg-warning text-dark ms-2" title="Whitelist riêng"><i class="fas fa-list-alt me-1"></i>Custom</span>';
    }

    return `
        <div class="group-agent-item" data-agent-id="${agent.agent_id}"
             data-name="${(displayName + ' ' + (agent.hostname || '')).toLowerCase()}"
             data-ip="${(agent.ip_address || '').toLowerCase()}"
             data-status="${agent.status || 'unknown'}"
             oncontextmenu="showAgentContextMenu(event, '${agent.agent_id}')">
            <div class="agent-info">
                <div class="agent-avatar">
                    <i class="fas fa-desktop"></i>
                </div>
                <div class="agent-details">
                    <h6>${escapeHtml(displayName)}${policyBadgeHtml}</h6>
                    <div class="agent-meta">
                        <small><i class="fas fa-network-wired me-1"></i>${agent.ip_address || 'Unknown IP'}</small>
                        <small><i class="fas fa-clock me-1"></i>${lastSeen}</small>
                    </div>
                </div>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="status-badge ${statusInfo.class}">
                    <span class="status-dot ${statusInfo.class}"></span>
                    ${statusInfo.text}
                </span>
                <div class="agent-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick="viewAgentLogs('${agent.agent_id}')" title="View Logs">
                        <i class="fas fa-file-alt"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeAgentFromGroup('${agent.agent_id}')" title="Remove from Group">
                        <i class="fas fa-user-minus"></i>
                    </button>
                </div>
            </div>
        </div>
    `;
}

function updateStatistics() {
    const total = groupAgents.length;
    const active = groupAgents.filter(a => a.status === 'active').length;
    const inactive = groupAgents.filter(a => a.status === 'inactive').length;
    const offline = groupAgents.filter(a => a.status === 'offline' || !a.status).length;
    
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statActive').textContent = active;
    document.getElementById('statInactive').textContent = inactive;
    document.getElementById('statOffline').textContent = offline;
    document.getElementById('agentCount').textContent = total;
}

// ========================================
// ADD AGENT MODAL
// ========================================

async function openAddAgentModal() {
    // Reset target position if called directly from "Add Agent" button
    if (event && event.currentTarget && event.currentTarget.getAttribute && event.currentTarget.getAttribute('onclick') === 'openAddAgentModal()') {
        targetSlotPosition = null;
    }

    selectedAgents.clear();
    updateSelectedCount();
    
     // Update modal title
    const titleEl = document.querySelector('#addAgentModal .modal-title');
    if (titleEl) {
        if (targetSlotPosition) {
            titleEl.textContent = `Assign Agent to Position ${targetSlotPosition}`;
        } else {
            titleEl.innerHTML = '<i class="fas fa-plus-circle me-2"></i>Add Agent to Group';
        }
    }

    const modal = new bootstrap.Modal(document.getElementById('addAgentModal'));
    modal.show();
    
    // Load available agents
    const container = document.getElementById('availableAgentsContainer');
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>';
    
    await loadAllAgents();
    renderAvailableAgents();
}

function renderAvailableAgents() {
    const container = document.getElementById('availableAgentsContainer');
    
    // Filter out agents already in this group
    const groupAgentIds = new Set(groupAgents.map(a => a.agent_id));
    const availableAgents = allAgents.filter(a => !groupAgentIds.has(a.agent_id));
    
    if (availableAgents.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="fas fa-check-circle fa-2x mb-2"></i>
                <p class="mb-0">All agents are already in this group</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = availableAgents.map(agent => {
        const displayName = agent.display_name || agent.hostname || agent.agent_id;
        const statusInfo = getStatusInfo(agent.status);
        const currentGroup = agent.group_id ? 'In another group' : 'Unassigned';
        
        return `
            <div class="available-agent-item ${selectedAgents.has(agent.agent_id) ? 'selected' : ''}" 
                 data-agent-id="${agent.agent_id}"
                 data-name="${(displayName + ' ' + (agent.hostname || '')).toLowerCase()}"
                 data-ip="${(agent.ip_address || '').toLowerCase()}"
                 onclick="toggleAgentSelection('${agent.agent_id}')">
                <input type="checkbox" class="form-check-input" 
                       ${selectedAgents.has(agent.agent_id) ? 'checked' : ''}>
                <div class="flex-grow-1">
                    <div class="fw-semibold">${escapeHtml(displayName)}</div>
                    <small class="text-muted">
                        ${agent.ip_address || 'Unknown IP'} · 
                        <span class="status-badge ${statusInfo.class}" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;">
                            ${statusInfo.text}
                        </span> · 
                        ${currentGroup}
                    </small>
                </div>
            </div>
        `;
    }).join('');
}

function toggleAgentSelection(agentId) {
    if (targetSlotPosition !== null) {
        // Single selection mode for specific slot
        if (selectedAgents.has(agentId)) {
            selectedAgents.delete(agentId);
        } else {
            selectedAgents.clear();
            selectedAgents.add(agentId);
        }
        
        // Update all checkboxes
        document.querySelectorAll('.available-agent-item').forEach(item => {
            const id = item.dataset.agentId;
            const isSelected = selectedAgents.has(id);
            item.classList.toggle('selected', isSelected);
            item.querySelector('input[type="checkbox"]').checked = isSelected;
        });
    } else {
        // Multi-selection mode
        if (selectedAgents.has(agentId)) {
            selectedAgents.delete(agentId);
        } else {
            selectedAgents.add(agentId);
        }
        
        // Update UI
        const item = document.querySelector(`.available-agent-item[data-agent-id="${agentId}"]`);
        if (item) {
            item.classList.toggle('selected', selectedAgents.has(agentId));
            item.querySelector('input[type="checkbox"]').checked = selectedAgents.has(agentId);
        }
    }
    
    updateSelectedCount();
}

function updateSelectedCount() {
    const count = selectedAgents.size;
    document.getElementById('selectedCount').textContent = count;
    document.getElementById('confirmAddAgents').disabled = count === 0;
}

function filterAvailableAgents() {
    const searchTerm = document.getElementById('availableAgentSearch').value.toLowerCase();
    const items = document.querySelectorAll('.available-agent-item');
    
    items.forEach(item => {
        const name = item.dataset.name || '';
        const ip = item.dataset.ip || '';
        const matches = name.includes(searchTerm) || ip.includes(searchTerm);
        item.style.display = matches ? 'flex' : 'none';
    });
}

async function addSelectedAgents() {
    if (selectedAgents.size === 0) return;
    
    const btn = document.getElementById('confirmAddAgents');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Adding...';
    
    try {
        const promises = Array.from(selectedAgents).map(agentId => 
            fetch(`/api/agents/${agentId}/group`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group_id: groupId })
            })
        );
        
        await Promise.all(promises);

        // If adding to specific slot
        if (targetSlotPosition !== null && selectedAgents.size === 1) {
            const agentId = selectedAgents.values().next().value;
            await fetch(`/api/agents/${agentId}/position`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ position: targetSlotPosition })
            });
        }
        
        showSuccess(`Added ${selectedAgents.size} agent(s) to group`);
        bootstrap.Modal.getInstance(document.getElementById('addAgentModal')).hide();
        
        // Reload agents
        await loadGroupAgents();
        
    } catch (error) {
        console.error('Error adding agents:', error);
        showError('Failed to add some agents');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus me-1"></i>Add Selected (<span id="selectedCount">0</span>)';
    }
}

// ========================================
// AGENT ACTIONS
// ========================================

async function removeAgentFromGroup(agentId) {
    const agent = groupAgents.find(a => a.agent_id === agentId);
    const displayName = agent?.display_name || agent?.hostname || agentId;
    
    if (!confirm(`Remove "${displayName}" from this group?\n\nThe agent will be moved to Pending.`)) {
        return;
    }
    
    try {
        // Get pending group ID
        const groupsResponse = await fetch('/api/groups');
        const groupsData = await groupsResponse.json();
        const pendingGroup = groupsData.data?.find(g => g.is_system && g.name === 'pending');
        
        if (!pendingGroup) {
            throw new Error('Pending group not found');
        }
        
        const response = await fetch(`/api/agents/${agentId}/group`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_id: pendingGroup._id })
        });
        
        if (!response.ok) throw new Error('Failed to remove agent');
        
        showSuccess(`${displayName} removed from group`);
        await loadGroupAgents();
        
    } catch (error) {
        console.error('Error removing agent:', error);
        showError('Failed to remove agent from group');
    }
}

function viewAgentLogs(agentId) {
    window.location.href = `/logs?agent_id=${agentId}`;
}

function updateAgentStatus(agentId, status, data) {
    const agent = groupAgents.find(a => a.agent_id === agentId);
    if (agent) {
        agent.status = status;
        agent.last_heartbeat = data.last_heartbeat;
        
        if (currentView === 'map') {
            renderGroupMap(groupAgents);
        } else {
            renderGroupAgents(groupAgents);
        }
        updateStatistics();
    }
}

// ========================================
// FILTER & SEARCH
// ========================================

function filterGroupAgents() {
    const searchTerm = document.getElementById('agentSearch').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    
    const items = document.querySelectorAll('.group-agent-item');
    
    items.forEach(item => {
        const name = item.dataset.name || '';
        const ip = item.dataset.ip || '';
        const status = item.dataset.status || '';
        
        const matchesSearch = name.includes(searchTerm) || ip.includes(searchTerm);
        const matchesStatus = !statusFilter || status === statusFilter;
        
        item.style.display = (matchesSearch && matchesStatus) ? 'flex' : 'none';
    });
}

// ========================================
// EDIT GROUP
// ========================================

function openEditGroupModal() {
    const modal = new bootstrap.Modal(document.getElementById('editGroupModal'));
    modal.show();
}

async function saveGroupChanges() {
    const name = document.getElementById('editGroupName').value.trim();
    const description = document.getElementById('editGroupDescription').value.trim();
    
    if (!name) {
        showError('Group name is required');
        return;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description })
        });
        
        const result = await response.json();
        
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to update group');
        }
        
        // Update page
        document.getElementById('groupName').textContent = name;
        document.getElementById('groupDescription').textContent = description || 'No description';
        
        bootstrap.Modal.getInstance(document.getElementById('editGroupModal')).hide();
        showSuccess('Group updated successfully');
        
    } catch (error) {
        console.error('Error updating group:', error);
        showError(error.message || 'Failed to update group');
    }
}

// ========================================
// UTILITIES
// ========================================

function getStatusInfo(status) {
    switch (status) {
        case 'active':
            return { class: 'active', text: 'Active' };
        case 'inactive':
            return { class: 'inactive', text: 'Inactive' };
        case 'offline':
            return { class: 'offline', text: 'Offline' };
        default:
            return { class: 'offline', text: 'Unknown' };
    }
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch {
        return 'Invalid Date';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showSuccess(message) {
    if (typeof showNotification === 'function') {
        showNotification('success', message);
    } else {
        alert(message);
    }
}

function showError(message) {
    if (typeof showNotification === 'function') {
        showNotification('danger', message);
    } else {
        alert('Error: ' + message);
    }
}

// ========================================
// MAP VIEW & DRAG DROP
// ========================================

let currentView = 'list';
let targetSlotPosition = null;

function switchView(mode) {
    currentView = mode;
    const listContainer = document.getElementById('groupAgentsContainer');
    const mapWrapper = document.getElementById('groupMapWrapper');
    const filterParams = document.getElementById('listFilterParams');
    
    if (mode === 'map') {
        listContainer.style.display = 'none';
        mapWrapper.style.display = 'block';
        if (filterParams) filterParams.style.display = 'none';
        renderGroupMap(groupAgents);
    } else {
        listContainer.style.display = 'block';
        mapWrapper.style.display = 'none';
        if (filterParams) filterParams.style.display = 'block';
        renderGroupAgents(groupAgents); // Re-render to ensure latest state
    }
}

function updateGridLayout() {
    renderGroupMap(groupAgents);
}

function renderGroupMap(agents) {
    const mapContainer = document.getElementById('groupMapContainer');
    const unassignedContainer = document.getElementById('unassignedGrid');
    
    // Get Grid Configuration (limit processing if value is invalid)
    let rows = parseInt(document.getElementById('gridRows').value);
    let cols = parseInt(document.getElementById('gridCols').value);
    
    if (!rows || rows < 1) rows = 1;
    if (!cols || cols < 1) cols = 1;
    
    // Create Layout: Single flexible grid
    // Use CSS Grid in inline style for dynamic rows/cols
    const gridStyle = `display: grid; grid-template-columns: repeat(${cols}, 1fr); gap: 10px; padding: 10px;`;
    
    let html = `<div class="classroom-layout" style="${gridStyle}">`;
    
    const totalSlots = rows * cols;
    
    // Calculate size estimate (optional optimisation)
    
    for (let i = 0; i < totalSlots; i++) {
        const pos = i + 1; 
        html += renderSlot(pos, agents);
    }
    
    html += '</div>'; // End layout
    
    mapContainer.innerHTML = html;
    
    // Render Unassigned
    // Filter agents that have no position OR have position > totalSlots
    const unassigned = agents.filter(a => !a.position || a.position < 1 || a.position > totalSlots);
    
    // We sort unassigned by status (active first) then name
    unassigned.sort((a, b) => {
        if (a.status === 'active' && b.status !== 'active') return -1;
        if (a.status !== 'active' && b.status === 'active') return 1;
        return (a.display_name || '').localeCompare(b.display_name || '');
    });
    
    if (unassigned.length > 0) {
        unassignedContainer.innerHTML = unassigned.map(agent => renderDraggableCard(agent)).join('');
    } else {
        unassignedContainer.innerHTML = '<div class="text-muted p-3 w-100 text-center small" style="grid-column: 1 / -1;">All agents assigned to positions</div>';
    }
}

function renderSlot(pos, agents) {
    const agent = agents.find(a => a.position === pos);
    let content = '';
    
    if (agent) {
        content = renderDraggableCard(agent, true);
        return `
            <div class="device-slot occupied" id="slot-${pos}" 
                 ondrop="drop(event, ${pos})" 
                 ondragover="allowDrop(event)">
                 <div class="position-badge">${pos}</div>
                 ${content}
            </div>
        `;
    } else {
        // Empty slot - clickable to map agent
        return `
            <div class="device-slot empty" id="slot-${pos}" 
                 ondrop="drop(event, ${pos})" 
                 ondragover="allowDrop(event)"
                 onclick="openAssignPositionModal(${pos})"
                 title="Click to assign agent">
                 <div class="position-badge">${pos}</div>
                 <div class="slot-placeholder">
                    <i class="fas fa-plus"></i>
                 </div>
            </div>
        `;
    }
}

// ========================================
// ASSIGN POSITION MODAL
// ========================================

function openAssignPositionModal(pos) {
    targetSlotPosition = pos;
    const modalTitle = document.querySelector('#assignPositionModal .modal-title');
    if (modalTitle) modalTitle.textContent = `Assign Agent to Position ${pos}`;
    
    // Populate list
    // Filter agents in group that DO NOT have a position (or position is invalid/cleared)
    // Also include agents that might have high positions if they are considered unassigned in pool
    // But conceptually, we just want agents who are currently "Unassigned"
    
    // We can also allow moving agents? For simplicity, just unassigned ones first.
    // If user wants to swap, they can drag drop.
    const unassigned = groupAgents.filter(a => !a.position || a.position < 1);
    
    renderUnassignedAgentsList(unassigned);
    
    const modal = new bootstrap.Modal(document.getElementById('assignPositionModal'));
    modal.show();
}

function renderUnassignedAgentsList(agents) {
    const container = document.getElementById('unassignedAgentsList');
    if (!container) return;
    
    if (agents.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted">
                <p class="mb-2">No unassigned agents found</p>
                <small>Use "Add Agent" to bring new agents into the group first.</small>
            </div>
        `;
        return;
    }
    
    container.innerHTML = agents.map(agent => {
        const displayName = agent.display_name || agent.hostname || agent.agent_id;
        const statusInfo = getStatusInfo(agent.status);
        
        return `
            <button type="button" class="list-group-item list-group-item-action d-flex align-items-center gap-3 unassigned-list-item"
                    data-search="${(displayName + ' ' + (agent.ip_address || '')).toLowerCase()}"
                    onclick="assignAgentToPosition('${agent.agent_id}')">
                <div class="agent-avatar small" style="width: 32px; height: 32px; font-size: 0.8rem;">
                    <i class="fas fa-desktop"></i>
                </div>
                <div class="flex-grow-1 text-start">
                    <div class="fw-semibold small">${escapeHtml(displayName)}</div>
                    <div class="text-muted extra-small" style="font-size: 0.75rem;">
                        ${agent.ip_address || 'Unknown IP'}
                    </div>
                </div>
                <span class="badge ${getStatusBadgeClass(agent.status)} rounded-pill">
                    ${statusInfo.text}
                </span>
            </button>
        `;
    }).join('');
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'active': return 'bg-success';
        case 'inactive': return 'bg-warning text-dark';
        case 'offline': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

function filterUnassignedAgentsList() {
    const term = document.getElementById('unassignedAgentSearch').value.toLowerCase();
    const items = document.querySelectorAll('.unassigned-list-item');
    items.forEach(item => {
        const text = item.getAttribute('data-search') || '';
        item.style.display = text.includes(term) ? 'flex' : 'none';
    });
}

async function assignAgentToPosition(agentId) {
    if (targetSlotPosition === null) return;
    
    const btn = event.currentTarget;
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<div class="spinner-border spinner-border-sm text-primary me-2"></div> Assigning...';
    btn.disabled = true;

    try {
        await updateAgentPosition(agentId, targetSlotPosition);
        
        // Close modal
        const modalEl = document.getElementById('assignPositionModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();
        
        showSuccess('Agent assigned successfully');
    } catch (error) {
        console.error('Error assigning agent:', error);
        btn.innerHTML = originalContent;
        btn.disabled = false;
        showError('Failed to assign agent');
    }
}

function renderDraggableCard(agent, isCompact=false) {
    const statusClass = `status-${agent.status || 'offline'}`;
    const displayName = agent.display_name || agent.hostname;
    const shortIp = agent.ip_address || '---';

    // Policy overlay
    const policy = agentPolicies[agent.agent_id];
    const policyMode = policy?.override_mode || 'none';
    const policyClass = policyMode !== 'none' ? ` policy-${policyMode}` : '';
    let policyBadgeHtml = '';
    if (policyMode === 'isolate') {
        policyBadgeHtml = '<span class="policy-badge policy-badge-isolate" title="Cắt mạng"><i class="fas fa-ban"></i></span>';
    } else if (policyMode === 'custom_whitelist') {
        policyBadgeHtml = '<span class="policy-badge policy-badge-custom" title="Whitelist riêng"><i class="fas fa-list-alt"></i></span>';
    }

    // Right-click handler for context menu
    const ctxHandler = `oncontextmenu="showAgentContextMenu(event, '${agent.agent_id}')"`;

    if (isCompact) {
         return `
            <div class="device-card ${statusClass}${policyClass}"
                 id="card-${agent.agent_id}"
                 draggable="true"
                 data-agent-id="${agent.agent_id}"
                 ondragstart="drag(event, '${agent.agent_id}')"
                 ${ctxHandler}
                 title="${escapeHtml(displayName)}">
                ${policyBadgeHtml}
                <div class="device-icon">
                    <i class="fas fa-desktop"></i>
                </div>
                <div class="device-info">
                    <span class="device-ip">${escapeHtml(shortIp)}</span>
                </div>
            </div>
        `;
    }

    return `
        <div class="device-card ${statusClass}${policyClass}"
             id="card-${agent.agent_id}"
             draggable="true"
             style="width: 100px; height: 100px;"
             data-agent-id="${agent.agent_id}"
             ondragstart="drag(event, '${agent.agent_id}')"
             ${ctxHandler}>
            ${policyBadgeHtml}
            <div class="device-icon">
                <i class="fas fa-desktop"></i>
            </div>
            <div class="device-info">
                <div class="fw-bold small text-truncate" style="max-width: 90px;" title="${displayName}">${displayName}</div>
                <div class="small text-muted">${shortIp}</div>
            </div>
        </div>
    `;
}

// Drag and Drop Handlers

function allowDrop(ev) {
    ev.preventDefault();
    const slot = ev.currentTarget;
    if (slot && !slot.classList.contains('drag-over')) {
        slot.classList.add('drag-over');
    }
}

function drag(ev, agentId) {
    ev.dataTransfer.setData("agent_id", agentId);
    ev.dataTransfer.effectAllowed = 'move';
    const card = ev.currentTarget.closest('.device-card');
    if (card) {
        setTimeout(() => card.classList.add('is-dragging'), 0);
    }
}

function drop(ev, pos) {
    ev.preventDefault();
    const slot = ev.currentTarget;
    slot.classList.remove('drag-over');
    
    const agentId = ev.dataTransfer.getData("agent_id");
    if (!agentId) return;
    
    const card = document.getElementById(`card-${agentId}`);
    if (card) card.classList.remove('is-dragging');

    updateAgentPosition(agentId, pos);
}

function dropToUnassigned(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('drag-over');
    
    const agentId = ev.dataTransfer.getData("agent_id");
    if (!agentId) return;
    
    const card = document.getElementById(`card-${agentId}`);
    if (card) card.classList.remove('is-dragging');
    
    updateAgentPosition(agentId, null);
}

// Remove drag-over class when drag leaves
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('dragleave', function(ev) {
        if (ev.target.classList.contains('device-slot')) {
            ev.target.classList.remove('drag-over');
        }
    });
    
    document.addEventListener('dragend', function(ev) {
        // Clean up all drag-over states
        document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
        document.querySelectorAll('.is-dragging').forEach(el => el.classList.remove('is-dragging'));
    });
});

async function updateAgentPosition(agentId, position) {
    try {
        const response = await fetch(`/api/agents/${agentId}/position`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ position: position })
        });

        if (!response.ok) throw new Error('Failed to update position');

        // Update local state
        const agent = groupAgents.find(a => a.agent_id === agentId);
        if (agent) {
            agent.position = position;
        }

        if (position !== null) {
            const collidingAgent = groupAgents.find(a => a.position === position && a.agent_id !== agentId);
            if (collidingAgent) {
                collidingAgent.position = null;
            }
        }

        renderGroupMap(groupAgents);

    } catch (error) {
        console.error('Error updating position:', error);
        alert('Failed to update position');
    }
}

// ========================================
// AGENT POLICY — Context Menu & Actions
// ========================================

function showAgentContextMenu(event, agentId) {
    event.preventDefault();
    event.stopPropagation();

    ctxTargetAgentId = agentId;
    const agent = groupAgents.find(a => a.agent_id === agentId);
    const displayName = agent?.display_name || agent?.hostname || agentId;

    // Update header
    document.getElementById('ctxAgentName').textContent = displayName;

    // Position menu at cursor
    const menu = document.getElementById('agentContextMenu');
    menu.style.display = 'block';

    // Ensure menu stays within viewport
    const menuRect = menu.getBoundingClientRect();
    let x = event.clientX;
    let y = event.clientY;
    if (x + menuRect.width > window.innerWidth) x = window.innerWidth - menuRect.width - 8;
    if (y + menuRect.height > window.innerHeight) y = window.innerHeight - menuRect.height - 8;

    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
}

// Close context menu on click anywhere
document.addEventListener('click', () => {
    document.getElementById('agentContextMenu').style.display = 'none';
});
document.addEventListener('contextmenu', (e) => {
    // Close old menu if clicking outside device cards
    if (!e.target.closest('.device-card')) {
        document.getElementById('agentContextMenu').style.display = 'none';
    }
});

// ── Set Policy (none / isolate) ──

function ctxSetPolicy(mode) {
    document.getElementById('agentContextMenu').style.display = 'none';

    if (mode === 'none') {
        applyPolicy(ctxTargetAgentId, 'none');
        return;
    }

    if (mode === 'isolate') {
        // Open isolate confirm modal
        const agent = groupAgents.find(a => a.agent_id === ctxTargetAgentId);
        document.getElementById('isolateAgentName').textContent =
            agent?.display_name || agent?.hostname || ctxTargetAgentId;
        document.getElementById('isolateReason').value = '';

        const modal = new bootstrap.Modal(document.getElementById('isolateConfirmModal'));
        modal.show();

        // Wire confirm button (remove old listener first)
        const btn = document.getElementById('confirmIsolateBtn');
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener('click', async () => {
            newBtn.disabled = true;
            newBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';

            const reason = document.getElementById('isolateReason').value.trim();
            const durVal = document.getElementById('isolateDuration').value;
            const duration = durVal ? parseInt(durVal) : null;

            await applyPolicy(ctxTargetAgentId, 'isolate', reason, duration);
            bootstrap.Modal.getInstance(document.getElementById('isolateConfirmModal')).hide();
            newBtn.disabled = false;
            newBtn.innerHTML = '<i class="fas fa-ban me-1"></i>Cắt mạng';
        });
    }
}

// ── Custom Whitelist Modal ──

function ctxOpenCustomWhitelist() {
    document.getElementById('agentContextMenu').style.display = 'none';

    const agent = groupAgents.find(a => a.agent_id === ctxTargetAgentId);
    document.getElementById('customWlAgentName').textContent =
        agent?.display_name || agent?.hostname || ctxTargetAgentId;

    // Pre-fill from existing policy if any
    const policy = agentPolicies[ctxTargetAgentId];
    if (policy?.override_mode === 'custom_whitelist' && policy?.custom_whitelist?.length) {
        customWlDomains = policy.custom_whitelist.map(e => e.domain || e);
    } else {
        customWlDomains = [];
    }

    document.getElementById('customWlReason').value = policy?.reason || '';
    document.getElementById('customWlDomainInput').value = '';
    renderCustomWlDomains();

    const modal = new bootstrap.Modal(document.getElementById('customWhitelistModal'));
    modal.show();

    // Wire confirm button
    const btn = document.getElementById('confirmCustomWlBtn');
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', async () => {
        if (customWlDomains.length === 0) {
            showError('Thêm ít nhất 1 domain');
            return;
        }
        newBtn.disabled = true;
        newBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Đang xử lý...';

        const reason = document.getElementById('customWlReason').value.trim();
        const durVal = document.getElementById('customWlDuration').value;
        const duration = durVal ? parseInt(durVal) : null;
        const entries = customWlDomains.map(d => ({ domain: d }));

        await applyPolicy(ctxTargetAgentId, 'custom_whitelist', reason, duration, entries);
        bootstrap.Modal.getInstance(document.getElementById('customWhitelistModal')).hide();
        newBtn.disabled = false;
        newBtn.innerHTML = '<i class="fas fa-check me-1"></i>Áp dụng';
    });
}

function addCustomWlDomain() {
    const input = document.getElementById('customWlDomainInput');
    const domain = input.value.trim().toLowerCase();
    if (!domain) return;
    if (customWlDomains.includes(domain)) {
        input.value = '';
        return;
    }
    customWlDomains.push(domain);
    input.value = '';
    renderCustomWlDomains();
    input.focus();
}

// Allow Enter key to add domain
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('customWlDomainInput')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); addCustomWlDomain(); }
    });
});

function removeCustomWlDomain(domain) {
    customWlDomains = customWlDomains.filter(d => d !== domain);
    renderCustomWlDomains();
}

function renderCustomWlDomains() {
    const container = document.getElementById('customWlDomainList');
    if (customWlDomains.length === 0) {
        container.innerHTML = '<div class="custom-wl-empty"><i class="fas fa-inbox me-1"></i>Chưa có domain nào</div>';
        return;
    }
    container.innerHTML = customWlDomains.map(d => `
        <div class="custom-wl-domain-item">
            <span><i class="fas fa-globe text-primary me-2"></i>${escapeHtml(d)}</span>
            <button class="btn-remove" onclick="removeCustomWlDomain('${escapeHtml(d)}')" title="Xóa">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `).join('');
}

// ── View Policy Info ──

async function ctxViewPolicy() {
    document.getElementById('agentContextMenu').style.display = 'none';

    const agent = groupAgents.find(a => a.agent_id === ctxTargetAgentId);
    document.getElementById('policyInfoAgentName').textContent =
        agent?.display_name || agent?.hostname || ctxTargetAgentId;

    const body = document.getElementById('policyInfoBody');
    body.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></div>';

    const modal = new bootstrap.Modal(document.getElementById('policyInfoModal'));
    modal.show();

    try {
        const resp = await fetch(`/api/agents/${ctxTargetAgentId}/policy`);
        const result = await resp.json();
        const p = result.data || {};

        const modeLabels = {
            none: '<span class="badge bg-success">Bình thường</span>',
            isolate: '<span class="badge bg-danger">Cắt mạng</span>',
            custom_whitelist: '<span class="badge bg-warning text-dark">Whitelist riêng</span>',
        };

        let html = `
            <div class="mb-2"><strong>Mode:</strong> ${modeLabels[p.override_mode] || modeLabels.none}</div>
        `;
        if (p.reason) html += `<div class="mb-2"><strong>Lý do:</strong> ${escapeHtml(p.reason)}</div>`;
        if (p.applied_by_username) html += `<div class="mb-2"><strong>Áp dụng bởi:</strong> ${escapeHtml(p.applied_by_username)}</div>`;
        if (p.expires_at) html += `<div class="mb-2"><strong>Hết hạn:</strong> ${formatTimestamp(p.expires_at)}</div>`;
        if (p.updated_at) html += `<div class="mb-2"><strong>Cập nhật:</strong> ${formatTimestamp(p.updated_at)}</div>`;

        if (p.override_mode === 'custom_whitelist' && p.custom_whitelist?.length) {
            html += `<div class="mt-2"><strong>Domains (${p.custom_whitelist.length}):</strong>
                <ul class="list-unstyled mb-0 mt-1">
                    ${p.custom_whitelist.map(e => `<li class="small"><i class="fas fa-globe text-primary me-1"></i>${escapeHtml(e.domain || e)}</li>`).join('')}
                </ul>
            </div>`;
        }

        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = '<div class="text-danger small">Không tải được policy</div>';
    }
}

// ── Core API call ──

async function applyPolicy(agentId, mode, reason = '', durationMinutes = null, customWhitelist = null) {
    try {
        const body = { mode };
        if (reason) body.reason = reason;
        if (durationMinutes) body.duration_minutes = durationMinutes;
        if (customWhitelist) body.custom_whitelist = customWhitelist;

        const resp = await fetch(`/api/agents/${agentId}/policy`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        const result = await resp.json();

        if (!resp.ok || !result.success) {
            throw new Error(result.error || 'Failed to set policy');
        }

        // Update local cache
        agentPolicies[agentId] = result.data;

        // Re-render
        if (currentView === 'map') {
            renderGroupMap(groupAgents);
        } else {
            renderGroupAgents(groupAgents);
        }

        const modeMessages = {
            none: 'Đã bỏ chặn — trở về bình thường',
            isolate: 'Đã cắt mạng',
            custom_whitelist: 'Đã áp dụng whitelist riêng',
        };
        showSuccess(modeMessages[mode] || 'Policy updated');

    } catch (error) {
        console.error('Error setting policy:', error);
        showError(error.message || 'Không thể cập nhật policy');
    }
}

// ========================================
// INLINE WHITELIST EDITOR
// ========================================

/**
 * Load whitelist entries for this group from API
 */
async function wlLoadEntries() {
    const container = document.getElementById('wlDomainList');
    if (!container) return;

    try {
        const res = await fetch(`/api/whitelist?group_id=${groupId}`);
        const data = await res.json();

        if (!data.success) {
            container.innerHTML = '<div class="wl-empty-state"><p>Lỗi tải whitelist</p></div>';
            return;
        }

        // Combine group entries (primary) — global entries shown separately if needed
        const groupEntries = (data.group || []).map(e => ({...e, _scope: 'group'}));
        const globalEntries = (data.global || []).map(e => ({...e, _scope: 'global'}));

        wlAllEntries = [...groupEntries, ...globalEntries];
        wlEntries = [...wlAllEntries];

        // Update counters
        const countEl = document.getElementById('wlCount');
        const totalEl = document.getElementById('wlTotalCount');
        if (countEl) countEl.textContent = groupEntries.length;
        if (totalEl) totalEl.textContent = wlAllEntries.length;

        wlRenderList();
    } catch (err) {
        console.error('wlLoadEntries error:', err);
        container.innerHTML = '<div class="wl-empty-state"><p>Lỗi kết nối</p></div>';
    }
}

/**
 * Render the filtered whitelist entries
 */
function wlRenderList() {
    const container = document.getElementById('wlDomainList');
    if (!container) return;

    if (wlEntries.length === 0) {
        container.innerHTML = `
            <div class="wl-empty-state">
                <i class="fas fa-shield-alt d-block"></i>
                <p>Chưa có domain nào${wlAllEntries.length > 0 ? ' khớp bộ lọc' : ''}</p>
            </div>`;
        return;
    }

    const html = wlEntries.map(entry => {
        const val = entry.value || entry.domain || '';
        const type = entry.type || 'domain';
        const category = entry.category || '';
        const isActive = entry.is_active !== false;
        const priority = entry.priority || 'normal';
        const scope = entry._scope || 'group';
        const entryId = entry._id || entry.id || '';
        const isGlobal = scope === 'global';

        // Icon by type
        let iconClass = 'fas fa-globe text-primary';
        if (type === 'ip') iconClass = 'fas fa-network-wired text-success';
        else if (type === 'url') iconClass = 'fas fa-link text-info';

        // Category badge
        let catBadge = '';
        if (category && category !== 'general' && category !== 'uncategorized') {
            catBadge = `<span class="badge bg-primary-subtle text-primary">${category}</span>`;
        }

        // Scope badge
        const scopeBadge = isGlobal
            ? '<span class="badge bg-secondary">global</span>'
            : '<span class="badge bg-success-subtle text-success">group</span>';

        // Priority star
        const star = priority === 'high' ? '<i class="fas fa-star wl-priority-star" title="High priority"></i>' : '';

        // Delete button — only for group entries
        const deleteBtn = isGlobal
            ? ''
            : `<div class="wl-actions">
                <button class="btn btn-outline-danger btn-sm" onclick="wlDeleteEntry('${entryId}')" title="Xoá">
                    <i class="fas fa-trash-alt"></i>
                </button>
               </div>`;

        return `
            <div class="wl-entry" data-entry-id="${entryId}" data-scope="${scope}">
                <div class="wl-entry-info">
                    <div class="wl-entry-icon"><i class="${iconClass}"></i></div>
                    <div class="wl-entry-text">
                        <div class="wl-entry-value">${wlEscapeHtml(val)}</div>
                        <div class="wl-entry-badges">
                            <span class="badge bg-light text-secondary">${type}</span>
                            ${catBadge}
                            ${scopeBadge}
                        </div>
                    </div>
                    ${star}
                </div>
                ${deleteBtn}
            </div>`;
    }).join('');

    container.innerHTML = html;
}

/**
 * Filter visible entries by search text and type
 */
function wlFilterList() {
    const search = (document.getElementById('wlSearch')?.value || '').toLowerCase().trim();
    const typeFilter = document.getElementById('wlFilterType')?.value || '';

    wlEntries = wlAllEntries.filter(entry => {
        const val = (entry.value || entry.domain || '').toLowerCase();
        const type = entry.type || 'domain';

        if (search && !val.includes(search)) return false;
        if (typeFilter && type !== typeFilter) return false;
        return true;
    });

    wlRenderList();
}

/**
 * Add a new whitelist entry (supports comma-separated bulk)
 */
async function wlAddEntry() {
    const input = document.getElementById('wlNewValue');
    const typeSelect = document.getElementById('wlNewType');
    const btn = document.getElementById('wlAddBtn');
    if (!input) return;

    const raw = input.value.trim();
    if (!raw) { input.focus(); return; }

    // Split by comma, newline, or space (for bulk)
    const values = raw.split(/[,\n\s]+/).map(v => v.trim().toLowerCase()).filter(Boolean);
    if (values.length === 0) return;

    const type = typeSelect?.value || 'domain';

    // Build items
    const items = values.map(val => ({
        value: val,
        type: type,
        category: 'general',
        scope: 'group',
        group_id: groupId,
        is_active: true,
        priority: 'normal'
    }));

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const res = await fetch('/api/whitelist/bulk', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ items })
        });
        const data = await res.json();

        if (data.success) {
            input.value = '';
            showSuccess(`Đã thêm ${data.added_count || values.length} domain`);
            await wlLoadEntries();
        } else {
            showError(data.error || 'Không thể thêm domain');
        }
    } catch (err) {
        console.error('wlAddEntry error:', err);
        showError('Lỗi kết nối server');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus"></i>';
    }
}

/**
 * Delete a whitelist entry
 */
async function wlDeleteEntry(entryId) {
    if (!entryId) return;
    if (!confirm('Xoá domain này khỏi whitelist?')) return;

    try {
        const res = await fetch('/api/whitelist/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ item_ids: [entryId] })
        });
        const data = await res.json();

        if (data.success) {
            showSuccess('Đã xoá domain');
            await wlLoadEntries();
        } else {
            showError(data.error || 'Không thể xoá');
        }
    } catch (err) {
        console.error('wlDeleteEntry error:', err);
        showError('Lỗi kết nối');
    }
}

/**
 * Handle Enter key in the add input
 */
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.id === 'wlNewValue') {
        e.preventDefault();
        wlAddEntry();
    }
});

/**
 * Escape HTML to prevent XSS
 */
function wlEscapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
