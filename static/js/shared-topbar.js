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
  const ACCOUNT_VIP_MODAL_ID = 'shared-vip-preview-modal';
  const ACCOUNT_STYLE_ID = 'shared-account-panel-styles';
  const VIP_REFERENCE_IMAGES = [
    {
      title: 'VIP 专属工作台',
      description: '会员可解锁更完整的电商设计工作流与高质感画面模板。',
      eyebrow: 'WORKSPACE',
      metrics: ['模板 120+', '批量任务', '高阶出图'],
    },
    {
      title: '高阶视觉参考',
      description: '通过精选参考图案例，快速了解开通 VIP 后的创作风格与交付效果。',
      eyebrow: 'REFERENCE',
      metrics: ['风格案例', '商业质感', '品牌统一'],
    },
    {
      title: '多端权益展示',
      description: '展示会员权益、专属模板和更顺滑的任务处理体验。',
      eyebrow: 'BENEFITS',
      metrics: ['Web / H5 / 详情页', '专属权益', '稳定协作'],
    },
  ];
  const VIP_PLAN_OPTIONS = [
    {
      key: 'month',
      title: '连续包月',
      price: '30',
      origin: '原价 ¥48',
      unit: '¥1/天',
      badge: '',
      trial: '',
    },
    {
      key: 'year',
      title: '连续包年',
      price: '1.1',
      origin: '原价 ¥358',
      unit: '¥0.6/天',
      badge: '超低价试用',
      trial: '试用 7 天',
    },
    {
      key: 'quarter',
      title: '连续包季',
      price: '68',
      origin: '原价 ¥128',
      unit: '¥0.76/天',
      badge: '',
      trial: '',
    },
  ];

  const runtimeConfig = window.AI_IMAGE_CONFIG || {};
  const SUPABASE_URL = String(runtimeConfig.supabaseUrl || '').trim();
  const SUPABASE_ANON_KEY = String(runtimeConfig.supabaseAnonKey || '').trim();
  const LOGIN_COUNTDOWN_SECONDS = 60;

  const accountState = {
    open: false,
    loginOpen: false,
    vipPreviewOpen: false,
    vipPreviewIndex: 0,
    vipSelectedPlan: 'plan_2',
    vipPlans: [],
    vipPlansLoaded: false,
    vipPlansPromise: null,
    vipPayBusy: false,
    vipCheckoutPending: false,
    vipCheckoutTrigger: null,
    vipCheckoutMessage: '',
    loading: false,
    session: null,
    points: null,
    panel: null,
    dialog: null,
    loginModal: null,
    loginDialog: null,
    vipModal: null,
    vipDialog: null,
    vipImage: null,
    vipTitle: null,
    vipDescription: null,
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

  function getVipPlanList() {
    return Array.isArray(accountState.vipPlans) && accountState.vipPlans.length ? accountState.vipPlans : VIP_PLAN_OPTIONS;
  }

  function normalizeVipPlanValue(value) {
    return value == null ? '' : String(value).trim();
  }

  function buildVipPlansFromConfig(config) {
    if (!config || typeof config !== 'object') {
      return [];
    }
    return [1, 2, 3].map((index) => {
      const title = normalizeVipPlanValue(config[`plan_name_${index}`]);
      const price = normalizeVipPlanValue(config[`discount_price_${index}`]);
      if (!title || !price) {
        return null;
      }
      const originalPrice = normalizeVipPlanValue(config[`original_price_${index}`]);
      return {
        key: `plan_${index}`,
        title,
        price,
        origin: originalPrice ? `原价 ¥${originalPrice}` : '',
        unit: normalizeVipPlanValue(config[`price_note_${index}`]),
        points: Number(config[`points_${index}`] || 0),
        badge: normalizeVipPlanValue(config[`badge_${index}`]),
        trial: normalizeVipPlanValue(config[`trial_text_${index}`]),
      };
    }).filter(Boolean);
  }

  async function loadVipPlanConfig(force = false) {
    if (accountState.vipPlansLoaded && !force) {
      return accountState.vipPlans;
    }
    if (accountState.vipPlansPromise && !force) {
      return accountState.vipPlansPromise;
    }
    accountState.vipPlansPromise = (async () => {
      try {
        const supabase = await getSupabaseClient();
        const { data, error } = await supabase
          .from('vip_plan_config')
          .select('*')
          .eq('config_key', 'default')
          .maybeSingle();
        if (error) {
          throw error;
        }
        const plans = buildVipPlansFromConfig(data);
        accountState.vipPlans = plans.length ? plans : VIP_PLAN_OPTIONS;
      } catch (error) {
        accountState.vipPlans = VIP_PLAN_OPTIONS;
      }
      accountState.vipPlansLoaded = true;
      const currentPlans = getVipPlanList();
      if (!currentPlans.some((item) => item.key === accountState.vipSelectedPlan)) {
        accountState.vipSelectedPlan = currentPlans[1]?.key || currentPlans[0]?.key || 'plan_1';
      }
      if (accountState.vipModal) {
        renderVipPlanCards();
        syncVipPreviewSelectedPlan();
      }
      return accountState.vipPlans;
    })().finally(() => {
      accountState.vipPlansPromise = null;
    });
    return accountState.vipPlansPromise;
  }

  function setVipPlanSelection(planKey) {
    const plans = getVipPlanList();
    if (!plans.some((item) => item.key === planKey)) {
      return;
    }
    accountState.vipSelectedPlan = planKey;
    syncVipPreviewSelectedPlan();
  }

  function getVipPlanArticleMarkup(plan, isSelected) {
    const badgeHtml = plan.badge && isSelected
      ? `<div class="shared-vip-preview-modal__plan-badge">${plan.badge}</div>`
      : '';
    const trialHtml = plan.trial ? `<span>${plan.trial}</span>` : '';
    const originHtml = plan.origin ? `<div class="shared-vip-preview-modal__plan-origin">${plan.origin}</div>` : '';
    const unitHtml = plan.unit ? `<div class="shared-vip-preview-modal__plan-unit">${plan.unit}</div>` : '';
    const pointsHtml = Number.isFinite(plan.points) && plan.points > 0
      ? `<div class="shared-vip-preview-modal__plan-points">赠送积分 ${plan.points}</div>`
      : '';
    return `
      <article class="shared-vip-preview-modal__plan${isSelected ? ' is-featured' : ''}" tabindex="0" role="button" data-vip-plan="${plan.key}" aria-pressed="${isSelected ? 'true' : 'false'}">
        ${badgeHtml}
        <div class="shared-vip-preview-modal__plan-title">${plan.title}</div>
        <div class="shared-vip-preview-modal__plan-price">¥${plan.price}${trialHtml}</div>
        ${originHtml}
        ${unitHtml}
        ${pointsHtml}
      </article>
    `;
  }

  function bindVipPlanEvents(modal) {
    modal.querySelectorAll('[data-vip-plan]').forEach((planEl) => {
      const activatePlan = () => {
        const planKey = planEl.getAttribute('data-vip-plan');
        if (!planKey || planKey === accountState.vipSelectedPlan) {
          return;
        }
        setVipPlanSelection(planKey);
      };
      planEl.addEventListener('click', activatePlan);
      planEl.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          activatePlan();
        }
      });
    });
  }

  function renderVipPlanCards() {
    const modal = accountState.vipModal;
    if (!modal) {
      return;
    }
    const pricingEl = modal.querySelector('.shared-vip-preview-modal__pricing');
    if (!pricingEl) {
      return;
    }
    const plans = getVipPlanList();
    pricingEl.innerHTML = plans.map((plan) => getVipPlanArticleMarkup(plan, plan.key === accountState.vipSelectedPlan)).join('');
    bindVipPlanEvents(modal);
  }

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
        displayPhone: maskPhoneDisplay(phone),
      };
    }

    const fallback = normalizeSessionUserLabel(session);
    return {
      phone: '',
      displayPhone: fallback || '已登录用户',
    };
  }

  function ensureStyles() {
    let style = document.getElementById(ACCOUNT_STYLE_ID);
    if (!style) {
      style = document.createElement('style');
      style.id = ACCOUNT_STYLE_ID;
      document.head.appendChild(style);
    }

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
      .shared-login-modal[hidden],
      .shared-vip-preview-modal[hidden] {
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
        position: relative;
        background:
          radial-gradient(circle at 86% 18%, rgba(255, 255, 255, 0.58), transparent 22%),
          linear-gradient(135deg, #fff7ef 0%, #f7edf8 58%, #eef2ff 100%);
        border: 1px solid rgba(216, 180, 144, 0.28);
        border-radius: 14px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.56);
      }

      .shared-account-panel__membership::after {
        content: '';
        position: absolute;
        right: -18px;
        top: -14px;
        width: 112px;
        height: 112px;
        border-radius: 28px;
        background: radial-gradient(circle at 32% 30%, rgba(255, 255, 255, 0.82), rgba(207, 222, 255, 0.2) 58%, rgba(207, 222, 255, 0) 72%);
        opacity: 0.8;
        pointer-events: none;
        transform: rotate(-18deg);
      }

      .shared-account-panel__membership-head {
        position: relative;
        z-index: 1;
        padding: 14px 14px 12px;
        text-align: left;
        display: grid;
        gap: 7px;
        justify-items: start;
        min-height: 122px;
        box-sizing: border-box;
        align-content: center;
      }

      .shared-account-panel__membership-badge {
        display: inline-flex;
        align-items: center;
        min-height: 24px;
        padding: 0 10px;
        border-radius: 999px;
        background: rgba(91, 52, 30, 0.08);
        color: rgba(91, 52, 30, 0.84);
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        max-width: 100%;
      }

      .shared-account-panel__membership-title {
        margin: 0;
        color: #2f1e15;
        font-family: var(--font-display);
        font-size: 16px;
        line-height: 1.18;
        letter-spacing: -0.03em;
        max-width: min(160px, 100%);
        word-break: break-word;
      }

      .shared-account-panel__membership-desc {
        color: rgba(70, 46, 32, 0.78);
        font-size: 12px;
        line-height: 1.45;
        max-width: min(156px, 100%);
        word-break: break-word;
        overflow-wrap: anywhere;
      }

      .shared-account-panel__membership-meta {
        display: none;
        align-items: center;
        min-height: 24px;
        padding: 0 10px;
        border-radius: 999px;
        background: rgba(43, 38, 34, 0.08);
        color: #3f342b;
        font-size: 11px;
        font-weight: 600;
        line-height: 1;
        max-width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .shared-account-panel__membership.is-active .shared-account-panel__membership-badge {
        background: rgba(25, 120, 86, 0.12);
        color: #0f7a56;
      }

      .shared-account-panel__membership.is-active .shared-account-panel__membership-title {
        font-size: 20px;
        color: #20110b;
      }

      .shared-account-panel__membership.is-active .shared-account-panel__membership-desc {
        font-size: 13px;
        color: rgba(47, 30, 21, 0.84);
      }

      .shared-account-panel__membership.is-active .shared-account-panel__membership-meta {
        display: inline-flex;
      }

      .shared-account-panel__membership-row {
        display: grid;
        gap: 0;
      }

      .shared-account-panel__membership .btn.primary {
        margin: 0 14px 14px;
        min-height: 34px;
        border: 0;
        border-radius: 999px;
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

      .shared-vip-preview-modal {
        position: fixed;
        inset: 0;
        z-index: 181;
        display: grid;
        place-items: center;
        padding: 24px;
        background: rgba(11, 15, 25, 0.58);
        backdrop-filter: blur(16px);
      }

      .shared-vip-preview-modal__dialog {
        position: relative;
        width: 800px;
        height: 500px;
        max-width: calc(100vw - 24px);
        max-height: calc(100dvh - 24px);
        display: grid;
        grid-template-columns: 292px minmax(0, 1fr);
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 10px;
        background:
          radial-gradient(circle at 78% 14%, rgba(255, 194, 124, 0.1), transparent 24%),
          linear-gradient(180deg, rgba(10, 10, 11, 0.99), rgba(15, 14, 14, 0.985));
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.48);
        outline: none;
      }

      .shared-vip-preview-modal__media {
        position: relative;
        min-height: 100%;
        border-radius: 10px 0 0 10px;
        background:
          radial-gradient(circle at top, rgba(96, 165, 250, 0.24), transparent 44%),
          linear-gradient(160deg, #0f172a 0%, #162447 48%, #1d4ed8 100%);
        color: #fff;
        padding: 0;
        overflow: hidden;
      }

      .shared-vip-preview-modal__visual {
        position: relative;
        display: grid;
        grid-template-rows: auto 1fr auto;
        align-content: space-between;
        gap: 28px;
        width: 100%;
        min-height: 100%;
        padding: 54px 36px 46px;
        box-sizing: border-box;
        background: transparent;
        box-shadow: none;
        overflow: hidden;
      }

      #shared-vip-preview-image {
        width: 100%;
        max-width: 100%;
        height: 100%;
      }

      #shared-vip-preview-image::before,
      #shared-vip-preview-image::after {
        content: none;
      }

      .shared-vip-preview-modal__visual-top {
        display: grid;
        justify-items: start;
        gap: 12px;
        position: relative;
        z-index: 1;
      }

      .shared-vip-preview-modal__visual-badge,
      .shared-vip-preview-modal__visual-status {
        display: inline-flex;
        align-items: center;
        min-height: 30px;
        padding: 0 12px;
        border-radius: 999px;
        border: 1px solid rgba(255, 221, 176, 0.08);
        background: rgba(255, 244, 228, 0.06);
        color: rgba(255, 236, 212, 0.78);
        font-size: 11px;
        letter-spacing: 0.14em;
      }

      .shared-vip-preview-modal__visual-stage {
        display: grid;
        align-content: end;
        gap: 18px;
        position: relative;
        z-index: 1;
      }

      .shared-vip-preview-modal__visual-card {
        position: relative;
        display: grid;
        gap: 18px;
        padding: 26px 24px 22px;
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(10px);
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.14),
          0 18px 32px rgba(8, 15, 32, 0.22);
      }

      .shared-vip-preview-modal__visual-card::before {
        content: '';
        position: absolute;
        inset: 12px;
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        pointer-events: none;
      }

      .shared-vip-preview-modal__visual-card-head {
        display: grid;
        justify-items: center;
        gap: 16px;
        text-align: center;
      }

      .shared-vip-preview-modal__visual-card-title {
        margin: 0 0 10px;
        color: #ffffff;
        font-size: clamp(28px, 2.8vw, 40px);
        line-height: 1.12;
        letter-spacing: -0.04em;
        text-align: center;
      }

      .shared-vip-preview-modal__visual-card-copy {
        margin: 0;
        color: rgba(255, 255, 255, 0.8);
        font-size: 13px;
        line-height: 1.7;
        text-align: center;
      }

      .shared-vip-preview-modal__visual-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 62px;
        min-height: 62px;
        padding: 0 16px;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.12);
        color: #ffffff;
        font-size: 17px;
        font-weight: 700;
        letter-spacing: 0.08em;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.14);
      }

      .shared-vip-preview-modal__visual-metrics {
        display: grid;
        gap: 12px;
      }

      .shared-vip-preview-modal__visual-metric {
        display: grid;
        grid-template-columns: 42px minmax(0, 1fr);
        align-items: center;
        gap: 4px 12px;
      }

      .shared-vip-preview-modal__visual-metric-value {
        grid-column: 2;
        color: #ffffff;
        font-size: 14px;
        font-weight: 700;
      }

      .shared-vip-preview-modal__visual-metric-label {
        grid-column: 2;
        color: rgba(255, 255, 255, 0.72);
        font-size: 12px;
      }

      .shared-vip-preview-modal__visual-metric::before {
        content: '';
        grid-column: 1;
        grid-row: 1 / span 2;
        width: 34px;
        height: 34px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.2);
        box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.18), 0 8px 14px rgba(15, 23, 42, 0.24);
      }

      .shared-vip-preview-modal__visual-bottom {
        display: grid;
        gap: 10px;
        padding-top: 2px;
        position: relative;
        z-index: 1;
      }

      .shared-vip-preview-modal__visual-chip {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: rgba(255, 255, 255, 0.84);
        font-size: 12px;
      }

      .shared-vip-preview-modal__visual-chip::before {
        content: '';
        width: 5px;
        height: 5px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.82);
        box-shadow: 0 0 10px rgba(255, 255, 255, 0.24);
      }

      .shared-vip-preview-modal__glow {
        position: absolute;
        inset: auto 0 0 0;
        height: 46%;
        background: linear-gradient(180deg, rgba(10, 10, 10, 0), rgba(10, 10, 10, 0.8));
        pointer-events: none;
      }

      .shared-vip-preview-modal__content {
        display: grid;
        grid-template-rows: auto auto auto auto 1fr;
        gap: 12px;
        padding: 16px 18px 16px 14px;
        color: #f8eadb;
        align-content: start;
        background:
          radial-gradient(circle at 86% 8%, rgba(255, 197, 120, 0.08), transparent 24%),
          linear-gradient(180deg, rgba(9, 9, 9, 0.96), rgba(14, 14, 14, 0.99));
      }

      .shared-vip-preview-modal__account {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 12px;
        padding: 4px 2px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      }

      .shared-vip-preview-modal__avatar {
        width: 42px;
        height: 42px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #f8d6b0, #b6733c);
        color: #3f240f;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.08em;
      }

      .shared-vip-preview-modal__account-copy {
        min-width: 0;
      }

      .shared-vip-preview-modal__account-name {
        color: #fff8ef;
        font-size: 16px;
        font-weight: 700;
      }

      .shared-vip-preview-modal__account-meta {
        margin-top: 3px;
        color: rgba(255, 233, 208, 0.62);
        font-size: 11px;
      }

      .shared-vip-preview-modal__account-id {
        color: rgba(255, 233, 208, 0.72);
        font-size: 12px;
        white-space: nowrap;
      }

      .shared-vip-preview-modal__switcher {
        display: inline-grid;
        grid-template-columns: 1fr 1fr;
        gap: 5px;
        width: 110px;
        padding: 3px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.05);
      }

      .shared-vip-preview-modal__switcher-btn {
        min-width: 102px;
        height: 34px;
        padding: 0 14px;
        border: none;
        border-radius: 999px;
        background: transparent;
        color: rgba(255, 232, 208, 0.64);
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
      }

      .shared-vip-preview-modal__switcher-btn.is-active {
        background: linear-gradient(135deg, rgba(255, 226, 190, 0.28), rgba(206, 137, 76, 0.28));
        color: #fff5ea;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
      }

      .shared-vip-preview-modal__pricing {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }

      .shared-vip-preview-modal__plan {
        position: relative;
        display: grid;
        align-content: start;
        gap: 5px;
        min-height: 136px;
        padding: 15px 12px 12px;
        border-radius: 18px;
        border: 1px solid rgba(255, 229, 194, 0.08);
        background: linear-gradient(180deg, rgba(255, 248, 236, 0.045), rgba(255, 242, 224, 0.018));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        cursor: pointer;
        transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
      }

      .shared-vip-preview-modal__plan:hover {
        border-color: rgba(247, 192, 122, 0.28);
        transform: translateY(-1px);
      }

      .shared-vip-preview-modal__plan.is-featured {
        border-color: rgba(247, 192, 122, 0.72);
        background:
          radial-gradient(circle at 50% 0, rgba(255, 214, 154, 0.34), transparent 34%),
          linear-gradient(180deg, rgba(98, 66, 40, 0.92), rgba(58, 38, 25, 0.96));
        transform: translateY(-2px);
        box-shadow:
          0 12px 24px rgba(0, 0, 0, 0.22),
          inset 0 1px 0 rgba(255, 240, 220, 0.18);
      }

      .shared-vip-preview-modal__plan-badge {
        position: absolute;
        top: -9px;
        left: 50%;
        transform: translateX(-50%);
        padding: 4px 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, #ffe3b8, #f6b56f);
        color: #5d3313;
        font-size: 10px;
        font-weight: 700;
        white-space: nowrap;
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.14);
      }

      .shared-vip-preview-modal__plan-title {
        margin-top: 4px;
        color: rgba(255, 241, 223, 0.88);
        font-size: 12px;
        font-weight: 500;
      }

      .shared-vip-preview-modal__plan-price {
        color: #fff8ed;
        font-size: 28px;
        font-weight: 800;
        line-height: 0.96;
        letter-spacing: -0.03em;
      }

      .shared-vip-preview-modal__plan-price span {
        margin-left: 4px;
        color: rgba(255, 237, 214, 0.88);
        font-size: 11px;
        font-weight: 600;
      }

      .shared-vip-preview-modal__plan-origin {
        color: rgba(255, 232, 206, 0.42);
        font-size: 11px;
        text-decoration: line-through;
      }

      .shared-vip-preview-modal__plan-unit {
        margin-top: auto;
        color: rgba(255, 236, 213, 0.76);
        font-size: 11px;
      }

      .shared-vip-preview-modal__benefit-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        min-height: 40px;
        padding: 0 14px;
        border-radius: 14px;
        background: linear-gradient(90deg, rgba(138, 89, 41, 0.74), rgba(82, 55, 31, 0.34));
        color: rgba(255, 239, 218, 0.92);
      }

      .shared-vip-preview-modal__benefit-bar span {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 999px;
        background: linear-gradient(135deg, #ffe0b1, #f4af67);
        color: #643515;
        font-size: 11px;
        font-weight: 800;
      }

      .shared-vip-preview-modal__benefit-bar strong {
        font-size: 11px;
        font-weight: 600;
      }

      .shared-vip-preview-modal__detail-card {
        position: relative;
        display: block;
        padding: 0;
        border-radius: 22px;
        background: transparent;
        border: none;
        box-shadow: none;
        transform: none;
        overflow: visible;
      }

      .shared-vip-preview-modal__detail-card::before {
        content: none;
      }

      .shared-vip-preview-modal__detail-copy {
        display: none;
      }

      .shared-vip-preview-modal__eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: fit-content;
        padding: 5px 10px;
        border-radius: 999px;
        background: rgba(255, 217, 176, 0.08);
        color: #f4cfa2;
        font-size: 10px;
        letter-spacing: 0.14em;
      }

      .shared-vip-preview-modal__title {
        margin: 0;
        font-size: clamp(25px, 2.3vw, 35px);
        line-height: 0.98;
        letter-spacing: -0.06em;
        color: #fff7eb;
      }

      .shared-vip-preview-modal__description {
        margin: 0;
        max-width: 30ch;
        color: rgba(255, 238, 219, 0.76);
        font-size: 12px;
        line-height: 1.7;
      }

      .shared-vip-preview-modal__list {
        display: grid;
        gap: 9px;
        margin: 6px 0 0;
        padding: 14px 15px;
        list-style: none;
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.034), rgba(255, 255, 255, 0.018));
        border: 1px solid rgba(255, 255, 255, 0.05);
      }

      .shared-vip-preview-modal__list li {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        color: rgba(255, 241, 226, 0.9);
        font-size: 12px;
        line-height: 1.52;
      }

      .shared-vip-preview-modal__list li::before {
        content: '✦';
        color: #ffcf97;
        font-size: 12px;
      }

      .shared-vip-preview-modal__paybox {
        position: relative;
        display: grid;
        justify-items: center;
        gap: 16px;
        min-height: 172px;
        padding: 24px 22px;
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(24, 24, 24, 0.98), rgba(18, 18, 18, 0.99));
        border: 1px solid rgba(255, 255, 255, 0.06);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        overflow: hidden;
        text-align: center;
      }

      .shared-vip-preview-modal__paybox::before {
        content: none;
      }

      .shared-vip-preview-modal__payinfo {
        display: grid;
        justify-items: center;
        gap: 10px;
        min-width: 0;
        width: 100%;
      }

      .shared-vip-preview-modal__plan-points {
        color: rgba(255, 232, 204, 0.72);
        font-size: 11px;
        line-height: 1.4;
      }

      .shared-vip-preview-modal__paylabel {
        display: flex;
        align-items: baseline;
        justify-content: center;
        flex-wrap: wrap;
        gap: 4px;
        color: #ffffff;
        font-size: 17px;
        font-weight: 600;
        line-height: 1;
      }

      .shared-vip-preview-modal__paycurrency {
        color: #ffffff;
        font-size: 26px;
        font-weight: 700;
        line-height: 1;
      }

      .shared-vip-preview-modal__paylabel strong {
        font-size: 46px;
        line-height: 0.92;
        letter-spacing: -0.04em;
        color: #ffffff;
      }

      .shared-vip-preview-modal__paymethod {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 9px;
        min-height: 22px;
        color: #f7f7f7;
        font-size: 14px;
        line-height: 1.4;
      }

      .shared-vip-preview-modal__paymethod-icon {
        width: 18px;
        height: 18px;
        border-radius: 5px;
        background: linear-gradient(180deg, #4da3ff, #1677ff);
        position: relative;
        flex: 0 0 auto;
      }

      .shared-vip-preview-modal__paymethod-icon::before {
        content: '支';
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        color: #fff;
        font-size: 11px;
        font-weight: 700;
      }

      .shared-vip-preview-modal__agreement {
        color: rgba(255, 255, 255, 0.72);
        font-size: 12px;
        line-height: 1.45;
        text-align: center;
      }

      .shared-vip-preview-modal__agreement-link {
        color: rgba(221, 191, 152, 0.9);
      }

      .shared-vip-preview-modal__payextras {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-top: 6px;
        color: rgba(216, 185, 148, 0.96);
        font-size: 12px;
        flex-wrap: wrap;
      }

      .shared-vip-preview-modal__payextra {
        padding: 0;
        border: none;
        background: transparent;
        color: inherit;
        font-size: inherit;
        line-height: 1.2;
        cursor: pointer;
        transition: color 0.18s ease, opacity 0.18s ease;
      }

      .shared-vip-preview-modal__payextra:hover {
        color: rgba(255, 226, 190, 0.88);
      }

      .shared-vip-preview-modal__payextra-divider {
        width: 1px;
        height: 12px;
        background: rgba(216, 185, 148, 0.34);
      }

      .shared-vip-preview-modal__footer {
        display: grid;
        justify-items: center;
        gap: 12px;
        margin-top: 8px;
        width: 100%;
      }

      .shared-vip-preview-modal__action {
        min-height: 46px;
        min-width: min(100%, 220px);
        border-radius: 14px;
        padding: 0 18px;
        background: linear-gradient(135deg, #ffe6c8, #f6bb75 56%, #efaa60);
        color: #4e2a10;
        font-size: 14px;
        font-weight: 700;
        box-shadow:
          inset 0 1px 0 rgba(255, 255, 255, 0.22),
          0 8px 18px rgba(164, 103, 43, 0.18);
      }

      .shared-vip-preview-modal__action:disabled {
        cursor: not-allowed;
        opacity: 0.72;
        transform: none;
      }

      .shared-vip-preview-modal__action.is-loading {
        opacity: 0.82;
      }

      .shared-vip-preview-modal__action-status {
        min-height: 18px;
        color: rgba(255, 255, 255, 0.72);
        font-size: 12px;
        line-height: 1.5;
        text-align: center;
      }

      .shared-vip-preview-modal__action-status.is-error {
        color: #fca5a5;
      }

      .shared-vip-preview-modal__action-status.is-success {
        color: #86efac;
      }

      .shared-vip-preview-modal__close {
        position: absolute;
        top: 18px;
        right: 18px;
        z-index: 8;
        width: 40px;
        height: 40px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.08);
        color: #fff4e8;
        font-size: 20px;
        pointer-events: auto;
      }

      @media (max-width: 980px) {
        .shared-vip-preview-modal__dialog {
          width: min(800px, calc(100vw - 24px));
          height: auto;
          grid-template-columns: 1fr;
          min-height: auto;
        }

        .shared-vip-preview-modal__media {
          min-height: 280px;
          padding: 20px 20px 0;
        }

        .shared-vip-preview-modal__content {
          padding: 18px 18px 18px;
        }

        .shared-vip-preview-modal__pricing {
          grid-template-columns: 1fr;
        }

        .shared-vip-preview-modal__paybox {
          justify-items: center;
          gap: 14px;
          min-height: 156px;
          padding: 16px 18px;
        }
      }

      @media (max-width: 720px) {
        .shared-vip-preview-modal {
          padding: 16px;
        }

        .shared-vip-preview-modal__account {
          grid-template-columns: auto 1fr;
        }

        .shared-vip-preview-modal__pricing {
          grid-template-columns: 1fr;
        }

        .shared-vip-preview-modal__plan.is-featured {
          transform: none;
        }

        .shared-vip-preview-modal__paybox {
          justify-items: center;
          text-align: center;
        }

        .shared-vip-preview-modal__payinfo {
          width: 100%;
        }

        .shared-vip-preview-modal__footer {
          justify-items: center;
        }
      }

      @media (max-width: 560px) {
        .shared-vip-preview-modal__title {
          font-size: 24px;
        }

        .shared-vip-preview-modal__switcher {
          width: 100%;
        }

        .shared-vip-preview-modal__switcher-btn {
          min-width: 0;
        }
      }

      .shared-vip-preview-modal__action,
      .shared-vip-preview-modal__close {
        border: none;
        cursor: pointer;
        transition: transform 0.18s ease, opacity 0.18s ease, background 0.18s ease;
      }

      .shared-vip-preview-modal__close:hover {
        transform: translateY(-1px);
        background: rgba(255, 255, 255, 0.12);
      }

      .shared-vip-preview-modal__action:hover {
        transform: translateY(-1px);
        opacity: 0.96;
      }

      @media (prefers-reduced-motion: reduce) {
        .shared-vip-preview-modal__action,
        .shared-vip-preview-modal__close {
          transition: none;
        }
      }

    `;
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
                <span class="shared-account-panel__membership-badge" id="shared-account-panel-membership-badge">会员中心</span>
                <h3 class="shared-account-panel__membership-title" id="shared-account-panel-membership-title">会员套餐和价格</h3>
                <div class="shared-account-panel__membership-desc" id="shared-account-panel-membership-desc">登录后即可查看账号权益、同步会话和积分余额。</div>
                <div class="shared-account-panel__membership-meta" id="shared-account-panel-membership-meta"></div>
              </div>
              <div class="shared-account-panel__membership-row">
                <button class="btn primary" type="button" data-account-panel-login id="shared-account-panel-login-link">开通VIP</button>
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

    panel.querySelector('[data-account-panel-login]')?.addEventListener('click', (event) => {
      event.preventDefault();
      closeAccountPanel();
      if (accountState.session) {
        openVipPreviewModal(event.currentTarget);
        return;
      }
      openLoginModal(event.currentTarget);
    });

    accountState.logoutButton?.addEventListener('click', (event) => {
      event.preventDefault();
      openLoginModal(event.currentTarget);
    });

    return panel;
  }

  function disposeVipPreviewModal() {
    if (accountState.vipModal?.parentNode) {
      accountState.vipModal.parentNode.removeChild(accountState.vipModal);
    }
    accountState.vipModal = null;
    accountState.vipDialog = null;
    accountState.vipImage = null;
    accountState.vipTitle = null;
    accountState.vipDescription = null;
  }

  function ensureVipPreviewModal() {
    const existingModal = document.getElementById(ACCOUNT_VIP_MODAL_ID);
    const needsRebuild = !existingModal
      || !existingModal.querySelector('.shared-vip-preview-modal__detail-card')
      || !existingModal.querySelector('.shared-vip-preview-modal__paymethod-icon');

    if (!needsRebuild && accountState.vipModal === existingModal) {
      return accountState.vipModal;
    }

    disposeVipPreviewModal();

    if (existingModal?.parentNode) {
      existingModal.parentNode.removeChild(existingModal);
    }

    ensureStyles();

    const modal = document.createElement('div');
    modal.id = ACCOUNT_VIP_MODAL_ID;
    modal.className = 'shared-vip-preview-modal';
    modal.hidden = true;
    modal.innerHTML = `
      <div class="shared-vip-preview-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="shared-vip-preview-title" tabindex="-1">
        <button class="shared-vip-preview-modal__close" type="button" data-vip-preview-close aria-label="关闭会员参考弹窗">×</button>
        <div class="shared-vip-preview-modal__media" aria-hidden="true">
          <div class="shared-vip-preview-modal__visual" id="shared-vip-preview-image" aria-label="VIP 权益预览" role="img"></div>
        </div>
        <div class="shared-vip-preview-modal__content">
          <div class="shared-vip-preview-modal__account">
            <div class="shared-vip-preview-modal__avatar">VIP</div>
            <div class="shared-vip-preview-modal__account-copy">
              <div class="shared-vip-preview-modal__account-name">已登录用户</div>
              <div class="shared-vip-preview-modal__account-meta">登录后可同步账号信息并开通会员</div>
            </div>
          </div>
          <div class="shared-vip-preview-modal__switcher">
            <button class="shared-vip-preview-modal__switcher-btn is-active" type="button">标准会员</button>
          </div>
          <div class="shared-vip-preview-modal__pricing"></div>
          <div class="shared-vip-preview-modal__detail-card">
            <div class="shared-vip-preview-modal__paybox">
              <div class="shared-vip-preview-modal__payinfo">
                <div class="shared-vip-preview-modal__paylabel">支付：<span class="shared-vip-preview-modal__paycurrency">¥</span><strong>1.1</strong></div>
                <div class="shared-vip-preview-modal__paymethod">
                  <span class="shared-vip-preview-modal__paymethod-icon"></span>
                  <span>支付宝扫码开通</span>
                </div>
                <div class="shared-vip-preview-modal__agreement">支付即视为您已同意<span class="shared-vip-preview-modal__agreement-link">《会员服务协议》</span></div>
                <div class="shared-vip-preview-modal__footer">
                  <button class="shared-vip-preview-modal__action" type="button" data-vip-preview-open-login>立即开通</button>
                  <div class="shared-vip-preview-modal__action-status" data-vip-preview-status aria-live="polite"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    accountState.vipModal = modal;
    accountState.vipDialog = modal.querySelector('.shared-vip-preview-modal__dialog');
    accountState.vipImage = modal.querySelector('#shared-vip-preview-image');
    accountState.vipTitle = modal.querySelector('#shared-vip-preview-title');
    accountState.vipDescription = modal.querySelector('#shared-vip-preview-description');

    modal.querySelectorAll('[data-vip-preview-close]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeVipPreviewModal();
      });
    });

    modal.addEventListener('click', (event) => {
      const closeButton = event.target instanceof Element
        ? event.target.closest('[data-vip-preview-close]')
        : null;
      if (closeButton) {
        event.preventDefault();
        closeVipPreviewModal();
        return;
      }
      if (event.target === modal) {
        closeVipPreviewModal();
      }
    });

    renderVipPlanCards();
    syncVipPreviewSelectedPlan();

    modal.querySelector('[data-vip-preview-open-login]')?.addEventListener('click', (event) => {
      event.preventDefault();
      submitVipCheckout(event.currentTarget);
    });

    return modal;
  }

  function showVipPreviewSlide(index = 0) {
    const total = VIP_REFERENCE_IMAGES.length;
    if (!total) {
      return;
    }
    const normalizedIndex = ((index % total) + total) % total;
    const current = VIP_REFERENCE_IMAGES[normalizedIndex];
    accountState.vipPreviewIndex = normalizedIndex;
    if (accountState.vipImage) {
      accountState.vipImage.innerHTML = `
        <div class="shared-vip-preview-modal__visual-top">
          <div class="shared-login-modal__brand">
            <p class="shared-login-modal__brand-name">aiimg</p>
            <p class="shared-login-modal__brand-tag">ai image workspace</p>
          </div>
        </div>
        <div class="shared-vip-preview-modal__visual-stage">
          <div class="shared-login-modal__left-copy">
            <h3 class="shared-login-modal__left-title">一站式 AI 出图空间</h3>
            <p class="shared-vip-preview-modal__visual-card-copy">开通会员后可解锁更多专属权益与更高任务上限</p>
          </div>
        </div>
      `;
      accountState.vipImage.setAttribute('aria-label', current.title);
    }
    if (accountState.vipTitle) {
      accountState.vipTitle.textContent = current.title;
    }
    if (accountState.vipDescription) {
      accountState.vipDescription.textContent = current.description;
    }
  }

  function syncVipPreviewSelectedPlan() {
    const modal = accountState.vipModal;
    if (!modal) {
      return;
    }
    const plans = getVipPlanList();
    const selectedPlan = plans.find((item) => item.key === accountState.vipSelectedPlan) || plans[0];
    if (!selectedPlan) {
      return;
    }
    modal.querySelectorAll('[data-vip-plan]').forEach((planEl) => {
      const isSelected = planEl.getAttribute('data-vip-plan') === selectedPlan.key;
      planEl.classList.toggle('is-featured', isSelected);
      if (planEl instanceof HTMLElement) {
        planEl.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
      }
      const badgeEl = planEl.querySelector('.shared-vip-preview-modal__plan-badge');
      if (badgeEl) {
        badgeEl.hidden = !isSelected || !selectedPlan.badge;
        badgeEl.textContent = selectedPlan.badge || '';
      } else if (isSelected && selectedPlan.badge) {
        planEl.insertAdjacentHTML('afterbegin', `<div class="shared-vip-preview-modal__plan-badge">${selectedPlan.badge}</div>`);
      }
    });

    const payStrong = modal.querySelector('.shared-vip-preview-modal__paylabel strong');
    if (payStrong) {
      payStrong.textContent = selectedPlan.price;
    }

    renderVipCheckoutAction();
  }

  function getSelectedVipPlan() {
    const plans = getVipPlanList();
    return plans.find((item) => item.key === accountState.vipSelectedPlan) || plans[0] || null;
  }

  function getVipPlanPayType(plan) {
    const normalizedKey = String(plan?.key || '').trim().toLowerCase();
    return normalizedKey === 'plan_1' ? 'one_time' : 'subscribe';
  }

  function setVipCheckoutStatus(message, type = '') {
    accountState.vipCheckoutMessage = message || '';
    const statusEl = accountState.vipModal?.querySelector('[data-vip-preview-status]');
    if (!statusEl) {
      return;
    }
    statusEl.textContent = accountState.vipCheckoutMessage;
    statusEl.className = `shared-vip-preview-modal__action-status${type ? ` is-${type}` : ''}`;
  }

  function renderVipCheckoutAction() {
    const modal = accountState.vipModal;
    if (!modal) {
      return;
    }
    const button = modal.querySelector('[data-vip-preview-open-login]');
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }
    const plan = getSelectedVipPlan();
    const payType = getVipPlanPayType(plan);
    const idleText = payType === 'subscribe' ? '立即订阅' : '立即购买';
    button.disabled = Boolean(accountState.vipPayBusy);
    button.classList.toggle('is-loading', Boolean(accountState.vipPayBusy));
    button.textContent = accountState.vipPayBusy ? '跳转支付中...' : idleText;
    const statusEl = modal.querySelector('[data-vip-preview-status]');
    if (statusEl) {
      statusEl.textContent = accountState.vipCheckoutMessage || '';
    }
  }

  async function ensureVipCheckoutSession() {
    if (accountState.session) {
      return accountState.session;
    }
    const syncedSession = await syncServerSessionFromBrowser();
    return syncedSession || null;
  }

  async function submitVipCheckout(trigger) {
    if (accountState.vipPayBusy) {
      return;
    }
    accountState.vipCheckoutTrigger = trigger || document.activeElement || null;
    const session = await ensureVipCheckoutSession();
    if (!session) {
      accountState.vipCheckoutPending = true;
      setVipCheckoutStatus('请先登录后再继续开通会员', 'error');
      closeVipPreviewModal({ restoreFocus: false });
      openLoginModal(accountState.vipCheckoutTrigger);
      return;
    }
    const plan = getSelectedVipPlan();
    if (!plan) {
      setVipCheckoutStatus('未找到可用套餐，请刷新后重试', 'error');
      return;
    }
    const userId = getSessionUserUid(session);
    if (!userId) {
      accountState.vipCheckoutPending = true;
      setVipCheckoutStatus('登录状态已失效，请重新登录后重试', 'error');
      closeVipPreviewModal({ restoreFocus: false });
      openLoginModal(accountState.vipCheckoutTrigger);
      return;
    }

    accountState.vipPayBusy = true;
    setVipCheckoutStatus('正在创建支付订单，请稍候...');
    renderVipCheckoutAction();

    try {
      let response = await fetch('/api/pay/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          user_id: userId,
          product_id: String(plan.key || '').trim(),
          amount: String(plan.price || '').trim(),
          pay_type: getVipPlanPayType(plan),
        }),
      });
      let result = await response.json().catch(() => ({}));

      if (response.status === 401) {
        const refreshedSession = await syncServerSessionFromBrowser();
        if (!refreshedSession || !getSessionUserUid(refreshedSession)) {
          throw new Error(result?.message || '登录状态已失效，请重新登录');
        }
        response = await fetch('/api/pay/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json',
          },
          credentials: 'same-origin',
          body: JSON.stringify({
            user_id: getSessionUserUid(refreshedSession),
            product_id: String(plan.key || '').trim(),
            amount: String(plan.price || '').trim(),
            pay_type: getVipPlanPayType(plan),
          }),
        });
        result = await response.json().catch(() => ({}));
      }

      if (!response.ok || !result?.success) {
        throw new Error(result?.message || result?.error || '创建支付订单失败，请稍后重试');
      }

      const paymentUrl = String(result?.data?.payment_url || '').trim();
      if (!paymentUrl) {
        throw new Error('支付链接为空，请稍后重试');
      }

      accountState.vipCheckoutPending = false;
      setVipCheckoutStatus('订单创建成功，正在跳转支付...', 'success');
      renderVipCheckoutAction();
      window.location.href = paymentUrl;
    } catch (error) {
      setVipCheckoutStatus(error?.message || '创建支付订单失败，请稍后重试', 'error');
      renderVipCheckoutAction();
    } finally {
      accountState.vipPayBusy = false;
      renderVipCheckoutAction();
    }
  }

  function syncVipPreviewAccountInfo() {
    const modal = accountState.vipModal;
    if (!modal) {
      return;
    }
    const nameEl = modal.querySelector('.shared-vip-preview-modal__account-name');
    const metaEl = modal.querySelector('.shared-vip-preview-modal__account-meta');
    const userDisplay = getSessionUserDisplay(accountState.session);
    const phoneText = userDisplay.displayPhone;
    if (nameEl) {
      nameEl.textContent = phoneText || '已登录用户';
    }
    if (metaEl) {
      metaEl.textContent = accountState.session ? '当前已登录账号，可直接开通会员' : '登录后可同步账号信息并开通会员';
    }
  }

  async function openVipPreviewModal(trigger) {
    if (!accountState.session) {
      openLoginModal(trigger);
      return;
    }
    await loadVipPlanConfig();
    const modal = ensureVipPreviewModal();
    if (!modal) {
      return;
    }
    if (accountState.loginOpen) {
      closeLoginModal({ restoreFocus: false });
    }
    accountState.returnFocusTo = trigger || document.activeElement;
    accountState.vipPreviewOpen = true;
    syncVipPreviewAccountInfo();
    showVipPreviewSlide(accountState.vipPreviewIndex || 0);
    renderVipPlanCards();
    syncVipPreviewSelectedPlan();
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => {
      accountState.vipDialog?.focus();
    });
  }

  function closeVipPreviewModal(options = {}) {
    const { restoreFocus = true } = options;
    if (!accountState.vipModal) {
      return;
    }
    accountState.vipPreviewOpen = false;
    accountState.vipModal.hidden = true;
    document.body.style.overflow = '';
    const returnFocusTo = accountState.returnFocusTo;
    if (restoreFocus) {
      accountState.returnFocusTo = null;
    }
    if (restoreFocus && returnFocusTo && typeof returnFocusTo.focus === 'function') {
      returnFocusTo.focus();
    }
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
      if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        return Promise.reject(new Error('Supabase 前端配置缺失'));
      }
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
    if (accountState.vipCheckoutPending) {
      accountState.vipCheckoutPending = false;
      window.alert(message);
      await openVipPreviewModal(accountState.vipCheckoutTrigger || null);
      await submitVipCheckout(accountState.vipCheckoutTrigger || null);
      return;
    }
    window.alert(message);
    const next = new URLSearchParams(window.location.search).get('next');
    const target = next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/api/') ? next : '/';
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

  function formatMembershipExpiryLabel(value) {
    const rawValue = String(value || '').trim();
    if (!rawValue) {
      return '';
    }
    const expireDate = new Date(rawValue);
    if (Number.isNaN(expireDate.getTime())) {
      return '';
    }
    const now = new Date();
    const diffMs = expireDate.getTime() - now.getTime();
    const diffDays = Math.max(0, Math.ceil(diffMs / 86400000));
    if (diffDays <= 0) {
      return '会员已到期，可重新开通';
    }
    return `会员已开通，剩余 ${diffDays} 天`;
  }

  function getMembershipPlanLabel(points) {
    if (!points?.membership_active) {
      return '会员套餐和价格';
    }
    return '个人版';
  }

  function getMembershipMetaLabel(points) {
    if (!points?.membership_active) {
      return '支持高清生成 · 积分加速';
    }
    const rawValue = String(points?.subscribe_expire || '').trim();
    if (!rawValue) {
      return '会员权益已生效';
    }
    const expireDate = new Date(rawValue);
    if (Number.isNaN(expireDate.getTime())) {
      return '会员权益已生效';
    }
    const month = String(expireDate.getMonth() + 1).padStart(2, '0');
    const day = String(expireDate.getDate()).padStart(2, '0');
    return `有效期至 ${month}-${day}`;
  }

  function renderMembershipCard() {
    if (!accountState.panel) {
      return;
    }
    const membershipCard = accountState.panel.querySelector('.shared-account-panel__membership');
    const badgeEl = document.getElementById('shared-account-panel-membership-badge');
    const titleEl = document.getElementById('shared-account-panel-membership-title');
    const descEl = document.getElementById('shared-account-panel-membership-desc');
    const metaEl = document.getElementById('shared-account-panel-membership-meta');
    const actionEl = document.getElementById('shared-account-panel-login-link');
    const isLoggedIn = Boolean(accountState.session);
    const membershipActive = Boolean(isLoggedIn && accountState.points?.membership_active && accountState.points?.subscribe_expire);

    membershipCard?.classList.toggle('is-active', membershipActive);

    if (badgeEl) {
      badgeEl.textContent = membershipActive ? '已开通会员' : '会员中心';
    }
    if (titleEl) {
      titleEl.textContent = membershipActive ? getMembershipPlanLabel(accountState.points) : '会员套餐和价格';
    }
    if (descEl) {
      descEl.textContent = membershipActive
        ? (formatMembershipExpiryLabel(accountState.points?.subscribe_expire) || '会员权益已生效')
        : (isLoggedIn ? '开通后即可查看套餐版本、权益时长和积分余额。' : '登录后即可查看账号权益、同步会话和积分余额。');
    }
    if (metaEl) {
      metaEl.textContent = getMembershipMetaLabel(accountState.points);
      metaEl.hidden = !membershipActive;
    }
    if (actionEl) {
      actionEl.hidden = membershipActive;
      actionEl.textContent = isLoggedIn ? '立即开通' : '登录后开通';
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
    renderMembershipCard();

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

  function openLoginModal(trigger) {
    ensureLoginModal();
    if (accountState.vipPreviewOpen) {
      closeVipPreviewModal({ restoreFocus: false });
    }
    setLoginModalView('sms');
    accountState.returnFocusTo = trigger || document.activeElement;
    accountState.loginOpen = true;
    accountState.loginModal.hidden = false;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => {
      accountState.loginPhoneInput?.focus();
    }, 0);
  }

  function closeLoginModal(options = {}) {
    const { restoreFocus = true } = options;
    if (!accountState.loginModal) {
      return;
    }
    accountState.loginOpen = false;
    accountState.loginModal.hidden = true;
    if (!accountState.open && !accountState.vipPreviewOpen) {
      document.body.style.overflow = '';
    }
    const returnFocusTo = accountState.returnFocusTo;
    if (restoreFocus) {
      accountState.returnFocusTo = null;
    }
    if (restoreFocus && returnFocusTo && typeof returnFocusTo.focus === 'function') {
      returnFocusTo.focus();
    }
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
        openVipPreviewModal(trigger);
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



