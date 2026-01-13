let groupAgents = [];
let allAgents = [];
let selectedAgents = new Set();
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
    
    return `
        <div class="group-agent-item" data-agent-id="${agent.agent_id}" 
             data-name="${(displayName + ' ' + (agent.hostname || '')).toLowerCase()}"
             data-ip="${(agent.ip_address || '').toLowerCase()}"
             data-status="${agent.status || 'unknown'}">
            <div class="agent-info">
                <div class="agent-avatar">
                    <i class="fas fa-desktop"></i>
                </div>
                <div class="agent-details">
                    <h6>${escapeHtml(displayName)}</h6>
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
    // Styling based on status
    const statusClass = `status-${agent.status || 'offline'}`;
    const displayName = agent.display_name || agent.hostname;
    const version = agent.agent_version || 'v1';
    const shortIp = agent.ip_address || '---';
    
    // Compact View for Grid
    if (isCompact) {
         return `
            <div class="device-card ${statusClass}" 
                 id="card-${agent.agent_id}" 
                 draggable="true" 
                 data-agent-id="${agent.agent_id}"
                 ondragstart="drag(event, '${agent.agent_id}')"
                 title="${escapeHtml(displayName)}">
                
                <div class="device-icon">
                    <i class="fas fa-desktop"></i>
                </div>
                
                <div class="device-info">
                    <span class="device-ip">${escapeHtml(shortIp)}</span>
                </div>
            </div>
        `;
    }

    // Larger View for Unassigned Pool
    return `
        <div class="device-card ${statusClass}" 
             id="card-${agent.agent_id}" 
             draggable="true" 
             style="width: 100px; height: 100px;" 
             data-agent-id="${agent.agent_id}"
             ondragstart="drag(event, '${agent.agent_id}')">
            
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
