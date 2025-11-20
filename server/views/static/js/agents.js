let agentsData = [];
let groupsData = [];
const agentLogs = {};
let currentDropTarget = null;

/**
 * Safely re-render the group board once both groups and agents are available.
 *
 * We fetch agents and groups independently (and often in parallel). When the
 * groups finish loading before the agents, the group board is rendered with an
 * empty agentsData array which results in zero counts until the user manually
 * refreshes.  Centralising this logic ensures we never render stale data.
 */
function refreshGroupBoardIfReady() {
    if (Array.isArray(groupsData) && groupsData.length > 0) {
        renderGroups();
    }
}

function getAgentId(agent) {
    return agent?.agent_id || agent?._id || agent?.id;
}

function normalizeAgentString(value) {
    return typeof value === 'string' ? value.trim() : '';
}

function getAgentDisplayName(agent) {
    if (!agent) return 'Unknown Agent';
    const displayName = normalizeAgentString(agent.display_name);
    const hostname = normalizeAgentString(agent.hostname);
    return displayName || hostname || agent.agent_id || 'Unknown Agent';
}

function getAgentHostname(agent) {
    return normalizeAgentString(agent?.hostname);
}

function shouldShowHostname(agent, displayName) {
    const hostname = getAgentHostname(agent);
    return Boolean(hostname) && hostname.toLowerCase() !== displayName.toLowerCase();
}

function buildAgentSearchValue(agent) {
    return [
        normalizeAgentString(agent?.display_name).toLowerCase(),
        normalizeAgentString(agent?.hostname).toLowerCase(),
        (agent?.agent_id || '').toLowerCase(),
        (agent?.device_id || '').toLowerCase()
    ].filter(Boolean).join(' ');
}

function formatAgentNameWithIp(agent) {
    const friendlyName = getAgentDisplayName(agent);
    if (agent?.ip_address) {
        return `${friendlyName} (${agent.ip_address})`;
    }
    return friendlyName;
}

/**
 * Parse timestamp with Vietnam timezone support
 */
function parseTimestampCorrectly(timestamp) {
    if (!timestamp) return null;
    
    try {
        if (timestamp instanceof Date) {
            return timestamp;
        }

        if (typeof timestamp === 'number') {
            return new Date(timestamp);
        } 
        const normalized = String(timestamp).trim();

        // If the timestamp already contains an explicit timezone indicator, let the Date
        // constructor handle the conversion (it always stores values as vietnam internally).
        if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) {
            return new Date(normalized);
        }

        // For naive ISO strings (no timezone info), treat them as vietnam explicitly.
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(normalized)) {
            return new Date(`${normalized}Z`);
        }

        return new Date(normalized);
        
    } catch (e) {
        console.error('Error parsing timestamp:', timestamp, e);
        return new Date(timestamp);
    }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString) {
    if (!isoString) return 'Never';
    
    try {
        const date = parseTimestampCorrectly(isoString);
        return date.toLocaleString();
    } catch (e) {
        console.error('Error parsing timestamp:', isoString, e);
        return 'Invalid Date';
    }
}

/**
 * Get status display info
 */
function getStatusInfo(status) {
    switch (status) {
        case 'active':
            return { class: 'active', text: 'Active', icon: 'check-circle' };
        case 'inactive':
            return { class: 'inactive', text: 'Inactive', icon: 'exclamation-triangle' };
        case 'offline':
            return { class: 'offline', text: 'Offline', icon: 'times-circle' };
        case 'pending':
            return { class: 'pending', text: 'Pending', icon: 'hourglass-half' };
        default:
            return { class: 'unknown', text: 'Unknown', icon: 'question-circle' };
        
    }
}

/**
 * Format OS information for display
 */
function formatOsInfo(agent) {
    const osInfo = agent.os_info || agent.platform;

    if (!osInfo) {
        return 'Unknown OS';
    }

    if (typeof osInfo === 'string') {
        return osInfo;
    }

    if (typeof osInfo === 'object') {
        const parts = [osInfo.name || osInfo.platform, osInfo.version, osInfo.arch];
        const formatted = parts.filter(Boolean).join(' · ');
        return formatted || 'Unknown OS';
    }

    return String(osInfo);
}

function getGroupName(groupId) {
    if (!groupId) return 'Pending';
    const group = groupsData.find(g => g._id === groupId);
    return group ? group.name : 'Pending';
}

/**
 * Get latest real-time log message for an agent
 */
function getLatestLog(agentId) {
    const log = agentLogs[agentId];
    if (!log) {
        return '<span class="text-muted">Đang chờ log real-time...</span>';
    }

    return `[${log.display_time || '---'}] ${log.message || 'N/A'}`;
}

