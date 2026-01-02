/**
 * System Broadcast Handler
 * -----------------------
 * Client-side component for displaying and managing system broadcasts.
 * Shows alerts from Super Admin to Tenant Admins.
 */

const BroadcastHandler = {
    config: null,
    broadcasts: [],
    container: null,
    refreshInterval: null,
    socket: null,
    initialized: false,

    /**
     * Initialize the broadcast handler
     */
    async init() {
        if (this.initialized) return;
        
        // Create container for broadcasts
        this.createContainer();
        
        // Load configuration
        await this.loadConfig();
        
        // Load active broadcasts
        await this.loadBroadcasts();
        
        // Setup auto-refresh
        this.setupAutoRefresh();
        
        // Setup WebSocket if available
        this.setupWebSocket();
        
        this.initialized = true;
        console.log('[Broadcast] Handler initialized');
    },

    /**
     * Create the broadcast container element
     */
    createContainer() {
        // Check if container already exists
        if (document.getElementById('broadcast-container')) {
            this.container = document.getElementById('broadcast-container');
            return;
        }
        
        this.container = document.createElement('div');
        this.container.id = 'broadcast-container';
        this.container.className = 'broadcast-container';
        this.container.setAttribute('role', 'alert');
        this.container.setAttribute('aria-live', 'polite');
        
        // Insert at the top of main content or after navbar
        const mainContent = document.querySelector('main') || 
                           document.querySelector('.main-content') ||
                           document.querySelector('.container-fluid');
        
        if (mainContent) {
            mainContent.insertBefore(this.container, mainContent.firstChild);
        } else {
            // Fallback: insert after body's first child
            document.body.insertBefore(this.container, document.body.firstChild.nextSibling);
        }
    },

    /**
     * Load broadcast configuration from server
     */
    async loadConfig() {
        try {
            const response = await fetch('/api/broadcasts/config', {
                headers: {
                    'Authorization': 'Bearer ' + this.getToken()
                }
            });
            
            const data = await response.json();
            if (data.success) {
                this.config = data.data;
            } else {
                // Use defaults
                this.config = {
                    types: {
                        info: { bgClass: 'alert-info', icon: 'fa-info-circle', dismissible: true },
                        warning: { bgClass: 'alert-warning', icon: 'fa-exclamation-triangle', dismissible: true },
                        danger: { bgClass: 'alert-danger', icon: 'fa-exclamation-circle', dismissible: false }
                    },
                    display: {
                        maxVisible: 3,
                        autoRefreshInterval: 60000,
                        animationDuration: 300
                    }
                };
            }
        } catch (error) {
            console.error('[Broadcast] Error loading config:', error);
        }
    },

    /**
     * Load active broadcasts from server
     */
    async loadBroadcasts() {
        try {
            const response = await fetch('/api/broadcasts/active', {
                headers: {
                    'Authorization': 'Bearer ' + this.getToken()
                }
            });
            
            const data = await response.json();
            if (data.success) {
                this.broadcasts = data.data.broadcasts || [];
                this.render();
            }
        } catch (error) {
            console.error('[Broadcast] Error loading broadcasts:', error);
        }
    },

    /**
     * Render broadcasts to the container
     */
    render() {
        if (!this.container) return;
        
        // Clear existing broadcasts
        this.container.innerHTML = '';
        
        if (this.broadcasts.length === 0) {
            this.container.style.display = 'none';
            return;
        }
        
        this.container.style.display = 'block';
        
        // Render each broadcast
        this.broadcasts.forEach(broadcast => {
            const element = this.createBroadcastElement(broadcast);
            this.container.appendChild(element);
        });
    },

    /**
     * Create HTML element for a single broadcast
     */
    createBroadcastElement(broadcast) {
        const typeConfig = broadcast.type_config || this.config?.types?.[broadcast.type] || {
            bgClass: 'alert-info',
            icon: 'fa-info-circle'
        };
        
        const div = document.createElement('div');
        div.className = `system-broadcast alert ${typeConfig.bg_class || typeConfig.bgClass} alert-dismissible fade show`;
        div.setAttribute('data-broadcast-id', broadcast.id);
        div.setAttribute('role', 'alert');
        
        // Build content
        let html = `
            <div class="broadcast-content">
                <div class="broadcast-header">
                    <i class="fas ${typeConfig.icon} me-2"></i>
                    <strong>${this.escapeHtml(broadcast.title)}</strong>
                </div>
                <div class="broadcast-message">
                    ${this.escapeHtml(broadcast.message)}
                </div>
        `;
        
        // Add timestamp if available
        if (broadcast.created_at) {
            const date = new Date(broadcast.created_at);
            html += `
                <div class="broadcast-meta text-muted small mt-1">
                    <i class="fas fa-clock me-1"></i>
                    ${date.toLocaleDateString()} ${date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </div>
            `;
        }
        
        html += '</div>';
        
        // Add dismiss button if dismissible
        if (broadcast.is_dismissible) {
            html += `
                <button type="button" class="btn-close" aria-label="Dismiss" 
                        onclick="BroadcastHandler.dismiss('${broadcast.id}')"></button>
            `;
        }
        
        div.innerHTML = html;
        return div;
    },

    /**
     * Dismiss a broadcast
     */
    async dismiss(broadcastId) {
        try {
            const response = await fetch(`/api/broadcasts/${broadcastId}/dismiss`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer ' + this.getToken(),
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Animate removal
                const element = this.container.querySelector(`[data-broadcast-id="${broadcastId}"]`);
                if (element) {
                    element.classList.remove('show');
                    setTimeout(() => {
                        element.remove();
                        
                        // Remove from local array
                        this.broadcasts = this.broadcasts.filter(b => b.id !== broadcastId);
                        
                        // Hide container if no more broadcasts
                        if (this.broadcasts.length === 0) {
                            this.container.style.display = 'none';
                        }
                    }, this.config?.display?.animationDuration || 300);
                }
            } else {
                console.error('[Broadcast] Failed to dismiss:', data.error);
            }
        } catch (error) {
            console.error('[Broadcast] Error dismissing broadcast:', error);
        }
    },

    /**
     * Setup auto-refresh interval
     */
    setupAutoRefresh() {
        const interval = this.config?.display?.autoRefreshInterval || 60000;
        
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        this.refreshInterval = setInterval(() => {
            this.loadBroadcasts();
        }, interval);
    },

    /**
     * Setup WebSocket for real-time updates
     */
    setupWebSocket() {
        // Check if Socket.IO is available
        if (typeof io === 'undefined') {
            console.log('[Broadcast] Socket.IO not available, using polling');
            return;
        }
        
        try {
            // Connect to admin namespace
            this.socket = io('/admin', {
                auth: {
                    token: this.getToken()
                }
            });
            
            this.socket.on('connect', () => {
                console.log('[Broadcast] WebSocket connected');
            });
            
            this.socket.on('broadcast_update', (event) => {
                this.handleBroadcastEvent(event);
            });
            
            this.socket.on('disconnect', () => {
                console.log('[Broadcast] WebSocket disconnected');
            });
            
            this.socket.on('error', (error) => {
                console.error('[Broadcast] WebSocket error:', error);
            });
            
        } catch (error) {
            console.error('[Broadcast] Error setting up WebSocket:', error);
        }
    },

    /**
     * Handle real-time broadcast events
     */
    handleBroadcastEvent(event) {
        console.log('[Broadcast] Received event:', event.type);
        
        switch (event.type) {
            case 'new_broadcast':
                // Add new broadcast to the list
                this.broadcasts.unshift(event.data);
                
                // Trim to max visible
                const maxVisible = this.config?.display?.maxVisible || 3;
                if (this.broadcasts.length > maxVisible) {
                    this.broadcasts = this.broadcasts.slice(0, maxVisible);
                }
                
                this.render();
                
                // Show notification
                this.showNotification(event.data);
                break;
                
            case 'update_broadcast':
                // Update existing broadcast
                const index = this.broadcasts.findIndex(b => b.id === event.data.id);
                if (index >= 0) {
                    this.broadcasts[index] = event.data;
                    this.render();
                }
                break;
                
            case 'remove_broadcast':
                // Remove broadcast
                this.broadcasts = this.broadcasts.filter(b => b.id !== event.data.id);
                this.render();
                break;
        }
    },

    /**
     * Show browser notification for new broadcast
     */
    showNotification(broadcast) {
        // Check if notifications are supported and permitted
        if (!('Notification' in window)) return;
        
        if (Notification.permission === 'granted') {
            new Notification('System Broadcast', {
                body: broadcast.title,
                icon: '/static/img/logo.png'
            });
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission();
        }
    },

    /**
     * Get JWT token from storage
     */
    getToken() {
        return localStorage.getItem('jwt_token') || 
               sessionStorage.getItem('jwt_token') || '';
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Cleanup handler
     */
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        if (this.socket) {
            this.socket.disconnect();
        }
        
        if (this.container) {
            this.container.remove();
        }
        
        this.initialized = false;
    }
};

