/**
 * login.js — page logic for /login.
 *
 * Extracted from the inline ``<script>`` in login.html.
 *
 * The page is reached *before* any session exists so it can't depend on the
 * full admin SaintAPI surface (auth cookie isn't set yet). Direct fetch is
 * fine here — we explicitly include credentials so the server can set the
 * httpOnly access_token cookie on the response.
 */

async function handleLogin(event) {
  event.preventDefault();

  const btn = document.getElementById('loginBtn');
  const errorDiv = document.getElementById('loginError');
  const errorMsg = document.getElementById('errorMessage');

  // Show loading
  btn.classList.add('loading');
  btn.disabled = true;
  errorDiv.classList.remove('show');

  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  try {
    const response = await fetch('/api/admin/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (data.success) {
      // Cookies are set by server (httpOnly); redirect to dashboard.
      window.location.href = '/';
    } else {
      errorMsg.textContent = data.error || 'Login failed';
      errorDiv.classList.add('show');
    }
  } catch (err) {
    errorMsg.textContent = 'Connection error. Please try again.';
    errorDiv.classList.add('show');
  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }

  return false;
}

// Focus username on load
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('username').focus();
});
