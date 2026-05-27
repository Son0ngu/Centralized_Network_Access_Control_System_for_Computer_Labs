const { test, expect } = require('@playwright/test');

const adminUsername = process.env.E2E_ADMIN_USERNAME || 'admin';
const adminPassword = process.env.E2E_ADMIN_PASSWORD || 'admin123456';

function attachRuntimeErrorCollector(page) {
  const errors = [];
  page.on('pageerror', (error) => {
    errors.push(error.message || String(error));
  });
  return errors;
}

async function login(page) {
  await page.goto('/login');
  await expect(page.locator('#loginForm')).toBeVisible();

  await page.fill('#username', adminUsername);
  await page.fill('#password', adminPassword);

  const responsePromise = page.waitForResponse((response) => (
    response.url().includes('/api/admin/auth/login')
    && response.request().method() === 'POST'
  ));
  await page.click('#loginBtn');
  const response = await responsePromise;
  let body = null;
  try {
    body = await response.json();
  } catch (_) {
    body = null;
  }

  if (!response.ok() || (body && body.success === false)) {
    const detail = body && (body.error || body.message)
      ? `: ${body.error || body.message}`
      : '';
    throw new Error(
      `E2E login failed for "${adminUsername}" with HTTP ${response.status()}${detail}. ` +
      'Set E2E_ADMIN_USERNAME/E2E_ADMIN_PASSWORD if your local admin is different.'
    );
  }

  await page.waitForURL('**/', { timeout: 15000 });
  await expect(page.locator('#userMenuDropdown')).toBeVisible({ timeout: 15000 });
  await page.waitForFunction(() => window.SAINT_AUTH && window.SAINT_AUTH.isLoggedIn === true);
}

async function expectSaintCoreLoaded(page) {
  const missing = await page.evaluate(() => (
    ['SaintAPI', 'SaintToast', 'SaintDate', 'SaintLog', 'SaintUtils']
      .filter((name) => typeof window[name] === 'undefined')
  ));
  expect(missing).toEqual([]);
}

test.describe('SAINT admin browser smoke', () => {
  test('login loads dashboard with shared JS core', async ({ page }) => {
    const errors = attachRuntimeErrorCollector(page);

    await login(page);
    await expectSaintCoreLoaded(page);
    await expect(page.locator('body')).toBeVisible();
    await expect(page.locator('nav')).toContainText('Firewall Controller');

    expect(errors).toEqual([]);
  });

  test('admin pages render after SaintAPI migration', async ({ page }) => {
    const errors = attachRuntimeErrorCollector(page);
    const paths = [
      '/',
      '/agents',
      '/groups',
      '/whitelist',
      '/logs',
      '/api-keys',
      '/admin/users',
      '/admin/audit',
      '/profile',
    ];

    await login(page);

    for (const path of paths) {
      await page.goto(path);
      await expect(page.locator('body')).toBeVisible();
      await expectSaintCoreLoaded(page);
      await expect(page).not.toHaveURL(/\/login$/);
    }

    expect(errors).toEqual([]);
  });

  test('profile change-password button is visible without hover', async ({ page }) => {
    const errors = attachRuntimeErrorCollector(page);

    await login(page);
    await page.goto('/profile');

    const button = page.locator('#changeBtn');
    await expect(button).toBeVisible();
    await expect(button).toContainText('Change Password');

    const style = await button.evaluate((element) => {
      const computed = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
        borderColor: computed.borderColor,
        width: rect.width,
        height: rect.height,
      };
    });

    expect(style.color).not.toBe('rgb(255, 255, 255)');
    expect(style.backgroundColor).not.toBe('rgb(255, 255, 255)');
    expect(style.borderColor).not.toBe('rgb(255, 255, 255)');
    expect(style.width).toBeGreaterThan(120);
    expect(style.height).toBeGreaterThan(32);
    expect(errors).toEqual([]);
  });

  test('SaintAPI sends CSRF token for unsafe admin requests', async ({ page }) => {
    const errors = attachRuntimeErrorCollector(page);

    await login(page);
    await expectSaintCoreLoaded(page);

    const result = await page.evaluate(async () => {
      const csrfToken = window.SaintAPI.getCsrfToken();
      try {
        const response = await window.SaintAPI.post('/api/api-keys/validate', {
          api_key: 'invalid-e2e-smoke-key',
        });
        return {
          ok: true,
          csrfPresent: Boolean(csrfToken),
          response,
        };
      } catch (error) {
        return {
          ok: false,
          csrfPresent: Boolean(csrfToken),
          status: error.status,
          body: error.body,
          message: error.message,
        };
      }
    });

    expect(result.csrfPresent).toBe(true);
    expect(result.ok).toBe(true);
    expect(result.response.success).toBe(true);
    expect(result.response.valid).toBe(false);
    expect(errors).toEqual([]);
  });
});