// Add CSS styles
const broadcastStyles = document.createElement('style');
broadcastStyles.textContent = `
    .broadcast-container {
        position: relative;
        z-index: 1040;
        margin-bottom: 1rem;
    }
    
    .system-broadcast {
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        animation: slideDown 0.3s ease-out;
    }
    
    .system-broadcast:last-child {
        margin-bottom: 0;
    }
    
    .system-broadcast .broadcast-header {
        font-size: 1rem;
        margin-bottom: 0.25rem;
    }
    
    .system-broadcast .broadcast-message {
        font-size: 0.9rem;
    }
    
    .system-broadcast .broadcast-meta {
        font-size: 0.75rem;
    }
    
    .system-broadcast.alert-danger {
        border-left: 4px solid #dc3545;
    }
    
    .system-broadcast.alert-warning {
        border-left: 4px solid #ffc107;
    }
    
    .system-broadcast.alert-info {
        border-left: 4px solid #17a2b8;
    }
    
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(broadcastStyles);

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize for tenant admins, not on super admin pages
    const isSuperAdminPage = window.location.pathname.startsWith('/super-admin');
    
    if (!isSuperAdminPage) {
        // Delay initialization to ensure token is available
        setTimeout(() => {
            if (BroadcastHandler.getToken()) {
                BroadcastHandler.init();
            }
        }, 500);
    }
});

// Export for global access
window.BroadcastHandler = BroadcastHandler;
