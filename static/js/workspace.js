document.addEventListener('DOMContentLoaded', () => {
  const generateBtn = document.getElementById('generateBtn');
    const introView = document.getElementById('introView');
    const resultView = document.getElementById('resultView');
    const resultGrid = document.getElementById('resultGrid');
    const resultMeta = document.getElementById('resultMeta');
    const resultStatusMessage = document.getElementById('resultStatusMessage');
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
    const moreBtn = document.getElementById('moreBtn');
    const moreMenu = document.getElementById('moreMenu');
    const moreOptions = Array.from(document.querySelectorAll('.more-option'));
    const outputCountValue = document.getElementById('outputCountValue');
    const gridLogicValue = document.getElementById('gridLogicValue');
    const navItems = Array.from(document.querySelectorAll('[data-mode]'));
    const aplusModulesSection = document.getElementById('aplusModulesSection');
    const aplusModulesGrid = document.getElementById('aplusModulesGrid');
    const aplusModulesHint = document.getElementById('aplusModulesHint');
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

    const buildEmptyThumbsMarkup = (label = '待上传素材') => `
      <div class="thumb">${label} 1</div>
      <div class="thumb">${label} 2</div>
      <div class="thumb">${label} 3</div>
    `;
    const emptyThumbsMarkup = buildEmptyThumbsMarkup();
    const emptyReferenceThumbsMarkup = buildEmptyThumbsMarkup('待上传参考图');
    const emptyProductThumbsMarkup = buildEmptyThumbsMarkup('待上传商品图');
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
        initialResultMeta: '系统将根据服饰商品图、平台策略、卖点与风格参考生成服饰穿戴结果。',
        initialTaskSummary: '统一输出为适合服装展示、筛选下载与继续排版的结果结构。',
        resultFallback: '已生成服饰穿戴结果',
        itemFallback: '已生成该服饰展示结果。',
        successFallback: '已完成 {count} 张服饰结果生成',
        errorFallback: '服饰穿戴生成失败，请稍后重试',
        selectedPrefix: '正在分析服饰穿搭方案，并吸收「{style}」风格参考，请稍候…',
        defaultPrefix: '正在分析服饰穿搭方案，请稍候…',
        imageProgress: '正在生成服饰穿戴图，请稍候…',
        outputStatLabel: '输出张数',
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
    let currentMode = PAGE_MODE;
    let selectedOutputCount = 6;
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
    const getImageSizeRatio = () => imageSizeSelect?.value || '1:1';

    const getStyleLoadingLabel = () => platformLoadingLabels[getPlatformLabel()] || `正在分析 ${getPlatformLabel()} 趋势`;

    const getStyleSuccessMessage = () => platformSuccessLabels[getPlatformLabel()] || `已生成 4 组${getPlatformLabel()}风格方案`;

    const formatOutputCount = (count) => String(count).padStart(2, '0');

    const getGridLogicLabel = (count) => {
      const columns = count <= 8 ? 2 : 3;
      return `${columns}×${Math.ceil(count / columns)}`;
    };

    const getCurrentModeConfig = () => modeConfig[currentMode] || modeConfig.suite;
    const modePlanLabelMap = { suite: '套图', aplus: 'A+ 模块', fashion: '服饰穿搭图' };
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
          };
        }

        const rawState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const selectedSource = rawState.fashionSelectedModelSource === 'custom'
          ? 'custom'
          : rawState.fashionSelectedModelSource === 'ai'
            ? 'ai'
            : '';
        const selectedId = typeof rawState.fashionSelectedModelId === 'string' ? rawState.fashionSelectedModelId : '';
        const generationDone = rawState.fashionModelGenerationState === 'done'
          && rawState.fashionGeneratedModel
          && rawState.fashionGeneratedModel.id === selectedId;
        const customSelected = selectedSource === 'custom'
          && Array.isArray(rawState.fashionCustomModels)
          && rawState.fashionCustomModels.some((item) => item && item.id === selectedId);
        const hasSelectedModel = selectedSource === 'ai' ? Boolean(generationDone) : Boolean(customSelected);
        const sceneStep = rawState.fashionFlowStep === 'scene';
        const sceneGenerationState = rawState.fashionSceneGenerationState;
        const hasSceneGroups = Array.isArray(rawState.fashionSceneGroups) && rawState.fashionSceneGroups.length > 0;
        const selectedSceneGroupIds = Array.isArray(rawState.fashionSelectedSceneGroupIds)
          ? rawState.fashionSelectedSceneGroupIds.filter((item, index, list) => item && list.indexOf(item) === index)
          : [];
        const selectedPoseIds = Array.isArray(rawState.fashionSelectedPoseIds)
          ? rawState.fashionSelectedPoseIds.filter((item, index, list) => item && list.indexOf(item) === index)
          : [];
        const hasPose = selectedSceneGroupIds.length > 0 && selectedPoseIds.length >= selectedSceneGroupIds.length;
        const hasShotSizes = Boolean(rawState.fashionSelectedShotSizes);
        const hasViewAngles = Boolean(rawState.fashionSelectedViewAngles);
        const selectedSceneCount = Math.min(selectedSceneGroupIds.length, selectedPoseIds.length);

        if (!hasSelectedModel) {
          return {
            hasSelectedModel: false,
            disabled: true,
            label: '请选择模特',
            step: sceneStep ? 'scene' : 'model',
          };
        }
        if (!sceneStep) {
          return {
            hasSelectedModel: true,
            disabled: false,
            label: '生成推荐场景',
            step: 'model',
          };
        }
        if (sceneGenerationState === 'loading') {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '生成中...',
            step: 'scene',
          };
        }
        if (sceneGenerationState === 'error') {
          return {
            hasSelectedModel: true,
            disabled: false,
            label: '重新生成推荐场景',
            step: 'scene',
          };
        }
        if (sceneGenerationState !== 'done' || !hasSceneGroups) {
          return {
            hasSelectedModel: true,
            disabled: false,
            label: '生成推荐场景',
            step: 'scene',
          };
        }
        if (!hasPose) {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '请选择姿态',
            step: 'scene',
          };
        }
        if (!hasShotSizes || !hasViewAngles) {
          return {
            hasSelectedModel: true,
            disabled: true,
            label: '请选择景别和视角',
            step: 'scene',
          };
        }
        return {
          hasSelectedModel: true,
          disabled: false,
          label: `生成服饰穿戴图（${selectedSceneCount}个场景）`,
          step: 'scene',
        };
      } catch (error) {
        console.error('Failed to read fashion selection state:', error);
        return {
          hasSelectedModel: false,
          disabled: true,
          label: '请选择模特',
          step: 'model',
        };
      }
    };

    const applyFashionGenerateButtonState = (state = getFashionSelectionState()) => {
      fashionCtaState = {
        hasSelectedModel: Boolean(state.hasSelectedModel),
        disabled: Boolean(state.disabled),
        label: state.label || '请选择模特',
        step: state.step === 'scene' ? 'scene' : 'model',
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
      [sellingInput, platformSelect, countrySelect, textTypeSelect, imageSizeSelect].forEach((element) => {
        if (!element?.id || !(element.id in values)) {
          return;
        }
        setElementValue(element, values[element.id]);
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
      if ((result?.mode || currentMode) === 'aplus') {
        return result?.plan?.module_count || result?.images?.length || Math.max(selectedAplusModules.size, 1);
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
      outputCountValue.textContent = formatOutputCount(selectedOutputCount);
      gridLogicValue.textContent = getGridLogicLabel(selectedOutputCount);
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
      currentMode = ['suite', 'aplus', 'fashion'].includes(mode) ? mode : PAGE_MODE;
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
        moreActions.hidden = currentMode === 'aplus';
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

    const syncMoreButtonLabel = () => {
      if (!moreBtn) {
        return;
      }
      moreBtn.textContent = `…(${selectedOutputCount}张)`;
      moreBtn.setAttribute('aria-label', `更多操作，当前已选输出 ${selectedOutputCount} 张`);
    };

    const openMoreMenu = () => {
      if (moreMenu && moreBtn) {
        moreMenu.hidden = false;
        moreBtn.setAttribute('aria-expanded', 'true');
      }
      persistState();
    };

    const setSelectedOutputCount = (count) => {
      selectedOutputCount = count;
      if (moreOptions && moreOptions.length > 0) {
        moreOptions.forEach((option) => {
          option.classList.toggle('is-selected', Number(option.dataset.count) === count);
        });
      }
      syncMoreButtonLabel();
      syncOutputCountSummary();
      persistState();
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

    const setFashionFlowStepState = (step) => {
      const api = getFashionWorkspaceApi();
      if (api && typeof api.setFlowStep === 'function') {
        api.setFlowStep(step);
        return api.getState();
      }
      return syncFashionState({ fashionFlowStep: step === 'scene' || step === 'result' ? step : 'model' });
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
      appendFilesToFormData(formData, 'images', getProductFiles(), isFashionPage ? 5 : 3);
      if (currentMode === 'fashion') {
        appendFilesToFormData(formData, 'reference_images', getReferenceFiles());
      }
      return { formData, selectedStyle };
    };

    const requestFashionScenePlan = async () => {
      const currentFashionState = getFashionSelectionState();
      applyFashionGenerateButtonState(currentFashionState);
      if (!currentFashionState.hasSelectedModel) {
        return;
      }

      setFashionFlowStepState('scene');
      syncFashionState({
        fashionSceneGenerationState: 'loading',
        fashionSceneGroups: [],
        fashionSelectedSceneGroupIds: [],
        fashionSelectedPoseIds: [],
        fashionSelectedShotSizes: '',
        fashionSelectedViewAngles: '',
        fashionScenePrompt: '',
        fashionSceneError: '',
        fashionScenePlanRaw: null,
      });
      showIntroView();
      setResultStatus('正在生成推荐场景...', '');

      try {
        const { formData } = buildBaseGenerateFormData();
        formData.append('fashion_action', 'scene_plan');
        const response = await fetch('/api/generate-suite', {
          method: 'POST',
          body: formData,
        });
        const result = await response.json();
        const scenePlan = result?.plan || null;
        const sceneGroups = Array.isArray(scenePlan?.scene_groups) ? scenePlan.scene_groups : [];

        if (!response.ok || !result.success || !scenePlan || !sceneGroups.length) {
          throw new Error(result.error || '推荐场景生成失败，请稍后重试');
        }

        syncFashionState({
          fashionFlowStep: 'scene',
          fashionSceneGenerationState: 'done',
          fashionSceneGroups: sceneGroups,
          fashionSceneError: '',
          fashionScenePlanRaw: scenePlan,
        });
        setResultStatus(scenePlan.summary || '推荐场景已生成，请继续选择姿态、景别与视角。', 'success');
      } catch (error) {
        syncFashionState({
          fashionFlowStep: 'scene',
          fashionSceneGenerationState: 'error',
          fashionSceneGroups: [],
          fashionSelectedSceneGroupIds: [],
          fashionSelectedPoseIds: [],
          fashionSelectedShotSizes: '',
          fashionSelectedViewAngles: '',
          fashionScenePrompt: '',
          fashionScenePlanRaw: null,
          fashionSceneError: error.message || '推荐场景生成失败，请稍后重试',
        });
        setResultStatus(error.message || '推荐场景生成失败，请稍后重试', 'error');
      }
    };

    const submitFashionGenerate = async () => {
      const fashionApi = getFashionWorkspaceApi();
      const fashionState = fashionApi?.getState ? fashionApi.getState() : null;
      const fashionCta = fashionState?.cta || getFashionSelectionState();
      applyFashionGenerateButtonState(fashionCta);
      if (fashionCta.disabled) {
        return;
      }

      const config = getCurrentModeConfig();
      const { formData, selectedStyle } = buildBaseGenerateFormData();
      formData.append('fashion_action', 'generate');
      formData.append('fashion_scene_plan', JSON.stringify(fashionState?.fashionScenePlanRaw || {}));
      formData.append('fashion_scene_group_ids', JSON.stringify(fashionState?.fashionSelectedSceneGroupIds || []));
      formData.append('fashion_pose_ids', JSON.stringify(fashionState?.fashionSelectedPoseIds || []));
      formData.append('fashion_shot_size', fashionState?.fashionSelectedShotSizes || '');
      formData.append('fashion_view_angle', fashionState?.fashionSelectedViewAngles || '');

      resetResultStatus();
      resetResultState();
      if (resultMeta) {
        resultMeta.textContent = selectedStyle?.title
          ? config.selectedPrefix.replace('{style}', selectedStyle.title)
          : config.initialResultMeta;
      }
      generateBtn.disabled = true;
      updateGenerateButtonLabel(config.planLoadingLabel);
      setResultStatus(selectedStyle?.title ? config.selectedPrefix.replace('{style}', selectedStyle.title) : config.defaultPrefix);
      showResultView();
      persistState();

      try {
        const responsePromise = fetch('/api/generate-suite', {
          method: 'POST',
          body: formData,
        });

        window.setTimeout(() => {
          if (generateBtn.disabled) {
            updateGenerateButtonLabel(config.imageLoadingLabel);
            setResultStatus(config.imageProgress);
          }
        }, 1200);

        const response = await responsePromise;
        const result = await response.json();

        if (!response.ok || !result.success || !Array.isArray(result.images)) {
          throw new Error(result.error || config.errorFallback);
        }

        currentResult = result;
        currentResultItems = normalizeResultItems(result);
        selectedResultKeys = new Set();
        updateTaskSummary(result);
        renderResultCards(currentResultItems);
        setResultStatus(result.plan?.summary || config.successFallback.replace('{count}', String(getCurrentOutputMetric(result))), 'success');
        syncFashionState({ fashionFlowStep: 'result' });
        saveStateToLocalStorage();
      } catch (error) {
        resetResultState();
        if (resultMeta) {
          resultMeta.textContent = '生成失败后可修改卖点、平台或素材后重试。';
        }
        setResultStatus(error.message || config.errorFallback, 'error');
        showIntroView();
        persistState();
      } finally {
        applyFashionGenerateButtonState();
      }
    };

    let currentFiles = [];
    let currentReferenceFiles = [];
    let currentProductJson = null;

    const getProductFiles = () => currentFiles.slice(0, isFashionPage ? 5 : 3);
    const getReferenceFiles = () => (isFashionPage ? currentReferenceFiles.slice(0, 3) : []);

    const renderThumbList = (container, files, emptyMarkup, labelPrefix, uploadButton, uploadHint, isFashionUpload = false) => {
      if (!container) {
        return;
      }
      container.innerHTML = '';
      const maxFiles = isFashionUpload ? 5 : 3;
      if (!files.length) {
        // 初始状态显示上传按钮
        container.style.display = 'none';
        if (uploadButton) uploadButton.style.display = '';
        if (uploadHint) uploadHint.style.display = '';
        return;
      }
      container.style.display = 'grid';
      if (uploadButton) uploadButton.style.display = 'none';
      if (uploadHint) uploadHint.style.display = 'none';
      files.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const item = document.createElement('div');
          item.className = 'thumb';
          item.style.backgroundImage = `url(${e.target.result})`;
          item.style.backgroundSize = 'cover';
          item.style.backgroundPosition = 'center';
          item.style.color = '#fff';
          item.innerHTML = `
            <button class="thumb-delete-btn" type="button" data-index="${index}" aria-label="删除">×</button>
          `;
          item.dataset.index = index;
          container.appendChild(item);
        };
        reader.readAsDataURL(file);
      });
      
      // 如果是fashion页面且未达到最大数量，显示+号按钮
      if (isFashionUpload && files.length < maxFiles) {
        const addButton = document.createElement('button');
        addButton.className = 'upload-btn';
        addButton.type = 'button';
        addButton.textContent = '+';
        container.appendChild(addButton);
      }
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
      input.addEventListener('change', (event) => {
        const rawFiles = Array.from(event.target.files || []);
        const invalidFile = rawFiles.find((file) => file && !file.type.startsWith('image/'));
        if (invalidFile) {
          event.target.value = '';
          setResultStatus(`仅支持上传图片文件：${invalidFile.name || '未命名文件'}`, 'error');
          return;
        }

        const maxFiles = isFashionUpload ? 5 : 3;
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
              currentProductJson = null;
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
      const isAplus = (result.mode || currentMode) === 'aplus';
      const parts = [
        result.task_name ? `任务：${result.task_name}` : '',
        result.generated_at ? `生成时间：${result.generated_at}` : '',
        isAplus ? (result.plan?.module_count ? `模块数量：${result.plan.module_count}` : '') : (result.plan?.output_count ? `输出张数：${result.plan.output_count}` : ''),
        styleMeta,
      ].filter(Boolean);
      return parts.join(' · ') || getCurrentModeConfig().resultFallback;
    };

    const normalizeImagePath = (value = '') => String(value || '').trim().replace(/\\/g, '/').replace(/^\/+/, '').replace(/^generated-suites\//, '');

    const normalizeImageUrl = (item = {}) => {
      const rawUrl = typeof item.image_url === 'string' ? item.image_url.trim() : '';
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

      return [
        ...referenceItems.map((item, index) => ({
          ...item,
          image_url: normalizeImageUrl(item),
          sort: item.sort || index + 1,
          kind: item.kind || 'reference',
        })),
        ...generatedItems
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

    const downloadItemsAsZip = async (items = []) => {
      const downloadableItems = getDownloadableItems(items);
      if (!downloadableItems.length) {
        throw new Error('未找到可下载的图片文件');
      }
      const zipSourceItems = downloadableItems.filter((item) => item.image_path);
      if (!zipSourceItems.length) {
        throw new Error('当前图片缺少下载路径，请重新生成后再试');
      }
      const response = await fetch('/api/download-zip', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_paths: zipSourceItems.map((item) => item.image_path),
        }),
      });
      if (!response.ok) {
        let message = '打包下载失败，请稍后重试';
        try {
          const payload = await response.json();
          if (payload?.error) {
            message = payload.error;
          }
        } catch (error) {
          console.error('Failed to parse zip download error:', error);
        }
        throw new Error(message);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const disposition = response.headers.get('Content-Disposition') || '';
      const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const basicMatch = disposition.match(/filename="?([^";]+)"?/i);
      const downloadName = utf8Match
        ? decodeURIComponent(utf8Match[1])
        : (basicMatch ? basicMatch[1] : 'ai-images.zip');
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = downloadName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
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
      const selectedStyleMeta = buildSelectedStyleMeta(result.selected_style);
      taskSummaryLine.textContent = selectedStyleMeta
        ? `${result.plan?.summary || '已生成可管理的任务结果。'} · ${selectedStyleMeta}`
        : (result.plan?.summary || '已生成可管理的任务结果。');
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
              ${imageUrl ? `<img src="${imageUrl}" alt="${escapeHtml(item.title || item.type || '生成结果')}" loading="lazy" data-role="preview-image" data-index="${index}">` : '<div class="image-shape"></div>'}
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
      if (!resultStatusMessage) {
        return;
      }
      resultStatusMessage.textContent = '';
      resultStatusMessage.className = 'result-status-message';
    };

    const resetResultState = () => {
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
      resultStatusMessage.textContent = message || '';
      resultStatusMessage.className = `result-status-message${type ? ` ${type}` : ''}`;
      persistState();
    };

    const saveStateToLocalStorage = () => {
      try {
        const existingState = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        const state = {
          ...existingState,
          currentMode: PAGE_MODE,
          selectedOutputCount,
          selectedAplusModules: Array.from(selectedAplusModules),
          currentStyleResults,
          selectedStyleIndex,
          currentResult,
          currentResultItems,
          currentProductJson,
          selectedResultKeys: Array.from(selectedResultKeys),
          previewIndex,
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

        if (Number.isInteger(state.previewIndex) && state.previewIndex >= 0 && state.previewIndex < currentResultItems.length) {
          openPreview(state.previewIndex);
        } else {
          closePreview();
        }

        restoreScrollState(state.scroll || {});
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
          const result = await response.json();

          if (!response.ok || !result.success) {
            throw new Error(result.error || '生成失败，请稍后重试');
          }

          sellingInput.value = result.text || '';
          currentProductJson = result.product_json && typeof result.product_json === 'object'
            ? result.product_json
            : null;
          sellingMessage.textContent = 'AI 文案已生成';
          sellingMessage.className = 'field-message success';
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
          const result = await response.json();

          if (!response.ok || !result.success || !Array.isArray(result.styles)) {
            throw new Error(result.error || '风格分析失败，请稍后重试');
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
        if (currentMode === 'fashion') {
          const fashionState = getFashionSelectionState();
          applyFashionGenerateButtonState(fashionState);
          if (!fashionState.hasSelectedModel) {
            return;
          }
          if (fashionState.step !== 'scene' || fashionState.label === '生成推荐场景' || fashionState.label === '重新生成推荐场景') {
            await requestFashionScenePlan();
            return;
          }
          await submitFashionGenerate();
          return;
        }
        const { formData, selectedStyle } = buildBaseGenerateFormData();
        const config = getCurrentModeConfig();
        const endpoint = currentMode === 'aplus' ? '/api/generate-aplus' : '/api/generate-suite';
        if (currentMode === 'aplus') {
          if (!selectedAplusModules.size) {
            setResultStatus('请至少选择 1 个 A+ 模块后再生成。', 'error');
            return;
          }
          formData.append('selected_modules', JSON.stringify(Array.from(selectedAplusModules)));
        } else {
          formData.append('output_count', String(selectedOutputCount));
        }

        resetResultStatus();
        resetResultState();
        if (resultMeta) {
          resultMeta.textContent = selectedStyle?.title
            ? config.selectedPrefix.replace('{style}', selectedStyle.title)
            : config.initialResultMeta;
        }
        generateBtn.disabled = true;
        updateGenerateButtonLabel(config.planLoadingLabel);
        setResultStatus(selectedStyle?.title ? config.selectedPrefix.replace('{style}', selectedStyle.title) : config.defaultPrefix);
        showResultView();
        persistState();

        try {
          const responsePromise = fetch(endpoint, {
            method: 'POST',
            body: formData,
          });

          window.setTimeout(() => {
            if (generateBtn.disabled) {
              updateGenerateButtonLabel(config.imageLoadingLabel);
              setResultStatus(config.imageProgress);
            }
          }, 1200);

          const response = await responsePromise;
          const result = await response.json();

          if (!response.ok || !result.success || !Array.isArray(result.images)) {
            throw new Error(result.error || config.errorFallback);
          }

          currentResult = result;
          currentResultItems = normalizeResultItems(result);
          selectedResultKeys = new Set();
          updateTaskSummary(result);
          renderResultCards(currentResultItems);
          setResultStatus(result.plan?.summary || config.successFallback.replace('{count}', String(getCurrentOutputMetric(result))), 'success');
          saveStateToLocalStorage();
        } catch (error) {
          resetResultState();
          if (resultMeta) {
            resultMeta.textContent = '生成失败后可修改卖点、平台或素材后重试。';
          }
          setResultStatus(error.message || config.errorFallback, 'error');
          persistState();
        } finally {
          generateBtn.disabled = false;
          updateGenerateButtonLabel(config.generateBtnLabel);
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