function normalizeAgentLog(log) {
    if (!log) return null;

    const displayTime = log.display_time || formatTimestamp(log.timestamp);
    
    //  Extract domain from log
    let domain = log.domain || log.destination || 'N/A';
    
    // If domain is missing, try to extract from message
    if (domain === 'N/A' && log.message) {
        // Try patterns like "Domain: example.com" or "Blocked: example.com"
        const domainMatch = log.message.match(/(?:domain|destination|blocked|allowed)[:：\s]+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
        if (domainMatch) {
            domain = domainMatch[1];
        }
    }
    
    return {
        ...log,
        display_time: displayTime,
        source_ip: log.source_ip || log.src_ip || 'unknown',
        dest_ip: log.dest_ip || log.destination || 'unknown',
        domain: domain, //  Add extracted domain
        message: log.message || 'N/A'
    };
}

function renderAgentLogContent(agentId) {
    const log = normalizeAgentLog(agentLogs[agentId]);

    if (!log) {
        return `
            <div class="agent-log-empty">
                <i class="fas fa-clock me-2"></i>
                <span>Đang chờ log real-time...</span>
            </div>
        `;
    }

    const levelClass = (log.level || 'info').toLowerCase();
    const routeText = (log.source_ip && log.dest_ip)
        ? `${log.source_ip} → ${log.dest_ip}${log.port ? ':' + log.port : ''}`
        : '';

    return `
        <div class="agent-log-header">
            <div class="d-flex align-items-center gap-2">
                <i class="fas fa-stream text-primary"></i>
                <span class="fw-semibold">Last activity</span>
            </div>
            <div class="text-muted">
                <i class="fas fa-clock me-1"></i>${log.display_time || '---'}
            </div>
        </div>
        <div class="agent-log-body">
            <div class="d-flex align-items-center gap-2 mb-1">
                <span class="badge rounded-pill log-level ${levelClass}">${log.level || 'INFO'}</span>
                ${log.action ? `<span class="badge rounded-pill bg-light text-dark border action-badge">${log.action}</span>` : ''}
            </div>
            <div class="agent-log-message">
                <i class="fas fa-globe me-1"></i>
                <strong>${log.domain}</strong>
            </div>
            ${routeText ? `<div class="agent-log-meta text-muted"><i class="fas fa-location-arrow me-1"></i>${routeText}</div>` : ''}
        </div>
    `;
}

function updateAgentLogElement(agentId) {
    const logElement = document.getElementById(`agent-log-${agentId}`);
    if (logElement) {
        logElement.innerHTML = renderAgentLogContent(agentId);
    }
}

async function preloadLatestLogsForAgents(agentIds = []) {
    if (!agentIds.length) return;

    try {
        const limit = Math.min(Math.max(agentIds.length * 3, 50), 300);
        const response = await fetch(`/api/logs?limit=${limit}`);

        if (!response.ok) return;

        const data = await response.json();
        const latestByAgent = {};

        (data.logs || []).forEach((log) => {
            if (!log.agent_id) return;
            if (latestByAgent[log.agent_id]) return;
            latestByAgent[log.agent_id] = normalizeAgentLog(log);
        });

        Object.entries(latestByAgent).forEach(([agentId, log]) => {
            agentLogs[agentId] = log;
            updateAgentLogElement(agentId);
        });
    } catch (error) {
        console.error('Error preloading latest logs:', error);
    }
}

/**
 * Load agents from API
 */
async function loadAgents() {
    try {
        console.log(' Loading agents...');
        
        const [agentsResponse, statsResponse] = await Promise.all([
            fetch('/api/agents').catch(err => ({ ok: false, statusText: err.message })),
            fetch('/api/agents/statistics').catch(err => ({ ok: false, statusText: err.message }))
        ]);
        
        if (agentsResponse.ok) {
            const data = await agentsResponse.json();
            agentsData = data.agents || [];
            console.log(' Loaded agents:', agentsData);
            renderAgents(agentsData);
            await preloadLatestLogsForAgents(agentsData.map(agent => getAgentId(agent)).filter(Boolean));
        } else {
            console.error(' Failed to load agents:', agentsResponse.statusText);
            showError('Failed to load agents');
        }
        
        if (statsResponse.ok) {
            const statsData = await statsResponse.json();
            updateStatistics(statsData.data);
        } else {
            updateStatistics();
        }
    
    // Ensure the group board reflects the latest agent assignments/counts
        // even if the groups were fetched before the agents finished loading.
        refreshGroupBoardIfReady();

    } catch (error) {
        console.error(' Error loading agents:', error);
        showError('Error loading agents');
        updateStatistics();
    }
}

/**
 * Update statistics display
 */
function updateStatistics(stats = null) {
    const setCount = (elementId, value) => {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value ?? 0;
        }
    };

    if (stats) {
        setCount('totalAgentsCount', stats.total || 0);
        setCount('activeAgentsCount', stats.active || 0);
        setCount('inactiveAgentsCount', stats.inactive || 0);
        setCount('offlineAgentsCount', stats.offline || 0);
        setCount('pendingAgentsCount', stats.pending || 0);
    } else {
        // Calculate from current data
        const total = agentsData.length;
        const active = agentsData.filter(a => a.status === 'active').length;
        const inactive = agentsData.filter(a => a.status === 'inactive').length;
        const offline = agentsData.filter(a => a.status === 'offline').length;
        
        const pending = agentsData.filter(a => a.status === 'pending').length;

        setCount('totalAgentsCount', total);
        setCount('activeAgentsCount', active);
        setCount('inactiveAgentsCount', inactive);
        setCount('offlineAgentsCount', offline);
        setCount('pendingAgentsCount', pending);
    }
}

