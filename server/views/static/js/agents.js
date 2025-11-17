let agentsData = [];
const agentLogs = {};
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
    
    // ✅ Extract domain from log
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
        domain: domain, // ✅ Add extracted domain
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
            await preloadLatestLogsForAgents(agentsData.map(agent => agent.agent_id).filter(Boolean));
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
        agentElement.className = 'p-4 border-bottom agent-item';
        agentElement.dataset.name = (agent.hostname || '').toLowerCase();
        agentElement.dataset.ip = agent.ip_address || '';
        agentElement.dataset.status = agent.status || 'unknown';
        
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
                                ${agent.hostname || 'Unknown Host'}
                            </h6>
                            <div class="d-flex align-items-center mb-2">
                                <span class="agent-status ${statusInfo.class}">
                                    <span class="pulse-indicator ${statusInfo.class}"></span>
                                    ${statusInfo.text}${timeSince}
                                </span>
                                <small class="ms-3 text-muted">
                                    <i class="fas fa-network-wired me-1"></i>
                                    ${agent.ip_address || 'Unknown IP'}
                                </small>
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
                        <div class="agent-log-panel flex-grow-1" id="agent-log-${agent.agent_id}">
                            ${renderAgentLogContent(agent.agent_id)}
                        </div>
                        <div class="btn-group btn-group-sm flex-shrink-0" role="group">
                            <button type="button" class="btn btn-outline-primary btn-action"
                                    onclick="viewAgentLogs('${agent.agent_id}')" 
                                    title="View Logs">
                                <i class="fas fa-file-alt"></i>
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-action" 
                                    onclick="removeAgent('${agent.agent_id}')" 
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

/**
 * Filter agents based on search and status
 */
function filterAgents() {
    const searchTerm = document.getElementById('agent-search').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const agentItems = document.querySelectorAll('.agent-item');
    
    agentItems.forEach(item => {
        const name = item.dataset.name;
        const ip = item.dataset.ip;
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

function viewAgentLogs(agentId) {
    window.location.href = `/logs?agent_id=${agentId}`;
}

async function pingAgent(agentId) {
    const agent = agentsData.find(a => a.agent_id === agentId);
    const agentName = agent ? `${agent.hostname} (${agent.ip_address})` : agentId;
    
    const pingButton = document.querySelector(`[onclick="pingAgent('${agentId}')"]`);
    if (pingButton) {
        pingButton.disabled = true;
        pingButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    }
    
    try {
        showNotification('info', `Pinging agent ${agentName}...`);
        
        const response = await fetch(`/api/agents/${agentId}/ping`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const responseTime = data.data.response_time;
            showNotification('success', ` Ping successful! Response time: ${responseTime}s`);
            
            // Update agent status
            if (agent) {
                agent.status = 'active';
                renderAgents(agentsData);
                updateStatistics();
            }
        } else {
            showNotification('danger', ` Ping failed: ${data.error}`);
        }
        
    } catch (error) {
        console.error('Error pinging agent:', error);
        showNotification('danger', `Failed to ping agent: ${error.message}`);
    } finally {
        if (pingButton) {
            pingButton.disabled = false;
            pingButton.innerHTML = '<i class="fas fa-wifi"></i>';
        }
    }
}

async function removeAgent(agentId) {
    const agent = agentsData.find(a => a.agent_id === agentId);
    const agentName = agent ? `${agent.hostname} (${agent.ip_address})` : agentId;
    
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

/**
 * Initialize page
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log(' Agents page initialized');
    loadAgents();
    
    // Setup search and filter
    const searchInput = document.getElementById('agent-search');
    const statusFilter = document.getElementById('status-filter');
    
    if (searchInput) {
        searchInput.addEventListener('input', filterAgents);
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', filterAgents);
    }
    
    // Setup Socket.IO for real-time updates
    if (typeof io !== 'undefined') {
        const socket = io();
        
        socket.on('agent_update', (data) => {
            console.log(' Agent update received:', data);
            loadAgents();
        });
        
        socket.on('new_log', (logData) => {
            console.log(' New log received:', logData);
            if (logData.agent_id) {
                agentLogs[logData.agent_id] = normalizeAgentLog(logData);
                updateAgentLogElement(logData.agent_id);
            }
        });
        
        socket.on('connect', () => {
            console.log(' Socket.IO connected');
        });
        
        socket.on('disconnect', () => {
            console.log(' Socket.IO disconnected');
        });
    }
});