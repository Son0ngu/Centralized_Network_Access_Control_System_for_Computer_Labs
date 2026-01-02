/**
 * Impersonation Banner and Handler
 * ---------------------------------
 * Shows a warning banner during impersonation and handles exit.
 */

(function() {
    'use strict';

    // Configuration
    const IMPERSONATION_STORAGE_KEY = 'impersonation_token';
    const ORIGINAL_TOKEN_KEY = 'original_token';
    const SESSION_KEY = 'impersonation_session_id';
    
    // Banner HTML
    const bannerHTML = `
        <div id="impersonation-banner" class="impersonation-banner">
            <div class="impersonation-banner-content">
                <div class="impersonation-warning">
                    <i class="fas fa-user-secret"></i>
                    <span class="impersonation-label">IMPERSONATION MODE</span>
                </div>
                <div class="impersonation-info">
                    <span>Viewing as: <strong id="impersonation-tenant-name">Unknown Tenant</strong></span>
                    <span class="separator">|</span>
                    <span>Session: <code id="impersonation-session-id"></code></span>
                    <span class="separator">|</span>
                    <span class="impersonation-timer">
                        <i class="fas fa-clock"></i>
                        <span id="impersonation-time-remaining">--:--</span>
                    </span>
                </div>
                <button class="btn btn-sm btn-danger impersonation-exit-btn" onclick="ImpersonationHandler.exit()">
                    <i class="fas fa-sign-out-alt me-1"></i>
                    Exit Impersonation
                </button>
            </div>
            <div class="impersonation-warning-text">
                <i class="fas fa-exclamation-triangle"></i>
                All actions are being logged for audit purposes
            </div>
        </div>
    `;

    // Banner CSS (injected if not present)
    const bannerCSS = `
        .impersonation-banner {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(220, 53, 69, 0.4);
            animation: impersonation-pulse 2s infinite;
        }

        @keyframes impersonation-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.9; }
        }

        .impersonation-banner-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 20px;
            flex-wrap: wrap;
            gap: 10px;
        }

        .impersonation-warning {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
            font-size: 1.1rem;
        }

        .impersonation-warning i {
            font-size: 1.5rem;
        }

        .impersonation-label {
            background: rgba(0, 0, 0, 0.2);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.85rem;
            letter-spacing: 1px;
        }

        .impersonation-info {
            display: flex;
            align-items: center;
            gap: 15px;
            font-size: 0.9rem;
        }

        .impersonation-info .separator {
            opacity: 0.5;
        }

        .impersonation-timer {
            background: rgba(0, 0, 0, 0.2);
            padding: 4px 10px;
            border-radius: 4px;
        }

        .impersonation-exit-btn {
            font-weight: 600;
            padding: 8px 20px;
            border: 2px solid white;
            background: transparent;
            transition: all 0.2s;
        }

        .impersonation-exit-btn:hover {
            background: white;
            color: #dc3545;
        }

        .impersonation-warning-text {
            background: rgba(0, 0, 0, 0.15);
            padding: 6px 20px;
            text-align: center;
            font-size: 0.85rem;
        }

        /* Adjust body padding when banner is shown */
        body.impersonating {
            padding-top: 100px !important;
        }

        /* Action restriction overlay */
        .impersonation-restricted {
            position: relative;
        }

        .impersonation-restricted::after {
            content: "Action restricted during impersonation";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(220, 53, 69, 0.9);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            z-index: 1000;
        }

        @media (max-width: 768px) {
            .impersonation-banner-content {
                flex-direction: column;
                text-align: center;
            }

            .impersonation-info {
                flex-direction: column;
                gap: 5px;
            }

            .impersonation-info .separator {
                display: none;
            }
        }
    `;

    // Impersonation Handler
    window.ImpersonationHandler = {
        isActive: false,
        sessionData: null,
        timerInterval: null,
        expiresAt: null,

        /**
         * Initialize impersonation handler
         */
        init: function() {
            // Check if impersonating
            const impersonationToken = localStorage.getItem(IMPERSONATION_STORAGE_KEY);
            const sessionId = localStorage.getItem(SESSION_KEY);
            
            if (impersonationToken && sessionId) {
                this.isActive = true;
                this.injectStyles();
                this.showBanner();
                this.startTimer();
                this.markRestrictedActions();
            }
        },

        /**
         * Start impersonation (called from super admin dashboard)
         */
        start: function(token, sessionId, tenantName, expiresAt) {
            // Save original token
            const currentToken = localStorage.getItem('jwt_token');
            if (currentToken && currentToken !== token) {
                localStorage.setItem(ORIGINAL_TOKEN_KEY, currentToken);
            }
            
            // Set impersonation token
            localStorage.setItem('jwt_token', token);
            localStorage.setItem(IMPERSONATION_STORAGE_KEY, token);
            localStorage.setItem(SESSION_KEY, sessionId);
            localStorage.setItem('impersonation_tenant_name', tenantName);
            localStorage.setItem('impersonation_expires_at', expiresAt);
            
            // Redirect to tenant dashboard
            window.location.href = '/dashboard';
        },

        /**
         * Exit impersonation
         */
        exit: async function() {
            if (!this.isActive) return;
            
            try {
                const sessionId = localStorage.getItem(SESSION_KEY);
                
                // Call API to end impersonation
                const response = await fetch('/api/super/end-impersonation', {
                    method: 'POST',
                    headers: {
                        'Authorization': 'Bearer ' + localStorage.getItem('jwt_token'),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ session_id: sessionId })
                });

                // Clear impersonation data regardless of API result
                this.clearImpersonation();
                
                // Redirect back to super admin dashboard
                window.location.href = '/super-admin/';
            } catch (error) {
                console.error('Error ending impersonation:', error);
                
                // Still clear and redirect even on error
                this.clearImpersonation();
                window.location.href = '/super-admin/';
            }
        },

        /**
         * Clear all impersonation data
         */
        clearImpersonation: function() {
            // Restore original token
            const originalToken = localStorage.getItem(ORIGINAL_TOKEN_KEY);
            if (originalToken) {
                localStorage.setItem('jwt_token', originalToken);
            }
            
            // Clear impersonation storage
            localStorage.removeItem(IMPERSONATION_STORAGE_KEY);
            localStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(ORIGINAL_TOKEN_KEY);
            localStorage.removeItem('impersonation_tenant_name');
            localStorage.removeItem('impersonation_expires_at');
            
            // Stop timer
            if (this.timerInterval) {
                clearInterval(this.timerInterval);
            }
            
            // Remove banner
            const banner = document.getElementById('impersonation-banner');
            if (banner) {
                banner.remove();
            }
            
            document.body.classList.remove('impersonating');
            this.isActive = false;
        },

        /**
         * Inject CSS styles
         */
        injectStyles: function() {
            if (document.getElementById('impersonation-styles')) return;
            
            const style = document.createElement('style');
            style.id = 'impersonation-styles';
            style.textContent = bannerCSS;
            document.head.appendChild(style);
        },

        /**
         * Show impersonation banner
         */
        showBanner: function() {
            if (document.getElementById('impersonation-banner')) return;
            
            document.body.insertAdjacentHTML('afterbegin', bannerHTML);
            document.body.classList.add('impersonating');
            
            // Set tenant name
            const tenantName = localStorage.getItem('impersonation_tenant_name') || 'Unknown Tenant';
            document.getElementById('impersonation-tenant-name').textContent = tenantName;
            
            // Set session ID (shortened)
            const sessionId = localStorage.getItem(SESSION_KEY);
            if (sessionId) {
                document.getElementById('impersonation-session-id').textContent = 
                    sessionId.substring(0, 8) + '...';
            }
        },

        /**
         * Start countdown timer
         */
        startTimer: function() {
            const expiresAtStr = localStorage.getItem('impersonation_expires_at');
            if (!expiresAtStr) return;
            
            this.expiresAt = new Date(expiresAtStr);
            
            const updateTimer = () => {
                const now = new Date();
                const remaining = this.expiresAt - now;
                
                if (remaining <= 0) {
                    // Session expired
                    clearInterval(this.timerInterval);
                    this.handleExpired();
                    return;
                }
                
                const hours = Math.floor(remaining / 3600000);
                const minutes = Math.floor((remaining % 3600000) / 60000);
                const seconds = Math.floor((remaining % 60000) / 1000);
                
                let timeStr;
                if (hours > 0) {
                    timeStr = `${hours}h ${minutes}m`;
                } else if (minutes > 0) {
                    timeStr = `${minutes}m ${seconds}s`;
                } else {
                    timeStr = `${seconds}s`;
                }
                
                const timerEl = document.getElementById('impersonation-time-remaining');
                if (timerEl) {
                    timerEl.textContent = timeStr;
                    
                    // Flash warning when time is low
                    if (remaining < 300000) { // Less than 5 minutes
                        timerEl.style.color = '#ffeb3b';
                        timerEl.style.fontWeight = 'bold';
                    }
                }
            };
            
            updateTimer();
            this.timerInterval = setInterval(updateTimer, 1000);
        },

        /**
         * Handle session expiration
         */
        handleExpired: function() {
            alert('Your impersonation session has expired. You will be redirected to the Super Admin dashboard.');
            this.clearImpersonation();
            window.location.href = '/super-admin/';
        },

        /**
         * Mark restricted action buttons
         */
        markRestrictedActions: function() {
            // List of selectors for restricted actions
            const restrictedSelectors = [
                '[data-action="delete"]',
                '.btn-delete',
                '.delete-btn',
                '[data-action="create-api-key"]',
                '[data-action="update-admin"]',
                '.admin-delete',
            ];
            
            restrictedSelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    el.classList.add('impersonation-restricted');
                    el.disabled = true;
                    el.title = 'Action restricted during impersonation';
                });
            });
        },

        /**
         * Check if current token is impersonation
         */
        isImpersonating: function() {
            return this.isActive;
        }
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ImpersonationHandler.init());
    } else {
        ImpersonationHandler.init();
    }

})();
