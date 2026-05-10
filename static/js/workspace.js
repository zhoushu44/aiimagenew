document.addEventListener('DOMContentLoaded', () => {
  let socket = null;
  const socketReconnectAttempts = [];
  const MAX_SOCKET_RECONNECT_ATTEMPTS = 5;
  
  const initWebSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}`;
    
    try {
      socket = new WebSocket(wsUrl);
      
      socket.onopen = () => {
        console.log('[WebSocket] Connected');
        socketReconnectAttempts.length = 0;
      };
      
      socket.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason);
        if (socketReconnectAttempts.length < MAX_SOCKET_RECONNECT_ATTEMPTS) {
          const delay = Math.min(1000 * Math.pow(2, socketReconnectAttempts.length), 30000);
          console.log(`[WebSocket] Reconnecting in ${delay}ms...`);
          setTimeout(() => {
            socketReconnectAttempts.push(Date.now());
            initWebSocket();
          }, delay);
        }
      };
      
      socket.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'task_update' && data.task_id && data.task) {
            window.dispatchEvent(new CustomEvent('taskUpdate', {
              detail: {
                taskId: data.task_id,
                task: data.task
              }
            }));
          }
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e);
        }
      };
    } catch (error) {
      console.error('[WebSocket] Failed to initialize:', error);
    }
  };
  
  const subscribeTask = (taskId) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'subscribe_task', task_id: taskId }));
    }
  };

  const createScrollRelayController = (primary, getSecondary) => {
    let boundSecondary = null;

    const getSecondaryContainer = () => {
      if (typeof getSecondary === 'function') {
        return getSecondary();
      }
      return getSecondary || null;
    };

    const getMaxScrollTop = (element) => Math.max(0, element.scrollHeight - element.clientHeight);

    const canScroll = (element) => {
      if (!element) return false;
      return element.scrollHeight > element.clientHeight + 1;
    };

    const applyDelta = (element, deltaY) => {
      if (!element || !deltaY || !canScroll(element)) return deltaY;
      const start = element.scrollTop;
      const max = getMaxScrollTop(element);
      const target = Math.min(max, Math.max(0, start + deltaY));
      element.scrollTop = target;
      return deltaY - (target - start);
    };

    const getHoveredContainer = (event, secondary) => {
      const hoveredNode = document.elementFromPoint(event.clientX, event.clientY);
      if (!hoveredNode) return null;
      if (secondary && secondary.contains(hoveredNode)) return secondary;
      if (primary.contains(hoveredNode)) return primary;
      return null;
    };

    const onWheel = (event) => {
      if (event.defaultPrevented) return;
      const secondary = getSecondaryContainer();
      const preferred = getHoveredContainer(event, secondary) || primary;
      const fallback = preferred === primary ? secondary : primary;
      if (!canScroll(preferred) && !canScroll(fallback)) return;
      let remainingDelta = event.deltaY;
      const startPreferredTop = preferred ? preferred.scrollTop : 0;
      const startFallbackTop = fallback ? fallback.scrollTop : 0;
      remainingDelta = applyDelta(preferred, remainingDelta);
      if (remainingDelta) {
        remainingDelta = applyDelta(fallback, remainingDelta);
      }
      const preferredChanged = !!preferred && preferred.scrollTop !== startPreferredTop;
      const fallbackChanged = !!fallback && fallback.scrollTop !== startFallbackTop;
      if (preferredChanged || fallbackChanged) {
        event.preventDefault();
      }
    };

    const bind = (element) => {
      if (!element || element.dataset.scrollRelayBound === '1') return;
      element.addEventListener('wheel', onWheel, { passive: false });
      element.dataset.scrollRelayBound = '1';
    };

    const refreshBindings = () => {
      bind(primary);
      const secondary = getSecondaryContainer();
      if (secondary && secondary !== boundSecondary) {
        bind(secondary);
        boundSecondary = secondary;
      }
    };

    refreshBindings();
    return { refreshBindings };
  };
  
  const unsubscribeTask = (taskId) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'unsubscribe_task', task_id: taskId }));
    }
  };
  
  initWebSocket();
  
  const generateBtn = document.getElementById('generateBtn');
    const introView = document.getElementById('introView');
    const resultView = document.getElementById('resultView');
    const resultGrid = document.getElementById('resultGrid');
    const resultMeta = document.getElementById('resultMeta');
    const resultStatusMessage = document.getElementById('resultStatusMessage');
    const generationProgressBar = document.getElementById('generationProgressBar');
    const generationProgressFill = generationProgressBar ? generationProgressBar.querySelector('.progress-bar-fill') : null;
    const progressCancelBtn = document.getElementById('progressCancelBtn');
    const taskSummaryLine = document.getElementById('taskSummaryLine');
    const taskOutputCount = document.getElementById('taskOutputCount');
    const taskSelectedCount = document.getElementById('taskSelectedCount');
    const taskSelectAll = document.getElementById('taskSelectAll');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const downloadSelectedBtn = document.getElementById('downloadSelectedBtn');
    const generateTitlesBtn = document.getElementById('generateTitlesBtn');
    const titleSuggestionPanel = document.getElementById('titleSuggestionPanel');
    const previewModal = document.getElementById('previewModal');
    const controlRail = document.querySelector('.control-rail');
    const workspaceMain = document.querySelector('.workspace-main');
    const getActiveResultScrollContainer = () => {
      if (resultView?.classList.contains('active')) {
        return resultView.querySelector('.result-console') || resultView;
      }
      return null;
    };
    const previewBackdrop = document.getElementById('previewBackdrop');
    const previewCloseBtn = document.getElementById('previewCloseBtn');
    const previewDownloadBtn = document.getElementById('previewDownloadBtn');
    const previewImage = document.getElementById('previewImage');
    const previewTitle = document.getElementById('previewTitle');
    const previewType = document.getElementById('previewType');
    const previewPrevBtn = document.getElementById('previewPrevBtn');
    const previewNextBtn = document.getElementById('previewNextBtn');
    const aiWriteBtn = document.getElementById('aiWriteBtn');
    const sellingInput = document.getElementById('sellingInput');
    const sellingMessage = document.getElementById('sellingMessage');
    const styleBtn = document.getElementById('styleBtn');
    const styleResultsMessage = document.getElementById('styleResultsMessage');
    const styleResultsGrid = document.getElementById('styleResultsGrid');
    const platformSelect = document.getElementById('platformSelect');
    const countrySelect = document.getElementById('countrySelect');
    const textTypeSelect = document.getElementById('textTypeSelect');
    const imageSizeSelect = document.getElementById('imageSizeSelect');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const thumbs = document.getElementById('thumbs');
    const referenceFileInput = document.getElementById('referenceFileInput');
    const referenceUploadBtn = document.getElementById('referenceUploadBtn');
    const referenceThumbs = document.getElementById('referenceThumbs');
    const moreActions = document.getElementById('moreActions');
    const mainImageBtn = document.getElementById('mainImageBtn');
    const mainImageMenu = document.getElementById('mainImageMenu');
    const mainImageOptions = Array.from(document.querySelectorAll('[data-main-count]'));
    const moreBtn = document.getElementById('moreBtn');
    const moreMenu = document.getElementById('moreMenu');
    const moreOptions = Array.from(moreMenu ? moreMenu.querySelectorAll('[data-count]') : []);
    const outputCountValue = document.getElementById('outputCountValue');
    const gridLogicValue = document.getElementById('gridLogicValue');
    const navItems = Array.from(document.querySelectorAll('[data-mode]'));
    const aplusModulesSection = document.getElementById('aplusModulesSection');
    const aplusModulesGrid = document.getElementById('aplusModulesGrid');
    const aplusModulesHint = document.getElementById('aplusModulesHint');
    const scrollRelayController = controlRail ? createScrollRelayController(controlRail, getActiveResultScrollContainer) : null;
    const heroEyebrow = document.getElementById('heroEyebrow');
    const heroTitle = document.getElementById('heroTitle');
    const heroDescription = document.getElementById('heroDescription');
    const heroNote = document.getElementById('heroNote');
    const resultEyebrow = document.getElementById('resultEyebrow');
    const resultTitle = document.getElementById('resultTitle');
    const resultSelectAllLabel = document.getElementById('resultSelectAllLabel');
    const outputSystemLabel = document.getElementById('outputSystemLabel');
    const outputSystemMeta = document.getElementById('outputSystemMeta');
    const gridLogicLabel = document.getElementById('gridLogicLabel');
    const gridLogicMeta = document.getElementById('gridLogicMeta');
    const buildEmptyThumbsMarkup = (label = '待上传图片') => `
      <div class="thumb">${label} 1</div>
      <div class="thumb">${label} 2</div>
      <div class="thumb">${label} 3</div>
    `;
    const getProductUploadLimit = () => 3;

    const emptyThumbsMarkup = buildEmptyThumbsMarkup();
    const emptyReferenceThumbsMarkup = buildEmptyThumbsMarkup('待上传参考图');
    const emptyProductThumbsMarkup = buildEmptyThumbsMarkup('待上传商品图');
    const FASHION_SCENE_PLAN_REQUEST_TIMEOUT_MS = 180000;
    const APLUS_MODULE_META = {
      hero_value: {
        title: '首屏主视觉',
        tag: 'Hero',
        detail: '页面开场主视觉，突出商品主体、品牌识别与核心价值主张。',
      },
      usage_scene: {
        title: '使用场景图',
        tag: 'Scene',
        detail: '呈现真实使用场景，让用户快速理解商品用途、对象与使用方式。',
      },
      mood_scene: {
        title: '场景氛围图',
        tag: 'Mood',
        detail: '展示生活方式与情绪氛围，强化审美调性与场景代入感。',
      },
      brand_story: {
        title: '品牌故事图',
        tag: 'Brand',
        detail: '传达品牌理念、品牌调性、信任背书与故事化表达。',
      },
      effect_compare: {
        title: '效果对比图',
        tag: 'Compare',
        detail: '用于展示使用前后、升级前后或不同状态下的变化对比。',
      },
      craft_process: {
        title: '工艺制作图',
        tag: 'Craft',
        detail: '展示工艺制作过程、制造标准、做工流程与品质细节。',
      },
      series_showcase: {
        title: '系列展示图',
        tag: 'Series',
        detail: '展示多色、多规格、多 SKU 或系列化组合陈列。',
      },
      after_sales: {
        title: '售后保障图',
        tag: 'Support',
        detail: '说明质保、退换、客服响应、物流或服务承诺等保障信息。',
      },
      core_selling: {
        title: '核心卖点图',
        tag: 'Selling',
        detail: '聚焦关键差异点与竞争优势，用模块化布局突出转化信息。',
      },
      multi_angle: {
        title: '多角度图',
        tag: 'Angles',
        detail: '从多个角度呈现外观、轮廓、结构与整体形态。',
      },
      detail_zoom: {
        title: '商品细节图',
        tag: 'Detail',
        detail: '放大材质、纹理、接口、缝线、边角等局部细节与工艺。',
      },
      size_capacity: {
        title: '尺寸/容量/尺码图',
        tag: 'Size',
        detail: '展示尺寸、容量、尺码或适配范围等规格信息。',
      },
      spec_table: {
        title: '详细规格/参数表',
        tag: 'Specs',
        detail: '用表格或信息板形式承载更完整的商品参数与数据说明。',
      },
      accessories_gifts: {
        title: '配件/赠品图',
        tag: 'Bundle',
        detail: '明确收货包含的配件、赠品、包装内容与清单信息。',
      },
      ingredients_materials: {
        title: '商品成分图',
        tag: 'Formula',
        detail: '展示配方、材质、面料、成分构成或核心用料信息。',
      },
      usage_tips: {
        title: '使用建议图',
        tag: 'Tips',
        detail: '说明使用方法、注意事项、禁忌提醒与更佳使用建议。',
      },
    };
    const modeConfig = {
      main_image: {
        heroEyebrow: '01 / Cover Shot',
        title: 'AI商品主图',
        description: '上传商品图与参考图后，系统将生成多版本商品封面主图候选，适合作为电商第一张展示图使用。',
        note: 'Cover Only / Product First / No Detail Page',
        resultEyebrow: '02 / Cover Candidates',
        resultTitle: '主图生成结果',
        resultSelectAllLabel: '全选主图',
        outputSystemLabel: 'cover system',
        outputSystemMeta: '多版本封面主图候选，不做详情页、尺寸图、材质图、人群图、对比图或细节放大图。',
        gridLogicLabel: 'grid logic',
        gridLogicMeta: '统一宫格展示，便于对比选择最佳封面主图。',
        generateBtnLabel: '生成主图',
        planLoadingLabel: '正在规划主图方案',
        imageLoadingLabel: '正在生成主图，请稍候',
        initialResultMeta: '系统将根据产品图、参考图与核心卖点生成多版本封面主图候选。',
        initialTaskSummary: '所有图片均为商品封面主图候选，不包含详情页、尺寸图、材质图、人群图、对比图或细节放大图。',
        resultFallback: '已生成主图候选',
        itemFallback: '已生成封面主图候选。',
        successFallback: '已完成 {count} 张主图生成',
        errorFallback: '主图生成失败，请稍后重试',
        selectedPrefix: '正在规划主图方案，并吸收「{style}」风格参考，请稍候…',
        defaultPrefix: '正在规划主图方案，请稍候…',
        imageProgress: '正在生成主图，请稍候…',
        outputStatLabel: '主图张数',
        estimatedSeconds: 90,
      },
      suite: {
        heroEyebrow: '01 / Editorial Intro',
        title: 'AI商品套图',
        description: '上传商品图后，系统将按平台规范、场景逻辑与卖点层级生成整套电商图像方案。新的版式以更强秩序、对比和编辑式结构呈现，适合跨境与平台首页展示。',
        note: 'Flat / Hard Edge / Poster Rhythm / Swiss Red Accent',
        resultEyebrow: '02 / Generated Boards',
        resultTitle: '生成结果',
        resultSelectAllLabel: '全选任务图片',
        outputSystemLabel: 'output system',
        outputSystemMeta: '主图、场景图、模特图、细节图、卖点图与详解图。',
        gridLogicLabel: 'grid logic',
        gridLogicMeta: '生成态采用统一宫格系统，便于浏览与批量处理。',
        generateBtnLabel: '一键生成爆款套图',
        planLoadingLabel: '正在分析套图方案',
        imageLoadingLabel: '正在生成套图，请稍候',
        initialResultMeta: '系统将根据平台策略、卖点与参考图生成真实结果。',
        initialTaskSummary: '统一输出为可选、可下载、可继续衍生标题的规整宫格结构。',
        resultFallback: '已生成真实套图结果',
        itemFallback: '已生成该图类型的套图结果。',
        successFallback: '已完成 {count} 张结果生成',
        errorFallback: '套图生成失败，请稍后重试',
        selectedPrefix: '正在分析套图方案，并吸收「{style}」风格参考，请稍候…',
        defaultPrefix: '正在分析套图方案，请稍候…',
        imageProgress: '正在生成套图，请稍候…',
        outputStatLabel: '输出张数',
        estimatedSeconds: 130,
      },
      mode2: {
        heroEyebrow: '01 / Multi Image Lab',
        title: 'AI模式2多图生成',
        description: '未上传图片时走文生图，上传 1 张或多张商品图时走图生图，适合快速验证 prompt 与成图方向。',
        note: 'Single Output / Prompt First / Edit Or Generate',
        resultEyebrow: '02 / Single Output',
        resultTitle: '模式2结果',
        resultSelectAllLabel: '全选当前图片',
        outputSystemLabel: 'single output',
        outputSystemMeta: '模式2固定单图输出，可直接预览、下载并继续调整提示词。',
        gridLogicLabel: 'generation path',
        gridLogicMeta: '自动根据是否上传图片切换文生图或图生图。',
        generateBtnLabel: '生成模式2图像',
        planLoadingLabel: '正在准备模式2请求',
        imageLoadingLabel: '正在生成模式2图片，请稍候',
        initialResultMeta: '系统将根据提示词与可选参考图生成 1 张模式2图片。',
        initialTaskSummary: '固定单图输出，适合快速试 prompt 和验证图生图效果。',
        resultFallback: '已生成模式2结果',
        itemFallback: '已生成模式2结果。',
        successFallback: '已完成模式2生成',
        errorFallback: '模式2生成失败，请稍后重试',
        selectedPrefix: '正在准备模式2生成，并吸收「{style}」风格参考，请稍候…',
        defaultPrefix: '正在准备模式2生成，请稍候…',
        imageProgress: '模式2正在生成，请稍候…',
        outputStatLabel: '输出张数',
        estimatedSeconds: 40,
      },
      aplus: {
        heroEyebrow: '01 / Module Console',
        title: 'AI A+详情页',
        description: '按平台、卖点与模块顺序生成更清晰的 A+ 结构图，方便继续排版和筛选。',
        note: 'Module Logic / Ordered Output',
        resultEyebrow: '02 / Module Boards',
        resultTitle: 'A+ 模块结果',
        resultSelectAllLabel: '全选模块图片',
        outputSystemLabel: 'module',
        outputSystemMeta: '主视觉、卖点、细节、场景与服务信息分模块输出。',
        gridLogicLabel: 'sequence',
        gridLogicMeta: '按叙事顺序查看，更适合高信息密度页面。',
        generateBtnLabel: '一键生成A+详情页',
        planLoadingLabel: '正在分析 A+ 模块方案',
        imageLoadingLabel: '正在生成 A+ 模块，请稍候',
        initialResultMeta: '系统将根据平台策略、卖点、参考图与所选模块生成 A+ 模块结果。',
        initialTaskSummary: '统一输出为可选、可下载、可继续衍生标题的 A+ 模块结构。',
        resultFallback: '已生成 A+ 详情页模块结果',
        itemFallback: '已生成该模块的 A+ 结果。',
        successFallback: '已完成 {count} 个模块结果生成',
        errorFallback: 'A+ 详情页生成失败，请稍后重试',
        selectedPrefix: '正在分析 A+ 模块方案，并吸收「{style}」风格参考，请稍候…',
        defaultPrefix: '正在分析 A+ 模块方案，请稍候…',
        imageProgress: '正在生成 A+ 模块，请稍候…',
        outputStatLabel: '模块数量',
        estimatedSeconds: 90,
      },
      fashion: {
        heroEyebrow: '01 / Styling Intro',
        title: 'AI服饰穿戴',
        description: '上传服饰商品图后，系统会按穿搭展示、模特氛围、卖点层级与平台展示逻辑生成更适合服装类商品的视觉方案，适合做穿搭套图与展示页素材。',
        note: 'Editorial Styling / Model Story / Outfit Focus / Fashion Contrast',
        resultEyebrow: '02 / Look Outputs',
        resultTitle: '穿搭结果',
        resultSelectAllLabel: '全选穿搭图片',
        outputSystemLabel: 'look system',
        outputSystemMeta: '输出可用于穿搭展示、氛围场景、面料细节与尺码说明的服饰视觉结果。',
        gridLogicLabel: 'styling logic',
        gridLogicMeta: '以穿搭叙事和商品主体统一性组织结果，适合服装类商品连续出图。',
        generateBtnLabel: '一键生成服饰穿戴图',
        planLoadingLabel: '正在分析服饰穿搭方案',
        imageLoadingLabel: '正在生成服饰穿戴图，请稍候',
        initialResultMeta: '系统将根据服饰商品图、已选模特与场景设置生成服饰穿戴结果。',
        initialTaskSummary: '统一输出为适合服装展示、筛选下载与继续排版的结果结构。',
        resultFallback: '已生成服饰穿戴结果',
        itemFallback: '已生成该服饰展示结果。',
        successFallback: '已完成 {count} 张服饰结果生成',
        errorFallback: '服饰穿戴生成失败，请稍后重试',
        selectedPrefix: '正在分析已选场景并生成服饰穿搭方案，请稍候…',
        defaultPrefix: '正在分析服饰穿搭方案，请稍候…',
        imageProgress: '正在生成服饰穿戴图，请稍候…',
        outputStatLabel: '输出张数',
        estimatedSeconds: 150,
      },
    };
    const defaultStyleBtnLabel = '开始分析';
    const refreshStyleBtnLabel = '重新分析风格';
    const platformLoadingLabels = {
      '亚马逊': '正在分析亚马逊趋势',
      '淘宝天猫1688': '正在分析天猫趋势',
      'Temu': '正在分析 Temu 趋势',
      'TikTok Shop': '正在分析 TikTok Shop 趋势',
      '拼多多抖音电商': '正在分析拼多多抖音电商趋势',
      'OZON': '正在分析 OZON 趋势',
      '独立站': '正在分析独立站趋势',
      'Shopee': '正在分析 Shopee 趋势',
      '阿里国际站': '正在分析阿里国际站趋势',
      '速卖通': '正在分析速卖通趋势',
      'SHEIN': '正在分析 SHEIN 趋势',
      '京东': '正在分析京东趋势',
    };
    const platformSuccessLabels = {
      '亚马逊': '已生成 4 组亚马逊风格方案',
      '淘宝天猫1688': '已生成 4 组天猫风格方案',
      'Temu': '已生成 4 组 Temu 风格方案',
      'TikTok Shop': '已生成 4 组 TikTok Shop 风格方案',
      '拼多多抖音电商': '已生成 4 组拼多多抖音电商风格方案',
      'OZON': '已生成 4 组 OZON 风格方案',
      '独立站': '已生成 4 组独立站风格方案',
      'Shopee': '已生成 4 组 Shopee 风格方案',
      '阿里国际站': '已生成 4 组阿里国际站风格方案',
      '速卖通': '已生成 4 组速卖通风格方案',
      'SHEIN': '已生成 4 组 SHEIN 风格方案',
      '京东': '已生成 4 组京东风格方案',
    };
    const PAGE_MODE = document.body.dataset.pageMode || 'suite';
    const isAplusPage = PAGE_MODE === 'aplus';
    const isFashionPage = PAGE_MODE === 'fashion';
    const isMode2Page = PAGE_MODE === 'mode2';
    let currentMode = PAGE_MODE;
    let selectedOutputCount = 6;
    let selectedMainImageCount = 0;
    let selectedAplusModules = new Set(isAplusPage
      ? ['hero_value', 'usage_scene', 'core_selling', 'detail_zoom']
      : []);
    let currentResult = null;
    let currentResultItems = [];
    let selectedResultKeys = new Set();
    let previewIndex = -1;
    let currentStyleResults = [];
    let selectedStyleIndex = -1;
    let fashionCtaState = {
      hasSelectedModel: false,
      label: '请选择模特',
    };
    const STORAGE_KEY = `aiDesignState:${PAGE_MODE}`;
    const PENDING_GENERATION_POLL_INTERVAL_MIN = 2000;
    const PENDING_GENERATION_POLL_INTERVAL_MAX = 6000;
    const PENDING_GENERATION_TIMEOUT = 11 * 60 * 1000;
    const PENDING_GENERATION_MAX_STATUS_FAILURES = 3;

    const getDynamicPollInterval = (elapsedMs) => {
      if (elapsedMs < 10000) return 2000;
      if (elapsedMs < 30000) return 3000;
      if (elapsedMs < 120000) return 5000;
      return 8000;
    };
    let pendingGenerationTask = null;
    let pendingGenerationPollTimer = null;
    let pendingGenerationPollFailureCount = 0;
    let isRestoringState = false;

    const escapeHtml = (value = '') => String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

    const setStyleButtonLabel = (label) => {
      styleBtn.innerHTML = `<span>${label}</span><span class="btn-icon">↻</span>`;
    };

    const getPlatformLabel = () => platformSelect?.value || '亚马逊';
    const getCountryReference = () => countrySelect?.value || '中国';
    const getTextType = () => textTypeSelect?.value || '中文';
    const getImageSizeRatio = () => {
      if (isFashionPage) {
        return document.querySelector('input[name="outputSpec"]:checked')?.value || '3:4';
      }
      return imageSizeSelect?.value || '1:1';
    };

    const getStyleLoadingLabel = () => platformLoadingLabels[getPlatformLabel()] || `正在分析 ${getPlatformLabel()} 趋势`;

    const getStyleSuccessMessage = () => platformSuccessLabels[getPlatformLabel()] || `已生成 4 组${getPlatformLabel()}风格方案`;

    const formatOutputCount = (count) => String(count).padStart(2, '0');

    const getCurrentModeConfig = () => modeConfig[currentMode] || modeConfig[PAGE_MODE] || modeConfig.suite;

    const getGridLogicLabel = (count) => {
      const columns = count <= 8 ? 2 : 3;
      return `${columns}×${Math.ceil(count / columns)}`;
    };

    const normalizeFashionSceneGroups = (groups) => {
      if (!Array.isArray(groups)) {
        return [];
      }
      return groups
        .filter((group) => group && typeof group === 'object')
        .map((group, groupIndex) => {
          const groupId = String(group.id || `scene-group-${groupIndex + 1}`);
          return {
            id: groupId,
            title: String(group.title || `场景组 ${groupIndex + 1}`),
            subtitle: String(group.subtitle || group.summary || group.description || ''),
            prompt: String(group.prompt || group.scene_prompt || group.scenePrompt || ''),
            poses: Array.isArray(group.poses)
              ? group.poses
                .filter((pose) => pose && typeof pose === 'object')
                .map((pose, poseIndex) => {
                  const rawPoseId = String(pose.id || '').trim();
                  return {
                    id: rawPoseId.startsWith(`${groupId}-`) ? rawPoseId : `${groupId}-pose-${poseIndex + 1}`,
                    title: String(pose.title || `姿态 ${poseIndex + 1}`),
                    subtitle: String(pose.subtitle || pose.summary || pose.description || ''),
                    prompt: String(pose.prompt || pose.pose_prompt || pose.scene_prompt || pose.posePrompt || ''),
                  };
                })
              : [],
          };
        })
        .filter((group) => group.poses.length > 0);
    };

    const normalizeFashionCameraValue = (value, allowedValues) => {
      const normalized = String(value || '').trim();
      return allowedValues.includes(normalized) ? normalized : '';
    };
    const inferFashionShotSize = (group, pose) => {
      const text = [group?.title, group?.subtitle, group?.prompt, pose?.title, pose?.subtitle, pose?.prompt]
        .filter(Boolean)
        .join(' ');
      if (/特写|近景|局部|细节|拉链|袖口|领口|纽扣|面料|纹理/.test(text)) {
        return '特写';
      }
      if (/半身|上半身|胸像/.test(text)) {
        return '半身';
      }
      if (/四分之三|3\/4|七分身|中景/.test(text)) {
        return '四分之三';
      }
      if (/全身|全景|站立|直立|完整|通身|落地/.test(text)) {
        return '全身';
      }
      return '半身';
    };
    const inferFashionViewAngle = (group, pose) => {
      const text = [group?.title, group?.subtitle, group?.prompt, pose?.title, pose?.subtitle, pose?.prompt]
        .filter(Boolean)
        .join(' ');
      if (/3\/4|四分之三|45度|斜侧|侧前方/.test(text)) {
        return '3/4侧';
      }
      if (/背面|背影|后背|背部/.test(text)) {
        return '背面';
      }
      if (/侧面|侧身|侧向/.test(text)) {
        return '侧面';
      }
      if (/正面|正向|正对/.test(text)) {
        return '正面';
      }
      return '正面';
    };
    const buildFashionPoseCameraSetting = (group, pose, currentSetting = {}) => ({
      shotSize: normalizeFashionCameraValue(currentSetting.shotSize, ['全身', '四分之三', '半身', '特写']) || inferFashionShotSize(group, pose),
      viewAngle: normalizeFashionCameraValue(currentSetting.viewAngle, ['正面', '侧面', '3/4侧', '背面']) || inferFashionViewAngle(group, pose),
    });
    const compactText = (value = '', maxLength = 32) => {
      const normalized = String(value || '').replace(/\s+/g, ' ').trim();
      if (!normalized) {
        return '';
      }
      return normalized.length > maxLength ? `${normalized.slice(0, maxLength).trim()}…` : normalized;
    };

    const getFashionSelectionState = () => {
      try {
        const fashionApi = window.fashionWorkspace;
        if (fashionApi && typeof fashionApi.getState === 'function') {
          return fashionApi.getState().cta || {
            hasSelectedModel: false,
            disabled: true,
            label: '请选择模特',
            step: 'model',
            action: 'select_model',
          };
        }

        const rawState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const sceneGroups = normalizeFashionSceneGroups(rawState.fashionSceneGroups);
        const validPoseIds = new Set(sceneGroups.flatMap((group) => group.poses.map((pose) => pose.id)));
        const selectedSource = rawState.fashionSelectedModelSource === 'custom'
          ? 'custom'
          : rawState.fashionSelectedModelSource === 'ai'
            ? 'ai'
            : '';
        const selectedId = typeof rawState.fashionSelectedModelId === 'string' ? rawState.fashionSelectedModelId : '';
        const customModels = Array.isArray(rawState.fashionCustomModels) ? rawState.fashionCustomModels : [];
        const generatedModel = rawState.fashionGeneratedModel && typeof rawState.fashionGeneratedModel === 'object'
          ? rawState.fashionGeneratedModel
          : null;
        const generationDone = rawState.fashionModelGenerationState === 'done'
          && generatedModel
          && generatedModel.id === selectedId;
        const customSelected = selectedSource === 'custom'
          && customModels.some((item) => item && item.id === selectedId);
        const hasSelectedModel = selectedSource === 'ai' ? Boolean(generationDone) : Boolean(customSelected);
        const selectedModel = selectedSource === 'ai'
          ? (generationDone ? generatedModel : null)
          : customModels.find((item) => item && item.id === selectedId);
        const hasSelectedModelImage = Boolean(
          selectedModel
          && (selectedModel.imageUrl || selectedModel.previewUrl || selectedModel.imagePath || selectedModel.downloadName),
        );
        const isSceneCapableStep = rawState.fashionFlowStep === 'scene' || rawState.fashionFlowStep === 'result';
        const currentStep = rawState.fashionFlowStep === 'result' ? 'result' : isSceneCapableStep ? 'scene' : 'model';
        const sceneGenerationState = rawState.fashionSceneGenerationState;
        const hasSceneGroups = sceneGroups.length > 0;
        const selectedPoseIds = Array.isArray(rawState.fashionSelectedPoseIds)
          ? rawState.fashionSelectedPoseIds
            .map((item) => String(item || '').trim())
            .filter((item, index, list) => item && validPoseIds.has(item) && list.indexOf(item) === index)
          : [];
        const selectedSceneCount = selectedPoseIds.length;
        const hasPose = selectedSceneCount > 0;

        if (!hasSelectedModel) {
          return {
            hasSelectedModel: false,
            disabled: true,
            label: '请选择模特',
            step: currentStep,
            action: 'select_model',
          };
        }
        if (!hasSelectedModelImage) {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '模特图片缺失',
            step: currentStep,
            action: 'select_model',
          };
        }
        if (sceneGenerationState === 'loading') {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '生成中...',
            step: currentStep,
            action: 'loading',
          };
        }
        if (sceneGenerationState !== 'done' || !hasSceneGroups) {
          return {
            hasSelectedModel: true,
            disabled: false,
            label: sceneGenerationState === 'error' ? '重新生成推荐场景' : '生成推荐场景',
            step: currentStep,
            action: 'scene_plan',
          };
        }
        if (!hasPose) {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '请选择场景',
            step: currentStep,
            action: 'select_scene',
          };
        }
        return {
          hasSelectedModel: true,
          disabled: false,
          label: `生成服饰穿戴图（${selectedSceneCount}个场景）`,
          step: currentStep,
          action: 'generate',
          selectedSceneCount,
        };
      } catch (error) {
        console.error('Failed to read fashion selection state:', error);
        return {
          hasSelectedModel: false,
          disabled: true,
          label: '请选择模特',
          step: 'model',
          action: 'select_model',
        };
      }
    };

    const applyFashionGenerateButtonState = (state = getFashionSelectionState()) => {
      fashionCtaState = {
        hasSelectedModel: Boolean(state.hasSelectedModel),
        disabled: Boolean(state.disabled),
        label: state.label || '请选择模特',
        step: state.step === 'scene' || state.step === 'result' ? state.step : 'model',
      };
      if (!generateBtn) {
        return;
      }
      generateBtn.disabled = fashionCtaState.disabled;
      updateGenerateButtonLabel(fashionCtaState.label);
      generateBtn.classList.toggle('fashion-generate-btn-disabled', fashionCtaState.disabled);
      generateBtn.classList.toggle('fashion-generate-btn-active', !fashionCtaState.disabled);
    };

    const getElementValue = (element) => {
      if (!element) {
        return '';
      }
      if (element.type === 'checkbox' || element.type === 'radio') {
        return element.checked;
      }
      return element.value;
    };

    const setElementValue = (element, value) => {
      if (!element || value === undefined || value === null) {
        return;
      }
      if (element.type === 'checkbox' || element.type === 'radio') {
        element.checked = Boolean(value);
        return;
      }
      element.value = value;
    };

    const collectControlValues = () => {
      const controls = [sellingInput, platformSelect, countrySelect, textTypeSelect, imageSizeSelect]
        .filter(Boolean);
      return controls.reduce((acc, element) => {
        if (element.id) {
          acc[element.id] = getElementValue(element);
        }
        return acc;
      }, {});
    };

    const restoreControlValues = (values = {}) => {
      const safeValues = values && typeof values === 'object' && !Array.isArray(values) ? values : {};
      [sellingInput, platformSelect, countrySelect, textTypeSelect, imageSizeSelect].forEach((element) => {
        if (!element?.id || !(element.id in safeValues)) {
          return;
        }
        setElementValue(element, safeValues[element.id]);
      });
    };

    const captureScrollState = () => ({
      windowY: window.scrollY || window.pageYOffset || 0,
      controlRail: controlRail ? controlRail.scrollTop : 0,
      workspaceMain: workspaceMain ? workspaceMain.scrollTop : 0,
    });

    const restoreScrollState = (scrollState = {}) => {
      window.requestAnimationFrame(() => {
        if (typeof scrollState.controlRail === 'number' && controlRail) {
          controlRail.scrollTop = scrollState.controlRail;
        }
        if (typeof scrollState.workspaceMain === 'number' && workspaceMain) {
          workspaceMain.scrollTop = scrollState.workspaceMain;
        }
        if (typeof scrollState.windowY === 'number' && !previewModal?.hidden) {
          return;
        }
        if (typeof scrollState.windowY === 'number') {
          window.scrollTo({ top: scrollState.windowY, left: 0, behavior: 'auto' });
        }
      });
    };

    const getViewState = () => ({
      introActive: introView.classList.contains('active'),
      resultActive: resultView.classList.contains('active'),
    });

    const applyViewState = (viewState = {}) => {
      const showResult = Boolean(viewState.resultActive);
      introView.classList.toggle('active', !showResult);
      resultView.classList.toggle('active', showResult);
      scrollRelayController?.refreshBindings();
    };

    const getTitleSuggestionsState = () => ({
      hidden: titleSuggestionPanel.hidden,
      html: titleSuggestionPanel.innerHTML,
      suggestions: titleSuggestionPanel.dataset.suggestions || '[]',
    });

    const restoreTitleSuggestionsState = (titleState = {}) => {
      titleSuggestionPanel.hidden = titleState.hidden ?? true;
      titleSuggestionPanel.innerHTML = titleState.html || '';
      titleSuggestionPanel.dataset.suggestions = titleState.suggestions || '[]';
    };

    const getCurrentOutputMetric = (result = currentResult) => {
      const activeMode = result?.mode || currentMode;
      if (activeMode === 'aplus') {
        return result?.plan?.module_count || result?.images?.length || Math.max(selectedAplusModules.size, 1);
      }
      if (activeMode === 'mode2' || activeMode === 'mode2-text2image' || activeMode === 'mode2-image-edit') {
        return result?.plan?.output_count || result?.images?.length || selectedOutputCount;
      }
      return result?.plan?.output_count || result?.images?.length || selectedOutputCount;
    };

    const syncOutputCountSummary = () => {
      if (taskOutputCount) {
        taskOutputCount.textContent = String(getCurrentOutputMetric()).padStart(2, '0');
      }
      if (currentMode === 'aplus') {
        outputCountValue.textContent = formatOutputCount(selectedAplusModules.size);
        gridLogicValue.textContent = `${selectedAplusModules.size} 模块`;
        return;
      }
      if (currentMode === 'mode2') {
        outputCountValue.textContent = formatOutputCount(selectedOutputCount);
        gridLogicValue.textContent = currentFiles.length ? '图生图' : '文生图';
        if (moreActions) {
          moreActions.hidden = true;
        }
        return;
      }
      outputCountValue.textContent = formatOutputCount(selectedOutputCount);
      gridLogicValue.textContent = getGridLogicLabel(selectedOutputCount);
      syncMainImageButtonLabel();
      syncMoreButtonLabel();
    };

    const updateGenerateButtonLabel = (label) => {
      if (isFashionPage) {
        generateBtn.textContent = label || fashionCtaState.label || '请选择模特';
        return;
      }
      generateBtn.textContent = label || getCurrentModeConfig().generateBtnLabel;
    };

    const renderAplusModuleCards = () => {
      if (!aplusModulesGrid || !aplusModulesHint) {
        return;
      }
      const cards = Array.from(aplusModulesGrid.querySelectorAll('[data-module]'));
      cards.forEach((card) => {
        const key = card.dataset.module;
        const isSelected = selectedAplusModules.has(key);
        card.classList.toggle('is-selected', isSelected);
        card.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
      });
      aplusModulesHint.textContent = `已选 ${selectedAplusModules.size}`;
    };

    const setMode = (mode, options = {}) => {
      const { preserveResultState = false, skipPersist = false } = options;
      currentMode = ['suite', 'mode2', 'aplus', 'fashion'].includes(mode) ? mode : PAGE_MODE;
      const config = getCurrentModeConfig();
      navItems.forEach((item) => {
        const isActive = item.dataset.mode === currentMode;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
      if (aplusModulesSection) {
        aplusModulesSection.hidden = currentMode !== 'aplus';
      }
      if (moreActions) {
        moreActions.hidden = currentMode === 'aplus' || currentMode === 'mode2';
      }
      heroEyebrow.textContent = config.heroEyebrow;
      heroTitle.textContent = config.title;
      heroDescription.textContent = config.description;
      heroNote.textContent = config.note;
      resultEyebrow.textContent = config.resultEyebrow;
      resultTitle.textContent = config.resultTitle;
      if (resultSelectAllLabel) {
        resultSelectAllLabel.textContent = config.resultSelectAllLabel;
      }
      outputSystemLabel.textContent = config.outputSystemLabel;
      outputSystemMeta.textContent = config.outputSystemMeta;
      gridLogicLabel.textContent = config.gridLogicLabel;
      gridLogicMeta.textContent = config.gridLogicMeta;
      updateGenerateButtonLabel(config.generateBtnLabel);
      if (isFashionPage) {
        applyFashionGenerateButtonState();
      }
      const outputStatLabel = document.querySelector('#taskStats .task-stat .stat-label');
      if (outputStatLabel) {
        outputStatLabel.textContent = config.outputStatLabel;
      }
      renderAplusModuleCards();
      syncOutputCountSummary();
      if (!preserveResultState) {
        resetResultState();
      }
      if (!skipPersist) {
        persistState();
      }
    };

    const closeMoreMenu = () => {
      if (moreMenu && moreBtn) {
        moreMenu.hidden = true;
        moreBtn.setAttribute('aria-expanded', 'false');
      }
      persistState();
    };

    const closeMainImageMenu = () => {
      if (mainImageMenu && mainImageBtn) {
        mainImageMenu.hidden = true;
        mainImageBtn.setAttribute('aria-expanded', 'false');
      }
      persistState();
    };

    const syncMainImageButtonLabel = () => {
      if (!mainImageBtn) {
        return;
      }
      mainImageBtn.textContent = `主图(${selectedMainImageCount}张)`;
      mainImageBtn.setAttribute('aria-label', `单独生成主图，当前已选 ${selectedMainImageCount} 张`);
    };

    const openMainImageMenu = () => {
      if (mainImageMenu && mainImageBtn) {
        mainImageMenu.hidden = false;
        mainImageBtn.setAttribute('aria-expanded', 'true');
      }
      persistState();
    };

    const syncMoreButtonLabel = () => {
      if (!moreBtn) {
        return;
      }
      moreBtn.textContent = `详情页(${selectedOutputCount}张)`;
      moreBtn.setAttribute('aria-label', `详情页生成，当前已选输出 ${selectedOutputCount} 张`);
    };

    const openMoreMenu = () => {
      if (moreMenu && moreBtn) {
        moreMenu.hidden = false;
        moreBtn.setAttribute('aria-expanded', 'true');
      }
      persistState();
    };

    const setSelectedMainImageCount = (count) => {
      selectedMainImageCount = Math.min(Math.max(Number(count) || 0, 0), 10);
      if (mainImageOptions && mainImageOptions.length > 0) {
        mainImageOptions.forEach((option) => {
          option.classList.toggle('is-selected', Number(option.dataset.mainCount) === selectedMainImageCount);
        });
      }
      syncMainImageButtonLabel();
      persistState();
    };

    const setSelectedOutputCount = (count) => {
      const normalizedCount = Number(count);
      selectedOutputCount = Number.isFinite(normalizedCount) ? normalizedCount : 6;
      if (moreOptions && moreOptions.length > 0) {
        moreOptions.forEach((option) => {
          option.classList.toggle('is-selected', Number(option.dataset.count) === selectedOutputCount);
        });
      }
      syncMoreButtonLabel();
      syncOutputCountSummary();
      persistState();
    };

    const getCompositeGenerateSelection = (isMode2 = false) => {
      const mainImageCount = Math.min(Math.max(Number(selectedMainImageCount) || 0, 0), 10);
      const detailImageCount = isMode2 ? getMode2RequestedOutputCount() : Math.min(Math.max(Number(selectedOutputCount) || 0, 0), 10);
      const shouldGenerateMainImage = mainImageCount > 0;
      const shouldGenerateDetailImage = detailImageCount > 0;
      let mode = 'none';
      if (shouldGenerateMainImage && shouldGenerateDetailImage) {
        mode = 'both';
      } else if (shouldGenerateMainImage) {
        mode = 'main_only';
      } else if (shouldGenerateDetailImage) {
        mode = 'detail_only';
      }
      return {
        mode,
        mainImageCount,
        detailImageCount,
        shouldGenerateMainImage,
        shouldGenerateDetailImage,
        totalOutputCount: mainImageCount + detailImageCount,
      };
    };

    const getCompositeGenerateStatusMessage = (selection) => {
      if (selection.mode === 'both') {
        return `开始生成主图 ${selection.mainImageCount} 张和详情页 ${selection.detailImageCount} 张...`;
      }
      if (selection.mode === 'main_only') {
        return `开始生成主图，共 ${selection.mainImageCount} 张...`;
      }
      if (selection.mode === 'detail_only') {
        return `开始生成详情页，共 ${selection.detailImageCount} 张...`;
      }
      return '请至少选择 1 张主图或 1 张详情页。';
    };

    const toggleAplusModule = (key) => {
      if (!isAplusPage || !APLUS_MODULE_META[key]) {
        return;
      }
      if (selectedAplusModules.has(key)) {
        if (selectedAplusModules.size === 1) {
          if (aplusModulesHint) {
            aplusModulesHint.textContent = '至少选择 1 个模块';
          }
          return;
        }
        selectedAplusModules.delete(key);
      } else {
        selectedAplusModules.add(key);
      }
      renderAplusModuleCards();
      syncOutputCountSummary();
      persistState();
    };

    const getSelectedStyle = () => {
      if (selectedStyleIndex < 0 || selectedStyleIndex >= currentStyleResults.length) {
        return null;
      }
      return currentStyleResults[selectedStyleIndex] || null;
    };

    const buildSelectedStyleMeta = (style) => {
      if (!style || typeof style !== 'object') {
        return '';
      }
      const title = String(style.title || '').trim();
      if (!title) {
        return '';
      }
      return `风格：${title}`;
    };

    const updateStyleSelectionMessage = () => {
      if (!styleResultsMessage) {
        return;
      }
      const selectedStyle = getSelectedStyle();
      if (!currentStyleResults.length) {
        styleResultsMessage.textContent = '';
        styleResultsMessage.className = 'style-results-message';
        return;
      }
      if (selectedStyle) {
        styleResultsMessage.textContent = `已选「${compactText(selectedStyle.title || '', 18)}」`;
        styleResultsMessage.className = 'style-results-message success';
        return;
      }
      styleResultsMessage.textContent = '点击卡片即可引用';
      styleResultsMessage.className = 'style-results-message';
    };

    const renderStyleCards = (styles = currentStyleResults) => {
      if (!styleResultsGrid) {
        currentStyleResults = Array.isArray(styles) ? styles : [];
        updateStyleSelectionMessage();
        return;
      }
      currentStyleResults = Array.isArray(styles) ? styles : [];
      if (!currentStyleResults.length) {
        styleResultsGrid.innerHTML = '';
        updateStyleSelectionMessage();
        return;
      }
      styleResultsGrid.innerHTML = currentStyleResults.map((style, index) => {
        const isSelected = index === selectedStyleIndex;
        const selectedClass = isSelected ? ' is-selected' : '';
        return `
          <button class="style-card${selectedClass}" type="button" data-role="select-style" data-index="${index}" aria-pressed="${isSelected ? 'true' : 'false'}">
            <div class="style-card-topline">
              <div class="style-card-title">${escapeHtml(compactText(style.title || '', 18))}</div>
            </div>
            <div class="style-card-colors">
              ${(Array.isArray(style.colors) ? style.colors : []).map((color) => `<span class="style-color-dot" style="background:${color}" title="${color}"></span>`).join('')}
            </div>
            <p class="style-card-reasoning">${escapeHtml(compactText(style.reasoning || '', 34))}</p>
          </button>
        `;
      }).join('');
      updateStyleSelectionMessage();
    };

    const selectStyleCard = (index) => {
      if (index < 0 || index >= currentStyleResults.length) {
        return;
      }
      selectedStyleIndex = index;
      renderStyleCards();
      persistState();
    };

    const appendFilesToFormData = (formData, fieldName, files, limit = 3) => {
      Array.from(files || []).slice(0, limit).forEach((file) => {
        formData.append(fieldName, file);
      });
    };

    const UPLOAD_PREVIEW_MAX_EDGE = 320;
    const UPLOAD_PREVIEW_QUALITY = 0.72;
    const UPLOAD_CONCURRENCY = 3;
    const UPLOAD_COMPRESS_MAX_EDGE = 2048;
    const UPLOAD_COMPRESS_QUALITY = 0.86;
    const UPLOAD_COMPRESS_THRESHOLD = 1024 * 1024;

    const formatFileSize = (bytes = 0) => {
      const size = Number(bytes) || 0;
      if (size >= 1024 * 1024) {
        return `${(size / 1024 / 1024).toFixed(1)}MB`;
      }
      if (size >= 1024) {
        return `${Math.max(1, Math.round(size / 1024))}KB`;
      }
      return `${size}B`;
    };

    const updateUploadHintText = (uploadHint, message) => {
      if (uploadHint && message) {
        uploadHint.textContent = message;
      }
    };

    const buildImagePreviewUrl = (file) => new Promise((resolve) => {
      if (!file || !file.type || !file.type.startsWith('image/')) {
        resolve('');
        return;
      }
      const objectUrl = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => {
        const width = image.naturalWidth || image.width || 0;
        const height = image.naturalHeight || image.height || 0;
        if (!width || !height) {
          URL.revokeObjectURL(objectUrl);
          resolve(objectUrl);
          return;
        }
        const scale = Math.min(1, UPLOAD_PREVIEW_MAX_EDGE / Math.max(width, height));
        if (scale >= 1) {
          resolve(objectUrl);
          return;
        }
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const context = canvas.getContext('2d');
        if (!context) {
          resolve(objectUrl);
          return;
        }
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(objectUrl);
        resolve(canvas.toDataURL('image/jpeg', UPLOAD_PREVIEW_QUALITY));
      };
      image.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        resolve('');
      };
      image.src = objectUrl;
    });

    const uploadFilesWithConcurrency = async (files, worker, concurrency = UPLOAD_CONCURRENCY) => {
      const selectedFiles = Array.from(files || []);
      const results = new Array(selectedFiles.length);
      let nextIndex = 0;
      const workerCount = Math.max(1, Math.min(concurrency, selectedFiles.length));
      await Promise.all(Array.from({ length: workerCount }, async () => {
        while (nextIndex < selectedFiles.length) {
          const index = nextIndex;
          nextIndex += 1;
          results[index] = await worker(selectedFiles[index], index);
        }
      }));
      return results;
    };

    const compressImageForUpload = (file) => new Promise((resolve) => {
      if (!file || !file.type || !file.type.startsWith('image/') || file.type === 'image/gif' || file.size < UPLOAD_COMPRESS_THRESHOLD) {
        resolve(file);
        return;
      }
      const objectUrl = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => {
        const width = image.naturalWidth || image.width || 0;
        const height = image.naturalHeight || image.height || 0;
        const scale = Math.min(1, UPLOAD_COMPRESS_MAX_EDGE / Math.max(width, height));
        if (!width || !height || scale >= 1) {
          URL.revokeObjectURL(objectUrl);
          resolve(file);
          return;
        }
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        const context = canvas.getContext('2d');
        if (!context) {
          URL.revokeObjectURL(objectUrl);
          resolve(file);
          return;
        }
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
          URL.revokeObjectURL(objectUrl);
          if (!blob || blob.size >= file.size) {
            resolve(file);
            return;
          }
          const compressedFile = new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), {
            type: 'image/jpeg',
            lastModified: Date.now(),
          });
          compressedFile._originalSize = file.size;
          resolve(compressedFile);
        }, 'image/jpeg', UPLOAD_COMPRESS_QUALITY);
      };
      image.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(file);
      };
      image.src = objectUrl;
    });

    const uploadFileToCosDirect = async (file, { storageGroup, storageSubdir = 'uploads' }) => {
      const presignResponse = await fetch('/api/reference-images/presign', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: file.name || 'image.jpg',
          content_type: file.type || 'application/octet-stream',
          file_size: file.size || 0,
          storage_group: storageGroup || 'temp',
          storage_subdir: storageSubdir || 'uploads',
        }),
      });
      const presign = await presignResponse.json().catch(() => ({}));
      if (!presignResponse.ok || !presign || presign.success === false || !presign.upload_url) {
        throw new Error((presign && presign.error) || '获取上传签名失败，请稍后重试');
      }
      const uploadResponse = await fetch(presign.upload_url, {
        method: 'PUT',
        headers: presign.headers || { 'Content-Type': file.type || 'application/octet-stream' },
        body: file,
      });
      if (!uploadResponse.ok) {
        throw new Error(`图片直传 COS 失败（${uploadResponse.status}）`);
      }
      return {
        imageUrl: String(presign.image_url || ''),
        imagePath: String(presign.image_path || ''),
        downloadName: String(presign.download_name || file.name || ''),
        mimeType: String(presign.mime_type || file.type || ''),
        storageGroup: String(presign.storage_group || storageGroup || ''),
        storageBackend: String(presign.storage_backend || 'cos'),
        compressedSize: file.size || 0,
        originalSize: file._originalSize || file.size || 0,
      };
    };

    const appendImageUrlsToFormData = (formData, fieldName, items, limit = 3) => {
      Array.from(items || []).slice(0, limit).forEach((item) => {
        const imageUrl = typeof item?.imageUrl === 'string' ? item.imageUrl.trim() : '';
        if (imageUrl) {
          formData.append(fieldName, imageUrl);
        }
      });
    };

    const getFashionWorkspaceApi = () => {
      const api = window.fashionWorkspace;
      return api && typeof api.getState === 'function' ? api : null;
    };

    const syncFashionState = (patch = {}) => {
      const api = getFashionWorkspaceApi();
      if (api && typeof api.patchState === 'function') {
        api.patchState(patch);
        return api.getState();
      }
      try {
        const rawState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const nextState = { ...rawState, ...(patch || {}) };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
      } catch (error) {
        console.error('Failed to sync fashion state:', error);
      }
      return null;
    };

    const clearFashionSceneStatePatch = () => ({
      fashionFlowStep: 'model',
      fashionSceneGenerationState: 'idle',
      fashionSceneGroups: [],
      fashionSelectedSceneGroupIds: [],
      fashionSelectedPoseIds: [],
      fashionPoseCameraSettings: {},
      fashionScenePrompt: '',
      fashionSceneError: '',
      fashionScenePlanRaw: null,
      fashionSceneStateVersion: 2,
    });

    const resetStaleFashionLoadingState = () => {
      if (!isFashionPage) {
        return;
      }
      try {
        const rawState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const patch = {};

        if (rawState.fashionSceneStateVersion !== 2) {
          Object.assign(patch, clearFashionSceneStatePatch());
        }

        if (rawState.fashionModelGenerationState === 'loading') {
          patch.fashionModelGenerationState = 'idle';
        }
        if (rawState.fashionSceneGenerationState === 'loading') {
          patch.fashionSceneGenerationState = 'idle';
          patch.fashionSceneError = '';
        }

        if (Object.keys(patch).length) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...rawState, ...patch }));
        }
      } catch (error) {
        console.error('Failed to reset stale fashion loading state:', error);
      }
    };

    const setFashionFlowStepState = (step) => {
      const api = getFashionWorkspaceApi();
      if (api && typeof api.setFlowStep === 'function') {
        api.setFlowStep(step);
        return api.getState();
      }
      return syncFashionState({ fashionFlowStep: step === 'scene' || step === 'result' ? step : 'model' });
    };

    const resolveFashionSelectedModel = (fashionState) => {
      if (!fashionState || typeof fashionState !== 'object') {
        return null;
      }
      const selectedSource = fashionState.fashionSelectedModelSource === 'custom'
        ? 'custom'
        : fashionState.fashionSelectedModelSource === 'ai'
          ? 'ai'
          : '';
      const selectedId = typeof fashionState.fashionSelectedModelId === 'string'
        ? fashionState.fashionSelectedModelId.trim()
        : '';
      if (!selectedSource || !selectedId) {
        return null;
      }
      const selectedModel = selectedSource === 'ai'
        ? (fashionState.fashionGeneratedModel && fashionState.fashionGeneratedModel.id === selectedId
          ? fashionState.fashionGeneratedModel
          : null)
        : (Array.isArray(fashionState.fashionCustomModels)
          ? fashionState.fashionCustomModels.find((model) => model && model.id === selectedId)
          : null);
      if (!selectedModel) {
        return null;
      }
      return {
        source: selectedSource,
        id: selectedId,
        model: selectedModel,
      };
    };

    const resolveFashionSelectedModelFile = async (selectedModel) => {
      if (!selectedModel || typeof selectedModel !== 'object') {
        return null;
      }
      const imageUrl = typeof selectedModel.imageUrl === 'string' ? selectedModel.imageUrl.trim() : '';
      const previewUrl = typeof selectedModel.previewUrl === 'string' ? selectedModel.previewUrl.trim() : '';
      const candidateDataUrl = imageUrl.startsWith('data:') ? imageUrl : previewUrl.startsWith('data:') ? previewUrl : '';
      const extensionFromMime = (mimeType = '') => {
        const normalizedMimeType = String(mimeType || '').trim().toLowerCase();
        if (normalizedMimeType === 'image/jpeg') {
          return 'jpg';
        }
        if (normalizedMimeType === 'image/svg+xml') {
          return 'svg';
        }
        return normalizedMimeType.split('/')[1] || 'png';
      };
      const safeNameFromMime = (mimeType = 'image/png') => {
        const normalizedExtension = extensionFromMime(mimeType);
        const rawDownloadName = typeof selectedModel.downloadName === 'string' ? selectedModel.downloadName.trim() : '';
        if (rawDownloadName) {
          const lastDotIndex = rawDownloadName.lastIndexOf('.');
          const baseName = lastDotIndex > 0 ? rawDownloadName.slice(0, lastDotIndex) : rawDownloadName;
          return `${baseName || selectedModel.id || 'fashion-model'}.${normalizedExtension}`;
        }
        return `${selectedModel.id || 'fashion-model'}.${normalizedExtension}`;
      };

      if (candidateDataUrl) {
        try {
          const match = candidateDataUrl.match(/^data:([^;,]+)?(;base64)?,(.*)$/);
          if (!match) {
            return null;
          }
          const mimeType = match[1] || 'image/png';
          const isBase64 = Boolean(match[2]);
          const rawContent = match[3] || '';
          const byteString = isBase64 ? atob(rawContent) : decodeURIComponent(rawContent);
          const bytes = new Uint8Array(byteString.length);
          for (let index = 0; index < byteString.length; index += 1) {
            bytes[index] = byteString.charCodeAt(index);
          }
          return new File([bytes], safeNameFromMime(mimeType), { type: mimeType });
        } catch (error) {
          console.error('Failed to rebuild selected fashion model file from data URL:', error);
        }
      }

      const candidateRemoteUrl = imageUrl || previewUrl;
      if (!candidateRemoteUrl) {
        return null;
      }

      try {
        const response = await fetch(candidateRemoteUrl);
        if (!response.ok) {
          return null;
        }
        const blob = await response.blob();
        const mimeType = blob.type || 'image/png';
        return new File([blob], safeNameFromMime(mimeType), { type: mimeType });
      } catch (error) {
        console.error('Failed to fetch selected fashion model file:', error);
        return null;
      }
    };

    const appendFashionSelectedModelToFormData = async (formData, fashionState, missingImageMessage = '当前已选模特图片缺失，请重新选择或重新上传后再继续') => {
      const selectedFashionModel = resolveFashionSelectedModel(fashionState);
      if (!selectedFashionModel) {
        throw new Error('当前已选模特不存在，请重新选择后再继续');
      }
      const selectedModel = selectedFashionModel.model || {};
      formData.append('fashion_selected_model_source', selectedFashionModel.source);
      formData.append('fashion_selected_model_id', selectedFashionModel.id);
      formData.append('fashion_selected_model_name', selectedModel.name || '');
      formData.append('fashion_selected_model_gender', selectedModel.gender || '');
      formData.append('fashion_selected_model_age', selectedModel.age || '');
      formData.append('fashion_selected_model_ethnicity', selectedModel.ethnicity || '');
      formData.append('fashion_selected_model_body_type', selectedModel.bodyType || '');
      formData.append('fashion_selected_model_appearance_details', selectedModel.appearanceDetails || '');
      formData.append('fashion_selected_model_summary', selectedModel.summary || '');
      formData.append('fashion_selected_model_detail_text', selectedModel.detailText || '');
      const modelImageUrl = (selectedModel.imageUrl || selectedModel.previewUrl || '').trim();
      if (!modelImageUrl) {
        throw new Error(missingImageMessage);
      }
      formData.append('fashion_selected_model_image_url', modelImageUrl);
      return selectedFashionModel;
    };

    const buildMode2Prompt = () => {
      const parts = [
        sellingInput ? sellingInput.value.trim() : '',
        `平台：${getPlatformLabel()}`,
        `国家：${getCountryReference()}`,
        `文字：${getTextType()}`,
      ].filter(Boolean);
      return parts.join('\n');
    };

    const getMode2RequestedOutputCount = () => Math.max(1, Number(selectedOutputCount) || 1);

    const cloneFormData = (formData) => {
      const cloned = new FormData();
      formData.forEach((value, key) => {
        cloned.append(key, value);
      });
      return cloned;
    };

    const normalizeMode2Result = (result) => {
      if (!result || typeof result !== 'object') {
        return null;
      }
      const normalizedMode = String(result.mode || '').trim();
      const modeKey = normalizedMode.startsWith('mode2') ? normalizedMode : 'mode2';
      return {
        ...result,
        mode: modeKey,
        task_name: result.task_name || '模式2单图任务',
        generated_at: result.generated_at || new Date().toLocaleString('zh-CN', { hour12: false }),
        plan: result.plan || {
          output_count: 1,
          summary: normalizedMode === 'mode2-image-edit'
            ? '已完成模式2图生图生成。'
            : '已完成模式2文生图生成。',
        },
        images: [{
          title: normalizedMode === 'mode2-image-edit' ? '模式2图生图' : '模式2文生图',
          type: normalizedMode === 'mode2-image-edit' ? '图生图' : '文生图',
          type_tag: 'Mode2',
          image_url: result.image_url,
          image_path: result.image_path,
          download_name: result.download_name,
          prompt: result.prompt,
          model: result.model,
          sort: 1,
          kind: 'generated',
          keywords: [normalizedMode === 'mode2-image-edit' ? '图生图' : '文生图', getImageSizeRatio()],
        }],
      };
    };

    const buildMode2AggregateResult = (results) => {
      const normalizedResults = Array.isArray(results)
        ? results.map((item) => normalizeMode2Result(item)).filter(Boolean)
        : [];
      if (!normalizedResults.length) {
        return null;
      }
      const baseResult = normalizedResults[0];
      const aggregatedImages = normalizedResults.flatMap((item, resultIndex) => {
        const generatedItems = Array.isArray(item.images) ? item.images : [];
        return generatedItems.map((generatedItem, imageIndex) => ({
          ...generatedItem,
          sort: resultIndex + imageIndex + 1,
          title: generatedItem.title || `模式2结果 ${resultIndex + imageIndex + 1}`,
        }));
      });
      return {
        ...baseResult,
        task_name: baseResult.task_name || `模式2单图任务（${aggregatedImages.length}张）`,
        plan: {
          ...(baseResult.plan || {}),
          output_count: aggregatedImages.length,
          summary: aggregatedImages.length > 1
            ? `已完成模式2生成，共 ${aggregatedImages.length} 张。`
            : (baseResult.plan?.summary || '已完成模式2生成。'),
        },
        images: aggregatedImages,
      };
    };

    const generateMode2Results = async (endpoint, formData, outputCount) => {
      const requests = [];
      for (let index = 0; index < outputCount; index += 1) {
        const requestFormData = cloneFormData(formData);
        requestFormData.append('async_task', '1');
        const response = await fetch(endpoint, {
          method: 'POST',
          body: requestFormData,
        });
        const taskPayload = await parseJsonResponse(response);
        if (!response.ok || !taskPayload?.success || !taskPayload.task_id) {
          const detailMessage = typeof taskPayload?.details === 'string' ? taskPayload.details.trim() : '';
          const baseMessage = taskPayload?.error || '模式2生成失败，请稍后重试';
          throw new Error(detailMessage ? `${baseMessage}｜${detailMessage}` : baseMessage);
        }
        const rawResult = await pollGenericTaskResult({
          taskId: taskPayload.task_id,
          loadingMessage: `模式2任务 ${index + 1}/${outputCount} 已提交，正在处理中…`,
          pendingMessage: `模式2任务 ${index + 1}/${outputCount} 排队中，请稍候…`,
          runningMessage: `模式2任务 ${index + 1}/${outputCount} 生成中，请稍候…`,
          statusErrorMessage: '模式2任务状态查询失败',
          timeoutMessage: '模式2任务等待超时，请稍后重试',
        });
        const result = normalizeMode2Result(rawResult);
        if (!result?.success || !Array.isArray(result.images)) {
          const detailMessage = typeof result?.details === 'string' ? result.details.trim() : '';
          const baseMessage = result?.error || '模式2生成失败，请稍后重试';
          throw new Error(detailMessage ? `${baseMessage}｜${detailMessage}` : baseMessage);
        }
        requests.push(result);
      }
      return buildMode2AggregateResult(requests);
    };

    const resolveGenerateRequest = (formData) => {
      if (currentMode === 'aplus') {
        return { endpoint: '/api/generate-aplus', isMode2: false };
      }
      if (currentMode === 'mode2') {
        const productAssets = getUploadedProductAssets();
        const productFiles = getProductFiles();
        const prompt = buildMode2Prompt();
        if (!prompt) {
          throw new Error('请先填写核心卖点或提示词后再生成。');
        }
        formData.delete('mode');
        formData.delete('selling_text');
        formData.delete('product_json');
        formData.delete('selected_style_title');
        formData.delete('selected_style_reasoning');
        formData.delete('selected_style_colors');
        formData.delete('output_count');
        formData.append('prompt', prompt);
        return {
          endpoint: productAssets.length || productFiles.length ? '/api/generate-mode2-image-edit' : '/api/generate-mode2-text2image',
          isMode2: true,
        };
      }
      return { endpoint: '/api/generate-suite', isMode2: false };
    };


    const buildBaseGenerateFormData = () => {
      const formData = new FormData();
      const selectedStyle = getSelectedStyle();
      formData.append('selling_text', sellingInput ? sellingInput.value.trim() : '');
      formData.append('platform', getPlatformLabel());
      formData.append('country', getCountryReference());
      formData.append('text_type', getTextType());
      formData.append('image_size_ratio', getImageSizeRatio());
      formData.append('mode', currentMode);
      if (currentProductJson) {
        formData.append('product_json', JSON.stringify(currentProductJson));
      }
      if (selectedStyle?.title) {
        formData.append('selected_style_title', selectedStyle.title);
      }
      if (selectedStyle?.reasoning) {
        formData.append('selected_style_reasoning', selectedStyle.reasoning);
      }
      if (Array.isArray(selectedStyle?.colors) && selectedStyle.colors.length) {
        formData.append('selected_style_colors', JSON.stringify(selectedStyle.colors));
      }
      const productAssets = getUploadedProductAssets();
      if (productAssets.length) {
        appendImageUrlsToFormData(formData, 'image_urls', productAssets, getProductUploadLimit());
      } else {
        appendFilesToFormData(formData, 'images', getProductFiles(), getProductUploadLimit());
      }
      const referenceAssets = getUploadedReferenceAssets();
      if (referenceAssets.length) {
        appendImageUrlsToFormData(formData, 'reference_image_urls', referenceAssets, 3);
      } else {
        appendFilesToFormData(formData, 'reference_images', getReferenceFiles());
      }
      return { formData, selectedStyle };
    };

    const buildFashionGenerateFormData = () => {
      const formData = new FormData();
      formData.append('mode', 'fashion');
      formData.append('image_size_ratio', getImageSizeRatio());
      const uploadedAssets = getUploadedProductAssets();
      if (uploadedAssets.length) {
        appendImageUrlsToFormData(formData, 'image_urls', uploadedAssets, getProductUploadLimit());
      } else {
        appendFilesToFormData(formData, 'images', getProductFiles(), getProductUploadLimit());
      }
      return formData;
    };

    const parseJsonResponse = async (response) => {
      const responseText = await response.text();
      if (!responseText) {
        return {};
      }
      try {
        return JSON.parse(responseText);
      } catch (error) {
        throw new Error(responseText.trim() || '服务端返回格式异常，请稍后重试');
      }
    };

    const getTaskQueueStatusMessage = (task, pendingMessage = '任务已提交，正在排队处理，请稍候…', runningMessage = '任务处理中，请稍候…') => {
      if (task?.status === 'running') return runningMessage;
      const aheadCount = Number(task?.ahead_count);
      const queueTier = String(task?.queue_tier || '').toLowerCase();
      const tierLabel = queueTier === 'priority' ? '付费优先队列' : '普通队列';
      if (Number.isFinite(aheadCount) && aheadCount > 0) {
        return `${tierLabel}排队中，前面还有 ${aheadCount} 人，请勿重复提交。`;
      }
      if (Number.isFinite(aheadCount) && aheadCount === 0) {
        return `${tierLabel}排队中，即将开始生成，请勿重复提交。`;
      }
      return pendingMessage;
    };

    const pollGenericTaskResult = async ({
      taskId,
      timeoutMs = PENDING_GENERATION_TIMEOUT,
      intervalMs,
      loadingMessage = '任务已提交，正在处理中，请稍候…',
      pendingMessage = '任务已提交，正在排队处理，请稍候…',
      runningMessage = '任务处理中，请稍候…',
      statusErrorMessage = '任务状态查询失败',
      timeoutMessage = '任务等待超时，请稍后重试',
      onPending,
      onProgress,
      onSuccess,
      onFailed,
    } = {}) => {
      const normalizedTaskId = String(taskId || '').trim();
      if (!normalizedTaskId) {
        throw new Error('缺少任务编号，请稍后重试');
      }
      if (typeof onPending === 'function') {
        onPending(loadingMessage);
      }
      
      subscribeTask(normalizedTaskId);
      
      const startedAt = Date.now();
      let taskCompleted = false;
      let taskResult = null;
      let taskError = null;
      
      const taskUpdateHandler = (event) => {
        const { taskId: updatedTaskId, task } = event.detail;
        if (updatedTaskId === normalizedTaskId) {
          if (typeof onProgress === 'function') {
            onProgress(task.result || {}, task);
          }
          if (task.status === 'succeeded') {
            taskCompleted = true;
            taskResult = task.result || {};
            if (typeof onSuccess === 'function') {
              onSuccess(task.result || {}, task);
            }
          } else if (task.status === 'failed') {
            taskCompleted = true;
            taskError = new Error(task.error || '任务执行失败，请稍后重试');
            if (typeof onFailed === 'function') {
              onFailed(task);
            }
          } else {
            if (typeof onPending === 'function') {
              onPending(getTaskQueueStatusMessage(task, pendingMessage, runningMessage), task);
            }
          }
        }
      };
      
      window.addEventListener('taskUpdate', taskUpdateHandler);
      
      try {
        while (Date.now() - startedAt < timeoutMs && !taskCompleted && !taskError) {
          const response = await fetch(`/api/generation-tasks/${encodeURIComponent(normalizedTaskId)}`);
          const result = await parseJsonResponse(response);
          if (!response.ok || !result?.success) {
            throw new Error(result?.error || statusErrorMessage);
          }
          const task = result.task || {};
          if (typeof onProgress === 'function') {
            onProgress(task.result || {}, task);
          }
          if (task.status === 'succeeded') {
            taskCompleted = true;
            taskResult = task.result || {};
            if (typeof onSuccess === 'function') {
              onSuccess(task.result || {}, task);
            }
            break;
          }
          if (task.status === 'failed') {
            taskCompleted = true;
            taskError = new Error(task.error || '任务执行失败，请稍后重试');
            if (typeof onFailed === 'function') {
              onFailed(task);
            }
            break;
          }
          if (typeof onPending === 'function') {
            onPending(getTaskQueueStatusMessage(task, pendingMessage, runningMessage), task);
          }
          const elapsedMs = Date.now() - startedAt;
          const currentInterval = typeof intervalMs === 'number' ? intervalMs : getDynamicPollInterval(elapsedMs);
          await new Promise((resolve) => window.setTimeout(resolve, currentInterval));
        }
        
        if (taskError) {
          throw taskError;
        }
        
        if (!taskCompleted) {
          throw new Error(timeoutMessage);
        }
        
        return taskResult;
      } finally {
        window.removeEventListener('taskUpdate', taskUpdateHandler);
        unsubscribeTask(normalizedTaskId);
      }
    };

    const debugGenerationTrace = (...args) => {
      console.log('[generation-trace]', ...args);
    };

    const markTaskTraceEvent = (task, stage, extra = {}) => {
      if (!task || typeof task !== 'object') {
        return task;
      }
      const now = Date.now();
      const currentTrace = task.trace && typeof task.trace === 'object' ? task.trace : {};
      const currentEvents = Array.isArray(currentTrace.events) ? currentTrace.events.slice() : [];
      const event = {
        stage: String(stage || '').trim() || 'unknown',
        ts: now / 1000,
        at: new Date(now).toISOString(),
        source: 'frontend',
        ...extra,
      };
      currentEvents.push(event);
      task.trace = {
        ...currentTrace,
        events: currentEvents.slice(-60),
        last_stage: event.stage,
        last_at: event.at,
        last_ts: event.ts,
      };
      return task;
    };

    const summarizeTaskTrace = (task) => {
      const events = Array.isArray(task?.trace?.events) ? task.trace.events : [];
      const findFirst = (stage) => events.find((item) => item?.stage === stage);
      const findLast = (stage) => events.slice().reverse().find((item) => item?.stage === stage);
      const getTime = (event) => {
        const ts = Number(event?.ts);
        if (Number.isFinite(ts)) {
          return ts * 1000;
        }
        const parsed = Date.parse(event?.at || '');
        return Number.isFinite(parsed) ? parsed : null;
      };
      const diffMs = (startEvent, endEvent) => {
        const start = getTime(startEvent);
        const end = getTime(endEvent);
        return Number.isFinite(start) && Number.isFinite(end) ? Math.max(Math.round(end - start), 0) : null;
      };
      const createdEvent = findFirst('task_created');
      const succeededEvent = findLast('task_succeeded') || findLast('task_result_ready');
      const pollEvent = findLast('frontend_poll_received');
      const successReceivedEvent = findLast('frontend_success_received');
      const renderStartEvent = findLast('frontend_result_render_start');
      const renderDoneEvent = findLast('frontend_result_render_done');
      const imageLoadedEvent = findLast('image_loaded');
      return {
        taskCreatedAt: createdEvent?.at || task?.created_at || '',
        taskSucceededAt: succeededEvent?.at || task?.updated_at || '',
        frontendPollAt: pollEvent?.at || '',
        frontendSuccessAt: successReceivedEvent?.at || '',
        renderStartedAt: renderStartEvent?.at || '',
        renderDoneAt: renderDoneEvent?.at || '',
        imageLoadedAt: imageLoadedEvent?.at || '',
        backendElapsedMs: Number.isFinite(succeededEvent?.elapsed_ms) ? succeededEvent.elapsed_ms : null,
        frontendPollDetectMs: diffMs(succeededEvent, pollEvent),
        frontendRenderWaitMs: diffMs(successReceivedEvent, renderStartEvent),
        frontendRenderMs: diffMs(renderStartEvent, renderDoneEvent),
        frontendImageLoadMs: diffMs(renderDoneEvent, imageLoadedEvent),
        frontendDisplayDelayMs: diffMs(succeededEvent, imageLoadedEvent),
        totalEndToEndMs: diffMs(createdEvent, imageLoadedEvent),
      };
    };

    const attachResultImageTrace = (task, rootElement) => {
      if (!task || !rootElement || typeof rootElement.querySelectorAll !== 'function') {
        return;
      }
      const images = rootElement.querySelectorAll('[data-role="preview-image"]');
      images.forEach((img, index) => {
        if (!(img instanceof HTMLImageElement) || img.dataset.traceBound === '1') {
          return;
        }
        img.dataset.traceBound = '1';
        const handleLoaded = () => {
          markTaskTraceEvent(task, 'image_loaded', {
            index,
            image_url: img.currentSrc || img.src || '',
          });
          const summary = summarizeTaskTrace(task);
          debugGenerationTrace('image_loaded_summary', {
            taskId: task.task_id || '',
            index,
            taskCreatedAt: summary.taskCreatedAt,
            taskSucceededAt: summary.taskSucceededAt,
            frontendPollAt: summary.frontendPollAt,
            renderDoneAt: summary.renderDoneAt,
            imageLoadedAt: summary.imageLoadedAt,
            backendElapsedMs: summary.backendElapsedMs,
            frontendPollDetectMs: summary.frontendPollDetectMs,
            frontendRenderMs: summary.frontendRenderMs,
            frontendImageLoadMs: summary.frontendImageLoadMs,
            frontendDisplayDelayMs: summary.frontendDisplayDelayMs,
            totalEndToEndMs: summary.totalEndToEndMs,
          });
        };
        if (img.complete && img.naturalWidth > 0) {
          window.setTimeout(handleLoaded, 0);
        } else {
          img.addEventListener('load', handleLoaded, { once: true });
        }
      });
    };

    const getPendingGenerationTaskIds = () => {
      if (Array.isArray(pendingGenerationTask?.taskIds)) {
        return pendingGenerationTask.taskIds.filter(Boolean);
      }
      return pendingGenerationTask?.taskId ? [pendingGenerationTask.taskId] : [];
    };

    const getPendingGenerationSpendAmount = () => {
      if (Array.isArray(pendingGenerationTask?.spendRecords)) {
        return pendingGenerationTask.spendRecords.reduce((total, item) => total + (Number(item?.amount) || 0), 0);
      }
      return Number(pendingGenerationTask?.spendRecord?.amount) || 0;
    };

    const mergeGenerationTaskResults = (tasks) => {
      const succeededTasks = Array.isArray(tasks) ? tasks : [];
      const results = succeededTasks.map((task) => task?.result).filter((result) => result && Array.isArray(result.images));
      const firstResult = results[0] || {};
      return {
        ...firstResult,
        mode: currentMode,
        images: results.flatMap((result) => result.images || []),
        reference_images: results.flatMap((result) => result.reference_images || []),
        plan: {
          ...(firstResult.plan || {}),
          summary: `已完成 ${results.reduce((total, result) => total + (Array.isArray(result.images) ? result.images.length : 0), 0)} 张结果生成`,
        },
      };
    };

    const completePendingGenerationTask = (task) => {
      stopGenerationProgress();
      resetPendingGenerationPollState();
      const normalizedTask = task && typeof task === 'object' ? task : {};
      const result = normalizedTask.result && typeof normalizedTask.result === 'object'
        ? normalizedTask.result
        : (Array.isArray(normalizedTask.images) ? normalizedTask : null);
      if (!result || !Array.isArray(result.images)) {
        return false;
      }
      const renderStartedAt = Date.now();
      markTaskTraceEvent(normalizedTask, 'frontend_result_render_start', {
        imageCount: Array.isArray(result.images) ? result.images.length : 0,
      });
      currentResult = result;
      currentResultItems = normalizeResultItems(result);
      selectedResultKeys = new Set();
      updateTaskSummary(result);
      renderResultCards(currentResultItems);
      markTaskTraceEvent(normalizedTask, 'frontend_result_render_done', {
        imageCount: currentResultItems.length,
        renderElapsedMs: Math.max(Date.now() - renderStartedAt, 0),
      });
      attachResultImageTrace(normalizedTask, resultGrid);
      const summary = summarizeTaskTrace(normalizedTask);
      debugGenerationTrace('render_done_summary', {
        taskId: normalizedTask?.task_id || pendingGenerationTask?.taskId || '',
        taskCreatedAt: summary.taskCreatedAt,
        taskSucceededAt: summary.taskSucceededAt,
        frontendPollAt: summary.frontendPollAt,
        renderStartedAt: summary.renderStartedAt,
        renderDoneAt: summary.renderDoneAt,
        backendElapsedMs: summary.backendElapsedMs,
        frontendPollDetectMs: summary.frontendPollDetectMs,
        frontendRenderWaitMs: summary.frontendRenderWaitMs,
        frontendRenderMs: summary.frontendRenderMs,
        frontendDisplayDelayMs: summary.frontendDisplayDelayMs,
        imageCount: currentResultItems.length,
      });
      const spendAmount = getPendingGenerationSpendAmount();
      setResultStatus(`${getCurrentModeConfig().successFallback.replace('{count}', String(getCurrentOutputMetric(result)))}${spendAmount > 0 ? `，已消耗 ${spendAmount} 积分` : ''}`, 'success');
      if (result.mode === 'fashion') {
        syncFashionState({ fashionFlowStep: 'result' });
      }
      stopPendingGenerationPolling();
      pendingGenerationTask = null;
      applyGenerateButtonReadyState({ mode: result.mode, fashionStep: result.mode === 'fashion' ? 'result' : undefined });
      saveStateToLocalStorage();
      return true;
    };

    const stopPendingGenerationPolling = () => {
      if (pendingGenerationPollTimer) {
        window.clearTimeout(pendingGenerationPollTimer);
        pendingGenerationPollTimer = null;
      }
    };

    const resetPendingGenerationPollState = () => {
      pendingGenerationPollFailureCount = 0;
    };

    const applyGenerateButtonPendingState = (label = getCurrentModeConfig().imageLoadingLabel) => {
      if (!generateBtn) {
        return;
      }
      generateBtn.disabled = false;
      generateBtn.dataset.pendingAction = 'cancel';
      updateGenerateButtonLabel(label);
    };

    const clearGenerateButtonPendingState = () => {
      if (!generateBtn) {
        return;
      }
      delete generateBtn.dataset.pendingAction;
    };

    const applyGenerateButtonReadyState = ({ mode = currentMode, label, fashionStep } = {}) => {
      clearGenerateButtonPendingState();
      if (mode === 'fashion') {
        if (fashionStep) {
          syncFashionState({ fashionFlowStep: fashionStep });
        }
        applyFashionGenerateButtonState();
        return;
      }
      if (generateBtn) {
        generateBtn.disabled = false;
        updateGenerateButtonLabel(label || getCurrentModeConfig().generateBtnLabel);
      }
    };

    const cancelPendingGenerationTask = async () => {
      const task = pendingGenerationTask;
      const taskIds = getPendingGenerationTaskIds();
      if (!taskIds.length) {
        return;
      }
      let refundInfo = '';
      try {
        const cancelResults = await Promise.all(taskIds.map(async (taskId) => {
          const response = await fetch(`/api/generation-tasks/${encodeURIComponent(taskId)}/cancel`, {
            method: 'POST',
            credentials: 'same-origin',
          });
          const result = await parseJsonResponse(response);
          if (!response.ok || !result.success) {
            console.warn('Cancel task request failed:', result.error);
          }
          return result;
        }));
        if (cancelResults.some((result) => result?.task?.refunded)) {
          refundInfo = '，积分已返还';
        } else if (cancelResults.some((result) => result?.task?.refund_error)) {
          refundInfo = '，积分未返还';
        }
      } catch (error) {
        console.warn('Cancel task request error:', error);
      }
      stopPendingGenerationPolling();
      pendingGenerationTask = null;
      resetPendingGenerationPollState();
      stopGenerationProgress();
      resetResultState();
      setResultStatus(`生成已取消${refundInfo}，可重新发起生成。`, '');
      applyGenerateButtonReadyState({ mode: task?.mode, fashionStep: task?.mode === 'fashion' ? 'scene' : undefined });
      saveStateToLocalStorage();
    };

    if (progressCancelBtn) {
      progressCancelBtn.addEventListener('click', () => {
        if (getPendingGenerationTaskIds().length) {
          cancelPendingGenerationTask();
        }
      });
    }

    const pollPendingGenerationTask = async ({ immediate = false } = {}) => {
      stopPendingGenerationPolling();
      if (!getPendingGenerationTaskIds().length) {
        return;
      }
      const startedAt = Number(pendingGenerationTask.startedAt) || Date.now();
      if (Date.now() - startedAt > PENDING_GENERATION_TIMEOUT) {
        const staleTask = pendingGenerationTask;
        stopPendingGenerationPolling();
        pendingGenerationTask = null;
        resetPendingGenerationPollState();
        stopGenerationProgress();
        setResultStatus('生成任务等待超时，请重新发起生成；如已扣分但没有结果，请联系客服核查。', 'error');
        applyGenerateButtonReadyState({ mode: staleTask?.mode, fashionStep: staleTask?.mode === 'fashion' ? 'scene' : undefined });
        saveStateToLocalStorage();
        return;
      }
      try {
        const taskIds = getPendingGenerationTaskIds();
        const taskResponses = await Promise.all(taskIds.map(async (taskId) => {
          const response = await fetch(`/api/generation-tasks/${encodeURIComponent(taskId)}`);
          const result = await parseJsonResponse(response);
          if (!response.ok || !result.success) {
            throw new Error(result.error || '生成任务状态查询失败');
          }
          return result.task || {};
        }));
        pendingGenerationPollFailureCount = 0;
        taskResponses.forEach((task) => {
          markTaskTraceEvent(task, 'frontend_poll_received', {
            status: task.status || '',
          });
          debugGenerationTrace('poll_received', {
            taskId: task.task_id || task.id || '',
            status: task.status || '',
            lastStage: task.trace?.last_stage || '',
            lastAt: task.trace?.last_at || '',
          });
        });
        const failedTask = taskResponses.find((task) => task.status === 'failed');
        if (failedTask) {
          const refunded = Boolean(failedTask.refunded);
          stopPendingGenerationPolling();
          pendingGenerationTask = null;
          resetPendingGenerationPollState();
          resetResultState();
          applyGenerateButtonReadyState({ mode: failedTask.mode, fashionStep: failedTask.mode === 'fashion' ? 'scene' : undefined });
          setResultStatus(refunded ? `${failedTask.error || '生成失败'}；本次扣减积分已自动返还。` : `${failedTask.error || '生成失败'}${failedTask.refund_error ? `；${failedTask.refund_error}` : ''}`, 'error');
          saveStateToLocalStorage();
          return;
        }
        if (taskResponses.every((task) => task.status === 'succeeded')) {
          taskResponses.forEach((task) => markTaskTraceEvent(task, 'frontend_success_received'));
          completePendingGenerationTask(mergeGenerationTaskResults(taskResponses));
          return;
        }
        const runningTask = taskResponses.find((task) => task.status === 'running');
        const pendingTask = taskResponses.find((task) => task.status !== 'running');
        setResultStatus(runningTask ? getCurrentModeConfig().imageProgress : getTaskQueueStatusMessage(pendingTask, '生成任务已提交，正在排队处理，请勿关闭页面。'));
      } catch (error) {
        pendingGenerationPollFailureCount += 1;
        const failureMessage = `正在等待生成任务完成，状态查询暂时失败：${error.message || error}`;
        setResultStatus(pendingGenerationPollFailureCount >= PENDING_GENERATION_MAX_STATUS_FAILURES
          ? `${failureMessage}；连续查询失败已自动停止，请稍后手动刷新页面或重新发起生成。`
          : failureMessage);
        if (pendingGenerationPollFailureCount >= PENDING_GENERATION_MAX_STATUS_FAILURES) {
          stopPendingGenerationPolling();
          pendingGenerationTask = null;
          resetPendingGenerationPollState();
          stopGenerationProgress();
          applyGenerateButtonReadyState({ mode: currentMode, fashionStep: currentMode === 'fashion' ? 'scene' : undefined });
          saveStateToLocalStorage();
          return;
        }
      }
      const elapsedMs = Date.now() - startedAt;
      const nextInterval = immediate ? 500 : getDynamicPollInterval(elapsedMs);
      pendingGenerationPollTimer = window.setTimeout(() => pollPendingGenerationTask(), nextInterval);
    };

    const savePendingGenerationTask = (taskId, spendRecord, mode = PAGE_MODE) => {
      savePendingGenerationTasks([taskId], [spendRecord], mode);
    };

    const savePendingGenerationTasks = (taskIds, spendRecords, mode = PAGE_MODE) => {
      startGenerationProgress();
      resetPendingGenerationPollState();
      pendingGenerationTask = {
        taskIds: taskIds.filter(Boolean),
        taskId: taskIds.find(Boolean) || '',
        mode,
        spendRecords: spendRecords.filter(Boolean),
        spendRecord: spendRecords.find(Boolean) || null,
        startedAt: Date.now(),
      };
      applyGenerateButtonPendingState(getCurrentModeConfig().imageLoadingLabel);
      saveStateToLocalStorage();
      pollPendingGenerationTask({ immediate: true });
    };

    const appendCompositeTaskFields = (formData, selection, taskType) => {
      const isMainTask = taskType === 'main';
      const mainImageCount = isMainTask ? selection.mainImageCount : 0;
      const detailImageCount = isMainTask ? 0 : selection.detailImageCount;
      formData.set('output_count', String(isMainTask ? mainImageCount : detailImageCount));
      formData.set('main_image_count', String(mainImageCount));
      formData.set('detail_image_count', String(detailImageCount));
      formData.set('generate_main_image', isMainTask ? '1' : '0');
      formData.set('generate_detail_image', isMainTask ? '0' : '1');
      formData.set('generate_scope', isMainTask ? 'main_only' : 'detail_only');
      formData.set('generate_task_type', isMainTask ? 'main_image' : 'detail_image');
      if (isMainTask) {
        const referenceAssets = getUploadedReferenceAssets();
        if (referenceAssets.length) {
          appendImageUrlsToFormData(formData, 'reference_image_urls', referenceAssets, 3);
        } else {
          appendFilesToFormData(formData, 'reference_images', getReferenceFiles());
        }
        if (currentProductJson) {
          formData.append('product_json', JSON.stringify(currentProductJson));
        }
        formData.append('prioritize_reference', '1');
        formData.append('generation_focus', 'product_main');
      }
    };

    const fetchJsonWithTimeout = async (url, options = {}, timeoutMs = 70000, timeoutMessage = '推荐场景生成超时，请稍后重试') => {
      const controller = typeof AbortController === 'function' ? new AbortController() : null;
      const timeoutId = controller
        ? window.setTimeout(() => controller.abort(), timeoutMs)
        : null;

      try {
        const response = await fetch(url, {
          ...options,
          signal: controller ? controller.signal : options.signal,
        });
        const result = await parseJsonResponse(response);

        return { response, result };
      } catch (error) {
        if (error?.name === 'AbortError') {
          throw new Error(timeoutMessage);
        }
        throw error;
      } finally {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
      }
    };

    const buildPointsRequestId = () => {
      if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
      }
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    };

    const requestPointsSpend = async ({ mode, outputCount = 0, selectedModulesCount = 0, selectedSceneCount = 0, type, reason, metadata }) => {
      const normalizedMode = String(mode || 'suite').trim() || 'suite';
      const normalizedMetadata = metadata && typeof metadata === 'object' ? metadata : {};
      const requestId = normalizedMetadata.request_id || buildPointsRequestId();
      const requestMetadata = {
        ...normalizedMetadata,
        request_id: requestId,
      };
      const response = await fetch('/api/points/spend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          mode: normalizedMode,
          output_count: Math.max(Number(outputCount) || 0, 0),
          selected_modules_count: Math.max(Number(selectedModulesCount) || 0, 0),
          selected_scene_count: Math.max(Number(selectedSceneCount) || 0, 0),
          type,
          reason,
          metadata: requestMetadata,
        }),
      });
      const result = await response.json().catch(() => ({}));
      const consume = result?.consume && typeof result.consume === 'object' ? result.consume : null;
      const consumeAmount = Number(consume?.amount) || 0;
      if (!response.ok || !result?.success) {
        const baseMessage = result?.error || '积分扣减失败，请稍后重试';
        if (response.status === 401) {
          throw new Error('请先登录后再生成');
        }
        if (response.status === 409 && result?.error === '积分不足') {
          throw new Error(`积分不足，当前生成需要 ${consumeAmount || 0} 积分`);
        }
        throw new Error(baseMessage);
      }
      const spendMetadata = consume?.metadata && typeof consume.metadata === 'object' ? consume.metadata : requestMetadata;
      if (consumeAmount <= 0) {
        return { skipped: true, points: result.points || null, consume, requestId, metadata: spendMetadata };
      }
      return {
        skipped: false,
        amount: consumeAmount,
        mode: consume?.mode || normalizedMode,
        type: consume?.type || type,
        reason: consume?.reason || reason,
        metadata: spendMetadata,
        requestId,
        refunded: false,
        rule: consume?.rule || null,
        consume,
        points: result.points || null,
      };
    };

    const requestPointsQuote = async ({ mode, outputCount = 0, selectedModulesCount = 0, selectedSceneCount = 0, type, reason, metadata }) => {
      const normalizedMode = String(mode || 'suite').trim() || 'suite';
      const response = await fetch('/api/points/quote', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          mode: normalizedMode,
          output_count: Math.max(Number(outputCount) || 0, 0),
          selected_modules_count: Math.max(Number(selectedModulesCount) || 0, 0),
          selected_scene_count: Math.max(Number(selectedSceneCount) || 0, 0),
          type,
          reason,
          metadata: metadata && typeof metadata === 'object' ? metadata : {},
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result?.success || !result?.quote) {
        throw new Error(result?.error || '积分报价失败，请稍后重试');
      }
      return result.quote;
    };

    const requestPointsRefund = async (spendRecord, failureMessage = '') => {
      if (!spendRecord || spendRecord.skipped || spendRecord.refunded || !(Number(spendRecord.amount) > 0)) {
        return null;
      }
      const refundMetadata = {
        ...(spendRecord.metadata && typeof spendRecord.metadata === 'object' ? spendRecord.metadata : {}),
        request_id: spendRecord.requestId || spendRecord.metadata?.request_id || '',
        refunded: true,
        refund_reason: 'generation_failed',
        failure_message: String(failureMessage || '').slice(0, 300),
      };
      const response = await fetch('/api/points/refund', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          amount: Number(spendRecord.amount),
          type: `${spendRecord.type || 'consume'}_refund`,
          reason: `${spendRecord.reason || '生成消耗'}失败返还`,
          metadata: refundMetadata,
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result?.success) {
        throw new Error(result?.error || '积分返还失败');
      }
      spendRecord.refunded = true;
      return result.points || null;
    };

    const syncSharedPointsState = (points) => {
      if (!points || typeof points !== 'object') {
        return;
      }
      window.dispatchEvent(new CustomEvent('shared-points-updated', {
        detail: { points },
      }));
    };

    const requestPointsRules = async () => {
      const response = await fetch('/api/points/rules', {
        method: 'GET',
        headers: {
          Accept: 'application/json',
        },
        credentials: 'same-origin',
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result?.success || !result?.rules) {
        throw new Error(result?.error || '读取积分规则失败，请稍后重试');
      }
      return result.rules;
    };

    const requestFashionScenePlan = async () => {
      const fashionApi = getFashionWorkspaceApi();
      const fashionState = fashionApi?.getState ? fashionApi.getState() : null;
      const currentFashionState = fashionState?.cta || getFashionSelectionState();
      applyFashionGenerateButtonState(currentFashionState);
      if (!currentFashionState.hasSelectedModel) {
        setResultStatus('请先选择模特后再生成推荐场景。', 'error');
        return;
      }

      setFashionFlowStepState('scene');
      syncFashionState({
        ...clearFashionSceneStatePatch(),
        fashionFlowStep: 'scene',
        fashionSceneGenerationState: 'loading',
      });
      showIntroView();
      setResultStatus('正在生成推荐场景...', '');
      startGenerationProgress(60);

      try {
        const formData = buildFashionGenerateFormData();
        await appendFashionSelectedModelToFormData(
          formData,
          fashionState,
          '当前已选模特图片缺失，请重新选择或重新上传后再生成推荐场景',
        );
        formData.append('fashion_action', 'scene_plan');
        const { response, result } = await fetchJsonWithTimeout('/api/generate-suite', {
          method: 'POST',
          body: formData,
        }, FASHION_SCENE_PLAN_REQUEST_TIMEOUT_MS, '推荐场景生成等待超时，请稍后重试');
        const scenePlan = result?.plan || null;
        const sceneGroups = Array.isArray(scenePlan?.scene_groups) ? scenePlan.scene_groups : [];

        if (!response.ok || !result.success || !scenePlan || !sceneGroups.length) {
          throw new Error(result.error || '推荐场景生成失败，请稍后重试');
        }

        syncFashionState({
          fashionFlowStep: 'scene',
          fashionSceneGenerationState: 'done',
          fashionSceneGroups: sceneGroups,
          fashionSelectedSceneGroupIds: [],
          fashionSelectedPoseIds: [],
          fashionSceneError: '',
          fashionScenePlanRaw: scenePlan,
          fashionSceneStateVersion: 2,
        });
        stopGenerationProgress();
        setResultStatus(scenePlan.summary || '推荐场景已生成，请继续选择姿态、景别与视角。', 'success');
      } catch (error) {
        syncFashionState({
          ...clearFashionSceneStatePatch(),
          fashionFlowStep: 'scene',
          fashionSceneGenerationState: 'error',
          fashionSceneError: error.message || '推荐场景生成失败，请稍后重试',
        });
        stopGenerationProgress();
        setResultStatus(error.message || '推荐场景生成失败，请稍后重试', 'error');
      }
    };

    const submitFashionGenerate = async () => {
      const fashionApi = getFashionWorkspaceApi();
      const fashionState = fashionApi?.getState ? fashionApi.getState() : null;
      const normalizedSelectedPoseIds = Array.isArray(fashionState?.fashionSelectedPoseIds)
        ? fashionState.fashionSelectedPoseIds
            .map((poseId) => String(poseId || '').trim())
            .filter(Boolean)
        : [];
      const normalizedSelectedEntries = normalizedSelectedPoseIds.reduce((acc, poseId) => {
        const selectedGroup = Array.isArray(fashionState?.fashionSceneGroups)
          ? fashionState.fashionSceneGroups.find((group) => Array.isArray(group?.poses) && group.poses.some((pose) => pose.id === poseId))
          : null;
        const selectedPose = selectedGroup?.poses.find((pose) => pose.id === poseId);
        if (!selectedGroup || !selectedPose) {
          return acc;
        }
        acc.push({
          group: selectedGroup,
          pose: selectedPose,
        });
        return acc;
      }, []);
      const normalizedPoseCameraSettings = normalizedSelectedEntries.reduce((acc, entry) => {
        acc[entry.pose.id] = buildFashionPoseCameraSetting(
          entry.group,
          entry.pose,
          fashionState?.fashionPoseCameraSettings?.[entry.pose.id] || {},
        );
        return acc;
      }, {});
      const normalizedFashionState = fashionState
        ? {
            ...fashionState,
            fashionSelectedPoseIds: normalizedSelectedEntries.map((entry) => entry.pose.id),
            fashionSelectedSceneGroupIds: normalizedSelectedEntries.reduce((groupIds, entry) => {
              if (!groupIds.includes(entry.group.id)) {
                groupIds.push(entry.group.id);
              }
              return groupIds;
            }, []),
            fashionPoseCameraSettings: {
              ...(fashionState?.fashionPoseCameraSettings || {}),
              ...normalizedPoseCameraSettings,
            },
          }
        : null;
      const fashionCta = normalizedFashionState?.cta || getFashionSelectionState();
      const canGenerateWithDefaults = Boolean(
        normalizedFashionState
        && normalizedFashionState.fashionFlowStep === 'scene'
        && normalizedFashionState.fashionSceneGenerationState === 'done'
        && normalizedSelectedEntries.length > 0,
      );
      applyFashionGenerateButtonState(canGenerateWithDefaults
        ? {
            ...fashionCta,
            disabled: false,
            label: `生成服饰穿戴图（${normalizedSelectedEntries.length}个场景）`,
          }
        : fashionCta);
      if (!canGenerateWithDefaults && fashionCta.disabled) {
        return;
      }

      const config = getCurrentModeConfig();
      const selectedSceneCount = normalizedSelectedEntries.length || fashionCta.selectedSceneCount || 1;
      const quotePayload = await requestPointsQuote({
        mode: 'fashion',
        selectedSceneCount,
        type: 'fashion_generate',
        reason: '服饰穿戴图生成消耗',
        metadata: {
          mode: 'fashion',
          selected_scene_count: selectedSceneCount,
          pose_ids: normalizedFashionState?.fashionSelectedPoseIds || [],
        },
      });
      const pointsCost = Number(quotePayload?.amount) || 0;
      const formData = buildFashionGenerateFormData();
      await appendFashionSelectedModelToFormData(formData, normalizedFashionState, '当前已选模特图片缺失，请重新选择或重新上传后再生成');
      formData.append('fashion_action', 'generate');
      formData.append('fashion_scene_plan', JSON.stringify(normalizedFashionState?.fashionScenePlanRaw || {}));
      formData.append('fashion_scene_group_ids', JSON.stringify(normalizedSelectedEntries.map((entry) => entry.group.id)));
      formData.append('fashion_pose_ids', JSON.stringify(normalizedFashionState?.fashionSelectedPoseIds || []));
      const selectedPoseCameraSettings = normalizedSelectedEntries.map((entry) => {
        const setting = normalizedFashionState?.fashionPoseCameraSettings?.[entry.pose.id] || {};
        return {
          pose_id: entry.pose.id,
          shot_size: setting.shotSize || '',
          view_angle: setting.viewAngle || '',
        };
      });
      formData.append('fashion_pose_camera_settings', JSON.stringify(selectedPoseCameraSettings));

      resetResultStatus();
      resetResultState();
      if (resultMeta) {
        resultMeta.textContent = config.initialResultMeta;
      }
      generateBtn.disabled = true;
      updateGenerateButtonLabel(config.planLoadingLabel);
      setResultStatus(`正在校验积分并生成，预计消耗 ${pointsCost} 积分`);
      startGenerationProgress(config.estimatedSeconds || 120, selectedSceneCount);
      renderLoadingResultCards(selectedSceneCount);
      showResultView();
      syncFashionState({ fashionFlowStep: 'result' });
      persistState();

      let spendRecord = null;
      try {
        spendRecord = await requestPointsSpend({
          mode: 'fashion',
          selectedSceneCount,
          type: 'fashion_generate',
          reason: '服饰穿戴图生成消耗',
          metadata: {
            mode: 'fashion',
            selected_scene_count: selectedSceneCount,
            pose_ids: normalizedFashionState?.fashionSelectedPoseIds || [],
          },
        });
        syncSharedPointsState(spendRecord?.points);
        formData.append('async_task', '1');
        formData.append('points_request_id', spendRecord?.requestId || '');
        formData.append('spend_record', JSON.stringify(spendRecord || {}));

        const response = await fetch('/api/generate-suite', {
          method: 'POST',
          body: formData,
        });
        const result = await parseJsonResponse(response);

        if (!response.ok || !result.success || !result.task_id) {
          const detailMessage = typeof result.details === 'string' ? result.details.trim() : '';
          const baseMessage = result.error || config.errorFallback;
          throw new Error(detailMessage ? `${baseMessage}｜${detailMessage}` : baseMessage);
        }

        savePendingGenerationTask(result.task_id, spendRecord, 'fashion');

        window.setTimeout(() => {
          if (generateBtn.disabled && pendingGenerationTask?.taskId === result.task_id) {
            updateGenerateButtonLabel(config.imageLoadingLabel);
            setResultStatus(config.imageProgress);
          }
        }, 1200);
      } catch (error) {
        let refundFailed = false;
        const didSpendPoints = Boolean(spendRecord && !spendRecord.skipped && Number(spendRecord.amount) > 0);
        if (didSpendPoints && !currentResultItems.length && !pendingGenerationTask?.taskId) {
          try {
            const refundedPoints = await requestPointsRefund(spendRecord, error.message || config.errorFallback);
            syncSharedPointsState(refundedPoints);
          } catch (refundError) {
            refundFailed = true;
          }
        }
        resetResultState();
        syncFashionState({ fashionFlowStep: 'scene' });
        if (resultMeta) {
          if (!didSpendPoints) {
            resultMeta.textContent = '生成前积分校验未通过，本次未发生实际扣分，可调整商品图、模特或场景设置后重试。';
          } else {
            resultMeta.textContent = refundFailed
              ? '生成失败，且自动返还积分失败，请联系客服核查。'
              : '生成失败后已自动返还本次扣减积分，可修改商品图、模特或场景设置后重试。';
          }
        }
        setResultStatus(!didSpendPoints
          ? (error.message || config.errorFallback)
          : (refundFailed ? `${error.message || config.errorFallback}；本次积分自动返还失败，请联系客服核查。` : `${error.message || config.errorFallback}；本次扣减积分已自动返还。`), 'error');
        persistState();
      } finally {
        applyFashionGenerateButtonState();
      }
    };

    let currentFiles = [];
    let currentReferenceFiles = [];
    let currentProductJson = null;
    let uploadedProductAssets = [];
    let uploadedReferenceAssets = [];

    const getProductFiles = () => currentFiles.slice(0, getProductUploadLimit());
    const getReferenceFiles = () => currentReferenceFiles.slice(0, 3);
    const getUploadedProductAssets = () => uploadedProductAssets.slice(0, getProductUploadLimit());
    const getUploadedReferenceAssets = () => uploadedReferenceAssets.slice(0, 3);

    const renderThumbList = (container, files, emptyMarkup, labelPrefix, uploadButton, uploadHint, isFashionUpload = false) => {
      if (!container) {
        return;
      }
      container.innerHTML = '';
      const maxFiles = getProductUploadLimit();
      if (!files.length) {
        container.style.display = 'none';
        if (uploadButton) uploadButton.style.display = '';
        if (uploadHint) uploadHint.style.display = '';
        return;
      }
      container.style.display = 'grid';
      if (uploadButton) uploadButton.style.display = '';
      if (uploadHint) uploadHint.style.display = '';
      files.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'thumb';
        item.style.backgroundSize = 'cover';
        item.style.backgroundPosition = 'center';
        item.style.color = '#fff';
        item.innerHTML = `
          <button class="thumb-delete-btn" type="button" data-index="${index}" aria-label="删除">×</button>
        `;
        item.dataset.index = index;
        const cachedPreviewUrl = file && file._previewUrl;
        if (cachedPreviewUrl) {
          item.style.backgroundImage = `url(${cachedPreviewUrl})`;
        } else if (file) {
          const objectUrl = URL.createObjectURL(file);
          file._previewUrl = objectUrl;
          item.style.backgroundImage = `url(${objectUrl})`;
          if (file.size > 1024 * 1024) {
            buildImagePreviewUrl(file).then((previewUrl) => {
              if (previewUrl && file._previewUrl === objectUrl) {
                file._previewUrl = previewUrl;
                item.style.backgroundImage = `url(${previewUrl})`;
              }
              URL.revokeObjectURL(objectUrl);
            }).catch(() => {
              URL.revokeObjectURL(objectUrl);
            });
          }
        }
        container.appendChild(item);
      });
      if (files.length < maxFiles) {
        const addButton = document.createElement('button');
        addButton.className = 'upload-btn';
        addButton.type = 'button';
        addButton.textContent = '+';
        container.appendChild(addButton);
      }
    };

    const uploadReferenceAssets = async (rawFiles, { storageGroup = 'temp', maxFiles = 3, existingCount = 0, label = '参考图', onProgress = null } = {}) => {
      const files = Array.from(rawFiles || []).filter((file) => file && String(file.type || '').startsWith('image/'));
      if (!files.length) {
        return { uploadedAssets: [], errorMessage: '' };
      }
      const availableSlots = maxFiles - existingCount;
      const selectedFiles = files.slice(0, availableSlots);
      let firstError = files.length > availableSlots ? `当前最多支持上传 ${maxFiles} 张${label}` : '';
      let completedCount = 0;
      const uploadedAssets = [];

      await uploadFilesWithConcurrency(selectedFiles, async (file, index) => {
        try {
          if (typeof onProgress === 'function') {
            onProgress({ completed: completedCount, total: selectedFiles.length, current: index + 1, file, state: 'compressing' });
          }
          const uploadFile = await compressImageForUpload(file);
          if (typeof onProgress === 'function') {
            onProgress({ completed: completedCount, total: selectedFiles.length, current: index + 1, file: uploadFile, originalFile: file, state: 'uploading' });
          }
          try {
            uploadedAssets[index] = await uploadFileToCosDirect(uploadFile, { storageGroup, storageSubdir: 'uploads' });
          } catch (directError) {
            const formData = new FormData();
            formData.append('file', uploadFile);
            formData.append('storage_group', storageGroup);
            formData.append('storage_subdir', 'uploads');
            const response = await fetch('/api/reference-images/upload', {
              method: 'POST',
              body: formData,
              credentials: 'include',
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok || !result || result.success === false || !result.image_url) {
              throw new Error((result && result.error) || (directError instanceof Error ? directError.message : `${label}上传失败，请稍后重试`));
            }
            uploadedAssets[index] = {
              imageUrl: String(result.image_url || ''),
              imagePath: String(result.image_path || ''),
              downloadName: String(result.download_name || uploadFile.name || file.name || ''),
              mimeType: String(result.mime_type || uploadFile.type || file.type || ''),
              storageGroup: String(result.storage_group || storageGroup || ''),
              storageBackend: String(result.storage_backend || 'server'),
              compressedSize: uploadFile.size || 0,
              originalSize: file.size || 0,
            };
          }
        } catch (error) {
          firstError = firstError || (error instanceof Error ? error.message : `${label}上传失败，请稍后重试`);
        } finally {
          completedCount += 1;
          if (typeof onProgress === 'function') {
            onProgress({ completed: completedCount, total: selectedFiles.length, current: index + 1, file, state: 'done' });
          }
        }
      });

      return { uploadedAssets: uploadedAssets.filter(Boolean), errorMessage: firstError };
    };

    const uploadFashionProductFiles = async (rawFiles, options = {}) => {
      return uploadReferenceAssets(rawFiles, {
        storageGroup: 'products',
        maxFiles: getProductUploadLimit(),
        existingCount: uploadedProductAssets.length,
        label: '商品图',
        ...options,
      });
    };

    const bindUploadInput = ({ button, input, thumbsContainer, emptyMarkup, labelPrefix, overLimitMessage, filesArray, isFashionUpload = false }) => {
      if (!button || !input || !thumbsContainer) {
        return;
      }
      
      const uploadBox = button.closest('.upload-box, .fashion-upload-box');
      const uploadTop = uploadBox?.querySelector('.upload-top, .fashion-upload-top');
      const uploadHint = uploadBox?.querySelector('.upload-hint, .fashion-upload-hint');
      
      // 绑定上传按钮点击事件
      button.addEventListener('click', () => {
        input.click();
      });
      
      // 绑定文件输入框变化事件
      input.addEventListener('change', async (event) => {
        const rawFiles = Array.from(event.target.files || []);
        const invalidFile = rawFiles.find((file) => file && !file.type.startsWith('image/'));
        if (invalidFile) {
          event.target.value = '';
          setResultStatus(`仅支持上传图片文件：${invalidFile.name || '未命名文件'}`, 'error');
          return;
        }

        if (filesArray === currentFiles) {
          const previewFiles = rawFiles.slice(0, Math.max(0, getProductUploadLimit() - filesArray.length));
          if (!previewFiles.length) {
            setResultStatus(`当前最多支持上传 ${getProductUploadLimit()} 张商品图`, 'error');
            event.target.value = '';
            return;
          }
          filesArray.push(...previewFiles);
          renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
          updateUploadHintText(uploadHint, `正在上传 ${previewFiles.length} 张商品图，请稍候...`);
          const originalButtonDisabled = button.disabled;
          button.disabled = true;
          const { uploadedAssets, errorMessage } = await uploadFashionProductFiles(rawFiles, {
            onProgress: ({ completed, total, file }) => {
              updateUploadHintText(uploadHint, `商品图上传中 ${completed}/${total}${file?.size ? ` · ${formatFileSize(file.size)}` : ''}`);
            },
          });
          if (uploadedAssets.length) {
            const maxFiles = getProductUploadLimit();
            uploadedProductAssets = uploadedProductAssets.concat(uploadedAssets).slice(0, maxFiles);
            currentProductJson = null;
          }
          if (uploadedAssets.length < previewFiles.length) {
            filesArray.splice(filesArray.length - previewFiles.length + uploadedAssets.length, previewFiles.length - uploadedAssets.length);
          }
          if (errorMessage) {
            setResultStatus(errorMessage, 'error');
          }
          renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
          updateUploadHintText(uploadHint, uploadedAssets.length ? `已上传 ${uploadedAssets.length} 张商品图` : '点击上传商品图');
          button.disabled = originalButtonDisabled;
          persistState();
          event.target.value = '';
          return;
        }

        if (filesArray === currentReferenceFiles) {
          const previewFiles = rawFiles.slice(0, Math.max(0, 3 - filesArray.length));
          if (!previewFiles.length) {
            setResultStatus('当前最多支持上传 3 张参考图', 'error');
            event.target.value = '';
            return;
          }
          filesArray.push(...previewFiles);
          renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
          updateUploadHintText(uploadHint, `正在上传 ${previewFiles.length} 张参考图，请稍候...`);
          const originalButtonDisabled = button.disabled;
          button.disabled = true;
          const { uploadedAssets, errorMessage } = await uploadReferenceAssets(rawFiles, {
            storageGroup: 'temp',
            maxFiles: 3,
            existingCount: uploadedReferenceAssets.length,
            label: '参考图',
            onProgress: ({ completed, total, file }) => {
              updateUploadHintText(uploadHint, `参考图上传中 ${completed}/${total}${file?.size ? ` · ${formatFileSize(file.size)}` : ''}`);
            },
          });
          if (uploadedAssets.length) {
            uploadedReferenceAssets = uploadedReferenceAssets.concat(uploadedAssets).slice(0, 3);
          }
          if (uploadedAssets.length < previewFiles.length) {
            filesArray.splice(filesArray.length - previewFiles.length + uploadedAssets.length, previewFiles.length - uploadedAssets.length);
          }
          if (errorMessage) {
            setResultStatus(errorMessage, 'error');
          }
          renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
          updateUploadHintText(uploadHint, uploadedAssets.length ? `已上传 ${uploadedAssets.length} 张参考图` : '点击上传参考图');
          button.disabled = originalButtonDisabled;
          persistState();
          event.target.value = '';
          return;
        }

        const maxFiles = getProductUploadLimit();
        const availableSlots = maxFiles - filesArray.length;
        const newFiles = rawFiles.slice(0, availableSlots);
        filesArray.push(...newFiles);
        if (rawFiles.length > availableSlots) {
          setResultStatus(overLimitMessage, 'error');
        }
        if (filesArray === currentFiles) {
          currentProductJson = null;
        }
        renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
        persistState();
      });
      
      // 绑定缩略图容器点击事件（用于删除图片）
      thumbsContainer.addEventListener('click', (event) => {
        const deleteBtn = event.target.closest('.thumb-delete-btn');
        if (deleteBtn) {
          const index = parseInt(deleteBtn.dataset.index, 10);
          if (!isNaN(index)) {
            filesArray.splice(index, 1);
            if (filesArray === currentFiles) {
              uploadedProductAssets.splice(index, 1);
              currentProductJson = null;
            }
            if (filesArray === currentReferenceFiles) {
              uploadedReferenceAssets.splice(index, 1);
            }
            input.value = '';
            renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
            persistState();
          }
        }

        // 处理+号按钮点击事件
        const addButton = event.target.closest('.upload-btn');
        if (addButton && addButton.textContent === '+') {
          input.click();
        }
      });
      
      // 初始渲染
      renderThumbList(thumbsContainer, filesArray, emptyMarkup, labelPrefix, button, uploadHint, isFashionUpload);
    };


    const buildResultMeta = (result) => {
      const styleMeta = buildSelectedStyleMeta(result.selected_style);
      const activeMode = result.mode || currentMode;
      const isAplus = activeMode === 'aplus';
      const isMode2 = activeMode === 'mode2' || activeMode === 'mode2-text2image' || activeMode === 'mode2-image-edit';
      const parts = [
        result.task_name ? `任务：${result.task_name}` : '',
        result.generated_at ? `生成时间：${result.generated_at}` : '',
        isAplus
          ? (result.plan?.module_count ? `模块数量：${result.plan.module_count}` : '')
          : (isMode2 ? (result.plan?.output_count ? `输出张数：${result.plan.output_count}` : '') : (result.plan?.output_count ? `输出张数：${result.plan.output_count}` : '')),
        styleMeta,
      ].filter(Boolean);
      return parts.join(' · ') || getCurrentModeConfig().resultFallback;
    };

    const normalizeImagePath = (value = '') => String(value || '').trim().replace(/\\/g, '/').replace(/^\/+/, '').replace(/^generated-suites\//, '');

    const normalizeImageUrl = (item = {}) => {
      const rawUrl = typeof item.image_url === 'string' ? item.image_url.trim() : '';
      if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
        return rawUrl;
      }
      const imagePath = normalizeImagePath(item.image_path);
      if (imagePath) {
        const expectedUrl = `/generated/${imagePath.split('/').map(encodeURIComponent).join('/')}`;
        if (!rawUrl || rawUrl.includes('/generated/generated-suites/')) {
          return expectedUrl;
        }
      }
      return rawUrl;
    };

    const getItemKey = (item, index = 0) => item.image_path || item.image_url || `${item.kind || 'item'}-${item.sort || index}`;

    const normalizeResultItems = (result) => {
      const referenceItems = Array.isArray(result.reference_images) ? result.reference_images : [];
      const generatedItems = Array.isArray(result.images) ? result.images : [];
      const activeMode = result?.mode || currentMode;
      const mode2GeneratedItems = !generatedItems.length && ['mode2', 'mode2-text2image', 'mode2-image-edit'].includes(activeMode) && result.image_url
        ? [{
            title: activeMode === 'mode2-image-edit' ? '模式2图生图' : '模式2文生图',
            type: activeMode === 'mode2-image-edit' ? '图生图' : '文生图',
            type_tag: 'Mode2',
            image_url: result.image_url,
            image_path: result.image_path,
            download_name: result.download_name,
            prompt: result.prompt,
            model: result.model,
            sort: 1,
            kind: 'generated',
          }]
        : [];

      return [
        ...referenceItems.map((item, index) => ({
          ...item,
          image_url: normalizeImageUrl(item),
          sort: item.sort || index + 1,
          kind: item.kind || 'reference',
        })),
        ...[...generatedItems, ...mode2GeneratedItems]
          .slice()
          .sort((a, b) => (a.sort || 0) - (b.sort || 0))
          .map((item, index) => ({
            ...item,
            image_url: normalizeImageUrl(item),
            sort: item.sort || index + 1,
            kind: item.kind || 'generated',
          })),
      ];
    };

    const getSelectedItems = () => currentResultItems.filter((item, index) => selectedResultKeys.has(getItemKey(item, index)));

    const getDownloadableItems = (items = []) => (Array.isArray(items) ? items : []).map((item) => {
      if (!item || (!item.image_url && !item.image_path)) {
        return null;
      }
      const image_path = normalizeImagePath(item.image_path);
      return {
        ...item,
        image_path,
        image_url: normalizeImageUrl({ ...item, image_path }),
      };
    }).filter(Boolean);

    const triggerFileDownload = (downloadUrl, downloadName) => {
      const normalizedUrl = typeof downloadUrl === 'string' ? downloadUrl.trim() : '';
      if (!normalizedUrl) {
        throw new Error('缺少下载地址，请稍后重试');
      }
      const link = document.createElement('a');
      link.href = normalizedUrl;
      if (downloadName) {
        link.download = downloadName;
      }
      document.body.appendChild(link);
      link.click();
      link.remove();
      return true;
    };

    const downloadItemsAsZip = async (items = []) => {
      const downloadableItems = getDownloadableItems(items);
      if (!downloadableItems.length) {
        throw new Error('未找到可下载的图片文件');
      }
      const zipSourceItems = downloadableItems.filter((item) => item.image_path || item.image_url);
      if (!zipSourceItems.length) {
        throw new Error('当前图片缺少下载路径，请重新生成后再试');
      }

      const cosItems = zipSourceItems.filter((item) => {
        const url = typeof item.image_url === 'string' ? item.image_url.trim() : '';
        return url.startsWith('http://') || url.startsWith('https://');
      });

      if (typeof JSZip !== 'undefined' && cosItems.length > 0) {
        try {
          const zip = new JSZip();
          const usedNames = new Set();
          let addedCount = 0;

          for (const item of zipSourceItems) {
            const rawUrl = typeof item.image_url === 'string' ? item.image_url.trim() : '';
            let imageUrl = rawUrl;
            if (!imageUrl.startsWith('http://') && !imageUrl.startsWith('https://')) {
              const imagePath = normalizeImagePath(item.image_path);
              if (imagePath) {
                imageUrl = `/generated/${imagePath.split('/').map(encodeURIComponent).join('/')}`;
              }
            }
            if (!imageUrl) continue;

            const baseName = item.download_name || (item.image_path || '').split('/').pop() || 'image.jpg';
            let stem = baseName.replace(/\.[^.]+$/, '') || 'image';
            let suffix = baseName.match(/\.[^.]+$/)?.[0] || '.jpg';
            let archiveName = `${stem}${suffix}`;
            let dupIdx = 2;
            while (usedNames.has(archiveName)) {
              archiveName = `${stem}-${dupIdx}${suffix}`;
              dupIdx++;
            }
            usedNames.add(archiveName);

            try {
              const resp = await fetch(imageUrl);
              if (!resp.ok) continue;
              const blob = await resp.blob();
              zip.file(archiveName, blob);
              addedCount++;
            } catch (err) {
              console.warn('Failed to fetch image for zip:', imageUrl, err);
            }
          }

          if (addedCount === 0) {
            throw new Error('未能下载任何图片');
          }

          const zipBlob = await zip.generateAsync({ type: 'blob' });
          const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
          const downloadName = `ai-images-${timestamp}.zip`;
          const objectUrl = URL.createObjectURL(zipBlob);
          const link = document.createElement('a');
          link.href = objectUrl;
          link.download = downloadName;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
          return true;
        } catch (err) {
          console.warn('Client-side zip failed, falling back to server:', err);
        }
      }

      const response = await fetch('/api/download-zip', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_paths: zipSourceItems.map((item) => item.image_path || item.image_url),
          async_task: true,
        }),
      });
      const taskPayload = await parseJsonResponse(response);
      if (!response.ok || !taskPayload?.success || !taskPayload.task_id) {
        throw new Error(taskPayload?.error || '打包下载失败，请稍后重试');
      }
      const taskResult = await pollGenericTaskResult({
        taskId: taskPayload.task_id,
        loadingMessage: '打包任务已提交，正在处理中…',
        pendingMessage: '打包任务排队中，请稍候…',
        runningMessage: '正在打包图片，请稍候…',
        statusErrorMessage: '打包任务状态查询失败',
        timeoutMessage: '图片打包等待超时，请稍后重试',
      });
      triggerFileDownload(taskResult?.download_url, taskResult?.download_name || 'ai-images.zip');
      return true;
    };

    const buildCardSubText = (item) => {
      if (item.kind === 'reference') {
        if (item.reference_source === 'product') {
          return '用户上传的商品原图，用于保持服饰主体一致。';
        }
        if (item.reference_source === 'fashion_reference') {
          return '用户上传的穿搭参考图，用于约束姿态、氛围或构图方向。';
        }
        return '用户上传参考图，可与生成图一起筛选和下载。';
      }
      if (Array.isArray(item.keywords) && item.keywords.length) {
        return item.keywords.join(' · ');
      }
      return getCurrentModeConfig().itemFallback;
    };

    const updateSelectionSummary = () => {
      const total = currentResultItems.length;
      const selected = selectedResultKeys.size;
      const hasItems = total > 0;
      const allSelected = hasItems && selected === total;
      if (taskOutputCount) {
        taskOutputCount.textContent = String(getCurrentOutputMetric()).padStart(2, '0');
      }
      if (taskSelectedCount) {
        taskSelectedCount.textContent = String(selected).padStart(2, '0');
      }
      if (taskSelectAll) {
        taskSelectAll.checked = allSelected;
        taskSelectAll.disabled = !hasItems;
      }
      selectAllBtn.textContent = allSelected ? '取消全选' : '全选';
      selectAllBtn.disabled = !hasItems;
      downloadSelectedBtn.disabled = selected === 0;
      generateTitlesBtn.disabled = !hasItems;
    };

    const updateTaskSummary = (result) => {
      const activeMode = result.mode || currentMode;
      const isFashion = activeMode === 'fashion';
      const isMode2 = activeMode === 'mode2' || activeMode === 'mode2-text2image' || activeMode === 'mode2-image-edit';
      const selectedStyleMeta = (isFashion || isMode2) ? '' : buildSelectedStyleMeta(result.selected_style);
      const defaultSummary = isFashion
        ? '已生成服饰穿戴结果。'
        : (isMode2
          ? (activeMode === 'mode2-image-edit' ? '已生成模式2图生图结果。' : '已生成模式2文生图结果。')
          : '已生成可管理的任务结果。');
      taskSummaryLine.textContent = selectedStyleMeta
        ? `${result.plan?.summary || defaultSummary} · ${selectedStyleMeta}`
        : (result.plan?.summary || defaultSummary);
      resultMeta.textContent = buildResultMeta(result);
      updateSelectionSummary();
      persistState();
    };

    const triggerDownload = (item) => {
      if (!item?.image_url) {
        return false;
      }
      const link = document.createElement('a');
      link.href = item.image_url;
      link.download = item.download_name || `${item.title || item.type || 'image'}.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      return true;
    };

    const copyText = async (text) => {
      if (!text) {
        return false;
      }
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      const helper = document.createElement('textarea');
      helper.value = text;
      helper.setAttribute('readonly', 'readonly');
      helper.style.position = 'fixed';
      helper.style.opacity = '0';
      document.body.appendChild(helper);
      helper.select();
      const copied = document.execCommand('copy');
      helper.remove();
      return copied;
    };

    const toggleItemSelection = (key) => {
      if (selectedResultKeys.has(key)) {
        selectedResultKeys.delete(key);
      } else {
        selectedResultKeys.add(key);
      }
      renderResultCards(currentResultItems);
      persistState();
    };

    const setAllSelections = (checked) => {
      selectedResultKeys = checked
        ? new Set(currentResultItems.map((item, index) => getItemKey(item, index)))
        : new Set();
      renderResultCards(currentResultItems);
      persistState();
    };

    const openPreview = (index) => {
      if (index < 0 || index >= currentResultItems.length) {
        return;
      }
      previewIndex = index;
      const item = currentResultItems[index];
      previewImage.src = item.image_url || '';
      previewImage.alt = item.title || item.type || '预览图片';
      previewTitle.textContent = item.title || item.type || '图片预览';
      previewType.textContent = `${item.kind === 'reference' ? '原图' : '生成图'} / ${item.type || ''}`;
      previewPrevBtn.disabled = index <= 0;
      previewNextBtn.disabled = index >= currentResultItems.length - 1;
      previewModal.hidden = false;
      document.body.style.overflow = 'hidden';
      persistState();
    };

    const closePreview = () => {
      previewModal.hidden = true;
      previewIndex = -1;
      previewImage.src = '';
      previewImage.alt = '预览图片';
      previewTitle.textContent = '图片预览';
      previewType.textContent = '预览';
      document.body.style.overflow = '';
      persistState();
    };

    const showPreviewOffset = (offset) => {
      if (previewIndex < 0) {
        return;
      }
      openPreview(previewIndex + offset);
    };

    const renderTitleSuggestions = () => {
      if (!currentResult) {
        titleSuggestionPanel.hidden = true;
        titleSuggestionPanel.innerHTML = '';
        setResultStatus('请先生成结果后再生成标题。', 'error');
        persistState();
        return;
      }

      const platform = getPlatformLabel();
      const sellingText = sellingInput?.value?.trim() || '';
      const titleSeeds = currentResultItems
        .filter((item) => item.kind === 'generated')
        .slice(0, 4)
        .flatMap((item) => [item.title, ...(item.keywords || [])])
        .filter(Boolean)
        .map((text) => String(text).trim())
        .filter(Boolean);
      const uniqueSeeds = Array.from(new Set(titleSeeds));
      const lead = uniqueSeeds.slice(0, 2).join(' · ') || '商品卖点';
      const tail = uniqueSeeds.slice(2, 6).join(' / ');
      const sellingLead = sellingText.split(/[，。；\n]/).map((part) => part.trim()).filter(Boolean).slice(0, 2).join(' · ');
      const suggestions = [
        `${platform}热销款 ${lead}${sellingLead ? ` · ${sellingLead}` : ''}`,
        `${lead} | ${platform}商品图上架主标题`,
        `${platform}跨境推荐 ${sellingLead || lead}${tail ? ` · ${tail}` : ''}`,
        `${lead}${tail ? ` · ${tail}` : ''} | 高转化详情展示`,
      ].map((text) => text.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 4);

      titleSuggestionPanel.hidden = false;
      titleSuggestionPanel.innerHTML = `
        <div class="small-label">Smart Listing Titles</div>
        <ol class="title-suggestion-list">
          ${suggestions.map((item, index) => `
            <li class="title-suggestion-item">
              <span class="title-suggestion-text">${escapeHtml(item)}</span>
              <button class="title-copy-btn" type="button" data-role="copy-title" data-title-index="${index}">复制</button>
            </li>
          `).join('')}
        </ol>
      `;
      titleSuggestionPanel.dataset.suggestions = JSON.stringify(suggestions);
      setResultStatus(`已生成 ${suggestions.length} 条轻量版上架标题建议`, 'success');
      persistState();
    };

    const renderLoadingResultCards = (count = 6) => {
      const safeCount = Math.max(1, Number(count) || 1);
      resultGrid.innerHTML = Array.from({ length: safeCount }, (_, index) => `
        <article class="result-card result-card-loading" aria-hidden="true">
          <div class="result-image">
            <div class="image-shape image-shape-loading"></div>
            <div class="overlay-chip">
              <span class="result-no">${String(index + 1).padStart(2, '0')}</span>
            </div>
          </div>
          <div class="result-body">
            <div class="result-topline">
              <div class="card-title skeleton-line skeleton-line-title"></div>
            </div>
            <div class="small-label skeleton-line skeleton-line-label"></div>
            <div class="card-sub skeleton-line skeleton-line-copy"></div>
            <div class="card-actions">
              <div class="card-action-btn skeleton-button"></div>
            </div>
          </div>
        </article>
      `).join('');
    };

    const renderResultCards = (items = []) => {
      updateSelectionSummary();
      if (!items.length) {
        resultGrid.innerHTML = '';
        return;
      }

      resultGrid.innerHTML = items.map((item, index) => {
        const imageUrl = item.image_url ? escapeHtml(item.image_url) : '';
        const hasImageClass = imageUrl ? ' has-image' : '';
        const itemKey = escapeHtml(getItemKey(item, index));
        const isSelected = selectedResultKeys.has(getItemKey(item, index));
        const selectedClass = isSelected ? ' is-selected' : '';
        const referenceClass = item.kind === 'reference' ? ' is-reference' : '';
        return `
          <article class="result-card${selectedClass}${referenceClass}" data-item-key="${itemKey}">
            <div class="result-image${hasImageClass}">
              <label class="card-check" aria-label="选择图片">
                <input type="checkbox" data-role="select-item" data-key="${itemKey}" ${isSelected ? 'checked' : ''}>
              </label>
              <div class="overlay-chip">
                <span class="result-no">${String(item.sort || index + 1).padStart(2, '0')}</span>
              </div>
              ${imageUrl ? `<img src="${imageUrl}" alt="${escapeHtml(item.title || item.type || '生成结果')}" loading="eager" decoding="async" fetchpriority="high" data-role="preview-image" data-index="${index}">` : '<div class="image-shape"></div>'}
            </div>
            <div class="result-body">
              <div class="result-topline">
                <div class="card-title">${escapeHtml(item.title || '')}</div>
              </div>
              <div class="small-label">${escapeHtml(item.type || '')}</div>
              <div class="card-sub">${escapeHtml(buildCardSubText(item))}</div>
              <div class="card-actions">
                <button class="card-action-btn" type="button" data-role="download-item" data-index="${index}">下载</button>
              </div>
            </div>
          </article>
        `;
      }).join('');
    };

    const showResultView = () => {
      introView.classList.remove('active');
      resultView.classList.add('active');
      resultView.scrollIntoView({ behavior: 'smooth', block: 'start' });
      persistState();
    };

    const showIntroView = () => {
      introView.classList.add('active');
      resultView.classList.remove('active');
      persistState();
    };

    const resetResultStatus = () => {
      hideGenerationProgress();
      if (!resultStatusMessage) {
        return;
      }
      resultStatusMessage.textContent = '';
      resultStatusMessage.className = 'result-status-message';
    };

    let progressTimer = null;
    let progressHideTimer = null;
    let progressStartTime = 0;
    let progressEstimatedSeconds = 0;

    const hideGenerationProgress = () => {
      if (!generationProgressBar || !generationProgressFill) {
        return;
      }
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      if (progressHideTimer) {
        clearTimeout(progressHideTimer);
        progressHideTimer = null;
      }
      generationProgressBar.hidden = true;
      generationProgressBar.classList.remove('is-active');
      generationProgressFill.style.width = '0%';
    };

    const startGenerationProgress = (estimatedSeconds, outputCount = 0) => {
      if (!generationProgressBar || !generationProgressFill) {
        return;
      }
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      if (progressHideTimer) {
        clearTimeout(progressHideTimer);
        progressHideTimer = null;
      }
      progressEstimatedSeconds = estimatedSeconds || getCurrentModeConfig().estimatedSeconds || 120;
      progressStartTime = Date.now();
      generationProgressBar.hidden = false;
      generationProgressBar.classList.add('is-active');
      generationProgressFill.style.width = '2%';
      progressTimer = setInterval(() => {
        const elapsed = (Date.now() - progressStartTime) / 1000;
        const pct = Math.min(Math.max((elapsed / progressEstimatedSeconds) * 95, 2), 92);
        generationProgressFill.style.width = pct + '%';
      }, 400);
    };

    const stopGenerationProgress = () => {
      if (!generationProgressBar || !generationProgressFill) {
        return;
      }
      if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
      }
      if (progressHideTimer) {
        clearTimeout(progressHideTimer);
        progressHideTimer = null;
      }
      generationProgressFill.style.width = '100%';
      generationProgressBar.classList.remove('is-active');
      progressHideTimer = setTimeout(() => {
        generationProgressBar.hidden = true;
        generationProgressFill.style.width = '0%';
        progressHideTimer = null;
      }, 500);
    };

    const resetResultState = () => {
      stopPendingGenerationPolling();
      hideGenerationProgress();
      pendingGenerationTask = null;
      const config = getCurrentModeConfig();
      currentResult = null;
      currentResultItems = [];
      selectedResultKeys = new Set();
      previewIndex = -1;
      resultGrid.innerHTML = '';
      taskSummaryLine.textContent = config.initialTaskSummary;
      if (taskOutputCount) {
        taskOutputCount.textContent = '00';
      }
      if (taskSelectedCount) {
        taskSelectedCount.textContent = '00';
      }
      if (taskSelectAll) {
        taskSelectAll.checked = false;
        taskSelectAll.disabled = true;
      }
      selectAllBtn.disabled = true;
      downloadSelectedBtn.disabled = true;
      generateTitlesBtn.disabled = true;
      titleSuggestionPanel.hidden = true;
      titleSuggestionPanel.innerHTML = '';
      titleSuggestionPanel.dataset.suggestions = '[]';
      closePreview();
      resultMeta.textContent = config.initialResultMeta;
      updateSelectionSummary();
    };

    const setResultStatus = (message, type = '') => {
      if (!resultStatusMessage) {
        return;
      }
      const normalizedType = type
        ? (String(type).startsWith('is-') ? String(type) : `is-${String(type)}`)
        : '';
      resultStatusMessage.textContent = message || '';
      resultStatusMessage.className = `result-status-message${normalizedType ? ` ${normalizedType}` : ''}`;
      persistState();
    };

    const saveStateToLocalStorage = () => {
      try {
        const existingState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const state = {
          ...existingState,
          currentMode: PAGE_MODE,
          selectedOutputCount,
          selectedMainImageCount,
          selectedAplusModules: Array.from(selectedAplusModules),
          currentStyleResults,
          selectedStyleIndex,
          currentResult,
          currentResultItems,
          currentProductJson,
          selectedResultKeys: Array.from(selectedResultKeys),
          previewIndex,
          pendingGenerationTask,
          viewState: getViewState(),
          resultMeta: resultMeta.textContent,
          resultStatus: {
            message: resultStatusMessage ? resultStatusMessage.textContent : '',
            className: resultStatusMessage ? resultStatusMessage.className : 'result-status-message',
          },
          taskSummaryLine: taskSummaryLine.textContent,
          taskOutputCount: taskOutputCount ? taskOutputCount.textContent : '00',
          taskSelectedCount: taskSelectedCount ? taskSelectedCount.textContent : '00',
          taskSelectAllChecked: taskSelectAll ? taskSelectAll.checked : false,
          titleSuggestions: getTitleSuggestionsState(),
          controlValues: collectControlValues(),
          moreMenu: {
            hidden: moreMenu ? moreMenu.hidden : true,
            expanded: moreBtn ? moreBtn.getAttribute('aria-expanded') === 'true' : false,
          },
          mainImageMenu: {
            hidden: mainImageMenu ? mainImageMenu.hidden : true,
            expanded: mainImageBtn ? mainImageBtn.getAttribute('aria-expanded') === 'true' : false,
          },
          scroll: captureScrollState(),
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (e) {
        console.error('Failed to save state:', e);
      }
    };

    const persistState = saveStateToLocalStorage;

    const restoreStateFromLocalStorage = () => {
      try {
        const savedState = localStorage.getItem(STORAGE_KEY);
        if (!savedState) {
          return false;
        }

        const state = JSON.parse(savedState);
        if (!state) {
          return false;
        }

        isRestoringState = true;

        currentMode = PAGE_MODE;
        if (typeof state.selectedOutputCount === 'number') {
          selectedOutputCount = state.selectedOutputCount;
        }
        if (typeof state.selectedMainImageCount === 'number') {
          selectedMainImageCount = Math.min(Math.max(state.selectedMainImageCount, 0), 10);
        }
        if (Array.isArray(state.selectedAplusModules) && state.selectedAplusModules.length) {
          selectedAplusModules = new Set(state.selectedAplusModules.filter((key) => APLUS_MODULE_META[key]));
        }
        if (!selectedAplusModules.size && isAplusPage) {
          selectedAplusModules = new Set(['hero_value', 'usage_scene', 'core_selling', 'detail_zoom']);
        }

        restoreControlValues(state.controlValues || {});
        setMode(currentMode, { preserveResultState: true, skipPersist: true });

        if (Array.isArray(state.currentStyleResults)) {
          currentStyleResults = state.currentStyleResults;
          selectedStyleIndex = Number.isInteger(state.selectedStyleIndex) ? state.selectedStyleIndex : -1;
          renderStyleCards(currentStyleResults);
        }

        currentResult = state.currentResult || null;
        if (currentResult && ['mode2-text2image', 'mode2-image-edit'].includes(currentResult.mode)) {
          currentResult = normalizeMode2Result(currentResult) || currentResult;
        }
        currentProductJson = state.currentProductJson && typeof state.currentProductJson === 'object'
          ? state.currentProductJson
          : null;
        if (currentResult && typeof currentResult === 'object') {
          if (Array.isArray(currentResult.reference_images)) {
            currentResult.reference_images = currentResult.reference_images.map((item) => ({
              ...item,
              image_url: normalizeImageUrl(item),
            }));
          }
          if (Array.isArray(currentResult.images)) {
            currentResult.images = currentResult.images.map((item) => ({
              ...item,
              image_url: normalizeImageUrl(item),
            }));
          }
        }
        currentResultItems = currentResult
          ? normalizeResultItems(currentResult)
          : (Array.isArray(state.currentResultItems)
            ? state.currentResultItems.map((item) => ({
                ...item,
                image_url: normalizeImageUrl(item),
              }))
            : []);
        selectedResultKeys = new Set(Array.isArray(state.selectedResultKeys) ? state.selectedResultKeys : []);
        pendingGenerationTask = state.pendingGenerationTask && state.pendingGenerationTask.taskId
          ? state.pendingGenerationTask
          : null;

        if (currentResultItems.length > 0) {
          renderResultCards(currentResultItems);
        } else {
          resultGrid.innerHTML = '';
          updateSelectionSummary();
        }

        taskSummaryLine.textContent = state.taskSummaryLine || getCurrentModeConfig().initialTaskSummary;
        resultMeta.textContent = state.resultMeta || getCurrentModeConfig().initialResultMeta;
        if (resultStatusMessage) {
          resultStatusMessage.textContent = state.resultStatus?.message || '';
          resultStatusMessage.className = state.resultStatus?.className || 'result-status-message';
        }
        if (taskOutputCount) {
          taskOutputCount.textContent = state.taskOutputCount || taskOutputCount.textContent;
        }
        if (taskSelectedCount) {
          taskSelectedCount.textContent = state.taskSelectedCount || taskSelectedCount.textContent;
        }
        if (taskSelectAll) {
          taskSelectAll.checked = Boolean(state.taskSelectAllChecked);
        }
        restoreTitleSuggestionsState(state.titleSuggestions || {});
        applyViewState(state.viewState || {});

        if (moreMenu && moreBtn) {
          const isExpanded = Boolean(state.moreMenu?.expanded);
          moreMenu.hidden = state.moreMenu?.hidden ?? !isExpanded;
          moreBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        }
        if (mainImageMenu && mainImageBtn) {
          const isExpanded = Boolean(state.mainImageMenu?.expanded);
          mainImageMenu.hidden = state.mainImageMenu?.hidden ?? !isExpanded;
          mainImageBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        }
        setSelectedMainImageCount(selectedMainImageCount);

        if (Number.isInteger(state.previewIndex) && state.previewIndex >= 0 && state.previewIndex < currentResultItems.length) {
          openPreview(state.previewIndex);
        } else {
          closePreview();
        }

        restoreScrollState(state.scroll || {});
        if (pendingGenerationTask?.taskId) {
          showResultView();
          const pendingCount = Number(pendingGenerationTask?.spendRecord?.metadata?.selected_scene_count) || Number(state.taskOutputCount) || 4;
          renderLoadingResultCards(pendingCount);
          setResultStatus('已恢复正在生成的任务，正在等待生成结果。');
          if (pendingGenerationTask.mode === 'fashion') {
            syncFashionState({ fashionFlowStep: 'result' });
          } else if (generateBtn) {
            applyGenerateButtonPendingState(getCurrentModeConfig().imageLoadingLabel);
          }
          pollPendingGenerationTask({ immediate: true });
        }
        return true;
      } catch (e) {
        console.error('Failed to restore state:', e);
        return false;
      } finally {
        isRestoringState = false;
      }
    };

    navItems.forEach((item) => {
      item.addEventListener('click', (event) => {
        if (item.dataset.navLink === 'true') {
          return;
        }
        event.preventDefault();
        setMode(item.dataset.mode);
      });
    });

    if (isAplusPage && aplusModulesGrid) {
      aplusModulesGrid.addEventListener('click', (event) => {
        const card = event.target.closest('[data-module]');
        if (!card) {
          return;
        }
        toggleAplusModule(card.dataset.module);
      });
    }

    if (styleResultsGrid) {
      styleResultsGrid.addEventListener('click', (event) => {
        const styleCard = event.target.closest('[data-role="select-style"]');
        if (!styleCard) {
          return;
        }
        selectStyleCard(Number(styleCard.dataset.index));
      });
    }

    if (taskSelectAll) {
      taskSelectAll.addEventListener('change', (event) => {
        setAllSelections(event.target.checked);
      });
    }

    if (selectAllBtn) {
      selectAllBtn.addEventListener('click', () => {
        const shouldSelectAll = selectedResultKeys.size !== currentResultItems.length;
        setAllSelections(shouldSelectAll);
      });
    }

    if (downloadSelectedBtn) {
      downloadSelectedBtn.addEventListener('click', async () => {
        const selectedItems = getSelectedItems();
        if (!selectedItems.length) {
          return;
        }
        try {
          downloadSelectedBtn.disabled = true;
          await downloadItemsAsZip(selectedItems);
        } catch (error) {
          console.error('Batch zip download failed:', error);
          setResultStatus(error.message || '打包下载失败，请稍后重试', 'error');
          window.alert(error.message || '打包下载失败，请稍后重试');
        } finally {
          updateSelectionSummary();
        }
      });
    }

    if (generateTitlesBtn) {
      generateTitlesBtn.addEventListener('click', () => {
        renderTitleSuggestions();
      });
    }

    if (resultGrid) {
      resultGrid.addEventListener('click', (event) => {
        const selectInput = event.target.closest('[data-role="select-item"]');
        if (selectInput) {
          toggleItemSelection(selectInput.dataset.key);
          return;
        }

        const previewTarget = event.target.closest('[data-role="preview-image"]');
        if (previewTarget) {
          openPreview(Number(previewTarget.dataset.index));
          return;
        }

        const downloadBtn = event.target.closest('[data-role="download-item"]');
        if (downloadBtn) {
          const item = currentResultItems[Number(downloadBtn.dataset.index)];
          if (!item) {
            return;
          }
          triggerDownload(item);
        }
      });
    }

    if (titleSuggestionPanel) {
      titleSuggestionPanel.addEventListener('click', async (event) => {
        const copyBtn = event.target.closest('[data-role="copy-title"]');
        if (!copyBtn) {
          return;
        }
        const suggestions = JSON.parse(titleSuggestionPanel.dataset.suggestions || '[]');
        const title = suggestions[Number(copyBtn.dataset.titleIndex)] || '';
        if (!title) {
          setResultStatus('未找到可复制的标题内容。', 'error');
          return;
        }
        try {
          await copyText(title);
          setResultStatus('标题建议已复制到剪贴板。', 'success');
        } catch (error) {
          setResultStatus('复制失败，请手动复制标题内容。', 'error');
        }
      });
    }

    if (previewBackdrop) {
      previewBackdrop.addEventListener('click', closePreview);
    }
    if (previewCloseBtn) {
      previewCloseBtn.addEventListener('click', closePreview);
    }
    if (previewDownloadBtn) {
      previewDownloadBtn.addEventListener('click', () => {
        if (previewIndex < 0) {
          return;
        }
        const item = currentResultItems[previewIndex];
        if (!item) {
          return;
        }
        triggerDownload(item);
      });
    }
    if (previewPrevBtn) {
      previewPrevBtn.addEventListener('click', () => showPreviewOffset(-1));
    }
    if (previewNextBtn) {
      previewNextBtn.addEventListener('click', () => showPreviewOffset(1));
    }

    document.addEventListener('keydown', (event) => {
      if (previewModal.hidden) {
        return;
      }
      if (event.key === 'Escape') {
        closePreview();
      } else if (event.key === 'ArrowLeft') {
        showPreviewOffset(-1);
      } else if (event.key === 'ArrowRight') {
        showPreviewOffset(1);
      }
    });

    if (mainImageBtn) {
      mainImageBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (mainImageMenu && mainImageMenu.hidden) {
          openMainImageMenu();
          return;
        }
        closeMainImageMenu();
      });
    }

    if (mainImageOptions && mainImageOptions.length > 0) {
      mainImageOptions.forEach((option) => {
        option.addEventListener('click', () => {
          setSelectedMainImageCount(Number(option.dataset.mainCount));
          closeMainImageMenu();
        });
      });
    }

    if (moreBtn) {
      moreBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (moreMenu && moreMenu.hidden) {
          openMoreMenu();
          return;
        }
        closeMoreMenu();
      });
    }

    if (moreOptions && moreOptions.length > 0) {
      moreOptions.forEach((option) => {
        option.addEventListener('click', () => {
          setSelectedOutputCount(Number(option.dataset.count));
          closeMoreMenu();
        });
      });
    }

    if (moreActions && !isAplusPage) {
      moreActions.addEventListener('change', persistState);
    }

    [sellingInput, platformSelect, countrySelect, textTypeSelect, imageSizeSelect].forEach((element) => {
      if (!element) {
        return;
      }
      element.addEventListener('input', () => {
        if (element === sellingInput) {
          currentProductJson = null;
        }
        persistState();
      });
      element.addEventListener('change', () => {
        if (element === sellingInput) {
          currentProductJson = null;
        }
        persistState();
      });
    });

    [window, controlRail, workspaceMain].forEach((target) => {
      if (!target) {
        return;
      }
      target.addEventListener('scroll', persistState, { passive: true });
    });

    renderAplusModuleCards();
    syncOutputCountSummary();
    resetStaleFashionLoadingState();

    const restored = restoreStateFromLocalStorage();
    if (!restored) {
      setMode(currentMode, { preserveResultState: false });
    }

    if (isFashionPage) {
      applyFashionGenerateButtonState();
      window.addEventListener('fashion:model-state-change', (event) => {
        applyFashionGenerateButtonState(event.detail?.cta || getFashionSelectionState());
      });
    }

    if (aiWriteBtn && sellingInput && sellingMessage) {
      aiWriteBtn.disabled = false;
      aiWriteBtn.addEventListener('click', async () => {
        const originalText = sellingInput.value;
        const formData = new FormData();
        formData.append('selling_text', originalText);
        appendFilesToFormData(formData, 'images', getProductFiles());

        sellingMessage.textContent = '';
        sellingMessage.className = 'field-message';
        aiWriteBtn.disabled = true;
        sellingInput.value = '生成中';

        try {
          const response = await fetch('/api/ai-write', {
            method: 'POST',
            body: formData,
          });
          const result = await parseJsonResponse(response);

          if (!response.ok || !result.success) {
            throw new Error(result.error || '生成失败，请稍后重试');
          }

          if (result.task_id) {
            await pollGenericTaskResult({
              taskId: result.task_id,
              loadingMessage: 'AI 文案任务已提交，正在处理中…',
              pendingMessage: 'AI 文案任务排队中，请稍候…',
              runningMessage: 'AI 文案生成中，请稍候…',
              statusErrorMessage: 'AI 文案任务状态查询失败',
              timeoutMessage: 'AI 文案生成等待超时，请稍后重试',
              onPending: (message, task) => {
                const partialResult = task?.result && typeof task.result === 'object' ? task.result : null;
                const partialText = typeof partialResult?.text === 'string' ? partialResult.text : '';
                if (partialText) {
                  sellingInput.value = partialText;
                  sellingMessage.textContent = '';
                  sellingMessage.className = 'field-message';
                  return;
                }
                sellingMessage.textContent = message || 'AI 文案生成中，请稍候…';
                sellingMessage.className = 'field-message';
                sellingInput.value = '生成中';
              },
              onProgress: (taskResult) => {
                const partialText = typeof taskResult?.text === 'string' ? taskResult.text : '';
                if (!partialText) {
                  return;
                }
                sellingInput.value = partialText;
                sellingMessage.textContent = '';
                sellingMessage.className = 'field-message';
              },
              onSuccess: (taskResult) => {
                sellingInput.value = taskResult?.text || '';
                currentProductJson = taskResult?.product_json && typeof taskResult.product_json === 'object'
                  ? taskResult.product_json
                  : null;
                sellingMessage.textContent = '';
                sellingMessage.className = 'field-message';
                persistState();
              },
            });
            return;
          }

          sellingInput.value = result.text || '';
          currentProductJson = result.product_json && typeof result.product_json === 'object'
            ? result.product_json
            : null;
          sellingMessage.textContent = '';
          sellingMessage.className = 'field-message';
          persistState();
        } catch (error) {
          sellingInput.value = originalText;
          sellingMessage.textContent = error.message || '生成失败，请稍后重试';
          sellingMessage.className = 'field-message error';
          persistState();
        } finally {
          aiWriteBtn.disabled = false;
        }
      });
    }

    if (styleBtn && sellingInput && styleResultsMessage && styleResultsGrid) {
      styleBtn.addEventListener('click', async () => {
        const formData = new FormData();
        formData.append('selling_text', sellingInput.value.trim());
        formData.append('platform', getPlatformLabel());
        appendFilesToFormData(formData, 'images', getProductFiles());

        currentStyleResults = [];
        selectedStyleIndex = -1;
        styleBtn.disabled = true;
        setStyleButtonLabel(getStyleLoadingLabel());
        styleResultsMessage.textContent = `${getStyleLoadingLabel()}，请稍候…`;
        styleResultsMessage.className = 'style-results-message';
        styleResultsGrid.innerHTML = '';
        persistState();

        try {
          const response = await fetch('/api/style-analysis', {
            method: 'POST',
            body: formData,
          });
          const result = await parseJsonResponse(response);

          if (!response.ok || !result.success) {
            throw new Error(result.error || '风格分析失败，请稍后重试');
          }

          if (result.task_id) {
            await pollGenericTaskResult({
              taskId: result.task_id,
              loadingMessage: `${getStyleLoadingLabel()}，请稍候…`,
              pendingMessage: '风格分析任务排队中，请稍候…',
              runningMessage: '风格分析中，请稍候…',
              statusErrorMessage: '风格分析任务状态查询失败',
              timeoutMessage: '风格分析等待超时，请稍后重试',
              onPending: (message) => {
                styleResultsMessage.textContent = message || `${getStyleLoadingLabel()}，请稍候…`;
                styleResultsMessage.className = 'style-results-message';
              },
              onSuccess: (taskResult) => {
                if (!Array.isArray(taskResult?.styles)) {
                  throw new Error('风格分析成功，但未返回可用结果');
                }
                renderStyleCards(taskResult.styles);
                setStyleButtonLabel(refreshStyleBtnLabel);
                styleResultsMessage.textContent = getStyleSuccessMessage();
                styleResultsMessage.className = 'style-results-message success';
                persistState();
              },
            });
            return;
          }

          if (!Array.isArray(result.styles)) {
            throw new Error('风格分析成功，但未返回可用结果');
          }
          renderStyleCards(result.styles);
          setStyleButtonLabel(refreshStyleBtnLabel);
          styleResultsMessage.textContent = getStyleSuccessMessage();
          styleResultsMessage.className = 'style-results-message success';
          persistState();
        } catch (error) {
          currentStyleResults = [];
          selectedStyleIndex = -1;
          styleResultsGrid.innerHTML = '';
          styleResultsMessage.textContent = error.message || '风格分析失败，请稍后重试';
          styleResultsMessage.className = 'style-results-message error';
          setStyleButtonLabel(defaultStyleBtnLabel);
          persistState();
        } finally {
          styleBtn.disabled = false;
        }
      });
    }

    if (generateBtn) {
      generateBtn.addEventListener('click', async () => {
        if (pendingGenerationTask?.taskId) {
          await cancelPendingGenerationTask();
          return;
        }
        const productFiles = getProductFiles();
        if (!productFiles || productFiles.length === 0) {
          setResultStatus('请先上传产品图片后再生成。', 'error');
          return;
        }
        if (currentMode === 'fashion') {
          const fashionState = getFashionSelectionState();
          applyFashionGenerateButtonState(fashionState);
          if (!fashionState.hasSelectedModel) {
            setResultStatus('请先选择模特后再继续。', 'error');
            return;
          }
          if (fashionState.action === 'scene_plan') {
            await requestFashionScenePlan();
            return;
          }
          if (fashionState.action !== 'generate') {
            setResultStatus(fashionState.label || '请先完成服饰穿搭前置步骤。', 'error');
            return;
          }
          await submitFashionGenerate();
          return;
        }
        const { formData, selectedStyle } = buildBaseGenerateFormData();
        const config = getCurrentModeConfig();
        let requestConfig;
        try {
          requestConfig = resolveGenerateRequest(formData);
        } catch (error) {
          setResultStatus(error.message || config.errorFallback, 'error');
          return;
        }
        const { endpoint, isMode2 } = requestConfig;
        const compositeSelection = getCompositeGenerateSelection(isMode2);
        if (!isMode2 && compositeSelection.mode === 'none') {
          setResultStatus(getCompositeGenerateStatusMessage(compositeSelection), 'error');
          return;
        }
        if (currentMode === 'aplus') {
          if (!selectedAplusModules.size && !compositeSelection.shouldGenerateMainImage) {
            setResultStatus('请至少选择 1 张主图或 1 个 A+ 模块后再生成。', 'error');
            return;
          }
          formData.append('selected_modules', JSON.stringify(Array.from(selectedAplusModules)));
        } else if (!isMode2) {
          formData.append('output_count', String(selectedOutputCount));
        }
        if (!isMode2) {
          formData.append('main_image_count', String(compositeSelection.mainImageCount));
          formData.append('detail_image_count', String(compositeSelection.detailImageCount));
          formData.append('generate_main_image', compositeSelection.shouldGenerateMainImage ? '1' : '0');
          formData.append('generate_detail_image', compositeSelection.shouldGenerateDetailImage ? '1' : '0');
          formData.append('generate_scope', compositeSelection.mode);
        }

        const generationJobs = [];
        if (!isMode2 && compositeSelection.shouldGenerateMainImage) {
          generationJobs.push({ type: 'main', count: compositeSelection.mainImageCount });
        }
        if (isMode2 || compositeSelection.shouldGenerateDetailImage) {
          generationJobs.push({ type: 'detail', count: isMode2 ? getMode2RequestedOutputCount() : compositeSelection.detailImageCount });
        }
        const plannedOutputCount = generationJobs.reduce((total, job) => total + job.count, 0);
        const generationStartMessage = isMode2 ? config.defaultPrefix : getCompositeGenerateStatusMessage(compositeSelection);
        const quotePayload = await requestPointsQuote({
          mode: currentMode,
          outputCount: plannedOutputCount,
          selectedModulesCount: selectedAplusModules.size,
          type: `${currentMode}_generate`,
          reason: `${config.title}生成消耗`,
          metadata: {
            mode: currentMode,
            output_count: plannedOutputCount,
            main_image_count: isMode2 ? 0 : compositeSelection.mainImageCount,
            detail_image_count: isMode2 ? plannedOutputCount : compositeSelection.detailImageCount,
            generate_scope: isMode2 ? 'detail_only' : compositeSelection.mode,
            generate_main_image: isMode2 ? false : compositeSelection.shouldGenerateMainImage,
            generate_detail_image: isMode2 ? true : compositeSelection.shouldGenerateDetailImage,
            selected_style: selectedStyle?.title || '',
            selected_modules: currentMode === 'aplus' ? Array.from(selectedAplusModules) : [],
          },
        });
        const pointsCost = Number(quotePayload?.amount) || 0;

        resetResultStatus();
        resetResultState();
        if (resultMeta) {
          resultMeta.textContent = selectedStyle?.title
            ? config.selectedPrefix.replace('{style}', selectedStyle.title)
            : config.initialResultMeta;
        }
        generateBtn.disabled = true;
        updateGenerateButtonLabel(config.planLoadingLabel);
        setResultStatus(`${generationStartMessage} 正在校验积分，预计消耗 ${pointsCost} 积分`);
        startGenerationProgress();
        showResultView();
        renderLoadingResultCards(plannedOutputCount);
        persistState();

        let spendRecord = null;
        try {
          spendRecord = await requestPointsSpend({
            mode: currentMode,
            outputCount: plannedOutputCount,
            selectedModulesCount: selectedAplusModules.size,
            type: `${currentMode}_generate`,
            reason: `${config.title}生成消耗`,
            metadata: {
              mode: currentMode,
              output_count: plannedOutputCount,
              main_image_count: isMode2 ? 0 : compositeSelection.mainImageCount,
              detail_image_count: isMode2 ? plannedOutputCount : compositeSelection.detailImageCount,
              generate_scope: isMode2 ? 'detail_only' : compositeSelection.mode,
              generate_main_image: isMode2 ? false : compositeSelection.shouldGenerateMainImage,
              generate_detail_image: isMode2 ? true : compositeSelection.shouldGenerateDetailImage,
              selected_style: selectedStyle?.title || '',
              selected_modules: currentMode === 'aplus' ? Array.from(selectedAplusModules) : [],
            },
          });
          syncSharedPointsState(spendRecord?.points);

          let result;
          let asyncSuiteTaskStarted = false;
          if (isMode2) {
            result = await generateMode2Results(endpoint, formData, plannedOutputCount);
          } else {
            const taskIds = [];
            const spendRecords = [];
            for (const job of generationJobs) {
              const taskFormData = cloneFormData(formData);
              appendCompositeTaskFields(taskFormData, compositeSelection, job.type);
              taskFormData.append('async_task', '1');
              taskFormData.append('points_request_id', spendRecord?.requestId || '');
              taskFormData.append('spend_record', JSON.stringify(spendRecord || {}));
              const response = await fetch(endpoint, {
                method: 'POST',
                body: taskFormData,
              });
              const taskPayload = await parseJsonResponse(response);
              if (!response.ok || !taskPayload?.success || !taskPayload.task_id) {
                const detailMessage = typeof taskPayload?.details === 'string' ? taskPayload.details.trim() : '';
                const baseMessage = taskPayload?.error || config.errorFallback;
                throw new Error(detailMessage ? `${baseMessage}｜${detailMessage}` : baseMessage);
              }
              taskIds.push(taskPayload.task_id);
              spendRecords.push(spendRecord);
            }
            savePendingGenerationTasks(taskIds, spendRecords, currentMode);
            asyncSuiteTaskStarted = true;
          }

          if (asyncSuiteTaskStarted) {
            return;
          }

          currentResult = result;
          currentResultItems = normalizeResultItems(result);
          selectedResultKeys = new Set();
          updateTaskSummary(result);
          renderResultCards(currentResultItems);
          stopGenerationProgress();
          setResultStatus(`${result.plan?.summary || config.successFallback.replace('{count}', String(getCurrentOutputMetric(result)))}，已消耗 ${pointsCost} 积分`, 'success');
          saveStateToLocalStorage();
        } catch (error) {
          let refundFailed = false;
          const didSpendPoints = Boolean(spendRecord && !spendRecord.skipped && Number(spendRecord.amount) > 0);
          if (didSpendPoints && !currentResultItems.length && !getPendingGenerationTaskIds().length) {
            try {
              const refundedPoints = await requestPointsRefund(spendRecord, error.message || config.errorFallback);
              syncSharedPointsState(refundedPoints);
            } catch (refundError) {
              refundFailed = true;
            }
          }
          resetResultState();
          if (resultMeta) {
            if (!didSpendPoints) {
              resultMeta.textContent = '生成前积分校验未通过，本次未发生实际扣分，可调整参数后重试。';
            } else {
              resultMeta.textContent = refundFailed
                ? '生成失败，且自动返还积分失败，请联系客服核查。'
                : '生成失败后已自动返还本次扣减积分，可修改卖点、平台或素材后重试。';
            }
          }
          setResultStatus(!didSpendPoints
            ? (error.message || config.errorFallback)
            : (refundFailed ? `${error.message || config.errorFallback}；本次积分自动返还失败，请联系客服核查。` : `${error.message || config.errorFallback}；本次扣减积分已自动返还。`), 'error');
          persistState();
        } finally {
          if (!getPendingGenerationTaskIds().length) {
            generateBtn.disabled = false;
            updateGenerateButtonLabel(config.generateBtnLabel);
          }
        }
      });
    }

    bindUploadInput({
      button: uploadBtn,
      input: fileInput,
      thumbsContainer: thumbs,
      emptyMarkup: isFashionPage ? emptyProductThumbsMarkup : emptyThumbsMarkup,
      labelPrefix: isFashionPage ? '商品图' : '素材',
      overLimitMessage: isFashionPage ? '最多仅保留前 5 张商品图，其余文件已忽略。' : '最多仅保留前 3 张图片，其余文件已忽略。',
      filesArray: currentFiles,
      isFashionUpload: isFashionPage
    });
    if (isFashionPage) {
      bindUploadInput({
        button: referenceUploadBtn,
        input: referenceFileInput,
        thumbsContainer: referenceThumbs,
        emptyMarkup: emptyReferenceThumbsMarkup,
        labelPrefix: '参考图',
        overLimitMessage: '最多仅保留前 3 张参考图，其余文件已忽略。',
        filesArray: currentReferenceFiles
      });
    }
  });

