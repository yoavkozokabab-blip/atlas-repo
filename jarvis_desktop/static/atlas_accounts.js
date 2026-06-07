/**
 * atlas_accounts.js — Atlas Accounts UI
 *
 * Manages the account screen (login / register / profile / blocked),
 * license gating of core workflows, and the account status chip.
 *
 * Depends only on the local server (/api/accounts/*) — no external calls.
 */
(function () {
  'use strict';

  // ─── State ────────────────────────────────────────────────────────────────
  let _state = null;           // last known account state
  let _screenMode = 'login';   // 'login' | 'register' | 'profile' | 'blocked'
  let _pollTimer = null;

  const POLL_INTERVAL_MS    = 60_000;   // check license every 60 s when idle
  const REFRESH_AFTER_LOGIN = 2_000;    // re-poll 2 s after login

  // ─── Helpers ──────────────────────────────────────────────────────────────

  function api(method, path, body) {
    return fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }).then(r => r.json()).catch(() => ({ ok: false, error: 'Network error' }));
  }

  function el(id) { return document.getElementById(id); }

  function setError(containerId, msg) {
    const c = el(containerId);
    if (!c) return;
    c.textContent = msg || '';
    c.style.display = msg ? 'block' : 'none';
  }

  function setLoading(btnId, loading) {
    const b = el(btnId);
    if (!b) return;
    b.disabled = loading;
    b.dataset.origText = b.dataset.origText || b.textContent;
    b.textContent = loading ? 'Please wait…' : b.dataset.origText;
  }

  // ─── Screen routing ───────────────────────────────────────────────────────

  function showAccountScreen(mode) {
    _screenMode = mode || _screenMode;

    // Hide all sub-panels
    ['acc-panel-login', 'acc-panel-register', 'acc-panel-profile', 'acc-panel-blocked']
      .forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });

    const panel = el('acc-panel-' + _screenMode);
    if (panel) panel.style.display = '';

    // Navigate to the accounts view
    if (typeof go === 'function') go('accounts');
  }

  function openAccountScreen() {
    refreshState().then(() => {
      if (!_state) { showAccountScreen('login'); return; }
      if (_state.authenticated) {
        const status = (_state.license && _state.license.status) || '';
        if (status === 'suspended' || status === 'banned') {
          showAccountScreen('blocked');
        } else {
          showAccountScreen('profile');
        }
      } else {
        showAccountScreen('login');
      }
    });
  }

  window.openAccountScreen = openAccountScreen;
  window.showAccPanel = showAccountScreen;

  // ─── API calls ────────────────────────────────────────────────────────────

  function refreshState() {
    return api('GET', '/api/accounts/state').then(data => {
      _state = data;
      _updateAccountChip();
      _applyLicenseGating();
      return data;
    });
  }

  function doLogin() {
    const email    = el('acc-login-email') && el('acc-login-email').value.trim();
    const password = el('acc-login-pwd')   && el('acc-login-pwd').value;
    setError('acc-login-error', '');
    if (!email || !password) { setError('acc-login-error', 'Email and password are required.'); return; }

    setLoading('acc-login-btn', true);
    api('POST', '/api/accounts/login', { email, password }).then(res => {
      setLoading('acc-login-btn', false);
      if (res.ok) {
        if (el('acc-login-pwd')) el('acc-login-pwd').value = '';
        setTimeout(() => refreshState().then(() => showAccountScreen('profile')), 300);
      } else {
        setError('acc-login-error', res.error || 'Login failed.');
      }
    });
  }

  function doRegister() {
    const email    = el('acc-reg-email')  && el('acc-reg-email').value.trim();
    const password = el('acc-reg-pwd')    && el('acc-reg-pwd').value;
    const confirm  = el('acc-reg-pwd2')   && el('acc-reg-pwd2').value;
    setError('acc-reg-error', '');

    if (!email || !password) { setError('acc-reg-error', 'Email and password are required.'); return; }
    if (password.length < 8) { setError('acc-reg-error', 'Password must be at least 8 characters.'); return; }
    if (password !== confirm) { setError('acc-reg-error', 'Passwords do not match.'); return; }

    setLoading('acc-reg-btn', true);
    api('POST', '/api/accounts/register', { email, password }).then(res => {
      setLoading('acc-reg-btn', false);
      if (res.ok) {
        if (el('acc-reg-pwd'))  el('acc-reg-pwd').value  = '';
        if (el('acc-reg-pwd2')) el('acc-reg-pwd2').value = '';
        setTimeout(() => refreshState().then(() => showAccountScreen('profile')), 300);
      } else {
        setError('acc-reg-error', res.error || 'Registration failed.');
      }
    });
  }

  function doLogout() {
    api('POST', '/api/accounts/logout').then(() => {
      _state = null;
      _updateAccountChip();
      _applyLicenseGating();
      showAccountScreen('login');
    });
  }

  function doRemoveDevice(deviceId) {
    if (!confirm('Remove this device? It will be signed out automatically.')) return;
    api('POST', '/api/accounts/devices/remove', { device_id: deviceId })
      .then(() => _renderDeviceList());
  }

  function _renderDeviceList() {
    const container = el('acc-device-list');
    if (!container) return;
    api('GET', '/api/accounts/devices').then(res => {
      const devices = res.devices || (Array.isArray(res) ? res : []);
      if (!devices.length) {
        container.innerHTML = '<p class="muted tiny">No devices found.</p>';
        return;
      }
      container.innerHTML = devices.map(d => `
        <div class="acc-device-row">
          <div>
            <span class="acc-device-name">${_escHtml(d.device_id.substring(0, 8) + '…')}</span>
            <span class="muted tiny"> — ${_escHtml(d.platform || 'unknown')} · v${_escHtml(d.app_version || '?')}</span>
            ${d.status === 'revoked' ? '<span class="acc-badge revoked">Revoked</span>' : ''}
          </div>
          ${d.status !== 'revoked' ? `<button class="btn ghost small" onclick="atlasAccounts.removeDevice('${_escHtml(d.device_id)}')">Remove</button>` : ''}
        </div>
      `).join('');
    });
  }

  function _escHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // ─── License gating ───────────────────────────────────────────────────────

  function _applyLicenseGating() {
    const authenticated = _state && _state.authenticated;
    const licenseValid  = _state && _state.license && _state.license.valid;
    const licStatus     = (_state && _state.license && _state.license.status) || '';
    const blocked       = licStatus === 'suspended' || licStatus === 'banned';

    // Locked nav items — require a valid license
    document.querySelectorAll('[data-lock="1"]').forEach(btn => {
      btn.disabled = !licenseValid && !blocked;
      btn.title = (!licenseValid && !blocked)
        ? 'Sign in to unlock — free for beta users'
        : (btn.dataset.origTitle || '');
    });

    // Show/hide account chip badge
    _updateAccountChip();
  }

  // ─── Account chip in topbar ───────────────────────────────────────────────

  function _updateAccountChip() {
    const chip = el('accountChip');
    if (!chip) return;

    if (!_state || !_state.authenticated) {
      chip.textContent = 'Sign in';
      chip.className = 'account-chip unsigned';
      return;
    }

    const user    = _state.user || {};
    const license = _state.license || {};
    const email   = user.email || '';
    const plan    = license.plan || 'free';
    const offline = license._offline ? ' (offline)' : '';

    chip.textContent = `${email.split('@')[0]} · ${plan}${offline}`;
    chip.className = 'account-chip signed-in' + (license._offline ? ' offline' : '');
  }

  // ─── Profile panel population ─────────────────────────────────────────────

  function _populateProfile() {
    if (!_state || !_state.authenticated) return;
    const user    = _state.user    || {};
    const license = _state.license || {};

    const emailEl = el('acc-profile-email');
    if (emailEl) emailEl.textContent = user.email || '—';

    const planEl = el('acc-profile-plan');
    if (planEl) planEl.textContent = license.plan || 'free';

    const statusEl = el('acc-profile-status');
    if (statusEl) statusEl.textContent = license.status || '—';

    const betaEl = el('acc-profile-beta');
    if (betaEl) betaEl.textContent = user.beta_flag ? 'Yes' : 'No';

    const offlineEl = el('acc-profile-offline');
    if (offlineEl) {
      if (license._offline) {
        const h = license._offline_grace_remaining_hours;
        offlineEl.textContent = `Offline — ${h != null ? h + ' hrs grace remaining' : 'grace period active'}`;
        offlineEl.style.display = '';
      } else {
        offlineEl.style.display = 'none';
      }
    }

    _renderDeviceList();
  }

  // ─── Polling ──────────────────────────────────────────────────────────────

  function _startPolling() {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(() => refreshState(), POLL_INTERVAL_MS);
  }

  // ─── Init ─────────────────────────────────────────────────────────────────

  function init() {
    // Initial state load (non-blocking)
    refreshState().then(state => {
      if (state && state.authenticated) {
        const licStatus = (state.license && state.license.status) || '';
        if (licStatus === 'suspended' || licStatus === 'banned') {
          showAccountScreen('blocked');
        }
      }
    });
    _startPolling();

    // Wire up account chip click
    const chip = el('accountChip');
    if (chip) chip.addEventListener('click', openAccountScreen);

    // Wire up view-accounts population
    document.addEventListener('atlas:viewchange', e => {
      if (e.detail && e.detail.view === 'accounts') {
        refreshState().then(() => _populateProfile());
      }
    });
  }

  // Public surface for inline onclick handlers in HTML
  window.atlasAccounts = {
    open:         openAccountScreen,
    login:        doLogin,
    register:     doRegister,
    logout:       doLogout,
    removeDevice: doRemoveDevice,
    switchPanel:  showAccountScreen,
    refresh:      refreshState,
  };

  // Run after DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
