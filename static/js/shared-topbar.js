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
    '/settings': 'settings',
  };

  const ACCOUNT_PANEL_ID = 'shared-account-panel';
  const ACCOUNT_LOGIN_MODAL_ID = 'shared-login-modal';
  const ACCOUNT_STYLE_ID = 'shared-account-panel-styles';
  const SUPABASE_URL = 'https://spb-kemqk3h0a423q1q5.supabase.opentrust.net';
  const SUPABASE_ANON_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNwYi1rZW1xazNoMGE0MjNxMXE1IiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NzYyNjcxMjUsImV4cCI6MjA5MTg0MzEyNX0.hKFA4d_dQwbecO8t0na0DptshXQNHTSEQ5E2VAd3o18';
  const LOGIN_COUNTDOWN_SECONDS = 60;

  const accountState = {
    open: false,
    loginOpen: false,
    loading: false,
    session: null,
    points: null,
    panel: null,
    dialog: null,
    loginModal: null,
    loginDialog: null,
    loginPhoneInput: null,
    supabaseClient: null,
    supabaseClientPromise: null,
    registerCountdown: 0,
    registerTimer: null,
    smsCountdown: 0,
    smsTimer: null,
    authBusy: false,
    registerBusy: false,
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

  function maskPhoneDisplay(phone) {
    const digits = String(phone || '').replace(/\D/g, '');
    if (digits.length >= 7) {
      return `${digits.slice(0, 3)}****${digits.slice(-4)}`;
    }
    return phone || '';
  }

  function getSessionUserPhone(session) {
    const user = session?.user || {};
    const metadata = user.user_metadata || {};
    const identities = Array.isArray(user.identities) ? user.identities : [];
    const identityDataList = identities
      .map((item) => item?.identity_data || {})
      .filter((item) => item && typeof item === 'object');
    return user.phone
      || metadata.phone
      || metadata.phone_number
      || identityDataList.map((item) => item.phone || item.phone_number).find(Boolean)
      || '';
  }

  function getSessionUserUid(session) {
    return session?.user?.id || '';
  }

  function getSessionUserDisplay(session) {
    const phone = getSessionUserPhone(session);
    if (phone) {
      return {
        phone,
        displayPhone: String(phone),
      };
    }

    const fallback = normalizeSessionUserLabel(session);
    return {
      phone: '',
      displayPhone: fallback || '已登录用户',
    };
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

      .shared-account-panel[hidden],
      .shared-login-modal[hidden] {
        display: none !important;
      }

      .shared-login-modal {
        position: fixed;
        inset: 0;
        z-index: 180;
        display: grid;
        place-items: center;
        padding: 20px;
        background: rgba(15, 23, 42, 0.36);
        backdrop-filter: blur(8px);
      }

      .shared-login-modal__dialog {
        position: relative;
        width: 800px;
        height: 500px;
        max-width: calc(100vw - 24px);
        max-height: calc(100dvh - 24px);
        overflow: hidden;
        border-radius: 10px;
        background: #fff;
        box-shadow: 0 24px 80px rgba(15, 23, 42, 0.28);
        display: grid;
        grid-template-columns: 300px minmax(0, 1fr);
        outline: none;
      }

      .shared-login-modal__close {
        position: absolute;
        top: 14px;
        right: 15px;
        width: 34px;
        height: 34px;
        border: 0;
        background: transparent;
        color: #9ca3af;
        font-size: 30px;
        line-height: 1;
        cursor: pointer;
        z-index: 2;
      }

      .shared-login-modal__left {
        min-height: 500px;
        border-radius: 10px 0 0 10px;
        background:
          radial-gradient(circle at top, rgba(96, 165, 250, 0.24), transparent 44%),
          linear-gradient(160deg, #0f172a 0%, #162447 48%, #1d4ed8 100%);
        color: #fff;
        padding: 54px 40px 46px;
        display: grid;
        align-content: space-between;
        gap: 32px;
      }

      .shared-login-modal__brand {
        display: grid;
        gap: 12px;
      }

      .shared-login-modal__brand-name {
        margin: 0;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: lowercase;
      }

      .shared-login-modal__brand-tag {
        margin: 0;
        color: rgba(255, 255, 255, 0.72);
        font-size: 13px;
        line-height: 1.6;
      }

      .shared-login-modal__left-copy {
        display: grid;
        gap: 18px;
      }

      .shared-login-modal__left-title {
        margin: 0;
        font-size: 36px;
        font-weight: 800;
        line-height: 1.18;
        letter-spacing: -0.03em;
      }

      .shared-login-modal__left-list {
        display: grid;
        gap: 10px;
        padding: 0;
        margin: 0;
        list-style: none;
      }

      .shared-login-modal__left-list li {
        position: relative;
        padding-left: 18px;
        color: rgba(255, 255, 255, 0.86);
        font-size: 14px;
        line-height: 1.7;
      }

      .shared-login-modal__left-list li::before {
        content: "";
        position: absolute;
        left: 0;
        top: 10px;
        width: 6px;
        height: 6px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.82);
      }

      .shared-login-modal__pages {
        position: relative;
        padding: 58px 94px 26px;
        display: grid;
        align-content: start;
        color: #0f1729;
      }

      .shared-login-modal__view {
        min-height: 344px;
      }

      .shared-login-modal__view[data-login-view="register"] {
        margin-top: -14px;
      }

      .shared-login-modal__title {
        margin: 0 0 30px;
        text-align: center;
        color: #0f1729;
        font-size: 24px;
        font-weight: 800;
        line-height: 32px;
      }

      .shared-login-modal__form {
        display: grid;
        gap: 0;
      }

      .shared-login-modal__form--register {
        gap: 0;
      }

      .shared-login-modal__field {
        display: grid;
        gap: 4px;
      }

      .shared-login-modal__error {
        min-height: 18px;
        color: #dc2626;
        font-size: 12px;
        line-height: 18px;
      }

      .shared-login-modal__status {
        min-height: 20px;
        margin-top: 8px;
        text-align: center;
        color: #8f98a7;
        font-size: 12px;
        line-height: 20px;
      }

      .shared-login-modal__status.is-error {
        color: #dc2626;
      }

      .shared-login-modal__status.is-success {
        color: #16a34a;
      }

      .shared-login-modal__input-row {
        height: 46px;
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        border-bottom: 1px solid #e5e7eb;
        color: #111827;
      }

      .shared-login-modal__country {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding-right: 16px;
        color: #111827;
        font-size: 14px;
      }

      select.shared-login-modal__country {
        max-width: 116px;
        border: 0;
        outline: 0;
        background: transparent;
        cursor: pointer;
        appearance: none;
      }

      .shared-login-modal__input-row input {
        width: 100%;
        border: 0;
        outline: 0;
        background: transparent;
        color: #111827;
        font-size: 14px;
      }

      .shared-login-modal__input-row input::placeholder {
        color: #b7beca;
      }

      .shared-login-modal__code-button {
        border: 0;
        background: transparent;
        color: #111827;
        font-size: 14px;
        cursor: pointer;
        padding-left: 18px;
      }

      .shared-login-modal__submit {
        height: 46px;
        margin-top: 24px;
        border: 0;
        border-radius: 999px;
        background: #bfc1c6;
        color: #fff;
        font-size: 16px;
        cursor: not-allowed;
      }

      .shared-login-modal__submit:not(:disabled) {
        background: #111827;
        cursor: pointer;
        box-shadow: 0 12px 24px rgba(17, 24, 39, 0.16);
      }

      .shared-login-modal__submit--register {
        margin-top: 10px;
      }

      .shared-login-modal__password-link {
        margin-top: 18px;
        border: 0;
        background: transparent;
        text-align: center;
        color: #a2a9b5;
        text-decoration: none;
        font-size: 14px;
        cursor: pointer;
      }

      .shared-login-modal__footer-links {
        margin-top: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 28px;
      }

      .shared-login-modal__footer-links .shared-login-modal__password-link {
        margin-top: 0;
      }

      .shared-login-modal__eye-button {
        border: 0;
        background: transparent;
        color: #a2a9b5;
        font-size: 18px;
        cursor: pointer;
        padding-left: 18px;
      }

      .shared-login-modal__third-party {
        margin-top: 26px;
        display: grid;
        justify-items: center;
        gap: 14px;
      }

      .shared-login-modal__register-entry {
        border: 0;
        background: transparent;
        color: #111827;
        font-size: 14px;
        cursor: pointer;
      }

      .shared-login-modal__register-entry strong {
        color: #1677ff;
        font-weight: 700;
      }

      .shared-login-modal__agreement {
        margin-top: 4px;
        display: grid;
        grid-template-columns: 18px minmax(0, 1fr);
        align-items: start;
        gap: 8px;
        color: #6b7280;
        font-size: 12px;
        line-height: 18px;
      }

      .shared-login-modal__agreement input {
        width: 16px;
        height: 16px;
        margin: 1px 0 0;
      }

      .shared-login-modal__agreement a {
        color: #1677ff;
        text-decoration: none;
      }

      .shared-login-modal__return-login {
        margin-top: 10px;
        text-align: center;
        color: #8f98a7;
        font-size: 14px;
      }

      .shared-login-modal__return-login button {
        border: 0;
        background: transparent;
        color: #1677ff;
        cursor: pointer;
        font-size: 14px;
      }

      .shared-login-modal__policy {
        position: absolute;
        left: 74px;
        right: 52px;
        bottom: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3px;
        color: #8f98a7;
        font-size: 13px;
        white-space: nowrap;
      }

      .shared-login-modal__checkbox {
        width: 16px;
        height: 16px;
        border: 1px solid #2563eb;
        border-radius: 3px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-right: 3px;
        background: #2563eb;
        color: #fff;
        font-size: 11px;
        line-height: 1;
      }

      .shared-login-modal__checkbox::before {
        content: "✓";
      }

      .shared-login-modal__policy a {
        color: #1677ff;
        text-decoration: none;
      }

      @media (max-width: 760px) {
        .shared-login-modal__dialog {
          width: min(100%, 420px);
          height: auto;
          min-height: 520px;
          grid-template-columns: 1fr;
        }

        .shared-login-modal__left {
          display: none;
        }

        .shared-login-modal__pages {
          padding: 74px 28px 64px;
        }

        .shared-login-modal__policy {
          left: 20px;
          right: 20px;
          bottom: 18px;
          flex-wrap: wrap;
          white-space: normal;
        }
      }

      .shared-account-panel__dialog {
        position: relative;
        width: min(100%, 278px);
        max-height: calc(100dvh - 90px);
        overflow: auto;
        border: 1px solid rgba(255, 255, 255, 0.74);
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 18px 46px rgba(15, 23, 42, 0.16);
        border-radius: 18px;
        padding: 11px;
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
        border: 0;
        border-radius: 12px;
        background: transparent;
        padding: 0;
        display: grid;
        gap: 10px;
      }


      .shared-account-panel__logout {
        min-height: 42px;
        border: 1px solid rgba(17, 24, 39, 0.08);
        background: rgba(255, 255, 255, 0.94);
        color: #b91c1c;
        cursor: pointer;
        margin-top: 2px;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        line-height: 1;
      }

      .shared-account-panel__hero {
        grid-template-columns: 32px minmax(0, 1fr);
        align-items: center;
      }

      .shared-account-panel__avatar {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background: #fff;
        border: 1px solid rgba(17, 24, 39, 0.12);
        color: #111827;
        font-family: var(--font-display);
        font-size: 15px;
        line-height: 1;
        flex: 0 0 auto;
        box-shadow: 0 8px 18px rgba(31, 41, 55, 0.08);
      }

      .shared-account-panel__hero-copy {
        min-width: 0;
        display: grid;
        gap: 3px;
      }

      .shared-account-panel__hero-title {
        margin: 0;
        font-family: var(--font-display);
        font-size: 14px;
        line-height: 1.05;
        letter-spacing: -0.03em;
      }

      .shared-account-panel__hero-meta,
      .shared-account-panel__hero-note,
      .shared-account-panel__membership-desc,
      .shared-account-panel__points-note,
      .shared-account-panel__link-note {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.45;
      }

      .shared-account-panel__membership {
        overflow: hidden;
        background: linear-gradient(180deg, #fde7d4 0%, #fdebdc 76%, #fff3e8 100%);
        border: 1px solid rgba(251, 146, 60, 0.14);
        border-radius: 7px;
      }

      .shared-account-panel__membership-head {
        padding: 16px 12px 14px;
        text-align: center;
        display: grid;
        gap: 5px;
      }

      .shared-account-panel__membership-title {
        margin: 0;
        color: #5b341e;
        font-family: var(--font-display);
        font-size: 14px;
        line-height: 1.1;
        letter-spacing: -0.02em;
      }

      .shared-account-panel__membership-desc {
        color: rgba(91, 52, 30, 0.65);
      }

      .shared-account-panel__membership-row {
        display: grid;
        gap: 0;
      }

      .shared-account-panel__membership .btn.primary {
        margin: 3px 16px 14px;
        min-height: 34px;
        border: 0;
        border-radius: 6px;
        background: #2b2622;
        color: #ffe5cd;
        font-family: var(--font-display);
        font-size: 14px;
        cursor: pointer;
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04), 0 9px 18px rgba(43, 38, 34, 0.16);
      }

      .shared-account-panel__membership .btn.primary:hover {
        background: #171412;
      }

      .shared-account-panel__points {
        margin-top: -12px;
        background: linear-gradient(180deg, #f3f1fb 0%, #f7f4ff 100%);
        border: 0;
        border-top: 0;
        border-radius: 0 0 12px 12px;
        padding: 8px 10px 10px;
      }

      .xdesign-user-info-panel__balance {
        width: 100%;
      }

      .xdesign-user-info-panel__balance-item {
        width: 100%;
        display: block;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.92);
        padding: 9px 14px;
        box-sizing: border-box;
      }

      .xdesign-user-info-panel__balance-name {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #3f342b;
      }

      .xdesign-user-info-panel__balance-name.active {
        color: #3f342b;
      }

      .xdesign-user-info-panel__balance-name img {
        width: 14px;
        height: 14px;
        object-fit: contain;
        flex: 0 0 auto;
      }

      .balance-label {
        display: inline-flex;
        align-items: center;
        color: #4b5563;
        font-size: 13px;
        line-height: 1;
      }

      .shared-account-panel__points-head {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
      }

      .shared-account-panel__claim-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 72px;
        height: 28px;
        padding: 0 10px;
        border: 1px solid rgba(29, 78, 216, 0.16);
        border-radius: 999px;
        background: rgba(37, 99, 235, 0.08);
        color: #1d4ed8;
        font-size: 12px;
        font-weight: 600;
        line-height: 1;
        cursor: pointer;
        transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, opacity 0.2s ease;
      }

      .shared-account-panel__claim-button:hover:not(:disabled) {
        background: rgba(37, 99, 235, 0.14);
        border-color: rgba(29, 78, 216, 0.28);
      }

      .shared-account-panel__claim-button:disabled {
        cursor: not-allowed;
        opacity: 0.66;
      }

      .shared-account-panel__claim-button.is-claimed {
        background: rgba(15, 23, 42, 0.06);
        border-color: rgba(15, 23, 42, 0.08);
        color: #6b7280;
      }

      .shared-account-panel__claim-button.is-loading {
        opacity: 0.78;
      }

      .shared-account-panel__claim-status {
        margin-top: 8px;
        min-height: 18px;
        color: #6b7280;
        font-size: 12px;
        line-height: 1.5;
      }

      .shared-account-panel__claim-status.is-success {
        color: #047857;
      }

      .shared-account-panel__claim-status.is-error {
        color: #dc2626;
      }

      .amount-label {
        margin-left: auto;
        display: inline-flex;
        align-items: center;
        color: #1f2937;
        font-size: 20px;
        line-height: 1;
        font-weight: 500;
        letter-spacing: -0.03em;
      }

      .shared-account-panel__points-note {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.45;
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

        .shared-account-panel__membership-row {
          grid-template-columns: 1fr;
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
              <div class="shared-account-panel__avatar" id="shared-account-panel-avatar">账</div>
              <div class="shared-account-panel__hero-copy">
                <div class="shared-account-panel__hero-meta" id="shared-account-panel-meta">立即登录</div>
                <div class="shared-account-panel__hero-note" id="shared-account-panel-note">您还未开通会员</div>
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
              <div class="xdesign-user-info-panel__balance">
                <div class="xdesign-user-info-panel__balance-item clickable">
                  <div class="xdesign-user-info-panel__balance-name active">
                    <img src="https://public.static.meitudata.com/xiuxiu-pc/xdesign-widgets/images/meidouInfo/meidou-icon.svg" alt="">
                    <div class="shared-account-panel__points-head">
                      <span class="balance-label">积分</span>
                      <button class="shared-account-panel__claim-button" type="button" id="shared-account-panel-daily-claim">今日领取</button>
                    </div>
                    <span class="amount-label" id="shared-account-panel-points">0</span>
                  </div>
                </div>
              </div>
              <div class="shared-account-panel__claim-status" id="shared-account-panel-claim-status" aria-live="polite"></div>
            </section>
          </section>

          <button class="shared-account-panel__logout" type="button" id="shared-account-panel-logout" aria-label="前往登录页">登录</button>
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
    accountState.dailyClaimButton = panel.querySelector('#shared-account-panel-daily-claim');
    accountState.claimStatus = panel.querySelector('#shared-account-panel-claim-status');
    accountState.claimBusy = false;
    accountState.pointsNote = null;
    accountState.summary = null;
    accountState.logoutButton = panel.querySelector('#shared-account-panel-logout');

    panel.addEventListener('click', (event) => {
      if (event.target === panel) {
        closeAccountPanel();
      }
    });

    accountState.closeButtons.forEach((button) => {
      button.addEventListener('click', closeAccountPanel);
    });

    accountState.dailyClaimButton?.addEventListener('click', () => {
      void submitDailyClaim();
    });

    return panel;
  }

  function ensureLoginModal() {
    if (accountState.loginModal) {
      return accountState.loginModal;
    }

    ensureStyles();

    const modal = document.createElement('div');
    modal.id = ACCOUNT_LOGIN_MODAL_ID;
    modal.className = 'shared-login-modal';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="shared-login-modal__dialog meitu-account-view meitu-account-login-popup-main meitu-account-login-popup-main-zh-Hans" role="dialog" aria-modal="true" aria-label="欢迎登录 aiimg" tabindex="-1">
        <button class="shared-login-modal__close" type="button" data-login-modal-close aria-label="关闭登录弹窗">×</button>
        <div class="shared-login-modal__left meitu-account-view meitu-account-login-popup-left" aria-hidden="true">
          <div class="shared-login-modal__brand">
            <p class="shared-login-modal__brand-name">aiimg</p>
            <p class="shared-login-modal__brand-tag">ai image workspace</p>
          </div>
          <div class="shared-login-modal__left-copy">
            <h3 class="shared-login-modal__left-title">一站式 AI 出图空间</h3>
          </div>
        </div>
        <div class="shared-login-modal__pages meitu-account-view meitu-account-login-popup-pages">
          <div class="shared-login-modal__view" data-login-view="sms">
            <h2 class="shared-login-modal__title">欢迎登录 aiimg</h2>
            <form class="shared-login-modal__form meitu-account-form meitu-account-phone-sms-login-view" data-auth-form="sms">
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-phone-input">
                  <span class="shared-login-modal__country">+86⌄</span>
                  <input class="shared-login-modal__phone" type="text" inputmode="numeric" maxlength="11" placeholder="请输入手机号码" autocomplete="tel">
                </div>
                <div class="shared-login-modal__error" data-error-for="sms-phone"></div>
              </div>
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-verify-code-input">
                  <input class="shared-login-modal__sms-code" type="text" inputmode="numeric" maxlength="6" placeholder="请输入验证码" autocomplete="one-time-code">
                  <button class="shared-login-modal__code-button" type="button" data-code-action="sms">获取验证码</button>
                </div>
                <div class="shared-login-modal__error" data-error-for="sms-code"></div>
              </div>
              <button class="shared-login-modal__submit" type="submit" disabled>登录</button>
              <div class="shared-login-modal__status" data-auth-status="sms" aria-live="polite"></div>
              <button class="shared-login-modal__password-link" type="button" data-login-view-switch="password">密码登录</button>
            </form>
          </div>
          <div class="shared-login-modal__view" data-login-view="password" hidden>
            <h2 class="shared-login-modal__title">密码登录</h2>
            <form class="shared-login-modal__form meitu-account-form meitu-account-phone-password-login-view" data-auth-form="password">
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-phone-input">
                  <span class="shared-login-modal__country">+86⌄</span>
                  <input class="shared-login-modal__password-phone" type="text" inputmode="numeric" maxlength="11" placeholder="请输入手机号码" autocomplete="tel">
                </div>
                <div class="shared-login-modal__error" data-error-for="password-phone"></div>
              </div>
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-password-input">
                  <input class="shared-login-modal__password-value" type="password" maxlength="16" placeholder="请输入密码" autocomplete="off">
                  <button class="shared-login-modal__eye-button" type="button" data-password-toggle aria-label="显示或隐藏密码">◌</button>
                </div>
                <div class="shared-login-modal__error" data-error-for="password-value"></div>
              </div>
              <button class="shared-login-modal__submit" type="submit" disabled>登录</button>
              <div class="shared-login-modal__status" data-auth-status="password" aria-live="polite"></div>
              <div class="shared-login-modal__footer-links">
                <button class="shared-login-modal__password-link" type="button" data-login-view-switch="sms">短信验证码登录</button>
                <a class="shared-login-modal__password-link" href="/forget">忘记密码</a>
              </div>
            </form>
          </div>
          <div class="shared-login-modal__view" data-login-view="register" hidden>
            <h2 class="shared-login-modal__title">注册 aiimg 账号</h2>
            <form class="shared-login-modal__form shared-login-modal__form--register meitu-account-form" data-auth-form="register">
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-phone-input">
                  <select class="shared-login-modal__country" aria-label="选择国家或地区" data-register-country>
                    <option value="+86" selected>+86 中国内地</option>
                    <option value="+852">+852 中国香港</option>
                    <option value="+853">+853 中国澳门</option>
                    <option value="+886">+886 中国台湾</option>
                  </select>
                  <input class="shared-login-modal__register-phone" type="text" inputmode="numeric" maxlength="11" placeholder="请输入手机号码" autocomplete="tel">
                </div>
                <div class="shared-login-modal__error" data-error-for="register-phone"></div>
              </div>
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-verify-code-input">
                  <input class="shared-login-modal__register-code" type="text" inputmode="numeric" maxlength="6" placeholder="请输入短信验证码" autocomplete="one-time-code">
                  <button class="shared-login-modal__code-button" type="button" data-code-action="register">获取验证码</button>
                </div>
                <div class="shared-login-modal__error" data-error-for="register-code"></div>
              </div>
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-password-input">
                  <input class="shared-login-modal__register-password" type="password" maxlength="16" placeholder="设置8-16位密码，需包含字母+数字" autocomplete="new-password">
                  <button class="shared-login-modal__eye-button" type="button" data-password-toggle aria-label="显示或隐藏密码">◌</button>
                </div>
                <div class="shared-login-modal__error" data-error-for="register-password"></div>
              </div>
              <div class="shared-login-modal__field">
                <div class="shared-login-modal__input-row meitu-account-input meitu-account-input-bordered meitu-account-password-input">
                  <input class="shared-login-modal__register-confirm" type="password" maxlength="16" placeholder="请再次输入密码" autocomplete="new-password">
                  <button class="shared-login-modal__eye-button" type="button" data-password-toggle aria-label="显示或隐藏密码">◌</button>
                </div>
                <div class="shared-login-modal__error" data-error-for="register-confirm"></div>
              </div>
              <label class="shared-login-modal__agreement">
                <input class="shared-login-modal__register-agreement" type="checkbox">
                <span>我已阅读并同意<a href="https://www.meitu.com/agreements/user-service.html" target="_blank" rel="noreferrer">《用户协议》</a><a href="https://www.meitu.com/agreements/privacy-policy.html" target="_blank" rel="noreferrer">《个人信息保护政策》</a><a href="https://www.meitu.com/agreements/account-rules.html" target="_blank" rel="noreferrer">《账号注册使用规则》</a></span>
              </label>
              <button class="shared-login-modal__submit shared-login-modal__submit--register" type="submit" disabled>立即注册</button>
              <div class="shared-login-modal__status" data-register-status aria-live="polite"></div>
              <div class="shared-login-modal__return-login">已有账号？<button type="button" data-login-view-switch="sms">返回登录</button></div>
            </form>
          </div>
          <div class="shared-login-modal__third-party meitu-account-third-party-login">
            <button class="shared-login-modal__register-entry" type="button" data-login-view-switch="register">还没有账号？<strong>立即注册</strong></button>
          </div>
          <div class="shared-login-modal__policy meitu-account-agreement-policy">
            <span class="shared-login-modal__checkbox" aria-hidden="true"></span>
            <span>我已阅读并同意</span><a href="https://www.meitu.com/agreements/user-service.html" target="_blank" rel="noreferrer">用户协议</a><span>、</span><a href="https://www.meitu.com/agreements/privacy-policy.html" target="_blank" rel="noreferrer">个人信息保护政策</a><span>和</span><a href="https://www.meitu.com/agreements/account-rules.html" target="_blank" rel="noreferrer">账号规则</a>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    accountState.loginModal = modal;
    accountState.loginDialog = modal.querySelector('.shared-login-modal__dialog');
    accountState.loginPhoneInput = modal.querySelector('.shared-login-modal__phone');

    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeLoginModal();
      }
      const switcher = event.target?.closest?.('[data-login-view-switch]');
      if (switcher) {
        event.preventDefault();
        setLoginModalView(switcher.dataset.loginViewSwitch || 'sms');
      }
    });

    modal.querySelectorAll('[data-login-modal-close]').forEach((button) => {
      button.addEventListener('click', closeLoginModal);
    });

    bindRegisterValidation();

    modal.querySelectorAll('[data-code-action="register"]').forEach((button) => {
      button.addEventListener('click', sendRegisterOtp);
    });

    modal.querySelectorAll('[data-code-action="sms"]').forEach((button) => {
      button.addEventListener('click', sendSmsLoginOtp);
    });

    modal.querySelectorAll('.shared-login-modal__form').forEach((form) => {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (form.dataset.authForm === 'register') {
          void submitRegisterForm();
          return;
        }
        if (form.dataset.authForm === 'sms') {
          void submitSmsLoginForm();
          return;
        }
        if (form.dataset.authForm === 'password') {
          void submitPasswordLoginForm();
        }
      });
    });

    return modal;
  }

  function updateAccountTriggers() {
    const isLoggedIn = Boolean(accountState.session);
    const label = isLoggedIn ? '账号面板' : '登录';
    accountState.triggerLabel = label;
    document.querySelectorAll('[data-account-panel-trigger]').forEach((trigger) => {
      trigger.textContent = label;
      trigger.hidden = false;
      trigger.setAttribute('aria-label', isLoggedIn ? '打开账号面板' : '打开登录会员面板');
    });
  }

  function normalizeSessionUserLabel(session) {
    const user = session?.user || {};
    return user.phone || user.email || user.id || '已登录用户';
  }

  function isSupabaseAuthStorageKey(key) {
    const normalizedKey = String(key || '').toLowerCase();
    if (!normalizedKey) {
      return false;
    }
    return normalizedKey === 'supabase.auth.token'
      || normalizedKey.includes('spb-kemqk3h0a423q1q5')
      || (normalizedKey.startsWith('sb-') && normalizedKey.includes('-auth-token'))
      || (normalizedKey.includes('supabase') && normalizedKey.includes('auth'));
  }

  function clearSupabaseBrowserAuthCache() {
    [window.localStorage, window.sessionStorage].forEach((storage) => {
      if (!storage) {
        return;
      }
      try {
        const keys = [];
        for (let index = 0; index < storage.length; index += 1) {
          const key = storage.key(index);
          if (isSupabaseAuthStorageKey(key)) {
            keys.push(key);
          }
        }
        keys.forEach((key) => storage.removeItem(key));
      } catch (error) {
      }
    });
  }

  function clearElement(el) {
    if (!el) return;
    el.innerHTML = '';
  }

  function normalizeDomesticPhone(value) {
    return String(value || '').replace(/\D/g, '').slice(0, 11);
  }

  function isValidDomesticPhone(value) {
    return /^1\d{10}$/.test(String(value || '').trim());
  }

  function isValidOtp(value) {
    return /^\d{6}$/.test(String(value || '').trim());
  }

  function isValidRegisterPassword(value) {
    const password = String(value || '');
    return /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d\S]{8,16}$/.test(password);
  }

  function getLoginModalError(name) {
    return accountState.loginModal?.querySelector(`[data-error-for="${name}"]`) || null;
  }

  function setLoginModalError(name, message) {
    setText(getLoginModalError(name), message || '');
  }

  function setRegisterStatus(message, type = '') {
    const status = accountState.loginModal?.querySelector('[data-register-status]');
    if (!status) {
      return;
    }
    status.textContent = message || '';
    status.className = `shared-login-modal__status${type ? ` is-${type}` : ''}`;
  }

  function getSupabaseClient() {
    if (accountState.supabaseClient) {
      return Promise.resolve(accountState.supabaseClient);
    }
    if (!accountState.supabaseClientPromise) {
      accountState.supabaseClientPromise = import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm').then(({ createClient }) => {
        accountState.supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
          auth: {
            autoRefreshToken: true,
            persistSession: true,
            detectSessionInUrl: true,
          },
        });
        return accountState.supabaseClient;
      });
    }
    return accountState.supabaseClientPromise;
  }

  async function getBrowserSupabaseSession() {
    try {
      const supabase = await getSupabaseClient();
      const { data } = await supabase.auth.getSession();
      return data?.session || null;
    } catch (error) {
      return null;
    }
  }

  async function syncServerSessionFromBrowser() {
    const browserSession = await getBrowserSupabaseSession();
    if (!browserSession) {
      return null;
    }
    await syncLoginModalSession(browserSession);
    accountState.session = browserSession;
    accountState.sessionLoaded = true;
    updateAccountTriggers();
    return browserSession;
  }

  async function requestPointsBalance() {
    const pointsResponse = await fetch('/api/points/balance', {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    });
    const pointsData = await pointsResponse.json().catch(() => ({}));
    return { pointsResponse, pointsData };
  }

  async function loadAccountPoints(force = false) {
    if (!accountState.session) {
      const syncedSession = await syncServerSessionFromBrowser();
      if (!syncedSession) {
        accountState.points = null;
        return null;
      }
    }
    if (accountState.points && !force) {
      return accountState.points;
    }
    try {
      let { pointsResponse, pointsData } = await requestPointsBalance();
      if (pointsResponse.status === 401) {
        await syncServerSessionFromBrowser();
        ({ pointsResponse, pointsData } = await requestPointsBalance());
      }
      if (pointsResponse.ok && pointsData.success) {
        accountState.points = pointsData.points || null;
        return accountState.points;
      }
    } catch (error) {
    }
    accountState.points = null;
    return null;
  }

  async function syncLoginModalSession(session) {
    try {
      await fetch('/api/auth/session-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ session }),
      });
    } catch (error) {
    }
  }

  async function completeLoginModalAuth(session, message) {
    if (!session) {
      throw new Error('认证成功，但未获取到登录会话');
    }
    await syncLoginModalSession(session);
    accountState.session = session;
    accountState.sessionLoaded = true;
    await loadAccountPoints(true);
    updateAccountTriggers();
    renderAccountPanel();
    closeLoginModal();
    closeAccountPanel();
    window.alert(message);
    const next = new URLSearchParams(window.location.search).get('next');
    const target = next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/api/') ? next : '/suite';
    window.location.href = target;
  }

  function getCurrentAuthView() {
    return accountState.loginModal?.querySelector('[data-login-view]:not([hidden])')?.dataset.loginView || 'sms';
  }

  function setAuthStatus(view, message, type = '') {
    const status = accountState.loginModal?.querySelector(`[data-auth-status="${view}"]`);
    if (!status) {
      return;
    }
    status.textContent = message || '';
    status.className = `shared-login-modal__status${type ? ` is-${type}` : ''}`;
  }

  function setClaimStatus(message, type = '') {
    if (!accountState.claimStatus) {
      return;
    }
    accountState.claimStatus.textContent = message || '';
    accountState.claimStatus.className = `shared-account-panel__claim-status${type ? ` is-${type}` : ''}`;
  }

  function isSameLocalDay(dateValue) {
    if (!dateValue) {
      return false;
    }
    const currentDate = new Date();
    const targetDate = new Date(dateValue);
    if (Number.isNaN(targetDate.getTime())) {
      return false;
    }
    return currentDate.getFullYear() === targetDate.getFullYear()
      && currentDate.getMonth() === targetDate.getMonth()
      && currentDate.getDate() === targetDate.getDate();
  }

  function renderDailyClaimButton() {
    const button = accountState.dailyClaimButton;
    if (!button) {
      return;
    }
    const isLoggedIn = Boolean(accountState.session);
    const alreadyClaimed = isSameLocalDay(accountState.points?.last_daily_claim_at);
    const busy = Boolean(accountState.claimBusy);
    button.disabled = busy || alreadyClaimed;
    button.textContent = busy ? '领取中...' : (alreadyClaimed ? '今日已领取' : '今日领取');
    button.classList.toggle('is-loading', busy);
    button.classList.toggle('is-claimed', !busy && alreadyClaimed);
    if (!isLoggedIn) {
      setClaimStatus('登录后可领取每日免费积分');
      return;
    }
    if (alreadyClaimed) {
      setClaimStatus('今日免费积分已领取', 'success');
      return;
    }
    if (!busy && !accountState.claimStatus?.textContent) {
      setClaimStatus('每日可免费领取一次积分');
    }
  }

  async function submitDailyClaim() {
    if (!accountState.session) {
      const syncedSession = await syncServerSessionFromBrowser();
      if (!syncedSession) {
        setClaimStatus('请先登录后再领取', 'error');
        openLoginModal();
        return;
      }
    }
    if (accountState.claimBusy) {
      return;
    }
    if (isSameLocalDay(accountState.points?.last_daily_claim_at)) {
      renderDailyClaimButton();
      return;
    }
    accountState.claimBusy = true;
    renderDailyClaimButton();
    setClaimStatus('正在领取今日免费积分...');
    try {
      let response = await fetch('/api/points/daily-claim', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
        },
        credentials: 'same-origin',
      });
      let result = await response.json().catch(() => ({}));
      if (response.status === 401) {
        await syncServerSessionFromBrowser();
        response = await fetch('/api/points/daily-claim', {
          method: 'POST',
          headers: {
            Accept: 'application/json',
          },
          credentials: 'same-origin',
        });
        result = await response.json().catch(() => ({}));
      }
      if (!response.ok || !result?.success) {
        const message = result?.error || '领取失败，请稍后重试';
        const alreadyClaimed = response.status === 409 || message.includes('已领取');
        if (result?.points && typeof result.points === 'object') {
          accountState.points = result.points;
          window.dispatchEvent(new CustomEvent('shared-points-updated', {
            detail: { points: result.points },
          }));
        } else if (response.status === 401) {
          accountState.points = null;
        }
        if (response.status === 401) {
          setClaimStatus('请先登录后再领取', 'error');
          openLoginModal();
          return;
        }
        setClaimStatus(alreadyClaimed ? '今日免费积分已领取' : message, alreadyClaimed ? 'success' : 'error');
        return;
      }
      if (result?.points && typeof result.points === 'object') {
        accountState.points = result.points;
        window.dispatchEvent(new CustomEvent('shared-points-updated', {
          detail: { points: result.points },
        }));
      } else {
        await loadAccountPoints(true);
      }
      renderAccountPanel();
      setClaimStatus(`领取成功，已到账 ${Number(result?.claimed ?? 0)} 积分`, 'success');
    } catch (error) {
      setClaimStatus(error?.message || '领取失败，请稍后重试', 'error');
    } finally {
      accountState.claimBusy = false;
      renderDailyClaimButton();
    }
  }

  function validateSmsLoginForm(showErrors = true) {
    if (!accountState.loginModal) {
      return false;
    }
    const phone = accountState.loginModal.querySelector('.shared-login-modal__phone')?.value || '';
    const code = accountState.loginModal.querySelector('.shared-login-modal__sms-code')?.value || '';
    const submit = accountState.loginModal.querySelector('[data-auth-form="sms"] .shared-login-modal__submit');
    const phoneError = phone && !isValidDomesticPhone(phone) ? '请输入 11 位中国内地手机号' : '';
    const codeError = code && !isValidOtp(code) ? '验证码需为 6 位纯数字' : '';
    const valid = isValidDomesticPhone(phone) && isValidOtp(code);
    if (showErrors) {
      setLoginModalError('sms-phone', phoneError);
      setLoginModalError('sms-code', codeError);
    }
    if (submit) {
      submit.disabled = !valid || accountState.authBusy;
    }
    renderSmsCountdown();
    return valid;
  }

  function validatePasswordLoginForm(showErrors = true) {
    if (!accountState.loginModal) {
      return false;
    }
    const phone = accountState.loginModal.querySelector('.shared-login-modal__password-phone')?.value || '';
    const password = accountState.loginModal.querySelector('.shared-login-modal__password-value')?.value || '';
    const submit = accountState.loginModal.querySelector('[data-auth-form="password"] .shared-login-modal__submit');
    const phoneError = phone && !isValidDomesticPhone(phone) ? '请输入 11 位中国内地手机号' : '';
    const passwordError = password && password.length < 6 ? '请输入正确的登录密码' : '';
    const valid = isValidDomesticPhone(phone) && password.length >= 6;
    if (showErrors) {
      setLoginModalError('password-phone', phoneError);
      setLoginModalError('password-value', passwordError);
    }
    if (submit) {
      submit.disabled = !valid || accountState.authBusy;
    }
    return valid;
  }

  function renderSmsCountdown() {
    const button = accountState.loginModal?.querySelector('[data-code-action="sms"]');
    if (!button) {
      return;
    }
    if (accountState.smsCountdown > 0) {
      button.disabled = true;
      button.textContent = `重发 ${accountState.smsCountdown}s`;
      return;
    }
    button.disabled = accountState.authBusy;
    button.textContent = '获取验证码';
  }

  function setSmsCountdown(seconds) {
    clearInterval(accountState.smsTimer);
    accountState.smsCountdown = Math.max(0, Number(seconds || 0));
    renderSmsCountdown();
    if (accountState.smsCountdown <= 0) {
      return;
    }
    accountState.smsTimer = window.setInterval(() => {
      accountState.smsCountdown -= 1;
      renderSmsCountdown();
      if (accountState.smsCountdown <= 0) {
        clearInterval(accountState.smsTimer);
        accountState.smsTimer = null;
        renderSmsCountdown();
      }
    }, 1000);
  }

  async function sendSmsLoginOtp() {
    const modal = accountState.loginModal;
    const phoneInput = modal?.querySelector('.shared-login-modal__phone');
    const phone = phoneInput?.value || '';
    if (!isValidDomesticPhone(phone)) {
      setLoginModalError('sms-phone', '请输入 11 位中国内地手机号');
      window.alert('手机号格式错误，请输入 11 位中国内地手机号');
      phoneInput?.focus();
      return;
    }
    if (accountState.smsCountdown > 0 || accountState.authBusy) {
      return;
    }
    accountState.authBusy = true;
    renderSmsCountdown();
    setAuthStatus('sms', '');
    try {
      const supabase = await getSupabaseClient();
      const { error } = await supabase.auth.signInWithOtp({ phone: `+86${phone}` });
      if (error) {
        throw error;
      }
      setSmsCountdown(LOGIN_COUNTDOWN_SECONDS);
      setAuthStatus('sms', '验证码已发送，请查收短信', 'success');
      modal.querySelector('.shared-login-modal__sms-code')?.focus();
    } catch (error) {
      setAuthStatus('sms', error.message || '验证码发送失败，请稍后重试', 'error');
    } finally {
      accountState.authBusy = false;
      validateSmsLoginForm(true);
    }
  }

  async function submitSmsLoginForm() {
    const modal = accountState.loginModal;
    if (!validateSmsLoginForm(true)) {
      setAuthStatus('sms', '请填写正确的手机号和 6 位验证码', 'error');
      return;
    }
    const phone = modal.querySelector('.shared-login-modal__phone')?.value || '';
    const code = modal.querySelector('.shared-login-modal__sms-code')?.value || '';
    accountState.authBusy = true;
    validateSmsLoginForm(true);
    setAuthStatus('sms', '正在登录...');
    let verifyError = null;
    try {
      const supabase = await getSupabaseClient();
      let session = null;
      const { data, error } = await supabase.auth.verifyOtp({ phone: `+86${phone}`, token: code, type: 'sms' });
      if (!error) {
        session = data?.session || (await supabase.auth.getSession()).data.session || null;
      } else {
        verifyError = error;
      }
      if (!session) {
        const payload = await verifySmsOtpByHttp(phone, code);
        session = {
          access_token: payload.access_token,
          refresh_token: payload.refresh_token,
          token_type: payload.token_type,
          expires_in: payload.expires_in,
          expires_at: payload.expires_at,
          user: payload.user || null,
        };
      }
      await completeLoginModalAuth(session, '登录成功');
    } catch (error) {
      const message = error?.message || verifyError?.message || '验证码过期 / 错误，请重新获取';
      setAuthStatus('sms', message, 'error');
    } finally {
      accountState.authBusy = false;
      validateSmsLoginForm(true);
    }
  }

  async function submitPasswordLoginForm() {
    const modal = accountState.loginModal;
    if (!validatePasswordLoginForm(true)) {
      setAuthStatus('password', '请填写正确的手机号和密码', 'error');
      return;
    }
    const phone = modal.querySelector('.shared-login-modal__password-phone')?.value || '';
    const password = modal.querySelector('.shared-login-modal__password-value')?.value || '';
    accountState.authBusy = true;
    validatePasswordLoginForm(true);
    setAuthStatus('password', '正在登录...');
    try {
      const supabase = await getSupabaseClient();
      const { data, error } = await supabase.auth.signInWithPassword({ phone: `+86${phone}`, password });
      if (error) {
        throw error;
      }
      const session = data?.session || (await supabase.auth.getSession()).data.session;
      await completeLoginModalAuth(session, '登录成功');
    } catch (error) {
      setAuthStatus('password', error.message || '手机号或密码错误', 'error');
    } finally {
      accountState.authBusy = false;
      validatePasswordLoginForm(true);
    }
  }

  function renderRegisterCountdown() {
    const button = accountState.loginModal?.querySelector('[data-code-action="register"]');
    if (!button) {
      return;
    }
    if (accountState.registerCountdown > 0) {
      button.disabled = true;
      button.textContent = `重发 ${accountState.registerCountdown}s`;
      return;
    }
    button.disabled = accountState.registerBusy;
    button.textContent = '获取验证码';
  }

  function setRegisterCountdown(seconds) {
    clearInterval(accountState.registerTimer);
    accountState.registerCountdown = Math.max(0, Number(seconds || 0));
    renderRegisterCountdown();
    if (accountState.registerCountdown <= 0) {
      return;
    }
    accountState.registerTimer = window.setInterval(() => {
      accountState.registerCountdown -= 1;
      renderRegisterCountdown();
      if (accountState.registerCountdown <= 0) {
        clearInterval(accountState.registerTimer);
        accountState.registerTimer = null;
        renderRegisterCountdown();
      }
    }, 1000);
  }

  function validateRegisterForm(showErrors = true) {
    if (!accountState.loginModal) {
      return false;
    }
    const phone = accountState.loginModal.querySelector('.shared-login-modal__register-phone')?.value || '';
    const code = accountState.loginModal.querySelector('.shared-login-modal__register-code')?.value || '';
    const password = accountState.loginModal.querySelector('.shared-login-modal__register-password')?.value || '';
    const confirm = accountState.loginModal.querySelector('.shared-login-modal__register-confirm')?.value || '';
    const agreed = Boolean(accountState.loginModal.querySelector('.shared-login-modal__register-agreement')?.checked);
    const submit = accountState.loginModal.querySelector('[data-auth-form="register"] .shared-login-modal__submit');
    const phoneError = phone && !isValidDomesticPhone(phone) ? '请输入 11 位中国内地手机号' : '';
    const codeError = code && !isValidOtp(code) ? '验证码需为 6 位纯数字' : '';
    const passwordError = password && !isValidRegisterPassword(password) ? '密码需为 8-16 位，且包含字母和数字' : '';
    const confirmError = confirm && password !== confirm ? '两次密码不一致' : '';
    const valid = isValidDomesticPhone(phone) && isValidOtp(code) && isValidRegisterPassword(password) && password === confirm && agreed;
    if (showErrors) {
      setLoginModalError('register-phone', phoneError);
      setLoginModalError('register-code', codeError);
      setLoginModalError('register-password', passwordError);
      setLoginModalError('register-confirm', confirmError);
    }
    if (submit) {
      submit.disabled = !valid || accountState.registerBusy;
    }
    renderRegisterCountdown();
    return valid;
  }

  function bindRegisterValidation() {
    const modal = accountState.loginModal;
    if (!modal) {
      return;
    }
    modal.querySelectorAll('.shared-login-modal__phone, .shared-login-modal__password-phone, .shared-login-modal__register-phone').forEach((input) => {
      input.addEventListener('input', () => {
        input.value = normalizeDomesticPhone(input.value);
        if (input.classList.contains('shared-login-modal__register-phone')) {
          validateRegisterForm(true);
        }
        if (input.classList.contains('shared-login-modal__phone')) {
          validateSmsLoginForm(true);
        }
        if (input.classList.contains('shared-login-modal__password-phone')) {
          validatePasswordLoginForm(true);
        }
      });
    });
    modal.querySelectorAll('.shared-login-modal__sms-code, .shared-login-modal__register-code').forEach((input) => {
      input.addEventListener('input', () => {
        input.value = String(input.value || '').replace(/\D/g, '').slice(0, 6);
        if (input.classList.contains('shared-login-modal__register-code')) {
          validateRegisterForm(true);
        }
        if (input.classList.contains('shared-login-modal__sms-code')) {
          validateSmsLoginForm(true);
        }
      });
    });
    modal.querySelectorAll('.shared-login-modal__register-password, .shared-login-modal__register-confirm, .shared-login-modal__register-agreement').forEach((input) => {
      input.addEventListener('input', () => validateRegisterForm(true));
      input.addEventListener('change', () => validateRegisterForm(true));
    });
    modal.querySelectorAll('.shared-login-modal__password-value').forEach((input) => {
      input.addEventListener('input', () => validatePasswordLoginForm(true));
      input.addEventListener('change', () => validatePasswordLoginForm(true));
    });
    modal.querySelectorAll('[data-password-toggle]').forEach((button) => {
      button.addEventListener('click', () => {
        const input = button.parentElement?.querySelector('input');
        if (!input) {
          return;
        }
        input.type = input.type === 'password' ? 'text' : 'password';
        button.textContent = input.type === 'password' ? '◌' : '●';
      });
    });
  }

  async function sendRegisterOtp() {
    const modal = accountState.loginModal;
    const phoneInput = modal?.querySelector('.shared-login-modal__register-phone');
    const phone = phoneInput?.value || '';
    if (!isValidDomesticPhone(phone)) {
      setLoginModalError('register-phone', '请输入 11 位中国内地手机号');
      window.alert('手机号格式错误，请输入 11 位中国内地手机号');
      phoneInput?.focus();
      return;
    }
    if (accountState.registerCountdown > 0 || accountState.registerBusy) {
      return;
    }
    accountState.registerBusy = true;
    renderRegisterCountdown();
    setRegisterStatus('');
    try {
      const supabase = await getSupabaseClient();
      const { error } = await supabase.auth.signInWithOtp({ phone: `+86${phone}` });
      if (error) {
        throw error;
      }
      setRegisterCountdown(LOGIN_COUNTDOWN_SECONDS);
      setRegisterStatus('验证码已发送，请查收短信', 'success');
      modal.querySelector('.shared-login-modal__register-code')?.focus();
    } catch (error) {
      setRegisterStatus(error.message || '验证码发送失败，请稍后重试', 'error');
    } finally {
      accountState.registerBusy = false;
      validateRegisterForm(true);
    }
  }

  async function submitRegisterForm() {
    const modal = accountState.loginModal;
    if (!validateRegisterForm(true)) {
      setRegisterStatus('请按要求完整填写注册信息并勾选协议', 'error');
      return;
    }
    const phone = modal.querySelector('.shared-login-modal__register-phone')?.value || '';
    const code = modal.querySelector('.shared-login-modal__register-code')?.value || '';
    const password = modal.querySelector('.shared-login-modal__register-password')?.value || '';
    accountState.registerBusy = true;
    validateRegisterForm(true);
    setRegisterStatus('正在验证验证码并创建账号...');
    try {
      const supabase = await getSupabaseClient();
      const { data: otpData, error: otpError } = await supabase.auth.verifyOtp({ phone: `+86${phone}`, token: code, type: 'sms' });
      if (otpError) {
        throw new Error(otpError.message || '验证码过期或错误，请重新获取');
      }
      const session = otpData?.session || (await supabase.auth.getSession()).data.session;
      if (!session) {
        throw new Error('验证码已通过，但未获取到登录会话');
      }
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) {
        const message = String(updateError.message || '');
        if (message.toLowerCase().includes('already') || message.includes('registered')) {
          const goLogin = window.confirm('该手机号已有账号，是否直接去登录？');
          if (goLogin) {
            setLoginModalView('sms');
          }
          return;
        }
        throw updateError;
      }
      await completeLoginModalAuth(session, '注册成功，已自动登录');
    } catch (error) {
      const message = error.message || '注册失败，请稍后重试';
      if (message.includes('already') || message.includes('registered') || message.includes('User already')) {
        const goLogin = window.confirm('该手机号已有账号，是否直接去登录？');
        if (goLogin) {
          setLoginModalView('sms');
        }
        return;
      }
      setRegisterStatus(message.includes('token') || message.includes('验证码') ? '验证码过期 / 错误，请重新获取' : message, 'error');
    } finally {
      accountState.registerBusy = false;
      validateRegisterForm(true);
    }
  }

  function renderAccountPanel() {
    if (!accountState.panel) {
      return;
    }

    const session = accountState.session;
    const isLoggedIn = Boolean(session);
    const userDisplay = getSessionUserDisplay(session);
    const displayPhone = userDisplay.displayPhone || '立即登录';
    const userUid = getSessionUserUid(session);

    const pointsBalance = isLoggedIn ? Number(accountState.points?.balance || 0) : 0;

    setText(accountState.avatar, '账');
    setText(accountState.meta, isLoggedIn ? displayPhone : '立即登录');
    accountState.meta?.classList.toggle('is-primary', !isLoggedIn);
    setText(accountState.note, isLoggedIn ? `用户UID：${userUid || '暂无 UID'}` : '您还未开通会员');
    setText(accountState.pointsValue, String(Number.isFinite(pointsBalance) ? pointsBalance : 0));

    if (!accountState.claimBusy) {
      if (!isLoggedIn) {
        setClaimStatus('登录后可领取每日免费积分');
      } else if (isSameLocalDay(accountState.points?.last_daily_claim_at)) {
        setClaimStatus('今日免费积分已领取', 'success');
      } else {
        setClaimStatus('每日可免费领取一次积分');
      }
    }
    renderDailyClaimButton();

    if (accountState.logoutButton) {
      accountState.logoutButton.hidden = false;
      accountState.logoutButton.textContent = isLoggedIn ? '退出登录' : '登录';
      accountState.logoutButton.setAttribute('aria-label', isLoggedIn ? '退出登录' : '前往登录页');
      accountState.logoutButton.onclick = async () => {
        if (!accountState.logoutButton) {
          return;
        }
        if (!accountState.session) {
          openLoginModal();
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
          clearSupabaseBrowserAuthCache();
          accountState.session = null;
          accountState.points = null;
          accountState.sessionLoaded = true;
          accountState.claimBusy = false;
          updateAccountTriggers();
          renderAccountPanel();
          closeAccountPanel();
          openLoginModal();
        } finally {
          accountState.logoutButton.disabled = false;
        }
      };
    }

    accountState.panel.hidden = !accountState.open;
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

    accountState.session = sessionData.authenticated
      ? { ...(sessionData.session || {}), user: sessionData.user || sessionData.session?.user || null }
      : null;

    if (!accountState.session) {
      const browserSession = await syncServerSessionFromBrowser();
      accountState.session = browserSession;
    }

    accountState.points = null;

    if (accountState.session) {
      await loadAccountPoints(true);
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


  function setLoginModalView(view) {
    ensureLoginModal();
    const nextView = ['password', 'register'].includes(view) ? view : 'sms';
    accountState.loginModal.querySelectorAll('[data-login-view]').forEach((el) => {
      el.hidden = el.dataset.loginView !== nextView;
    });
    accountState.loginModal.querySelector('.shared-login-modal__third-party').hidden = nextView === 'register';
    accountState.loginModal.querySelector('.shared-login-modal__policy').hidden = nextView === 'register';
    if (nextView === 'sms') {
      validateSmsLoginForm(true);
      setAuthStatus('sms', '');
    }
    if (nextView === 'password') {
      validatePasswordLoginForm(true);
      setAuthStatus('password', '');
    }
    if (nextView === 'register') {
      validateRegisterForm(true);
      setRegisterStatus('');
    }
    const nextInput = nextView === 'password'
      ? accountState.loginModal.querySelector('.shared-login-modal__password-phone')
      : nextView === 'register'
        ? accountState.loginModal.querySelector('.shared-login-modal__register-phone')
        : accountState.loginPhoneInput;
    window.setTimeout(() => {
      nextInput?.focus();
    }, 0);
  }

  function openLoginModal() {
    ensureLoginModal();
    setLoginModalView('sms');
    accountState.loginOpen = true;
    accountState.loginModal.hidden = false;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => {
      accountState.loginPhoneInput?.focus();
    }, 0);
  }

  function closeLoginModal() {
    if (!accountState.loginModal) {
      return;
    }
    accountState.loginOpen = false;
    accountState.loginModal.hidden = true;
    if (!accountState.open) {
      document.body.style.overflow = '';
    }
    accountState.dialog?.focus();
  }

  function openLoginPage() {
    openLoginModal();
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

    const isLoggedIn = Boolean(accountState.session);

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
        button.textContent = isLoggedIn ? '账号面板' : '登录';
        button.setAttribute('data-account-panel-trigger', 'true');
        button.setAttribute('aria-label', isLoggedIn ? '打开账号面板' : '打开登录会员面板');
        button.hidden = false;
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
      trigger.addEventListener('click', () => {
        openAccountPanel(trigger);
      });
    });
  }

  function bindGlobalEvents() {
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') {
        return;
      }
      if (accountState.loginOpen) {
        closeLoginModal();
        return;
      }
      if (accountState.open) {
        closeAccountPanel();
      }
    });

    window.addEventListener('shared-points-updated', (event) => {
    const nextPoints = event?.detail?.points;
    if (!nextPoints || typeof nextPoints !== 'object') {
      return;
    }
    accountState.points = nextPoints;
    renderAccountPanel();
  });

  document.addEventListener('click', (event) => {
      const trigger = event.target?.closest?.('[data-account-panel-login]');
      if (trigger) {
        event.preventDefault();
        openLoginModal();
      }
    });
  }

  function init() {
    ensureAccountPanel();
    ensureLoginModal();
    const config = TOPBAR_CONFIG[getMode()] || TOPBAR_CONFIG.landing;
    document.querySelectorAll('[data-shared-topbar]').forEach((topbar) => {
      populateTopbar(topbar, config);
    });
    wireAccountPanelTriggers();
    bindGlobalEvents();
    void refreshAccountPanel(true).then(() => {
      if (document.body?.dataset.authRequired === 'true' && !accountState.session) {
        openLoginModal();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
