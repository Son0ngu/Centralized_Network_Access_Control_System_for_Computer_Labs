/**
 * profile.js — page logic for /profile.
 *
 * Extracted from the inline ``<script>`` block in profile.html. The page now
 * just includes this file in ``extra_js``; the template is markup only.
 *
 * Depends on shared core modules loaded by base.html:
 *   - SaintAPI (api.js)  — fetch wrapper
 *   - SaintDate          — date formatting
 *
 * The local ``showAlert`` helper stays page-local because it targets DOM
 * nodes specific to this template (``#profileAlert``, ``#passwordAlert``).
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', async function () {
    const profileAlert = document.getElementById('profileAlert');
    const passwordAlert = document.getElementById('passwordAlert');

    function showAlert(alertEl, msg, isSuccess) {
      // Inline alert box (not a toast) because the alert sits next to the
      // form it relates to and persists for 5s. Keep this local.
      alertEl.className = `alert alert-${isSuccess ? 'success' : 'danger'}`;
      alertEl.innerHTML = `<i class="fas fa-${isSuccess ? 'check-circle' : 'exclamation-circle'} me-2"></i>${msg}`;
      alertEl.classList.remove('d-none');
      setTimeout(() => alertEl.classList.add('d-none'), 5000);
    }

    // Load profile data
    try {
      const data = await SaintAPI.get('/api/admin/auth/me');
      if (data && data.success && data.data) {
        const user = data.data;
        document.getElementById('profileUsername').value = user.username || '';
        document.getElementById('profileRole').value = user.role || '';
        document.getElementById('profileEmail').value = user.email || '';
        document.getElementById('profileCreatedAt').value =
          user.created_at ? SaintDate.formatVN(user.created_at) : 'N/A';

        document.getElementById('heroUsername').textContent = user.username || '';
        const badge = document.getElementById('heroRoleBadge');
        badge.textContent = user.role || '';
        if (user.role === 'admin') {
          badge.classList.add('role-admin');
        } else if (user.role === 'teacher') {
          badge.classList.add('role-teacher');
        }
        if (user.last_login) {
          document.getElementById('heroLastLogin').innerHTML =
            '<i class="fas fa-clock me-1"></i>Last login: ' + SaintDate.formatVN(user.last_login);
        }
      }
    } catch (err) {
      console.error('Error loading profile:', err);
    }

    // Update profile (email)
    document.getElementById('profileForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      const btn = document.getElementById('updateBtn');
      const orgText = btn.innerHTML;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving...';
      btn.disabled = true;
      profileAlert.classList.add('d-none');

      try {
        const data = await SaintAPI.put('/api/admin/auth/profile', {
          email: document.getElementById('profileEmail').value.trim(),
        });
        showAlert(profileAlert, data.message || 'Profile updated successfully', true);
      } catch (err) {
        // SaintAPIError exposes parsed body — surface the server's error string.
        const msg = (err && err.body && err.body.error) || err.message || 'Profile update failed';
        showAlert(profileAlert, msg, false);
      } finally {
        btn.innerHTML = orgText;
        btn.disabled = false;
      }
    });

    // Password strength indicator
    document.getElementById('newPassword').addEventListener('input', function () {
      const pw = this.value;
      const bar = document.getElementById('strengthBar');
      const text = document.getElementById('strengthText');
      let strength = 0;
      if (pw.length >= 8) strength++;
      if (pw.length >= 12) strength++;
      if (/[A-Z]/.test(pw)) strength++;
      if (/[0-9]/.test(pw)) strength++;
      if (/[^A-Za-z0-9]/.test(pw)) strength++;

      const levels = [
        { width: '0%',   color: '#dc3545', label: '' },
        { width: '20%',  color: '#dc3545', label: 'Very weak' },
        { width: '40%',  color: '#ffc107', label: 'Weak' },
        { width: '60%',  color: '#fd7e14', label: 'Medium' },
        { width: '80%',  color: '#20c997', label: 'Strong' },
        { width: '100%', color: '#28a745', label: 'Very strong' },
      ];
      const level = levels[strength] || levels[0];
      bar.style.width = level.width;
      bar.style.background = level.color;
      text.textContent = pw.length > 0 ? level.label : '';
    });

    // Change password
    document.getElementById('changePasswordForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      passwordAlert.classList.add('d-none');

      const oldPw = document.getElementById('oldPassword').value;
      const newPw = document.getElementById('newPassword').value;
      const confirmPw = document.getElementById('confirmPassword').value;

      if (!oldPw || !newPw || !confirmPw) {
        showAlert(passwordAlert, 'Please fill in all fields', false);
        return;
      }
      if (newPw.length < 8) {
        showAlert(passwordAlert, 'New password must be at least 8 characters', false);
        return;
      }
      if (newPw !== confirmPw) {
        showAlert(passwordAlert, 'Passwords do not match', false);
        return;
      }

      const btn = document.getElementById('changeBtn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';

      try {
        await SaintAPI.put('/api/admin/auth/change-password', {
          old_password: oldPw,
          new_password: newPw,
        });
        showAlert(passwordAlert, 'Password changed successfully!', true);
        this.reset();
        document.getElementById('strengthBar').style.width = '0%';
        document.getElementById('strengthText').textContent = '';
      } catch (err) {
        const msg = (err && err.body && err.body.error) || err.message || 'Password change failed';
        showAlert(passwordAlert, msg, false);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt me-2"></i>Change Password';
      }
    });
  });
})();
