(() => {
  const SHARED_TOPBAR_CONFIG = {
    homeLabel: 'AI Commerce Console',
    homeHref: '/',
    kicker: 'Shared Workspace / Minimal Tech Control',
    title: 'AI 电商视觉控制台',
    actions: [
      { kind: 'pill', text: 'Workspace' },
      { kind: 'account', text: '账号面板' },
    ],
  };

  const TOPBAR_CONFIG = {
    landing: SHARED_TOPBAR_CONFIG,
    suite: SHARED_TOPBAR_CONFIG,
    aplus: SHARED_TOPBAR_CONFIG,
    fashion: SHARED_TOPBAR_CONFIG,
    auth: SHARED_TOPBAR_CONFIG,
    settings: SHARED_TOPBAR_CONFIG,
  };

  const PATH_TO_MODE = {
    '/': 'landing',
    '/suite': 'suite',
    '/aplus': 'aplus',
    '/fashion': 'fashion',
    '/auth': 'auth',
    '/settings': 'settings',
  };

  const ACCOUNT_PANEL_ID = 'shared-account-panel';
  const ACCOUNT_STYLE_ID = 'shared-account-panel-styles';

  const accountState = {
    open: false,
    loading: false,
    session: null,
    points: null,
    panel: null,
    dialog: null,
    body: null,
    closeButtons: [],
    loadingView: null,
    emptyView: null,
    signedInView: null,
    pointsGrid: null,
    triggerLabel: '账号面板',
    returnFocusTo: null,
    sessionLoaded: false,
  };

  function getMode() {
    const bodyMode = document.body?.dataset?.pageMode?.trim();
    if (bodyMode && TOPBAR_CONFIG[bodyMode]) {
      return bodyMode;
    }

    const path = `${window.location.pathname}`.replace(/\/+$/, '') || '/';
    return PATH_TO_MODE[path] || 'landing';
  }

  function setText(el, value) {
    if (!el) return;
    el.textContent = value;
  }

  function ensureStyles() {
    if (document.getElementById(ACCOUNT_STYLE_ID)) {
      return;
    }

    const style = document.createElement('style');
    style.id = ACCOUNT_STYLE_ID;
    style.textContent = `
      .shared-account-panel {
        position: fixed;
        inset: 0;
        z-index: 120;
        padding: 72px 18px 18px;
        background: transparent;
        pointer-events: none;
        display: grid;
        justify-items: end;
        align-items: start;
      }

      .shared-account-panel::before {
        content: "";
        position: fixed;
        inset: 0;
        background:
          radial-gradient(circle at 84% 8%, rgba(255, 255, 255, 0.65), transparent 22%),
          linear-gradient(180deg, rgba(15, 23, 42, 0.02), rgba(15, 23, 42, 0.08) 34%, rgba(15, 23, 42, 0.04));
        backdrop-filter: blur(10px);
        pointer-events: auto;
      }

      .shared-account-panel[hidden] {
        display: none !important;
      }

      .shared-account-panel__dialog {
        position: relative;
        width: min(100%, 390px);
        max-height: calc(100dvh - 90px);
        overflow: auto;
        border: 1px solid var(--line);
        background: var(--surface-strong);
        box-shadow: var(--shadow);
        border-radius: var(--radius-xl);
        padding: 14px;
        display: grid;
        gap: 12px;
        outline: none;
        pointer-events: auto;
        z-index: 1;
        transform: translateX(-4px);
      }

      .shared-account-panel__dialog::before {
        content: "";
        position: absolute;
        inset: 0 auto auto 0;
        width: 100%;
        height: 4px;
        border-radius: var(--radius-xl) var(--radius-xl) 0 0;
        background: linear-gradient(90deg, rgba(31, 41, 55, 0.12), rgba(31, 41, 55, 0.03));
        pointer-events: none;
      }

      .shared-account-panel__header {
        position: absolute;
        top: 12px;
        right: 12px;
        z-index: 2;
      }

      .shared-account-panel__close {
        min-width: 36px;
        min-height: 36px;
        padding: 0;
        border-radius: 999px;
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        line-height: 1;
        font-size: 20px;
      }

      .shared-account-panel__status-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        padding: 8px 10px;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(248, 250, 252, 0.9);
      }

      .shared-account-panel__status-pill,
      .shared-account-panel__meta-pill {
        min-height: 30px;
        padding: 0 10px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.8);
        color: var(--muted-strong);
        font-size: 11px;
        white-space: nowrap;
      }

      .shared-account-panel__body {
        display: grid;
        gap: 10px;
      }

      .shared-account-panel__view {
        display: grid;
        gap: 10px;
      }

      .shared-account-panel__loading {
        display: none;
      }

      .shared-account-panel__loading-line.short {
        width: 56%;
      }

      .shared-account-panel__loading-line.tall {
        width: 84%;
        height: 14px;
      }

      @keyframes sharedAccountShimmer {
        0% { background-position: 0% 50%; }
        100% { background-position: 180% 50%; }
      }

      .shared-account-panel__hero,
      .shared-account-panel__membership,
      .shared-account-panel__points,
      .shared-account-panel__logout {
        border: 1px solid var(--line);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.88);
        padding: 13px;
        display: grid;
        gap: 10px;
      }


      .shared-account-panel__logout {
        min-height: 42px;
        border-color: rgba(239, 68, 68, 0.2);
        background: rgba(255, 255, 255, 0.94);
        color: #b91c1c;
        cursor: pointer;
        margin-top: 4px;
        width: 100%;
      }

      .shared-account-panel__hero {
        grid-template-columns: 34px minmax(0, 1fr);
        align-items: center;
      }

      .shared-account-panel__avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background: linear-gradient(135deg, var(--accent), #374151);
        color: #fff;
        font-family: var(--font-display);
        font-size: 15px;
        line-height: 1;
        flex: 0 0 auto;
        box-shadow: 0 8px 18px rgba(31, 41, 55, 0.14);
      }

      .shared-account-panel__hero-copy {
        min-width: 0;
        display: grid;
        gap: 3px;
      }

      .shared-account-panel__hero-title {
        margin: 0;
        font-family: var(--font-display);
        font-size: 18px;
        line-height: 1.05;
        letter-spacing: -0.04em;
      }

      .shared-account-panel__hero-meta,
      .shared-account-panel__hero-note,
      .shared-account-panel__membership-desc,
      .shared-account-panel__points-note,
      .shared-account-panel__link-note {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.5;
      }

      .shared-account-panel__membership {
        background: linear-gradient(180deg, rgba(255, 250, 244, 0.98), rgba(255, 244, 230, 0.94));
        border-color: rgba(245, 158, 11, 0.14);
      }

      .shared-account-panel__membership-head {
        display: grid;
        gap: 5px;
      }

      .shared-account-panel__membership-title {
        margin: 0;
        font-family: var(--font-display);
        font-size: 15px;
        line-height: 1.1;
        letter-spacing: -0.03em;
      }

      .shared-account-panel__membership-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
      }

      .shared-account-panel__membership .btn.primary {
        border-color: #f59e0b;
        background: linear-gradient(135deg, #f59e0b, #fb923c);
        color: #fff;
      }

      .shared-account-panel__points {
        gap: 8px;
      }

      .shared-account-panel__points-summary {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 12px;
        align-items: center;
      }

      .shared-account-panel__points-value {
        margin: 0;
        font-family: var(--font-display);
        font-size: 26px;
        line-height: 0.95;
        letter-spacing: -0.05em;
        color: var(--text);
      }

      .shared-account-panel__points-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-end;
      }

      .shared-account-panel__mini-btn {
        min-height: 34px;
        padding: 0 12px;
        border-radius: 999px;
        border: 1px solid var(--line-strong);
        background: rgba(255, 255, 255, 0.88);
        color: var(--text);
        cursor: pointer;
      }

      .shared-account-panel__links {
        gap: 8px;
      }

      .shared-account-panel__link {
        min-height: 46px;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.86);
        color: var(--text);
        text-decoration: none;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 0 14px;
      }

      .shared-account-panel__link-arrow {
        color: var(--muted);
        font-size: 18px;
        line-height: 1;
      }

      .shared-account-panel__info {
        display: none;
      }

      .shared-account-panel__actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: flex-end;
      }

      .shared-account-panel__actions .btn,
      .shared-account-panel__actions .shared-account-panel__close,
      .shared-account-panel__logout {
        min-height: 40px;
      }

      @media (max-width: 720px) {
        .shared-account-panel {
          padding: 10px;
          justify-items: stretch;
        }

        .shared-account-panel__dialog {
          width: 100%;
          max-height: calc(100dvh - 20px);
          padding: 12px;
          border-radius: 22px;
        }

        .shared-account-panel__membership-row,
        .shared-account-panel__points-summary {
          grid-template-columns: 1fr;
        }

        .shared-account-panel__points-summary {
          align-items: start;
        }

        .shared-account-panel__points-actions {
          justify-content: flex-start;
        }
      }

    `;
    document.head.appendChild(style);
  }

  function ensureAccountPanel() {
    if (accountState.panel) {
      return accountState.panel;
    }

    ensureStyles();

    const panel = document.createElement('div');
    panel.id = ACCOUNT_PANEL_ID;
    panel.className = 'shared-account-panel';
    panel.hidden = true;
    panel.innerHTML = `
      <div class="shared-account-panel__dialog" role="dialog" aria-modal="true" tabindex="-1">
        <div class="shared-account-panel__header">
          <button class="btn ghost shared-account-panel__close" type="button" data-account-panel-close aria-label="关闭账号面板">×</button>
        </div>

        <div class="shared-account-panel__body">
          <section class="shared-account-panel__view" id="shared-account-panel-static-view">
            <section class="shared-account-panel__hero">
              <div class="shared-account-panel__avatar" id="shared-account-panel-avatar">A</div>
              <div class="shared-account-panel__hero-copy">
                <h3 class="shared-account-panel__hero-title" id="shared-account-panel-name">账号面板</h3>
                <div class="shared-account-panel__hero-meta" id="shared-account-panel-meta">登录后可同步会话与积分。</div>
                <div class="shared-account-panel__hero-note" id="shared-account-panel-note">当前面板会在所有页面显示相同内容。</div>
              </div>
            </section>

            <section class="shared-account-panel__membership">
              <div class="shared-account-panel__membership-head">
                <h3 class="shared-account-panel__membership-title">会员套餐和价格</h3>
                <div class="shared-account-panel__membership-desc">登录后即可查看账号权益、同步会话和积分余额。</div>
              </div>
              <div class="shared-account-panel__membership-row">
                <div class="shared-account-panel__link-note">支持从当前入口直接跳转登录。</div>
                <button class="btn primary" type="button" data-account-panel-login id="shared-account-panel-login-link">立即登录</button>
              </div>
            </section>

            <section class="shared-account-panel__points">
              <div class="shared-account-panel__points-summary">
                <div>
                  <div class="shared-account-panel__label">美豆</div>
                  <p class="shared-account-panel__points-value" id="shared-account-panel-points">0</p>
                  <div class="shared-account-panel__points-note" id="shared-account-panel-points-note">余额、充值与明细会在登录后同步。</div>
                </div>
                <div class="shared-account-panel__points-actions">
                  <button class="shared-account-panel__mini-btn" type="button" data-account-panel-login>充值</button>
                  <button class="shared-account-panel__mini-btn" type="button" data-account-panel-login>明细</button>
                </div>
              </div>
              <div class="shared-account-panel__points-note" id="shared-account-panel-summary">登录后可查看更完整的账号信息。</div>
            </section>
          </section>

          <button class="shared-account-panel__logout" type="button" id="shared-account-panel-logout">退出登录</button>
        </div>
      </div>
    `;

    document.body.appendChild(panel);

    accountState.panel = panel;
    accountState.dialog = panel.querySelector('.shared-account-panel__dialog');
    accountState.body = panel.querySelector('.shared-account-panel__body');
    accountState.loadingView = null;
    accountState.emptyView = panel.querySelector('#shared-account-panel-static-view');
    accountState.signedInView = null;
    accountState.pointsGrid = null;
    accountState.closeButtons = Array.from(panel.querySelectorAll('[data-account-panel-close]'));
    accountState.avatar = panel.querySelector('#shared-account-panel-avatar');
    accountState.name = panel.querySelector('#shared-account-panel-name');
    accountState.meta = panel.querySelector('#shared-account-panel-meta');
    accountState.note = panel.querySelector('#shared-account-panel-note');
    accountState.pointsValue = panel.querySelector('#shared-account-panel-points');
    accountState.pointsNote = panel.querySelector('#shared-account-panel-points-note');
    accountState.summary = panel.querySelector('#shared-account-panel-summary');
    accountState.logoutButton = panel.querySelector('#shared-account-panel-logout');

    panel.addEventListener('click', (event) => {
      if (event.target === panel) {
        closeAccountPanel();
      }
    });

    accountState.closeButtons.forEach((button) => {
      button.addEventListener('click', closeAccountPanel);
    });

    accountState.logoutButton?.addEventListener('click', async () => {
      if (!accountState.logoutButton || accountState.logoutButton.hidden) {
        return;
      }
      accountState.logoutButton.disabled = true;
      try {
        const response = await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
          throw new Error(data.error || '退出登录失败');
        }
        accountState.session = null;
        accountState.points = null;
        accountState.sessionLoaded = true;
        updateAccountTriggers();
        renderAccountPanel();
      } finally {
        accountState.logoutButton.disabled = false;
      }
    });

    return panel;
  }

  function updateAccountTriggers() {
    const label = accountState.triggerLabel;
    document.querySelectorAll('[data-account-panel-trigger]').forEach((trigger) => {
      trigger.textContent = label;
      trigger.setAttribute('aria-label', '打开账号面板');
    });
  }

  function normalizeSessionUserLabel(session) {
    const user = session?.user || {};
    return user.phone || user.email || user.id || '已登录用户';
  }

  function clearElement(el) {
    if (!el) return;
    el.innerHTML = '';
  }

  function renderAccountPanel() {
    if (!accountState.panel) {
      return;
    }

    const session = accountState.session;
    const points = accountState.points || {};
    const isLoggedIn = Boolean(session);
    const user = session?.user || {};
    const label = isLoggedIn ? normalizeSessionUserLabel(session) : '账号访客';
    const avatar = label.trim().charAt(0).toUpperCase() || 'A';

    setText(accountState.avatar, avatar);
    setText(accountState.name, label);
    setText(accountState.meta, isLoggedIn ? `UID: ${user.id || '-'}` : '登录后可同步会话与积分。');
    setText(accountState.note, isLoggedIn ? '浏览器会话已与后端同步。' : '当前尚未建立可用会话。');
    setText(accountState.pointsValue, String(Number(points.balance || 0)));
    setText(accountState.pointsNote, isLoggedIn ? '来自 /api/points/balance' : '余额、充值与明细会在登录后同步。');
    setText(accountState.summary, isLoggedIn ? `累计获得 ${Number(points.total_earned || 0)}，累计消耗 ${Number(points.total_spent || 0)}。` : '登录后可查看更完整的账号信息。');

    if (accountState.logoutButton) {
      accountState.logoutButton.hidden = !isLoggedIn;
    }
  }

  async function fetchAccountState() {
    const sessionResponse = await fetch('/api/auth/session', {
      method: 'POST',
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    const sessionData = await sessionResponse.json();
    if (!sessionResponse.ok || !sessionData.success) {
      throw new Error(sessionData.error || '读取会话失败');
    }

    accountState.session = sessionData.authenticated ? (sessionData.session || null) : null;
    accountState.points = null;

    if (accountState.session) {
      try {
        const pointsResponse = await fetch('/api/points/balance', {
          method: 'GET',
          headers: { Accept: 'application/json' },
          credentials: 'same-origin',
        });
        const pointsData = await pointsResponse.json();
        if (pointsResponse.ok && pointsData.success) {
          accountState.points = pointsData.points || null;
        }
      } catch (error) {
        accountState.points = null;
      }
    }

    accountState.sessionLoaded = true;
    updateAccountTriggers();
  }

  async function refreshAccountPanel(silent = false) {
    ensureAccountPanel();
    accountState.loading = true;

    try {
      await fetchAccountState();
      renderAccountPanel();
    } catch (error) {
      accountState.session = null;
      accountState.points = null;
      accountState.sessionLoaded = true;
      updateAccountTriggers();
      renderAccountPanel();
    } finally {
      accountState.loading = false;
      if (accountState.open) {
        accountState.dialog?.focus();
      }
    }
  }


  function openLoginPage() {
    const next = `${window.location.pathname}${window.location.search}` || '/';
    window.location.href = `/auth?next=${encodeURIComponent(next)}`;
  }

  function openAccountPanel(trigger) {
    ensureAccountPanel();
    accountState.returnFocusTo = trigger || document.activeElement;
    accountState.open = true;
    accountState.panel.hidden = false;
    document.body.style.overflow = 'hidden';
    renderAccountPanel();
    accountState.dialog?.focus();
    void refreshAccountPanel(true);
  }

  function closeAccountPanel() {
    if (!accountState.panel) {
      return;
    }
    accountState.open = false;
    accountState.panel.hidden = true;
    document.body.style.overflow = '';
    const returnFocusTo = accountState.returnFocusTo;
    accountState.returnFocusTo = null;
    if (returnFocusTo && typeof returnFocusTo.focus === 'function') {
      returnFocusTo.focus();
    }
  }

  function populateTopbar(topbar, config) {
    const home = topbar.querySelector('[data-topbar-home]');
    const kicker = topbar.querySelector('[data-topbar-kicker]');
    const title = topbar.querySelector('[data-topbar-title]');
    const meta = topbar.querySelector('[data-topbar-meta]');

    if (home) {
      home.textContent = config.homeLabel;
      home.href = config.homeHref;
    }
    setText(kicker, config.kicker);
    setText(title, config.title);

    if (!meta) return;
    meta.innerHTML = '';

    for (const action of config.actions) {
      if (action.kind === 'pill') {
        const pill = document.createElement('span');
        pill.className = 'console-pill';
        pill.textContent = action.text;
        meta.appendChild(pill);
        continue;
      }

      if (action.kind === 'account') {
        const button = document.createElement('button');
        button.className = action.className || 'btn ghost';
        button.type = 'button';
        button.textContent = action.text;
        button.setAttribute('data-account-panel-trigger', 'true');
        button.setAttribute('aria-label', '打开账号面板');
        meta.appendChild(button);
        continue;
      }

      const link = document.createElement('a');
      link.className = action.className || 'btn ghost';
      link.href = action.href;
      link.textContent = action.text;
      if (action.target) link.target = action.target;
      if (action.rel) link.rel = action.rel;
      meta.appendChild(link);
    }
  }


  function wireAccountPanelTriggers() {
    document.querySelectorAll('[data-account-panel-trigger]').forEach((trigger) => {
      trigger.addEventListener('click', () => openAccountPanel(trigger));
    });
  }

  function bindGlobalEvents() {
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && accountState.open) {
        closeAccountPanel();
      }
    });

    document.addEventListener('click', (event) => {
      const trigger = event.target?.closest?.('[data-account-panel-login]');
      if (trigger) {
        event.preventDefault();
        openLoginPage();
      }
    });
  }

  function init() {
    ensureAccountPanel();
    const config = TOPBAR_CONFIG[getMode()] || TOPBAR_CONFIG.landing;
    document.querySelectorAll('[data-shared-topbar]').forEach((topbar) => {
      populateTopbar(topbar, config);
    });
    wireAccountPanelTriggers();
    bindGlobalEvents();
    void refreshAccountPanel(true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
