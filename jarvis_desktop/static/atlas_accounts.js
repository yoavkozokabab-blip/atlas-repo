/**
 * atlas_accounts.js — Atlas Accounts UI
 *
 * Dedicated pre-login auth layout + in-app profile.
 */
(function () {
  'use strict';

  let _state = null;
  let _screenMode = 'login';
  let _pollTimer = null;
  let _appRevealed = false;

  const POLL_INTERVAL_MS = 60_000;

  const AUTH_PANELS = ['acc-panel-login', 'acc-panel-register', 'acc-panel-state'];

  const LOGIN_ERROR_MAP = [
    { match: /valid email/i, title: 'Email needs attention', message: 'Enter a valid email address.', action: '' },
    { match: /no atlas account/i, title: 'Account not found', message: 'No Atlas account was found for this email.', action: '' },
    { match: /incorrect password/i, title: 'Incorrect password', message: 'Incorrect password. Try again or reset it.', action: '' },
    { match: /invalid email or password/i, title: 'Incorrect sign-in', message: 'No Atlas account matched that email and password.', action: 'Check the email and password, then try again.' },
    { match: /pending|waiting for beta approval/i, title: 'Beta approval pending', message: 'Your account was created and is waiting for beta approval.', action: 'The Atlas operator will approve beta access manually.' },
    { match: /suspended/i, title: 'Account suspended', message: 'This account is suspended. Contact the Atlas operator.', action: '' },
    { match: /banned/i, title: 'Account banned', message: 'This account is banned and cannot access Atlas.', action: '' },
    { match: /expired|license|not currently active/i, title: 'Access inactive', message: 'Your Atlas access is not currently active.', action: 'Contact the Atlas operator if this looks wrong.' },
    { match: /device.*revoked|no longer authorized/i, title: 'Device revoked', message: 'This device is no longer authorized for this account.', action: 'Sign in from an approved device or contact the Atlas operator.' },
    { match: /too many login/i, title: 'Too many attempts', message: 'Sign-in is temporarily locked after several failed attempts.', action: 'Wait 15 minutes, then try again.' },
    { match: /device limit|device_limit/i, title: 'Device limit reached', message: 'This account is already signed in on the maximum number of devices.', action: 'Sign in on an existing device and remove an old device from Your Account, or contact support.' },
    { match: /accounts service is not running/i, title: 'Sign-in unavailable', message: 'The Atlas accounts service is not running on this machine.', action: 'Restart Atlas. If the problem persists, check support docs or contact support@useatlas.dev.' },
    { match: /network error/i, title: 'Connection problem', message: 'Atlas could not reach the local accounts service.', action: 'Check your connection and restart Atlas, then try again.' },
  ];

  function api(method, path, body) {
    return fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }).then(r => r.json()).catch(() => ({ ok: false, error: 'Network error' }));
  }

  function el(id) { return document.getElementById(id); }

  function isValidEmail(value) {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value || '').trim());
  }

  function setFieldError(id, message) {
    const target = el(id);
    if (!target) return;
    target.textContent = message || '';
  }

  function selectedRadio(name) {
    const input = document.querySelector(`input[name="${name}"]:checked`);
    return input ? input.value : '';
  }

  function checkedValues(name) {
    return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map(input => input.value);
  }

  function fieldValue(id) {
    const target = el(id);
    return target ? target.value.trim() : '';
  }

  function setError(containerId, msg, title) {
    const c = el(containerId);
    if (!c) return;
    if (!msg) {
      c.textContent = '';
      c.style.display = 'none';
      return;
    }
    c.innerHTML = title ? `<strong>${_escHtml(title)}</strong>${_escHtml(msg)}` : _escHtml(msg);
    c.style.display = 'block';
  }

  function setLoading(btnId, loading) {
    const b = el(btnId);
    if (!b) return;
    b.disabled = loading;
    b.dataset.origText = b.dataset.origText || b.textContent;
    b.textContent = loading ? 'Please wait…' : b.dataset.origText;
  }

  function _escHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function _formatLoginError(raw) {
    const text = String(raw || 'Sign-in failed. Please try again.');
    for (const rule of LOGIN_ERROR_MAP) {
      if (rule.match.test(text)) return rule;
    }
    return {
      title: 'Sign-in failed',
      message: text,
      action: 'Try again or contact support@useatlas.dev if the problem continues.',
    };
  }

  function _licenseBlockState() {
    if (!_state || !_state.license) return null;
    const lic = _state.license;
    const status = lic.status || '';
    const userStatus = (_state.user && _state.user.status) || '';

    if (userStatus === 'suspended' || status === 'suspended') {
      return { icon: '!', title: 'Account suspended', message: 'This account is suspended. Contact the Atlas operator.', action: 'Atlas workflows are unavailable for this account.', showSignOut: true };
    }
    if (userStatus === 'banned' || status === 'banned') {
      return { icon: '!', title: 'Account banned', message: 'This account is banned and cannot access Atlas.', action: 'Atlas workflows are unavailable for this account.', showSignOut: true };
    }
    if (status === 'pending' || userStatus === 'pending') {
      return { icon: '...', title: 'Beta access pending', message: 'Your account was created and is waiting for beta approval.', action: 'Atlas beta access is manually approved. Your code stays local.', showSignOut: true };
    }
    if (status === 'device_revoked') {
      return { icon: '!', title: 'Device revoked', message: 'This device is no longer authorized for this account.', action: 'Sign in from an approved device or contact the Atlas operator.', showSignOut: true };
    }
    if (status === 'expired' || status === 'license_check_failed') {
      return { icon: '!', title: 'Access inactive', message: 'Your Atlas access is not currently active.', action: 'Contact the Atlas operator if this looks wrong.', showSignOut: true };
    }

    if (userStatus === 'suspended' || status === 'suspended') {
      return { icon: '⏸', title: 'Account suspended', message: 'Your account is suspended and Atlas features are unavailable.', action: 'Contact support@useatlas.dev to restore access.', showSignOut: true };
    }
    if (userStatus === 'banned' || status === 'banned') {
      return { icon: '🚫', title: 'Account banned', message: 'Your account has been banned from Atlas.', action: 'Contact support@useatlas.dev if you believe this is an error.', showSignOut: true };
    }
    if (status === 'pending' || userStatus === 'pending') {
      return { icon: '⏳', title: 'Beta access pending', message: 'Your account is registered but beta access has not been granted yet.', action: 'We will email you when your access is approved. You can contact support@useatlas.dev for status updates.', showSignOut: true };
    }
    if (status === 'offline_grace_expired') {
      return { icon: '📡', title: 'Offline grace expired', message: lic.message || 'Atlas has been offline too long without verifying your license.', action: 'Reconnect to the internet and sign in again to continue.', showSignOut: true };
    }
    if (status === 'local_state_tampered' || _state.state_integrity_error) {
      return { icon: '🔐', title: 'Session invalid', message: 'Your local account cache failed integrity checks.', action: 'Sign in again to refresh your session.', showSignOut: true };
    }
    if (status === 'account_unavailable') {
      return { icon: '🔑', title: 'Session expired', message: lic.message || 'Your session is no longer valid.', action: 'Sign in again to continue using Atlas.', showSignOut: true };
    }
    if (_state.user && !lic.valid && status !== 'unauthenticated') {
      return { icon: '🔒', title: 'License inactive', message: lic.message || 'Your Atlas license is not active.', action: 'Sign in again or contact support@useatlas.dev.', showSignOut: true };
    }
    return null;
  }

  function _showAuthStatePanel(spec) {
    AUTH_PANELS.forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });
    const panel = el('acc-panel-state');
    if (!panel) return;
    panel.style.display = '';
    if (el('acc-state-icon')) el('acc-state-icon').textContent = spec.icon || '⚠';
    if (el('acc-state-title')) el('acc-state-title').textContent = spec.title || 'Account unavailable';
    if (el('acc-state-message')) el('acc-state-message').textContent = spec.message || '';
    if (el('acc-state-action')) el('acc-state-action').textContent = spec.action || '';
    const signOut = el('acc-state-signout-btn');
    if (signOut) signOut.style.display = spec.showSignOut ? '' : 'none';
    const primary = el('acc-state-primary-btn');
    if (primary) primary.style.display = 'none';
    _setAuthMode(true);
  }

  function _setAuthMode(on) {
    document.body.classList.toggle('auth-mode', on);
    document.body.classList.toggle('app-authenticated', !on);
    document.body.classList.remove('auth-loading');
  }

  function _enterApp(options) {
    const firstReveal = !_appRevealed;
    _appRevealed = true;
    _setAuthMode(false);
    if (firstReveal) {
      if (typeof window.bootAtlasApp === 'function') window.bootAtlasApp();
      if (options && options.goHome !== false && typeof go === 'function') go('home');
      document.dispatchEvent(new CustomEvent('atlas:authenticated'));
    }
  }

  function showAccountScreen(mode) {
    _screenMode = mode || _screenMode;

    if (_screenMode === 'profile') {
      _enterApp({ goHome: false });
      _populateProfile();
      if (typeof go === 'function') go('accounts');
      return;
    }

    if (_screenMode === 'blocked' || _screenMode === 'state') {
      const block = _licenseBlockState();
      if (block) _showAuthStatePanel(block);
      else _showAuthStatePanel({
        icon: '⚠',
        title: 'Account restricted',
        message: 'Atlas features are unavailable for this account.',
        action: 'Contact support@useatlas.dev for help.',
        showSignOut: true,
      });
      return;
    }

    AUTH_PANELS.forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });
    const panel = el('acc-panel-' + _screenMode);
    if (panel) panel.style.display = '';
    _setAuthMode(true);
  }

  function openAccountScreen() {
    refreshState().then(() => {
      if (!_state || !_state.authenticated) {
        const block = _licenseBlockState();
        if (block) showAccountScreen('blocked');
        else showAccountScreen('login');
        return;
      }
      showAccountScreen('profile');
    });
  }

  window.openAccountScreen = openAccountScreen;
  window.showAccPanel = showAccountScreen;

  function refreshState() {
    return api('GET', '/api/accounts/state').then(data => {
      _state = data;
      _updateAccountChip();
      _applyLicenseGating();
      _syncLayoutFromState();
      return data;
    });
  }

  function _syncLayoutFromState() {
    if (!_state) {
      showAccountScreen('login');
      return;
    }
    if (_state.authenticated) {
      _enterApp();
      return;
    }
    const block = _licenseBlockState();
    if (block) {
      showAccountScreen('blocked');
    } else if (!document.body.classList.contains('auth-loading')) {
      _setAuthMode(true);
    }
  }

  function doLogin() {
    const email = el('acc-login-email') && el('acc-login-email').value.trim();
    const password = el('acc-login-pwd') && el('acc-login-pwd').value;
    setError('acc-login-error', '');
    setFieldError('acc-login-email-msg', '');
    if (email && !isValidEmail(email)) {
      setFieldError('acc-login-email-msg', 'Enter a valid email address.');
      if (el('acc-login-email')) el('acc-login-email').setAttribute('aria-invalid', 'true');
      return;
    }
    if (el('acc-login-email')) el('acc-login-email').removeAttribute('aria-invalid');
    if (!email || !password) {
      setError('acc-login-error', 'Enter both email and password to continue.', 'Missing fields');
      return;
    }

    setLoading('acc-login-btn', true);
    api('POST', '/api/accounts/login', { email, password }).then(res => {
      setLoading('acc-login-btn', false);
      if (res.ok) {
        if (el('acc-login-pwd')) el('acc-login-pwd').value = '';
        setTimeout(() => refreshState().then(() => _enterApp({ goHome: true })), 300);
      } else {
        const err = _formatLoginError(res.error || res.detail || res.message);
        setError('acc-login-error', `${err.message} ${err.action}`, err.title);
      }
    });
  }

  function collectBetaProfile() {
    const devValue = selectedRadio('acc-current-dev');
    const profile = {
      currently_developer: devValue === 'yes' ? true : devValue === 'no' ? false : null,
      project_use: fieldValue('acc-project-use'),
      company_name: fieldValue('acc-company-name'),
      company_size: fieldValue('acc-company-size'),
      developer_experience: fieldValue('acc-dev-exp'),
      primary_role: fieldValue('acc-primary-role'),
      coding_tools: checkedValues('acc-tools'),
      languages_frameworks: fieldValue('acc-languages'),
      repo_size: fieldValue('acc-repo-size'),
      atlas_help: checkedValues('acc-help'),
      notes: fieldValue('acc-notes'),
    };
    if (profile.currently_developer === null) return { error: 'Choose whether you currently work as a developer.' };
    const required = ['project_use', 'company_size', 'developer_experience', 'primary_role', 'repo_size'];
    if (required.some(key => !profile[key])) return { error: 'Complete the required beta profile fields.' };
    if (!profile.coding_tools.length) return { error: 'Select at least one main coding tool.' };
    if (!profile.atlas_help.length) return { error: 'Select what you want Atlas to help with most.' };
    if (!profile.company_name) delete profile.company_name;
    if (!profile.languages_frameworks) delete profile.languages_frameworks;
    if (!profile.notes) delete profile.notes;
    return { profile };
  }

  function doRegister() {
    const email = el('acc-reg-email') && el('acc-reg-email').value.trim();
    const password = el('acc-reg-pwd') && el('acc-reg-pwd').value;
    const confirm = el('acc-reg-pwd2') && el('acc-reg-pwd2').value;
    setError('acc-reg-error', '');
    setFieldError('acc-reg-email-msg', '');

    if (!email || !password) {
      setError('acc-reg-error', 'Email and password are required.', 'Missing fields');
      return;
    }
    if (!isValidEmail(email)) {
      setFieldError('acc-reg-email-msg', 'Enter a valid email address.');
      if (el('acc-reg-email')) el('acc-reg-email').setAttribute('aria-invalid', 'true');
      return;
    }
    if (el('acc-reg-email')) el('acc-reg-email').removeAttribute('aria-invalid');
    if (password.length < 8) {
      setError('acc-reg-error', 'Use at least 8 characters for your password.', 'Password too short');
      return;
    }
    if (password !== confirm) {
      setError('acc-reg-error', 'Passwords do not match.', 'Passwords differ');
      return;
    }
    const profileResult = collectBetaProfile();
    if (profileResult.error) {
      setError('acc-reg-error', profileResult.error, 'Beta profile incomplete');
      return;
    }

    setLoading('acc-reg-btn', true);
    api('POST', '/api/accounts/register', {
      email,
      password,
      confirm_password: confirm,
      beta_profile: profileResult.profile,
    }).then(res => {
      setLoading('acc-reg-btn', false);
      if (res.ok) {
        if (el('acc-reg-pwd')) el('acc-reg-pwd').value = '';
        if (el('acc-reg-pwd2')) el('acc-reg-pwd2').value = '';
        setTimeout(() => refreshState().then(() => showAccountScreen('blocked')), 300);
      } else {
        const err = _formatLoginError(res.error || res.detail || 'Registration failed.');
        setError('acc-reg-error', `${err.message} ${err.action}`, err.title);
      }
    });
  }

  function doLogout() {
    api('POST', '/api/accounts/logout').then(() => {
      _state = null;
      _appRevealed = false;
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

  function _applyLicenseGating() {
    const licenseValid = _state && _state.license && _state.license.valid;
    const licStatus = (_state && _state.license && _state.license.status) || '';
    const blocked = licStatus === 'suspended' || licStatus === 'banned';

    document.querySelectorAll('[data-lock="1"]').forEach(btn => {
      btn.disabled = !licenseValid;
      btn.title = (!licenseValid)
        ? 'Sign in to unlock — free for beta users'
        : (btn.dataset.origTitle || '');
    });

    _updateAccountChip();
  }

  function _updateAccountChip() {
    const chip = el('accountChip');
    if (!chip) return;

    if (!_state || !_state.authenticated) {
      chip.textContent = 'Account';
      chip.className = 'account-chip unsigned';
      return;
    }

    const user = _state.user || {};
    const license = _state.license || {};
    const email = user.email || '';
    const plan = license.plan || 'free';
    const offline = license._offline ? ' (offline)' : '';

    chip.textContent = `${email.split('@')[0]} · ${plan}${offline}`;
    chip.className = 'account-chip signed-in' + (license._offline ? ' offline' : '');
  }

  function _populateProfile() {
    if (!_state || !_state.authenticated) return;
    const user = _state.user || {};
    const license = _state.license || {};

    const emailEl = el('acc-profile-email');
    if (emailEl) emailEl.textContent = user.email || '—';

    const planEl = el('acc-profile-plan');
    if (planEl) planEl.textContent = license.plan || 'free';

    const statusEl = el('acc-profile-status');
    if (statusEl) statusEl.textContent = license.status || user.status || '—';

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

  function _startPolling() {
    if (_pollTimer) clearInterval(_pollTimer);
    _pollTimer = setInterval(() => refreshState(), POLL_INTERVAL_MS);
  }

  function init() {
    refreshState().finally(() => {
      document.body.classList.remove('auth-loading');
    });
    _startPolling();

    const chip = el('accountChip');
    if (chip) chip.addEventListener('click', openAccountScreen);

    document.addEventListener('atlas:viewchange', e => {
      if (e.detail && e.detail.view === 'accounts') {
        refreshState().then(() => _populateProfile());
      }
    });
  }

  window.atlasAccounts = {
    open: openAccountScreen,
    login: doLogin,
    register: doRegister,
    logout: doLogout,
    removeDevice: doRemoveDevice,
    switchPanel: showAccountScreen,
    refresh: refreshState,
    isAuthenticated: () => !!( _state && _state.authenticated),
    requireAccess: () => {
      if (_state && _state.authenticated) return true;
      const block = _licenseBlockState();
      if (block) showAccountScreen('blocked');
      else showAccountScreen('login');
      return false;
    },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