/**
 * Render agents list
 */
function renderAgents(agents) {
    const container = document.getElementById('agentsContainer');
    
    if (agents.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-laptop-code"></i>
                <h5 class="fw-bold">No Agents Registered</h5>
                <p>No agents have been registered yet. Install and run an agent on your target machines to get started.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = '';
    
    agents.forEach((agent, index) => {
        const agentId = getAgentId(agent);
        const statusInfo = getStatusInfo(agent.status);
        const lastSeen = formatTimestamp(agent.last_heartbeat);
        const registered = formatTimestamp(agent.registered_date);
        
        // Calculate time since last heartbeat
        let timeSince = '';
        if (agent.last_heartbeat) {
            const now = new Date();
            const lastHeartbeat = parseTimestampCorrectly(agent.last_heartbeat);
            const minutesSince = Math.round((now - lastHeartbeat) / (1000 * 60) * 10) / 10;
            timeSince = ` (${minutesSince}m ago)`;
        }
        
        const agentElement = document.createElement('div');
        agentElement.className = 'p-4 border-bottom agent-item draggable';
        const displayName = getAgentDisplayName(agent);
        const hostname = getAgentHostname(agent);
        const hostnameMeta = shouldShowHostname(agent, displayName)
            ? `<div class="agent-hostname text-muted"><i class="fas fa-desktop me-1"></i>${hostname}</div>`
            : '';

        agentElement.dataset.name = buildAgentSearchValue(agent);
        agentElement.dataset.ip = (agent.ip_address || '').toLowerCase();
        agentElement.dataset.status = agent.status || 'unknown';
        agentElement.dataset.groupId = agent.group_id || '';
        agentElement.dataset.id = agentId || '';
        agentElement.draggable = true;
        agentElement.addEventListener('dragstart', handleAgentDragStart);
        agentElement.addEventListener('dragend', handleAgentDragEnd);
        
        agentElement.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <div class="d-flex align-items-center">
                        <div class="me-3">
                            <i class="fas fa-desktop fa-2x text-primary"></i>
                        </div>
                        <div>
                            <h6 class="mb-2 fw-bold">
                                <i class="fas fa-server me-2"></i>
                                <span class="agent-display-name">${displayName}</span>
                            </h6>
                            ${hostnameMeta}
                            <div class="d-flex align-items-center mb-2 flex-wrap gap-2">
                                <span class="agent-status ${statusInfo.class}">
                                    <span class="pulse-indicator ${statusInfo.class}"></span>
                                    ${statusInfo.text}${timeSince}
                                </span>
                                <small class="text-muted">
                                    <i class="fas fa-network-wired me-1"></i>
                                    ${agent.ip_address || 'Unknown IP'}
                                </small>
                                <span class="badge bg-light text-dark border">
                                    <i class="fas fa-layer-group me-1"></i>${getGroupName(agent.group_id)}
                                </span>
                            </div>
                            <div class="row text-muted">
                                <div class="col-md-6">
                                    <small>
                                        <i class="fas fa-clock me-1"></i>
                                        Last seen: ${lastSeen}
                                    </small>
                                </div>
                                <div class="col-md-6">
                                    <small>
                                        <i class="fas fa-calendar me-1"></i>
                                        Registered: ${registered}
                                    </small>
                                </div>
                            </div>
                            <div class="row text-muted mt-2">
                                <div class="col-md-6">
                                    <small>
                                        <i class="fas fa-microchip me-1"></i>
                                        OS: ${formatOsInfo(agent)}
                                    </small>
                                </div>
                            </div>
                            ${agent.agent_version ? `
                                <div class="mt-1">
                                    <small class="text-muted">
                                        <i class="fas fa-code-branch me-1"></i>
                                        Version: ${agent.agent_version}
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="d-flex align-items-center justify-content-end gap-3">
                        <div class="agent-log-panel flex-grow-1" id="agent-log-${agentId}">
                            ${renderAgentLogContent(agentId)}
                        </div>
                        <div class="agent-actions d-flex align-items-center gap-2 flex-shrink-0">
                            <button type="button" class="btn btn-outline-secondary btn-action"
                                    data-action="edit-name"
                                    data-agent-id="${agentId}"
                                    onclick="editAgentDisplayName('${agentId}')"
                                    title="Edit Display Name">
                                <i class="fas fa-pen"></i>
                            </button>
                            <button type="button" class="btn btn-outline-primary btn-action"
                                    onclick="viewAgentLogs('${agentId}')"
                                    title="View Logs">
                                <i class="fas fa-file-alt"></i>
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-action"
                                    onclick="removeAgent('${agentId}')"
                                    title="Remove Agent">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(agentElement);
    });
}

function handleAgentDragStart(event) {
    const agentId = event.currentTarget.dataset.id;
    event.dataTransfer.setData('text/plain', agentId);
    event.dataTransfer.effectAllowed = 'move';
}

function handleAgentDragEnd() {
    if (currentDropTarget) {
        currentDropTarget.classList.remove('dropping');
        currentDropTarget = null;
    }
}

function handleGroupDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    const target = event.currentTarget;
    if (currentDropTarget && currentDropTarget !== target) {
        currentDropTarget.classList.remove('dropping');
    }
    target.classList.add('dropping');
    currentDropTarget = target;
}

function handleGroupDragLeave(event) {
    event.currentTarget.classList.remove('dropping');
}

function handleGroupDrop(event) {
    event.preventDefault();
    const groupId = event.currentTarget.dataset.groupId;
    const agentId = event.dataTransfer.getData('text/plain');
    event.currentTarget.classList.remove('dropping');
    currentDropTarget = null;

    if (groupId && agentId) {
        moveAgentToGroup(agentId, groupId);
    }
}

function renderGroups() {
    const board = document.getElementById('groupBoard');
    if (!board) return;

    if (!groupsData.length) {
        board.innerHTML = '<div class="text-muted">No groups found. Create one to get started.</div>';
        return;
    }

    board.innerHTML = '';

    groupsData.forEach(group => {
        const whitelistCount = (group.whitelist || []).length;
        
        //  Count agents in this group
        const agentsInGroup = agentsData.filter(a => a.group_id === group._id);
        const agentCount = agentsInGroup.length;
        
        const card = document.createElement('div');
        card.className = 'group-card';
        card.dataset.groupId = group._id;
        card.addEventListener('dragover', handleGroupDragOver);
        card.addEventListener('dragleave', handleGroupDragLeave);
        card.addEventListener('drop', handleGroupDrop);

        //  Render agents list
        const agentsListHtml = agentsInGroup.map(agent => {
            const statusInfo = getStatusInfo(agent.status);
            const displayName = getAgentDisplayName(agent);
            const hostname = getAgentHostname(agent);
            const hostnameHint = shouldShowHostname(agent, displayName)
                ? `<small class="agent-hostname-hint text-muted">${hostname}</small>`
                : '';
            return `
                <div class="group-agent-item" data-agent-id="${getAgentId(agent)}">
                    <div class="d-flex align-items-center gap-2 group-agent-identity">
                        <i class="fas fa-desktop text-primary" style="font-size: 0.9rem;"></i>
                        <div>
                            <span class="agent-name">${displayName}</span>
                            ${hostnameHint}
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <small class="text-muted">${agent.ip_address || 'N/A'}</small>
                        <span class="agent-status-dot ${statusInfo.class}" 
                              title="${statusInfo.text}"></span>
                    </div>
                </div>
            `;
        }).join('');

        card.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div class="group-name">
                    <i class="fas fa-layer-group text-primary"></i>
                    ${group.name}
                </div>
                <div class="group-actions">
                    ${group.is_system ? '' : `
                        <button class="btn btn-sm btn-outline-primary" data-action="edit" data-id="${group._id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${group._id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    `}
                </div>
            </div>
            <div class="group-meta">${group.description || 'No description'}</div>
            <div class="group-stats">
                <span class="badge bg-light text-dark border">
                    <i class="fas fa-shield-alt me-1"></i>Whitelist: ${whitelistCount}
                </span>
            </div>
            
            <!--  Agent count toggle -->
            <div class="group-agent-count" data-action="toggle-agents" data-group-id="${group._id}">
                <div class="d-flex align-items-center gap-2">
                    <i class="fas fa-users text-primary"></i>
                    <span class="fw-semibold">${agentCount} Agent${agentCount !== 1 ? 's' : ''}</span>
                </div>
                <i class="fas fa-chevron-down expand-icon text-muted"></i>
            </div>
            
            <!--  Agents list (collapsible) -->
            <div class="group-agents-list" id="agents-list-${group._id}">
                ${agentCount > 0 ? agentsListHtml : '<div class="text-muted text-center py-2"><small>No agents in this group</small></div>'}
            </div>
        `;

        board.appendChild(card);
    });

    //  Add event listeners for toggle
    board.querySelectorAll('[data-action="toggle-agents"]').forEach(toggle => {
        toggle.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent drag events
            const groupId = toggle.dataset.groupId;
            const agentsList = document.getElementById(`agents-list-${groupId}`);
            const groupCard = toggle.closest('.group-card');
            
            if (agentsList.classList.contains('expanded')) {
                agentsList.classList.remove('expanded');
                groupCard.classList.remove('expanded');
            } else {
                // Close all other expanded lists
                board.querySelectorAll('.group-agents-list.expanded').forEach(list => {
                    list.classList.remove('expanded');
                });
                board.querySelectorAll('.group-card.expanded').forEach(card => {
                    card.classList.remove('expanded');
                });
                
                // Expand this one
                agentsList.classList.add('expanded');
                groupCard.classList.add('expanded');
            }
        });
    });

    // Add click to view agent logs
    board.querySelectorAll('.group-agent-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            const agentId = item.dataset.agentId;
            viewAgentLogs(agentId);
        });
    });

    // Existing edit/delete event listeners
    board.querySelectorAll('button[data-action="edit"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openGroupModal(btn.dataset.id);
        });
    });

    board.querySelectorAll('button[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteGroup(btn.dataset.id);
        });
    });
}

/**
 * Filter agents based on search and status
 */
function filterAgents() {
    const searchTerm = document.getElementById('agent-search').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const agentItems = document.querySelectorAll('.agent-item');
    
    agentItems.forEach(item => {
        const name = (item.dataset.name || '').toLowerCase();
        const ip = (item.dataset.ip || '').toLowerCase();
        const status = item.dataset.status;
        
        const matchesSearch = name.includes(searchTerm) || ip.includes(searchTerm);
        const matchesStatus = !statusFilter || status === statusFilter;
        
        if (matchesSearch && matchesStatus) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

/**
 * Action functions
 */
function refreshAgents() {
    const button = event.target;
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Refreshing...';
    button.disabled = true;
    
    loadAgents().finally(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    });
}

async function moveAgentToGroup(agentId, groupId) {
    const resolvedAgentId = agentId || '';
    const resolvedGroupId = groupId || '';

    if (!resolvedAgentId || !resolvedGroupId) {
        showError('Invalid agent or group information');
        return;
    }

    try {
        // Show loading state
        const groupCard = document.querySelector(`[data-group-id="${resolvedGroupId}"]`);
        if (groupCard) {
            groupCard.style.opacity = '0.6';
            groupCard.style.pointerEvents = 'none';
        }

        const response = await fetch(`/api/agents/${resolvedAgentId}/group`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_id: resolvedGroupId })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok || result.success === false) {
            const errorMessage = result.error || result.message || 'Failed to move agent';
            throw new Error(errorMessage);
        }

        // Update local data immediately for instant UI feedback
        const agent = agentsData.find(a => getAgentId(a) === resolvedAgentId);
        if (agent) {
            agent.group_id = resolvedGroupId;
        }

        showSuccess(result.message || 'Agent moved to group');
        
         // Reload sequentially to avoid race conditions between the two datasets
        // (groups rely on the latest agents array to calculate counts correctly).
        await loadAgents();
        await loadGroups();
        
    } catch (error) {
        console.error('Error moving agent:', error);
        showError(error.message || 'Failed to move agent');
    } finally {
        // Remove loading state
        const groupCard = document.querySelector(`[data-group-id="${resolvedGroupId}"]`);
        if (groupCard) {
            groupCard.style.opacity = '1';
            groupCard.style.pointerEvents = 'auto';
        }
    }
}

async function loadGroups(skipAgentRerender = false) {
    try {
        console.log('Loading groups...');
        const response = await fetch('/api/groups');
        if (!response.ok) throw new Error('Failed to load groups');
        
        const data = await response.json();
        groupsData = data.data || [];
        
        console.log('Loaded groups:', groupsData.length);
        renderGroups();

        // Only re-render agents if explicitly needed (to update group badges)
        if (!skipAgentRerender && agentsData.length) {
            renderAgents(agentsData);
        }
    } catch (error) {
        console.error('Error loading groups:', error);
        const board = document.getElementById('groupBoard');
        if (board) {
            board.innerHTML = `<div class="text-danger">${error.message}</div>`;
        }
    }
}

function openGroupModal(groupId = null) {
    const modal = new bootstrap.Modal(document.getElementById('groupModal'));
    const title = document.getElementById('groupModalTitle');
    const nameInput = document.getElementById('groupNameInput');
    const descInput = document.getElementById('groupDescriptionInput');
    const idInput = document.getElementById('groupIdInput');

    if (groupId) {
        const group = groupsData.find(g => g._id === groupId);
        if (!group) return;
        title.textContent = 'Edit Group';
        nameInput.value = group.name || '';
        descInput.value = group.description || '';
        idInput.value = groupId;
    } else {
        title.textContent = 'Create Group';
        nameInput.value = '';
        descInput.value = '';
        idInput.value = '';
    }

    modal.show();
}

async function saveGroup() {
    const idInput = document.getElementById('groupIdInput');
    const nameInput = document.getElementById('groupNameInput');
    const descInput = document.getElementById('groupDescriptionInput');
    const payload = { name: nameInput.value.trim(), description: descInput.value.trim() };

    if (!payload.name) {
        showError('Group name is required');
        return;
    }

    const isEdit = Boolean(idInput.value);
    const url = isEdit ? `/api/groups/${idInput.value}` : '/api/groups';
    const method = isEdit ? 'PATCH' : 'POST';

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to save group');
        }

        bootstrap.Modal.getInstance(document.getElementById('groupModal')).hide();
        showSuccess(isEdit ? 'Group updated' : 'Group created');
        await loadGroups();
    } catch (error) {
        console.error('Error saving group:', error);
        showError(error.message || 'Failed to save group');
    }
}

async function deleteGroup(groupId) {
    const group = groupsData.find(g => g._id === groupId);
    if (!group) return;
    if (!confirm(`Delete group "${group.name}"?`)) return;

    try {
        const response = await fetch(`/api/groups/${groupId}`, { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to delete group');
        }

        showSuccess('Group deleted');
        await loadGroups();
        await loadAgents();
    } catch (error) {
        console.error('Error deleting group:', error);
        showError(error.message || 'Failed to delete group');
    }
}

function viewAgentLogs(agentId) {
    window.location.href = `/logs?agent_id=${agentId}`;
}

async function editAgentDisplayName(agentId) {
    const agent = agentsData.find(a => a.agent_id === agentId);
    if (!agent) {
        showError('Agent not found');
        return;
    }

    const currentDisplayName = normalizeAgentString(agent.display_name);
    const defaultValue = currentDisplayName || getAgentHostname(agent) || agentId;
    const newDisplayName = prompt(`Enter a new display name for ${agent.agent_id}:`, defaultValue);

    if (newDisplayName === null) {
        return; // User cancelled
    }

    const trimmedName = newDisplayName.trim();

    if (!trimmedName) {
        showError('Display name cannot be empty.');
        return;
    }

    if (trimmedName === currentDisplayName) {
        return;
    }

    const editButton = document.querySelector(`[data-action="edit-name"][data-agent-id="${agentId}"]`);
    if (editButton) {
        editButton.disabled = true;
        editButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }

    try {
        const response = await fetch(`/api/agents/${agentId}/display-name`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: trimmedName })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Failed to update display name');
        }

        agent.display_name = trimmedName;
        renderAgents(agentsData);
        showSuccess('Display name updated successfully');
    } catch (error) {
        console.error('Error updating display name:', error);
        showError(error.message || 'Failed to update display name');

        if (editButton) {
            editButton.disabled = false;
            editButton.innerHTML = '<i class="fas fa-pen"></i>';
        }
    }
}

async function removeAgent(agentId) {
    const agent = agentsData.find(a => a.agent_id === agentId);
    const agentName = agent ? formatAgentNameWithIp(agent) : agentId;
    
    if (!confirm(`Are you sure you want to remove agent "${agentName}"?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    const deleteButton = document.querySelector(`[onclick="removeAgent('${agentId}')"]`);
    if (deleteButton) {
        deleteButton.disabled = true;
        deleteButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }
    
    try {
        showNotification('info', `Removing agent ${agentName}...`);
        
        const response = await fetch(`/api/agents/${agentId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('success', `Agent ${agentName} removed successfully`);
            
            // Remove from local data
            const agentIndex = agentsData.findIndex(a => a.agent_id === agentId);
            if (agentIndex !== -1) {
                agentsData.splice(agentIndex, 1);
            }
            
            // Re-render agents list
            renderAgents(agentsData);
            updateStatistics();
        } else {
            throw new Error(data.error || 'Failed to remove agent');
        }
        
    } catch (error) {
        console.error('Error removing agent:', error);
        showNotification('danger', `Failed to remove agent: ${error.message}`);
        
        if (deleteButton) {
            deleteButton.disabled = false;
            deleteButton.innerHTML = '<i class="fas fa-trash"></i>';
        }
    }
}

/**
 * Show notification
 */
function showNotification(type, message) {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    const container = document.querySelector('.toast-container') || createToastContainer();
    container.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

function showError(message) {
    showNotification('danger', message);
}

function showSuccess(message) {
    showNotification('success', message);
}

/**
 * Quick update group agent count without full reload (faster)
 */
function updateGroupAgentCount(groupId) {
    const agentsInGroup = agentsData.filter(a => a.group_id === groupId);
    const agentCount = agentsInGroup.length;
    
    const countElement = document.querySelector(`[data-group-id="${groupId}"] .group-agent-count .fw-semibold`);
    if (countElement) {
        countElement.textContent = `${agentCount} Agent${agentCount !== 1 ? 's' : ''}`;
    }
    
    // Update agents list
    const agentsList = document.getElementById(`agents-list-${groupId}`);
    if (agentsList) {
        if (agentCount > 0) {
            const agentsListHtml = agentsInGroup.map(agent => {
                const statusInfo = getStatusInfo(agent.status);
                const displayName = getAgentDisplayName(agent);
                const hostname = getAgentHostname(agent);
                const hostnameHint = shouldShowHostname(agent, displayName)
                    ? `<small class="agent-hostname-hint text-muted">${hostname}</small>`
                    : '';
                return `
                    <div class="group-agent-item" data-agent-id="${getAgentId(agent)}">
                        <div class="d-flex align-items-center gap-2 group-agent-identity">
                            <i class="fas fa-desktop text-primary" style="font-size: 0.9rem;"></i>
                            <div>
                                <span class="agent-name">${displayName}</span>
                                ${hostnameHint}
                            </div>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <small class="text-muted">${agent.ip_address || 'N/A'}</small>
                            <span class="agent-status-dot ${statusInfo.class}" 
                                  title="${statusInfo.text}"></span>
                        </div>
                    </div>
                `;
            }).join('');
            agentsList.innerHTML = agentsListHtml;
            
            // Re-attach click events
            agentsList.querySelectorAll('.group-agent-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const agentId = item.dataset.agentId;
                    viewAgentLogs(agentId);
                });
            });
        } else {
            agentsList.innerHTML = '<div class="text-muted text-center py-2"><small>No agents in this group</small></div>';
        }
    }
}

/**
 * Update all group counts (when global status changes)
 */
function updateAllGroupCounts() {
    const uniqueGroupIds = [...new Set(agentsData.map(a => a.group_id).filter(Boolean))];
    uniqueGroupIds.forEach(groupId => {
        updateGroupAgentCount(groupId);
    });
}

/**
 * Periodic check for offline agents (every 30 seconds)
 */
function startPeriodicStatusCheck() {
    setInterval(async () => {
        console.log('Checking agent status...');
        
        try {
            const response = await fetch('/api/agents/statistics');
            if (response.ok) {
                const data = await response.json();
                const stats = data.data;
                
                // Check if stats changed significantly
                const currentStats = {
                    active: agentsData.filter(a => a.status === 'active').length,
                    inactive: agentsData.filter(a => a.status === 'inactive').length,
                    offline: agentsData.filter(a => a.status === 'offline').length
                };
                
                const hasChanges = 
                    stats.active !== currentStats.active ||
                    stats.inactive !== currentStats.inactive ||
                    stats.offline !== currentStats.offline;
                
                if (hasChanges) {
                    console.log('Status changed, reloading agents...');
                    await loadAgents();
                    updateAllGroupCounts();
                }
            }
        } catch (error) {
            console.error('Error checking status:', error);
        }
    }, 30000); // Every 30 seconds
}

// Add to DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Agents page initialized');
    loadAgents();
    loadGroups();
    
    // Setup search and filter
    const searchInput = document.getElementById('agent-search');
    const statusFilter = document.getElementById('status-filter');
    
    if (searchInput) {
        searchInput.addEventListener('input', filterAgents);
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', filterAgents);
    }
    
    const createGroupBtn = document.getElementById('createGroupBtn');
    if (createGroupBtn) {
        createGroupBtn.addEventListener('click', () => openGroupModal());
    }

    const refreshGroupsBtn = document.getElementById('refreshGroupsBtn');
    if (refreshGroupsBtn) {
        refreshGroupsBtn.addEventListener('click', loadGroups);
    }

    const saveGroupBtn = document.getElementById('saveGroupBtn');
    if (saveGroupBtn) {
        saveGroupBtn.addEventListener('click', saveGroup);
    }

    // Setup Socket.IO for real-time updates
    if (typeof io !== 'undefined') {
        const socket = io();
        
        // CRITICAL: Listen for heartbeat to update status
        socket.on('agent_heartbeat', (data) => {
            console.log('Agent heartbeat received:', data);
            
            // Update local agent data
            const agent = agentsData.find(a => getAgentId(a) === data.agent_id);
            if (agent) {
                const oldGroupId = agent.group_id;
                const oldStatus = agent.status;
                
                // Update agent fields
                agent.status = data.status || 'active';
                agent.last_heartbeat = data.last_heartbeat;
                agent.time_since_heartbeat = data.time_since_heartbeat;
                agent.metrics = data.metrics;
                
                console.log(`${getAgentDisplayName(agent)}: ${oldStatus} → ${agent.status}`);
                
                // Re-render agent row
                renderAgents(agentsData);
                
                // Update group count if status changed
                if (oldGroupId) {
                    updateGroupAgentCount(oldGroupId);
                }
                
                // Update statistics
                updateStatistics();
            } else {
                // New agent - reload everything
                console.log('New agent detected, reloading...');
                loadAgents();
                loadGroups();
            }
        });
        
        // Listen for agent updates (registration, deletion)
        socket.on('agent_update', (data) => {
            console.log('Agent update received:', data);
            loadAgents();
        });
        
        // Listen for agent group changes
        socket.on('agent_group_updated', (data) => {
            console.log('Agent group updated:', data);
            
            // Update local data
            const agent = agentsData.find(a => getAgentId(a) === data.agent_id);
            if (agent) {
                const oldGroupId = agent.group_id;
                agent.group_id = data.group_id;
                agent.status = data.status;
                
                // Update both old and new group counts
                if (oldGroupId) {
                    updateGroupAgentCount(oldGroupId);
                }
                if (data.group_id) {
                    updateGroupAgentCount(data.group_id);
                }
            }
            
            // Re-render agents list
            renderAgents(agentsData);
        });
        
        // Listen for agent registration
        socket.on('agent_registered', (data) => {
            console.log('Agent registered:', data);
            loadAgents();
            loadGroups(); // Reload groups to update pending count
        });
        
        // Listen for agent deletion
        socket.on('agent_deleted', (data) => {
            console.log('Agent deleted:', data);
            
            // Remove from local data
            const index = agentsData.findIndex(a => getAgentId(a) === data.agent_id);
            if (index !== -1) {
                const deletedAgent = agentsData[index];
                agentsData.splice(index, 1);
                
                // Update group count
                if (deletedAgent.group_id) {
                    updateGroupAgentCount(deletedAgent.group_id);
                }
                
                // Re-render
                renderAgents(agentsData);
                updateStatistics();
            }
        });
        
        // Listen for new logs
        socket.on('new_log', (logData) => {
            console.log('New log received:', logData);
            if (logData.agent_id) {
                agentLogs[logData.agent_id] = normalizeAgentLog(logData);
                updateAgentLogElement(logData.agent_id);
            }
        });
        
        socket.on('connect', () => {
            console.log('Socket.IO connected');
            // Reload data on reconnect
            loadAgents();
            loadGroups();
        });
        
        socket.on('disconnect', () => {
            console.log('Socket.IO disconnected');
        });
        
        socket.on('error', (error) => {
            console.error('Socket.IO error:', error);
        });
    } else {
        console.warn('Socket.IO not available - real-time updates disabled');
    }
    
    // Start periodic check
    startPeriodicStatusCheck();
});