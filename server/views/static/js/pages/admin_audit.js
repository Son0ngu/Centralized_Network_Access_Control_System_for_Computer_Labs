/**
 * admin_audit.js — page logic for /admin/audit.
 *
 * Extracted from the inline ``<script>`` block in admin_audit.html.
 *
 * Depends on shared core modules loaded by base.html:
 *   - SaintAPI   — fetch wrapper
 *   - SaintDate  — date formatting
 *
 * The previous inline copy carried its own ``formatDate`` (mm/dd/yyyy locale
 * string with HH:mm:ss) and its own ``escHtml``. Date formatting now comes
 * from SaintDate.formatVNFull; ``escHtml`` stays page-local since the audit
 * table builds non-trivial HTML strings and inlining the escape was the
 * cleanest way to keep cells safe.
 */

(function () {
  'use strict';
  const API = '/api/admin/audit';
  const PAGE_SIZE = 50;
  let currentPage = 0;
  let totalLogs = 0;

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.initCustomSelect === 'function') {
      window.initCustomSelect('filterAction');
      window.initCustomSelect('filterResource');
    }
    loadLogs();
    bindEvents();
  });

  async function loadLogs() {
    const params = new URLSearchParams();
    const username = document.getElementById('filterUsername').value.trim();
    const action = document.getElementById('filterAction').value;
    const resource = document.getElementById('filterResource').value;
    if (username) params.set('username', username);
    if (action) params.set('action', action);
    if (resource) params.set('resource_type', resource);
    params.set('limit', PAGE_SIZE);
    params.set('skip', currentPage * PAGE_SIZE);

    try {
      const data = await SaintAPI.get(`${API}?${params}`);
      if (data && data.success) {
        totalLogs = data.data.total || 0;
        renderTable(data.data.logs || []);
        renderPagination();
      }
    } catch (err) {
      console.error('Load audit logs error:', err);
    }
  }

  function renderTable(logs) {
    const tbody = document.getElementById('auditTableBody');
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No audit logs found</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map((l) => {
      const actionCategory = (l.action || '').split('.')[0];
      const badgeClass = {
        auth: 'action-auth', user: 'action-user', group: 'action-group',
        whitelist: 'action-whitelist', profile: 'action-profile',
      }[actionCategory] || 'action-other';
      const details = l.details && Object.keys(l.details).length > 0
        ? `<small class="text-muted"><div class="text-truncate" style="max-width: 200px;" title="${escHtml(JSON.stringify(l.details))}">${escHtml(JSON.stringify(l.details).substring(0, 80))}</div></small>`
        : '-';
      return `<tr class="audit-row align-middle text-nowrap">
        <td><small>${SaintDate.formatVNFull(l.timestamp)}</small></td>
        <td><strong>${escHtml(l.username)}</strong></td>
        <td class="d-none d-md-table-cell"><span class="badge bg-${l.role === 'admin' ? 'danger' : 'success'} badge-sm">${l.role}</span></td>
        <td><span class="action-badge ${badgeClass}">${escHtml(l.action)}</span></td>
        <td class="d-none d-md-table-cell">${escHtml(l.resource_type || '-')} ${l.resource_id ? '/ <small>' + escHtml(l.resource_id.substring(0, 8)) + '</small>' : ''}</td>
        <td>${details}</td>
        <td class="d-none d-lg-table-cell"><small class="text-muted">${escHtml(l.ip_address || '-')}</small></td>
      </tr>`;
    }).join('');
  }

  function renderPagination() {
    const totalPages = Math.ceil(totalLogs / PAGE_SIZE);
    const info = document.getElementById('paginationInfo');
    const nav = document.getElementById('paginationNav');
    const start = currentPage * PAGE_SIZE + 1;
    const end = Math.min((currentPage + 1) * PAGE_SIZE, totalLogs);
    info.textContent = totalLogs > 0 ? `Showing ${start}-${end} of ${totalLogs} logs` : 'No logs found';
    if (totalPages <= 1) { nav.innerHTML = ''; return; }
    let html = `<li class="page-item ${currentPage === 0 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${currentPage - 1}">&laquo;</a></li>`;
    for (let i = Math.max(0, currentPage - 2); i < Math.min(totalPages, currentPage + 3); i++) {
      html += `<li class="page-item ${i === currentPage ? 'active' : ''}">
            <a class="page-link" href="#" data-page="${i}">${i + 1}</a></li>`;
    }
    html += `<li class="page-item ${currentPage >= totalPages - 1 ? 'disabled' : ''}">
        <a class="page-link" href="#" data-page="${currentPage + 1}">&raquo;</a></li>`;
    nav.innerHTML = html;
    nav.querySelectorAll('.page-link').forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = parseInt(e.target.dataset.page, 10);
        if (page >= 0 && page < totalPages) { currentPage = page; loadLogs(); }
      });
    });
  }

  function bindEvents() {
    document.getElementById('filterBtn').addEventListener('click', () => { currentPage = 0; loadLogs(); });
    document.getElementById('refreshBtn').addEventListener('click', () => loadLogs());
    document.getElementById('clearFilterBtn').addEventListener('click', () => {
      document.getElementById('filterUsername').value = '';
      document.getElementById('filterAction').value = '';
      document.getElementById('filterResource').value = '';
      currentPage = 0; loadLogs();
    });
    document.getElementById('filterUsername').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { currentPage = 0; loadLogs(); }
    });
  }

  const escHtml = (value) => window.SaintUtils.escapeHtml(value);
})();
