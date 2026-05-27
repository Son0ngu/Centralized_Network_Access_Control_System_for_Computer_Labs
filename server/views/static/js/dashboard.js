(function () {
    // Simple connection test
    try {
        const socket = io();

        socket.on('connect', function () {
            SaintLog.debug('Connected to server for real-time updates');

            const statusDot = document.querySelector('.pulse-dot');
            if (statusDot) {
                statusDot.style.background = '#28a745';
            }
        });

        socket.on('disconnect', function () {
            SaintLog.debug('Disconnected from server');

            const statusDot = document.querySelector('.pulse-dot');
            if (statusDot) {
                statusDot.style.background = '#dc3545';
            }
        });

        socket.on('stats_update', function (statsData) {
            SaintLog.debug('Stats update received:', statsData);
            updateDashboardStats(statsData, true);
        });
    } catch (error) {
        SaintLog.debug('Socket.IO not available:', error);
    }

    function getStatElements() {
        return {
            totalLogs: document.getElementById('statTotalLogs'),
            allowed: document.getElementById('statAllowed'),
            blocked: document.getElementById('statBlocked'),
            activeAgents: document.getElementById('statActiveAgents'),
        };
    }

    function updateDashboardStats(stats, animate) {
        const els = getStatElements();

        if (els.totalLogs && stats.total_logs !== undefined) {
            setStatValue(els.totalLogs, stats.total_logs, animate);
        }
        if (els.allowed && stats.allowed_count !== undefined) {
            setStatValue(els.allowed, stats.allowed_count, animate);
        }
        if (els.blocked && stats.blocked_count !== undefined) {
            setStatValue(els.blocked, stats.blocked_count, animate);
        }
        if (els.activeAgents && stats.active_agents !== undefined) {
            setStatValue(els.activeAgents, stats.active_agents, animate);
        }
    }

    function setStatValue(element, value, animate) {
        if (animate) {
            const start = parseInt(element.textContent.replace(/,/g, ''), 10) || 0;
            if (start !== value) {
                animateNumber(element, start, value);
            }
        } else {
            element.textContent = value.toLocaleString();
        }
    }

    function animateNumber(element, start, end) {
        const duration = 1000;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            const current = Math.floor(start + (end - start) * progress);
            element.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    // Load initial statistics
    async function loadDashboardStats(animate) {
        try {
            try {
                const data = await SaintAPI.get('/api/logs/stats');
                if (data.success) {
                    // Use filtered stats when server applies RBAC filtering (teacher)
                    const useFiltered = data.has_filters;
                    updateDashboardStats({
                        total_logs: useFiltered ? (data.filtered_total || 0) : (data.total || 0),
                        allowed_count: useFiltered ? (data.filtered_allowed || 0) : (data.allowed || 0),
                        blocked_count: useFiltered ? (data.filtered_blocked || 0) : (data.blocked || 0),
                        active_agents: 0
                    }, animate);
                }
            } catch (e) {
                // Non-fatal — keep loading agent stats below.
            }

            // Load active agents count
            try {
                const agentsData = await SaintAPI.get('/api/agents/statistics');
                if (agentsData.success && agentsData.data) {
                    const el = document.getElementById('statActiveAgents');
                    if (el) {
                        setStatValue(el, agentsData.data.active || 0, animate);
                    }
                }
            } catch (e) {
                // Non-fatal.
            }
        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }

    setInterval(function () {
        location.reload();
    }, 30000);

    document.addEventListener('DOMContentLoaded', function () {
        // Load initial stats (no animation - just set values directly)
        loadDashboardStats(false);

        // Animate cards
        const cards = document.querySelectorAll('.status-card, .feature-card');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';

            setTimeout(() => {
                card.style.transition = 'all 0.6s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });

        // Refresh stats every 10 seconds (with animation for incremental updates)
        setInterval(function () { loadDashboardStats(true); }, 10000);
    });
})();
