/**
 * atlas_accounts.js â€” Atlas Accounts UI
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

  const AUTH_PANELS = ['acc-panel-login', 'acc-panel-register', 'acc-panel-state', 'acc-panel-submitted', 'acc-panel-submit-failed'];

  const DRAFT_KEY = 'atlas_account_profile_draft_v1';
  const DRAFT_SESSION_KEY = 'atlas_account_profile_session_v1';

  // Account setup wizard state
  let _regStep = 1;
  let _regWired = false;
  const _REG_STEPS = 5;
  const _STEP_NAMES = { 1: 'Account', 2: 'Developer profile', 3: 'Projects', 4: 'Goals', 5: 'Optional notes' };

  const LOGIN_ERROR_MAP = [
    { match: /valid email/i, title: 'Email needs attention', message: 'Enter a valid email address.', action: '' },
    { match: /no atlas account/i, title: 'Account not found', message: 'No Atlas account was found for this email.', action: '' },
    { match: /incorrect password/i, title: 'Incorrect password', message: 'Incorrect password. Try again or reset it.', action: '' },
    { match: /invalid email or password/i, title: 'Incorrect sign-in', message: 'No Atlas account matched that email and password.', action: 'Check the email and password, then try again.' },
    { match: /suspended/i, title: 'Account suspended', message: 'This account is suspended. Contact support.', action: '' },
    { match: /banned/i, title: 'Account banned', message: 'This account is banned and cannot access Atlas.', action: '' },
    { match: /expired|license|not currently active/i, title: 'Access inactive', message: 'Your Atlas access is not currently active.', action: 'Contact support if this looks wrong.' },
    { match: /device.*revoked|no longer authorized/i, title: 'Device revoked', message: 'This device is no longer authorized for this account.', action: 'Sign in from an authorized device or contact support.' },
    { match: /too many login/i, title: 'Too many attempts', message: 'Sign-in is temporarily locked after several failed attempts.', action: 'Wait 15 minutes, then try again.' },
    { match: /device limit|device_limit/i, title: 'Device limit reached', message: 'This account is already signed in on the maximum number of devices.', action: 'Sign in on an existing device and remove an old device from Your Account, or contact support.' },
    { match: /accounts service is not running/i, title: 'Sign-in unavailable', message: 'The Atlas accounts service is not running on this machine.', action: 'Restart Atlas. If the problem persists, check support docs or contact yoavkozokabab@gmail.com.' },
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
    b.textContent = loading ? 'Please waitâ€¦' : b.dataset.origText;
  }

  function _escHtml(str) {
    return String(str).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function _formatRegistrationError(res) {
    const code = res && res.code;
    const raw = String((res && (res.error || res.detail)) || 'Registration failed.');
    if (code === 'service_unavailable' || /could not reach|isn't available|unreachable|network error/i.test(raw)) {
      return {
        useSubmitFailedPanel: true,
        title: 'Account not created',
        message: 'We could not reach the Atlas account service.',
        detail: 'Your account has not been created yet. Your answers are saved locally.',
      };
    }
    if (code === 'duplicate_email' || /already registered|already exists/i.test(raw)) {
      return {
        title: 'Email already registered',
        message: 'An account with this email already exists.',
        detail: res.detail || 'Your account may already exist. Try signing in instead.',
      };
    }
    if (res && res.account_created && !res.submitted) {
      return {
        title: 'Account created â€” profile not confirmed',
        message: 'Your Atlas account was created, but we could not confirm it was saved.',
        detail: 'Try signing in. If your account is missing, contact yoavkozokabab@gmail.com with your email.',
      };
    }
    return {
      title: 'Account not created',
      message: raw,
      detail: 'Review your answers and try again, or contact yoavkozokabab@gmail.com if this continues.',
    };
  }

  function _showSubmitFailedPanel(spec) {
    AUTH_PANELS.forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });
    const panel = el('acc-panel-submit-failed');
    if (!panel) return;
    panel.style.display = '';
    if (el('acc-submit-failed-title')) el('acc-submit-failed-title').textContent = spec.title || 'Account not created';
    if (el('acc-submit-failed-message')) el('acc-submit-failed-message').textContent = spec.message || '';
    if (el('acc-submit-failed-detail')) el('acc-submit-failed-detail').textContent = spec.detail || '';
    _setAuthMode(true);
    _screenMode = 'submit-failed';
  }

  function _draftPayload(includeSecrets) {
    const dev = selectedRadio('acc-current-dev');
    return {
      step: _regStep,
      email: fieldValue('acc-reg-email'),
      currently_developer: dev,
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
      saved_at: new Date().toISOString(),
      password: includeSecrets && el('acc-reg-pwd') ? el('acc-reg-pwd').value : undefined,
      confirm_password: includeSecrets && el('acc-reg-pwd2') ? el('acc-reg-pwd2').value : undefined,
    };
  }

  function saveDraft(showToast) {
    try {
      const draft = _draftPayload(false);
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
      const session = _draftPayload(true);
      delete session.saved_at;
      sessionStorage.setItem(DRAFT_SESSION_KEY, JSON.stringify({
        password: session.password,
        confirm_password: session.confirm_password,
      }));
      if (showToast !== false && typeof toast === 'function') toast('Draft saved locally', 'success');
      return true;
    } catch (e) {
      return false;
    }
  }

  function restoreDraft() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return false;
      const draft = JSON.parse(raw);
      if (el('acc-reg-email') && draft.email) el('acc-reg-email').value = draft.email;
      if (draft.currently_developer) {
        const radio = document.querySelector(`input[name="acc-current-dev"][value="${draft.currently_developer}"]`);
        if (radio) radio.checked = true;
      }
      const setVal = (id, val) => { const t = el(id); if (t && val != null) t.value = val; };
      setVal('acc-project-use', draft.project_use);
      setVal('acc-company-name', draft.company_name);
      setVal('acc-company-size', draft.company_size);
      setVal('acc-dev-exp', draft.developer_experience);
      setVal('acc-primary-role', draft.primary_role);
      setVal('acc-languages', draft.languages_frameworks);
      setVal('acc-repo-size', draft.repo_size);
      setVal('acc-notes', draft.notes);
      (draft.coding_tools || []).forEach(v => {
        const cb = document.querySelector(`input[name="acc-tools"][value="${v}"]`);
        if (cb) cb.checked = true;
      });
      (draft.atlas_help || []).forEach(v => {
        const cb = document.querySelector(`input[name="acc-help"][value="${v}"]`);
        if (cb) cb.checked = true;
      });
      const sessRaw = sessionStorage.getItem(DRAFT_SESSION_KEY);
      if (sessRaw) {
        const sess = JSON.parse(sessRaw);
        if (el('acc-reg-pwd') && sess.password) el('acc-reg-pwd').value = sess.password;
        if (el('acc-reg-pwd2') && sess.confirm_password) el('acc-reg-pwd2').value = sess.confirm_password;
      }
      _updateConditionalFields();
      if (draft.step) _showRegStep(Number(draft.step) || 1);
      return true;
    } catch (e) {
      return false;
    }
  }

  function clearDraft() {
    try {
      localStorage.removeItem(DRAFT_KEY);
      sessionStorage.removeItem(DRAFT_SESSION_KEY);
    } catch (e) {}
  }

  function retrySubmit() {
    showAccountScreen('register');
    doRegister();
  }

  function _formatLoginError(raw) {
    const text = String(raw || 'Sign-in failed. Please try again.');
    for (const rule of LOGIN_ERROR_MAP) {
      if (rule.match.test(text)) return rule;
    }
    return {
      title: 'Sign-in failed',
      message: text,
      action: 'Try again or contact yoavkozokabab@gmail.com if the problem continues.',
    };
  }

  function _licenseBlockState() {
    if (!_state || !_state.license) return null;
    const lic = _state.license;
    const status = lic.status || '';
    const userStatus = (_state.user && _state.user.status) || '';

    if (userStatus === 'suspended' || status === 'suspended') {
      return { icon: '!', title: 'Account suspended', message: 'This account is suspended. Contact support.', action: 'Atlas workflows are unavailable for this account.', showSignOut: true };
    }
    if (userStatus === 'banned' || status === 'banned') {
      return { icon: '!', title: 'Account banned', message: 'This account is banned and cannot access Atlas.', action: 'Atlas workflows are unavailable for this account.', showSignOut: true };
    }
    if (status === 'device_revoked') {
      return { icon: '!', title: 'Device revoked', message: 'This device is no longer authorized for this account.', action: 'Sign in from an authorized device or contact support.', showSignOut: true };
    }
    if (status === 'expired' || status === 'past_due' || status === 'canceled' || status === 'cancelled' || status === 'trial_missing_expiry' || status === 'license_check_failed') {
      return { icon: '!', title: 'Access inactive', message: 'Your Atlas access is not currently active.', action: 'Contact support if this looks wrong.', showSignOut: true };
    }

    if (userStatus === 'suspended' || status === 'suspended') {
      return { icon: 'â¸', title: 'Account suspended', message: 'Your account is suspended and Atlas features are unavailable.', action: 'Contact yoavkozokabab@gmail.com to restore access.', showSignOut: true };
    }
    if (userStatus === 'banned' || status === 'banned') {
      return { icon: 'ðŸš«', title: 'Account banned', message: 'Your account has been banned from Atlas.', action: 'Contact yoavkozokabab@gmail.com if you believe this is an error.', showSignOut: true };
    }
    if (status === 'offline_grace_expired') {
      return { icon: 'ðŸ“¡', title: 'Offline grace expired', message: lic.message || 'Atlas has been offline too long without verifying your license.', action: 'Reconnect to the internet and sign in again to continue.', showSignOut: true };
    }
    if (status === 'local_state_tampered' || _state.state_integrity_error) {
      return { icon: 'ðŸ”', title: 'Session invalid', message: 'Your local account cache failed integrity checks.', action: 'Sign in again to refresh your session.', showSignOut: true };
    }
    if (status === 'account_unavailable') {
      return { icon: 'ðŸ”‘', title: 'Session expired', message: lic.message || 'Your session is no longer valid.', action: 'Sign in again to continue using Atlas.', showSignOut: true };
    }
    if (_state.user && !lic.valid && status !== 'unauthenticated') {
      return { icon: 'ðŸ”’', title: 'License inactive', message: lic.message || 'Your Atlas license is not active.', action: 'Sign in again or contact yoavkozokabab@gmail.com.', showSignOut: true };
    }
    return null;
  }

  function _showAuthStatePanel(spec) {
    AUTH_PANELS.forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });
    const panel = el('acc-panel-state');
    if (!panel) return;
    panel.style.display = '';
    if (el('acc-state-icon')) el('acc-state-icon').textContent = spec.icon || 'âš ';
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

  // â”€â”€ Account status taxonomy + in-app dashboards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Every signed-in account resolves to exactly one status. Active accounts get the
  // product; inactive/rejected accounts get a tailored in-app dashboard â€” never a
  // pre-login access wall.
  function _accountStatus() {
    if (!_state) return 'unknown';
    const user = _state.user || {};
    const lic = _state.license || {};
    const us = String(user.status || '').toLowerCase();
    const ls = String(lic.status || '').toLowerCase();
    if (_state.authenticated) {
      return 'active';
    }
    if (us === 'suspended' || us === 'banned' || ls === 'suspended' || ls === 'banned') return 'blocked';
    return 'inactive';
  }

  // Feature flag â€” the "Reapply" affordance is a placeholder for a future cohort
  // and stays hidden until the reapply flow exists (Part 6).
  const REAPPLY_ENABLED = false;

  const STATUS_DASH = {
    inactive: {
      // Calm/neutral â€” never error or warning styling (Part 5).
      tone: 'neutral',
      icon: 'â„¹ï¸',
      title: 'Account not active',
      message: 'You are signed in and your account exists â€” Atlas access is just not available right now.',
      steps: [
        { label: 'Your account exists', done: true },
        { label: 'You signed in successfully', done: true },
        { label: 'Atlas access is currently unavailable', done: false },
      ],
      showRefresh: true,
      showReapply: false,
      foot: 'If you think this is a mistake, contact support and we will take a look.',
    },
  };

  function _renderStatusDashboard(status) {
    const spec = STATUS_DASH[status] || STATUS_DASH.inactive;
    const set = (id, val) => { const e = el(id); if (e) e.textContent = val || ''; };
    const dash = el('statusDash');
    if (dash) dash.className = 'status-dash glass' + (spec.tone ? ' ' + spec.tone : '');
    set('statusDashIcon', spec.icon);
    set('statusDashTitle', spec.title);
    set('statusDashMessage', spec.message);

    const stepsEl = el('statusDashSteps');
    if (stepsEl) {
      const steps = spec.steps || [];
      stepsEl.innerHTML = steps.map(s => `<li class="${s.done ? '' : 'muted-step'}">${_escHtml(s.label)}</li>`).join('');
      stepsEl.style.display = steps.length ? '' : 'none';
    }

    const lic = (_state && _state.license) || {};
    const reasonEl = el('statusDashReason');
    if (reasonEl) {
      const reason = (status === 'inactive' && lic.message && lic.status !== 'unauthenticated') ? lic.message : '';
      reasonEl.textContent = reason ? ('Reason: ' + reason) : '';
      reasonEl.style.display = reason ? '' : 'none';
    }

    const etaEl = el('statusDashEta');
    if (etaEl) { etaEl.textContent = spec.eta || ''; etaEl.style.display = spec.eta ? '' : 'none'; }

    const refreshBtn = el('statusRefreshBtn');
    if (refreshBtn) refreshBtn.style.display = spec.showRefresh ? '' : 'none';
    const reapplyBtn = el('statusReapplyBtn');
    if (reapplyBtn) reapplyBtn.style.display = spec.showReapply ? '' : 'none';
    set('statusDashFoot', spec.foot);
  }

  function _recentName(it) {
    return it.repo_name || (it.repo_path || '').split(/[\\/]/).pop() || 'repository';
  }

  function _renderHomeRecent() {
    const aBox = el('homeRecentAnalyses');
    const rBox = el('homeRecentRepos');
    const xBox = el('homeRecentExports');
    const gs = el('homeGettingStarted');
    const homeView = el('view-home');
    if (homeView && !homeView.classList.contains('active')) return; // only fetch when visible

    api('GET', '/api/repositories/recent').then(res => {
      const items = (res && res.items) || [];
      // Section 3: Getting Started auto-hides once there is usage history.
      if (gs) gs.style.display = items.length ? 'none' : '';

      if (aBox) {
        aBox.innerHTML = items.length
          ? items.slice(0, 4).map(it => {
              const when = it.last_scan_at ? String(it.last_scan_at).slice(0, 10) : '';
              return `<div class="home-recent-item"><span>${_escHtml(_recentName(it))}</span><span class="muted">${_escHtml(when)}</span></div>`;
            }).join('')
          : '<span class="muted tiny">No analyses yet â€” scan a repository to get started.</span>';
      }
      if (rBox) {
        const seen = {}; const repos = [];
        items.forEach(it => { const p = it.repo_path || it.repo_name; if (p && !seen[p]) { seen[p] = 1; repos.push(it); } });
        rBox.innerHTML = repos.length
          ? repos.slice(0, 4).map(it => `<div class="home-recent-item"><span>${_escHtml(_recentName(it))}</span></div>`).join('')
          : '<span class="muted tiny">No repositories yet.</span>';
      }
    }).catch(() => {
      if (aBox) aBox.innerHTML = '<span class="muted tiny">No analyses yet.</span>';
      if (rBox) rBox.innerHTML = '<span class="muted tiny">No repositories yet.</span>';
    });

    // Recent exports â€” local history only (no server dependency / empty-state).
    if (xBox) {
      let exports = [];
      try { exports = JSON.parse(localStorage.getItem('atlas_recent_exports') || '[]'); } catch (e) {}
      xBox.innerHTML = (exports && exports.length)
        ? exports.slice(0, 4).map(x => `<div class="home-recent-item"><span>${_escHtml(x.label || x.target || 'export')}</span><span class="muted">${_escHtml(String(x.at || '').slice(0, 10))}</span></div>`).join('')
        : '<span class="muted tiny">No exports yet.</span>';
    }
  }

  const _HOME_STATUS_PILL = {
    active: { label: 'Active', cls: '' },
    blocked: { label: 'Suspended', cls: 'bad' },
    inactive: { label: 'Not active', cls: 'bad' },
  };

  function _renderHomeDashboard() {
    const dash = el('homeDashboard');
    if (!dash) return;
    dash.style.display = '';

    if (!_state || !_state.signed_in) {
      return;
    }

    const user = _state.user || {};
    const lic = _state.license || {};
    const status = _accountStatus();
    const name = (user.email || '').split('@')[0] || 'there';

    const welcome = el('homeWelcome');
    if (welcome) welcome.textContent = `Welcome back, ${name}`;

    // Single, clear account-status indicator (Part 8): status + plan in one pill.
    const pill = el('homeStatusPill');
    if (pill) {
      const s = _HOME_STATUS_PILL[status] || { label: status, cls: 'warn' };
      const plan = lic.plan || 'free';
      const planTitle = plan.charAt(0).toUpperCase() + plan.slice(1);
      pill.textContent = s.label + ' Â· ' + planTitle + (lic._offline ? ' Â· offline' : '');
      pill.className = 'status-pill' + (s.cls ? ' ' + s.cls : '');
    }

    const repoEl = el('homeRepoStatus');
    if (repoEl) {
      const summary = window.STATE && window.STATE.summary;
      if (summary && summary.ok) {
        const files = summary.file_count || summary.files || 0;
        repoEl.innerHTML = `<a href="#" onclick="go('center');return false;">${_escHtml(summary.repo_name || 'Current repository')}</a> Â· ${files} files`;
      } else {
        repoEl.textContent = 'No repository scanned yet';
      }
    }
    _renderHomeRecent();
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
        icon: 'âš ',
        title: 'Account restricted',
        message: 'Atlas features are unavailable for this account.',
        action: 'Contact yoavkozokabab@gmail.com for help.',
        showSignOut: true,
      });
      return;
    }

    AUTH_PANELS.forEach(id => { const e = el(id); if (e) e.style.display = 'none'; });
    const panel = el('acc-panel-' + _screenMode);
    if (panel) panel.style.display = '';
    if (_screenMode === 'register') {
      _wireRegisterEvents();
      resetRegisterWizard();
      restoreDraft();
    }
    _setAuthMode(true);
  }

  function openAccountScreen() {
    refreshState().then(() => {
      if (_state && _state.authenticated) {
        showAccountScreen('profile');
        return;
      }
      // Signed in but not active: keep them in-app on their status dashboard.
      if (_state && _state.signed_in && _accountStatus() !== 'blocked') {
        _enterApp({ goHome: false });
        _renderStatusDashboard(_accountStatus());
        if (typeof go === 'function') go('status');
        return;
      }
      const block = _licenseBlockState();
      if (block) showAccountScreen('blocked');
      else showAccountScreen('login');
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
    if (_screenMode === 'submitted' || _screenMode === 'submit-failed') {
      _setAuthMode(true);
      return;
    }
    if (!_state) {
      showAccountScreen('login');
      return;
    }
    if (_state.authenticated) {
      _enterApp();
      _renderHomeDashboard();
      return;
    }
    // Signed in but not yet active â€” route into the app to a status dashboard
    // (with branding + nav), never the pre-login access wall.
    if (_state.signed_in) {
      const status = _accountStatus();
      if (status === 'blocked') {
        const hard = _licenseBlockState();
        if (hard) { showAccountScreen('blocked'); return; }
      }
      const firstReveal = !_appRevealed;
      _enterApp({ goHome: false });
      _renderStatusDashboard(status);
      _renderHomeDashboard();
      if (firstReveal && typeof go === 'function') go('status');
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
        // refreshState() routes active accounts to home and inactive/rejected
        // accounts to the in-app status dashboard. Never stranded.
        setTimeout(() => refreshState(), 300);
      } else {
        const err = _formatLoginError(res.error || res.detail || res.message);
        setError('acc-login-error', `${err.message} ${err.action}`, err.title);
      }
    });
  }

  // â”€â”€ Account setup wizard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function _companyFieldsRelevant() {
    const dev = selectedRadio('acc-current-dev');
    const use = fieldValue('acc-project-use');
    const role = fieldValue('acc-primary-role');
    // Company questions only make sense for working developers on work projects.
    return !(dev === 'no' || use === 'personal' || role === 'student');
  }

  function _updateConditionalFields() {
    const wrap = el('acc-company-fields');
    if (wrap) wrap.style.display = _companyFieldsRelevant() ? '' : 'none';
  }

  function _validateRegStep(n, { quiet } = {}) {
    if (!quiet) setError('acc-reg-error', '');
    if (n === 1) {
      const email = fieldValue('acc-reg-email');
      const pwd = el('acc-reg-pwd') ? el('acc-reg-pwd').value : '';
      const pwd2 = el('acc-reg-pwd2') ? el('acc-reg-pwd2').value : '';
      let ok = true;
      if (!email || !isValidEmail(email)) { setFieldError('acc-reg-email-msg', 'Enter a valid email address.'); ok = false; }
      else setFieldError('acc-reg-email-msg', '');
      if (pwd.length < 8) { setFieldError('acc-reg-pwd-msg', 'Use at least 8 characters.'); ok = false; }
      else setFieldError('acc-reg-pwd-msg', '');
      if (pwd2 !== pwd || !pwd2) { setFieldError('acc-reg-pwd2-msg', pwd2 && pwd2 !== pwd ? 'Passwords do not match.' : 'Confirm your password.'); ok = false; }
      else setFieldError('acc-reg-pwd2-msg', '');
      return ok;
    }
    if (n === 2) {
      if (!fieldValue('acc-primary-role')) return _stepErr('Select your primary role.', quiet);
      if (!fieldValue('acc-dev-exp')) return _stepErr('Select your developer experience.', quiet);
      if (!selectedRadio('acc-current-dev')) return _stepErr('Choose whether you currently work as a developer.', quiet);
      return true;
    }
    if (n === 3) {
      if (!fieldValue('acc-project-use')) return _stepErr('Choose personal or work projects.', quiet);
      if (_companyFieldsRelevant() && !fieldValue('acc-company-size')) return _stepErr('Select your company size.', quiet);
      if (!fieldValue('acc-repo-size')) return _stepErr('Select your typical repository size.', quiet);
      if (!checkedValues('acc-tools').length) return _stepErr('Select at least one coding tool.', quiet);
      return true;
    }
    if (n === 4) {
      if (!checkedValues('acc-help').length) return _stepErr('Select what you want Atlas to help with.', quiet);
      return true;
    }
    return true;
  }

  function _stepErr(msg, quiet) { if (!quiet) setError('acc-reg-error', msg); return false; }

  function _showRegStep(n) {
    _regStep = Math.max(1, Math.min(_REG_STEPS, n));
    document.querySelectorAll('#acc-panel-register .acc-step').forEach(s => {
      s.hidden = (parseInt(s.dataset.step, 10) !== _regStep);
    });
    if (el('acc-step-num')) el('acc-step-num').textContent = _regStep;
    if (el('acc-step-name')) el('acc-step-name').textContent = _STEP_NAMES[_regStep] || '';
    if (el('acc-progress-fill')) el('acc-progress-fill').style.width = (_regStep / _REG_STEPS * 100) + '%';
    if (el('acc-back-btn')) el('acc-back-btn').style.display = _regStep > 1 ? '' : 'none';
    if (el('acc-next-btn')) el('acc-next-btn').style.display = _regStep < _REG_STEPS ? '' : 'none';
    if (el('acc-reg-btn')) el('acc-reg-btn').style.display = _regStep >= _REG_STEPS ? '' : 'none';
    const body = document.querySelector('#acc-panel-register .auth-wizard-body');
    if (body) body.scrollTop = 0;
    const first = document.querySelector(`#acc-panel-register .acc-step[data-step="${_regStep}"] input, #acc-panel-register .acc-step[data-step="${_regStep}"] select, #acc-panel-register .acc-step[data-step="${_regStep}"] textarea`);
    if (first) { try { first.focus(); } catch (e) {} }
  }

  function resetRegisterWizard() {
    _regStep = 1;
    _updateConditionalFields();
    _showRegStep(1);
  }

  function wizardNext() {
    if (!_validateRegStep(_regStep)) return;
    _updateConditionalFields();
    _showRegStep(_regStep + 1);
  }

  function wizardBack() { setError('acc-reg-error', ''); _showRegStep(_regStep - 1); }

  function _wireRegisterEvents() {
    if (_regWired) return;
    _regWired = true;
    // Immediate validation on the account step.
    const onEmail = () => { const v = fieldValue('acc-reg-email'); setFieldError('acc-reg-email-msg', v && !isValidEmail(v) ? 'Enter a valid email address.' : ''); };
    const onPwd = () => { const v = el('acc-reg-pwd') ? el('acc-reg-pwd').value : ''; setFieldError('acc-reg-pwd-msg', v && v.length < 8 ? 'Use at least 8 characters.' : ''); _onPwd2(); };
    const _onPwd2 = () => { const p = el('acc-reg-pwd') ? el('acc-reg-pwd').value : ''; const c = el('acc-reg-pwd2') ? el('acc-reg-pwd2').value : ''; setFieldError('acc-reg-pwd2-msg', c && c !== p ? 'Passwords do not match.' : ''); };
    if (el('acc-reg-email')) el('acc-reg-email').addEventListener('input', onEmail);
    if (el('acc-reg-pwd')) el('acc-reg-pwd').addEventListener('input', onPwd);
    if (el('acc-reg-pwd2')) el('acc-reg-pwd2').addEventListener('input', _onPwd2);
    // Conditional company fields.
    ['acc-current-dev-yes', 'acc-current-dev-no', 'acc-project-use', 'acc-primary-role'].forEach(id => {
      const e = el(id); if (e) e.addEventListener('change', _updateConditionalFields);
    });
    // Enter advances / submits.
    document.querySelectorAll('#acc-panel-register input').forEach(inp => {
      inp.addEventListener('input', () => saveDraft(false));
      inp.addEventListener('change', () => saveDraft(false));
      inp.addEventListener('keydown', ev => {
        if (ev.key !== 'Enter') return;
        ev.preventDefault();
        if (_regStep < _REG_STEPS) wizardNext(); else doRegister();
      });
    });
    if (el('acc-notes')) el('acc-notes').addEventListener('input', () => saveDraft(false));
  }

  function collectAccountProfile() {
    const devValue = selectedRadio('acc-current-dev');
    const companyRelevant = _companyFieldsRelevant();
    const profile = {
      currently_developer: devValue === 'yes' ? true : devValue === 'no' ? false : null,
      project_use: fieldValue('acc-project-use'),
      company_name: companyRelevant ? fieldValue('acc-company-name') : '',
      company_size: companyRelevant ? fieldValue('acc-company-size') : 'not_applicable',
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
    if (required.some(key => !profile[key])) return { error: 'Complete the required profile fields.' };
    if (!profile.coding_tools.length) return { error: 'Select at least one main coding tool.' };
    if (!profile.atlas_help.length) return { error: 'Select what you want Atlas to help with most.' };
    if (!profile.company_name) delete profile.company_name;
    if (!profile.languages_frameworks) delete profile.languages_frameworks;
    if (!profile.notes) delete profile.notes;
    return { profile };
  }

  function doRegister() {
    // Re-validate each step; jump to the first incomplete one.
    for (let s = 1; s <= _REG_STEPS - 1; s++) {
      if (!_validateRegStep(s, { quiet: true })) {
        _showRegStep(s);
        _validateRegStep(s);
        return;
      }
    }
    const email = el('acc-reg-email') && el('acc-reg-email').value.trim();
    const password = el('acc-reg-pwd') && el('acc-reg-pwd').value;
    const confirm = el('acc-reg-pwd2') && el('acc-reg-pwd2').value;
    setLoading('acc-reg-btn', true);
    saveDraft(false);
    api('POST', '/api/accounts/register', {
      email,
      password,
      confirm_password: confirm,
    }).then(res => {
      setLoading('acc-reg-btn', false);
      if (res.ok && res.submitted !== false) {
        if (el('acc-reg-pwd')) el('acc-reg-pwd').value = '';
        if (el('acc-reg-pwd2')) el('acc-reg-pwd2').value = '';
        clearDraft();
        _screenMode = 'submitted';
        showAccountScreen('submitted');
        refreshState();
      } else {
        saveDraft(false);
        const err = _formatRegistrationError(res);
        if (err.useSubmitFailedPanel) {
          _showSubmitFailedPanel(err);
        } else {
          setError('acc-reg-error', `${err.message} ${err.detail || ''}`.trim(), err.title);
          if (_regStep < _REG_STEPS) _showRegStep(_REG_STEPS);
        }
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
            <span class="acc-device-name">${_escHtml(d.device_id.substring(0, 8) + 'â€¦')}</span>
            <span class="muted tiny"> â€” ${_escHtml(d.platform || 'unknown')} Â· v${_escHtml(d.app_version || '?')}</span>
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
        ? 'Sign in to unlock'
        : (btn.dataset.origTitle || '');
    });

    _updateAccountChip();
  }

  function _isAdmin() {
    const role = _state && _state.user && _state.user.role;
    return role === 'admin' || role === 'superadmin';
  }

  function _updateAccountChip() {
    const chip = el('accountChip');
    const menu = el('userMenu');
    const summary = el('userMenuSummary');
    const adminEntry = el('userMenuAdmin');
    const accAdminEntry = el('acc-admin-entry');

    // Show the consolidated user menu for any signed-in account (including
    // inactive/rejected) so they always have Account + Sign out and are
    // never dependent on the loose pre-login chip.
    if (!_state || !_state.signed_in) {
      if (chip) { chip.textContent = 'Account'; chip.className = 'account-chip unsigned'; chip.style.display = ''; }
      if (menu) menu.style.display = 'none';
      if (adminEntry) adminEntry.style.display = 'none';
      if (accAdminEntry) accAdminEntry.style.display = 'none';
      return;
    }

    const user = _state.user || {};
    const license = _state.license || {};
    const email = user.email || '';
    const plan = license.plan || 'free';
    const offline = license._offline ? ' (offline)' : '';
    const admin = _isAdmin();

    // Signed in: show the consolidated user menu, hide the loose chip.
    if (chip) { chip.textContent = `${email.split('@')[0]} Â· ${plan}${offline}`; chip.className = 'account-chip signed-in' + (license._offline ? ' offline' : ''); chip.style.display = 'none'; }
    if (menu) menu.style.display = '';
    if (summary) summary.textContent = `${email.split('@')[0]}${admin ? ' Â· admin' : ''} â–¾`;
    if (adminEntry) adminEntry.style.display = admin ? '' : 'none';
    if (accAdminEntry) accAdminEntry.style.display = admin ? '' : 'none';
    document.body.classList.toggle('role-admin', admin);
  }

  function _populateProfile() {
    if (!_state || !_state.signed_in) return;
    const user = _state.user || {};
    const license = _state.license || {};

    const emailEl = el('acc-profile-email');
    if (emailEl) emailEl.textContent = user.email || 'â€”';

    const planEl = el('acc-profile-plan');
    if (planEl) planEl.textContent = license.plan || 'free';

    const statusEl = el('acc-profile-status');
    if (statusEl) statusEl.textContent = license.status || user.status || 'â€”';

    const offlineEl = el('acc-profile-offline');
    if (offlineEl) {
      if (license._offline) {
        const h = license._offline_grace_remaining_hours;
        offlineEl.textContent = `Offline â€” ${h != null ? h + ' hrs grace remaining' : 'grace period active'}`;
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

  // Re-check account status against the server without sign out / sign in.
  function refreshStatus() {
    const btn = el('statusRefreshBtn');
    let orig;
    if (btn) { orig = btn.textContent; btn.disabled = true; btn.textContent = 'Checkingâ€¦'; }
    return refreshState().then(() => {
      if (_state && _state.authenticated) {
        _enterApp({ goHome: true });
        _renderHomeDashboard();
        if (typeof toast === 'function') toast('Your Atlas account is now active ðŸŽ‰', 'success');
      } else {
        const status = _accountStatus();
        _renderStatusDashboard(status);
        _renderHomeDashboard();
        if (typeof toast === 'function') toast('Status checked â€” no change yet.', 'info');
      }
    }).finally(() => {
      if (btn) { btn.disabled = false; btn.textContent = orig || 'Refresh account status'; }
    });
  }

  function reapply() {
    if (typeof toast === 'function') toast('Reapplying will be available in a future release.', 'info');
  }

  // User-menu "Devices": open the account view and bring the device list into view.
  function openDevices() {
    if (typeof go === 'function') go('accounts');
    refreshState().then(() => _populateProfile());
    setTimeout(() => {
      const list = el('acc-device-list');
      if (list && list.scrollIntoView) { try { list.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {} }
    }, 150);
  }

  function init() {
    restoreDraft();
    refreshState().finally(() => {
      document.body.classList.remove('auth-loading');
    });
    _startPolling();

    const chip = el('accountChip');
    if (chip) chip.addEventListener('click', openAccountScreen);

    document.addEventListener('atlas:viewchange', e => {
      if (!e.detail) return;
      if (e.detail.view === 'accounts') {
        refreshState().then(() => _populateProfile());
      } else if (e.detail.view === 'home') {
        _renderHomeDashboard();
      } else if (e.detail.view === 'status') {
        _renderStatusDashboard(_accountStatus());
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
    wizardNext: wizardNext,
    wizardBack: wizardBack,
    saveDraft: () => saveDraft(true),
    retrySubmit: retrySubmit,
    restoreDraft: restoreDraft,
    refresh: refreshState,
    refreshStatus: refreshStatus,
    reapply: reapply,
    openDevices: openDevices,
    accountStatus: _accountStatus,
    isAuthenticated: () => !!( _state && _state.authenticated),
    isSignedIn: () => !!( _state && _state.signed_in),
    isAdmin: _isAdmin,
    requireAccess: () => {
      if (_state && _state.authenticated) return true;
      // Signed-in but not-active users are kept inside the app on their status
      // dashboard rather than bounced to a pre-login wall.
      if (_state && _state.signed_in && _accountStatus() !== 'blocked') {
        _enterApp({ goHome: false });
        _renderStatusDashboard(_accountStatus());
        if (typeof go === 'function') go('status');
        return false;
      }
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
