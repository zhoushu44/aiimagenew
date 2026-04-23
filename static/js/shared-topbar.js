(() => {
  const TOPBAR_CONFIG = {
    landing: {
      homeLabel: 'AIC',
      homeHref: '/',
      kicker: 'Minimal Commerce Console',
      title: 'AI 电商视觉控制台',
      actions: [
        { kind: 'pill', text: 'One-screen entry' },
        { kind: 'link', text: '登录 / 注册', href: '/auth', className: 'btn ghost' },
      ],
    },
    suite: {
      homeLabel: 'AI Commerce Console',
      homeHref: '/',
      kicker: 'Suite Workspace / Minimal Tech Control',
      title: '商品套图工作台',
      actions: [
        { kind: 'pill', text: 'Workspace' },
        { kind: 'link', text: '登录 / 注册', href: '/auth', className: 'btn ghost' },
      ],
    },
    aplus: {
      homeLabel: 'AI Commerce Console',
      homeHref: '/',
      kicker: 'A+ Workspace / Minimal Tech Control',
      title: 'A+详情页工作台',
      actions: [
        { kind: 'pill', text: 'Workspace' },
        { kind: 'link', text: '登录 / 注册', href: '/auth', className: 'btn ghost' },
      ],
    },
    fashion: {
      homeLabel: 'AI Commerce Console',
      homeHref: '/',
      kicker: 'Fashion Workspace / Minimal Tech Control',
      title: '服饰穿戴工作台',
      actions: [
        { kind: 'pill', text: 'Workspace' },
        { kind: 'link', text: '登录 / 注册', href: '/auth', className: 'btn ghost' },
      ],
    },
    auth: {
      homeLabel: 'AI Commerce Console',
      homeHref: '/',
      kicker: 'Account Access / Minimal Tech Control',
      title: '登录 / 注册',
      actions: [
        { kind: 'pill', text: 'Secure sign-in' },
        { kind: 'link', text: '返回首页', href: '/', className: 'btn ghost' },
      ],
    },
    settings: {
      homeLabel: 'AI Commerce Console',
      homeHref: '/',
      kicker: 'Protected Admin Screen / Minimal Tech Control',
      title: 'API Settings',
      actions: [
        { kind: 'pill', text: 'Admin' },
        { kind: 'link', text: '返回首页', href: '/', className: 'btn ghost' },
      ],
    },
  };

  const PATH_TO_MODE = {
    '/': 'landing',
    '/suite': 'suite',
    '/aplus': 'aplus',
    '/fashion': 'fashion',
    '/auth': 'auth',
    '/settings': 'settings',
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

      const link = document.createElement('a');
      link.className = action.className || 'btn ghost';
      link.href = action.href;
      link.textContent = action.text;
      if (action.target) link.target = action.target;
      if (action.rel) link.rel = action.rel;
      meta.appendChild(link);
    }
  }

  function init() {
    const config = TOPBAR_CONFIG[getMode()] || TOPBAR_CONFIG.landing;
    document.querySelectorAll('[data-shared-topbar]').forEach((topbar) => {
      populateTopbar(topbar, config);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
