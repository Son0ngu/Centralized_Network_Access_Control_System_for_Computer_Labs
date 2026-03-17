/* Base UI helpers extracted from base.html */
(function () {
    // Enhanced notification system using Bootstrap toasts
    window.showNotification = function (type, message, duration = 5000) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer || typeof bootstrap === 'undefined') {
            console.warn('Toast container or Bootstrap not available');
            return;
        }

        const toastId = 'toast-' + Date.now();
        const icons = {
            success: 'fas fa-check-circle',
            danger: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle',
            primary: 'fas fa-bell'
        };

        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="${icons[type] || icons.info} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);

        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: duration });
        toast.show();

        toastElement.addEventListener('hidden.bs.toast', function () {
            toastElement.remove();
        });
    };

    window.showLoading = function (element) {
        if (element) {
            element.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
            element.disabled = true;
        }
    };

    window.hideLoading = function (element, originalText) {
        if (element) {
            element.innerHTML = originalText;
            element.disabled = false;
        }
    };

    window.addEventListener('error', function (e) {
        console.error('Global error:', e.error || e.message);
        showNotification('danger', 'An unexpected error occurred. Please refresh the page.');
    });

    document.addEventListener('DOMContentLoaded', function () {
        document.body.style.opacity = '0';
        document.body.style.transition = 'opacity 0.3s ease';

        setTimeout(() => {
            document.body.style.opacity = '1';
        }, 100);
    });

    // --- Custom Select Logic ---
    const customSelects = new Map();

    window.initCustomSelect = function(selectId) {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        // Check if already initialized
        if (select.parentNode.classList.contains('custom-select-wrapper')) {
            window.updateCustomOptions(selectId); // Just update options if exists
            return; 
        }

        // Wrap select
        const wrapper = document.createElement('div');
        wrapper.className = 'custom-select-wrapper';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        // Create trigger
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        trigger.tabIndex = 0; // Make focusable
        trigger.innerHTML = `<span class="selection">${select.options[select.selectedIndex]?.text || 'Select...'}</span>`;
        wrapper.appendChild(trigger);

        // Create options container
        const optionsDiv = document.createElement('div');
        optionsDiv.className = 'custom-options';
        wrapper.appendChild(optionsDiv);
        
        // Function to populate/update options
        const populateOptions = () => {
            optionsDiv.innerHTML = '';
            Array.from(select.options).forEach(option => {
                const div = document.createElement('div');
                div.className = `custom-option ${option.selected ? 'selected' : ''}`;
                div.dataset.value = option.value;
                div.textContent = option.text;
                
                div.addEventListener('click', (e) => {
                    e.stopPropagation();
                    select.value = option.value;
                    select.dispatchEvent(new Event('change')); // Trigger native change
                    
                    // Update UI
                    trigger.querySelector('.selection').textContent = option.text;
                    optionsDiv.querySelectorAll('.custom-option').forEach(el => el.classList.remove('selected'));
                    div.classList.add('selected');
                    optionsDiv.classList.remove('open');
                });
                
                optionsDiv.appendChild(div);
            });
        };

        // Initial populate
        populateOptions();
        
        // Store update function for later use
        customSelects.set(selectId, populateOptions);

        // Toggle dropdown
        trigger.addEventListener('click', (e) => {
            // Close others
            document.querySelectorAll('.custom-options').forEach(el => {
                if (el !== optionsDiv) el.classList.remove('open');
            });
            optionsDiv.classList.toggle('open');
        });
        
        // Handle click outside to close
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                optionsDiv.classList.remove('open');
            }
        });
    };

    window.updateCustomOptions = function(selectId) {
        if (customSelects.has(selectId)) {
            customSelects.get(selectId)();
            
            // Also update trigger text to match new selected value
            const select = document.getElementById(selectId);
            const trigger = select.nextElementSibling; // .custom-select-trigger
            if (trigger) {
                const selectedOption = select.options[select.selectedIndex];
                if (selectedOption) {
                    trigger.querySelector('.selection').textContent = selectedOption.text;
                }
            }
        }
    };
})();

// ========================================
// USER SESSION — fetch current user info & logout
// ========================================
(function() {
    // Fetch current user info for navbar
    fetch('/api/admin/auth/me', { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.user) {
                const u = data.user;
                const nameEl = document.getElementById('navUsername');
                const roleEl = document.getElementById('navUserRole');
                if (nameEl) nameEl.textContent = u.username || 'User';
                if (roleEl) roleEl.textContent = 'Role: ' + (u.role || 'unknown');
            }
        })
        .catch(() => {});

    // Logout function
    window.doLogout = function() {
        fetch('/api/admin/auth/logout', {
            method: 'POST',
            credentials: 'same-origin',
        })
        .then(() => { window.location.href = '/login'; })
        .catch(() => { window.location.href = '/login'; });
    };
})();