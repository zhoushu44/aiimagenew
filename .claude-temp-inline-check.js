
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
    const outputSystemLabel = document.getElementById('outputSystemLabel');
    const outputSystemMeta = document.getElementById('outputSystemMeta');
    const gridLogicLabel = document.getElementById('gridLogicLabel');
    const gridLogicMeta = document.getElementById('gridLogicMeta');

    const emptyThumbsMarkup = `
      <div class="thumb">待上传素材 1</div>
      <div class="thumb">待上传素材 2</div>
      <div class="thumb">待上传素材 3</div>
    `;
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
        title: 'AI商品套图',
        description: '上传商品图后，系统将按平台规范、场景逻辑与卖点层级生成整套电商图像方案。新的版式以更强秩序、对比和编辑式结构呈现，适合跨境与平台首页展示。',
        note: 'Flat / Hard Edge / Poster Rhythm / Swiss Red Accent',
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
        title: 'AI A+详情页',
        description: '上传商品图后，系统会沿用平台、国家、文字类型、尺寸比例、卖点与风格分析能力，按模块生成更适合 A+ 详情页的信息分层与视觉结构。',
        note: 'Hero / Modular Storytelling / Feature Blocks / Detail Hierarchy',
        outputSystemLabel: 'module system',
        outputSystemMeta: '按模块组织品牌头图、卖点分栏、细节放大、场景与服务信息。',
        gridLogicLabel: 'structure logic',
        gridLogicMeta: '生成结果按 A+ 模块顺序输出，便于逐张查看、下载与继续排版。',
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
    };
    const defaultStyleBtnLabel = '爆款风格分析';
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
    let currentMode = 'suite';
    let selectedOutputCount = 8;
    let selectedAplusModules = new Set(['hero_value', 'usage_scene', 'core_selling', 'detail_zoom']);
    let currentResult = null;
    let currentResultItems = [];
    let selectedResultKeys = new Set();
    let previewIndex = -1;
    let currentStyleResults = [];
    let selectedStyleIndex = -1;

    const escapeHtml = (value = '') => String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');

    const setStyleButtonLabel = (label) => {
      styleBtn.innerHTML = `<span>${label}</span><span class="btn-icon">↻</span>`;
    };

    const getPlatformLabel = () => platformSelect.value || '亚马逊';
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

    const getCurrentOutputMetric = (result = currentResult) => {
      if ((result?.mode || currentMode) === 'aplus') {
        return result?.plan?.module_count || result?.images?.length || selectedAplusModules.size;
      }
      return result?.plan?.output_count || result?.images?.length || selectedOutputCount;
    };

    const syncOutputCountSummary = () => {
      if (currentMode === 'aplus') {
        outputCountValue.textContent = formatOutputCount(selectedAplusModules.size);
        gridLogicValue.textContent = `${selectedAplusModules.size} 模块`;
        return;
      }
      outputCountValue.textContent = formatOutputCount(selectedOutputCount);
      gridLogicValue.textContent = getGridLogicLabel(selectedOutputCount);
    };

    const updateGenerateButtonLabel = (label) => {
      generateBtn.textContent = label || getCurrentModeConfig().generateBtnLabel;
    };

    const renderAplusModuleCards = () => {
      const cards = Array.from(aplusModulesGrid.querySelectorAll('[data-module]'));
      cards.forEach((card) => {
        const key = card.dataset.module;
        const isSelected = selectedAplusModules.has(key);
        card.classList.toggle('is-selected', isSelected);
        card.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
      });
      aplusModulesHint.textContent = `已选择 ${selectedAplusModules.size} 个模块，至少选择 1 个模块`;
    };

    const setMode = (mode) => {
      currentMode = mode === 'aplus' ? 'aplus' : 'suite';
      const config = getCurrentModeConfig();
      navItems.forEach((item) => {
        const isActive = item.dataset.mode === currentMode;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
      aplusModulesSection.hidden = currentMode !== 'aplus';
      moreActions.hidden = currentMode !== 'suite';
      heroTitle.textContent = config.title;
      heroDescription.textContent = config.description;
      heroNote.textContent = config.note;
      outputSystemLabel.textContent = config.outputSystemLabel;
      outputSystemMeta.textContent = config.outputSystemMeta;
      gridLogicLabel.textContent = config.gridLogicLabel;
      gridLogicMeta.textContent = config.gridLogicMeta;
      updateGenerateButtonLabel(config.generateBtnLabel);
      const outputStatLabel = document.querySelector('#taskStats .task-stat .stat-label');
      if (outputStatLabel) {
        outputStatLabel.textContent = config.outputStatLabel;
      }
      renderAplusModuleCards();
      syncOutputCountSummary();
      resetResultState();
    };

    const closeMoreMenu = () => {
      moreMenu.hidden = true;
      moreBtn.setAttribute('aria-expanded', 'false');
    };

    const openMoreMenu = () => {
      moreMenu.hidden = false;
      moreBtn.setAttribute('aria-expanded', 'true');
    };

    const setSelectedOutputCount = (count) => {
      selectedOutputCount = count;
      moreOptions.forEach((option) => {
        option.classList.toggle('is-selected', Number(option.dataset.count) === count);
      });
      syncOutputCountSummary();
    };

    const toggleAplusModule = (key) => {
      if (!APLUS_MODULE_META[key]) {
        return;
      }
      if (selectedAplusModules.has(key)) {
        if (selectedAplusModules.size === 1) {
          aplusModulesHint.textContent = '至少选择 1 个模块';
          return;
        }
        selectedAplusModules.delete(key);
      } else {
        selectedAplusModules.add(key);
      }
      renderAplusModuleCards();
      syncOutputCountSummary();
    };

    const getSelectedStyle = () => {
      if (selectedStyleIndex < 0 || selectedStyleIndex >= currentStyleResults.length) {
        return null;
      }
      return currentStyleResults[selectedStyleIndex] || null;
    };

    const updateStyleSelectionMessage = () => {
      const selectedStyle = getSelectedStyle();
      if (!currentStyleResults.length) {
        styleResultsMessage.textContent = '';
        styleResultsMessage.className = 'style-results-message';
        return;
      }
      if (selectedStyle) {
        styleResultsMessage.textContent = `${getStyleSuccessMessage()}，已选风格「${selectedStyle.title || ''}」，后续生成将参考该风格。`;
        styleResultsMessage.className = 'style-results-message success';
        return;
      }
      styleResultsMessage.textContent = `${getStyleSuccessMessage()}，点击卡片可设为后续生成参考。`;
      styleResultsMessage.className = 'style-results-message';
    };

    const renderStyleCards = (styles = currentStyleResults) => {
      currentStyleResults = Array.isArray(styles) ? styles : [];
      if (!currentStyleResults.length) {
        styleResultsGrid.innerHTML = '';
        updateStyleSelectionMessage();
        return;
      }
      styleResultsGrid.innerHTML = currentStyleResults.map((style, index) => {
        const isSelected = index === selectedStyleIndex;
        const stateText = isSelected ? '已选风格' : '点击设为生成参考';
        const selectedClass = isSelected ? ' is-selected' : '';
        const hintText = isSelected
          ? '后续生成将优先吸收该风格的视觉气质、色彩与信息层级。'
          : `选择后会把该风格作为${currentMode === 'aplus' ? 'A+ 模块' : '套图'}规划参考。`;
        return `
          <button class="style-card${selectedClass}" type="button" data-role="select-style" data-index="${index}" aria-pressed="${isSelected ? 'true' : 'false'}">
            <div class="style-card-topline">
              <div class="style-card-title">${escapeHtml(style.title || '')}</div>
              <span class="style-card-state">${stateText}</span>
            </div>
            <div class="style-card-colors">
              ${(Array.isArray(style.colors) ? style.colors : []).map((color) => `<span class="style-color-dot" style="background:${color}" title="${color}"></span>`).join('')}
            </div>
            <p class="style-card-reasoning">${escapeHtml(style.reasoning || '')}</p>
            <div class="style-card-hint">${hintText}</div>
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
    };

    const buildSelectedStyleMeta = (style) => {
      if (!style?.title) {
        return '';
      }
      return `参考风格：${style.title}`;
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

    const getItemKey = (item, index = 0) => item.image_path || item.image_url || `${item.kind || 'item'}-${item.sort || index}`;

    const normalizeResultItems = (result) => {
      const referenceItems = Array.isArray(result.reference_images) ? result.reference_images : [];
      const generatedItems = Array.isArray(result.images) ? result.images : [];

      return [
        ...referenceItems.map((item, index) => ({
          ...item,
          sort: item.sort || index + 1,
          kind: item.kind || 'reference',
        })),
        ...generatedItems
          .slice()
          .sort((a, b) => (a.sort || 0) - (b.sort || 0))
          .map((item, index) => ({
            ...item,
            sort: item.sort || index + 1,
            kind: item.kind || 'generated',
          })),
      ];
    };

    const getSelectedItems = () => currentResultItems.filter((item, index) => selectedResultKeys.has(getItemKey(item, index)));

    const buildCardSubText = (item) => {
      if (item.kind === 'reference') {
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
      taskOutputCount.textContent = String(getCurrentOutputMetric()).padStart(2, '0');
      taskSelectedCount.textContent = String(selected).padStart(2, '0');
      taskSelectAll.checked = allSelected;
      taskSelectAll.disabled = !hasItems;
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
    };

    const setAllSelections = (checked) => {
      selectedResultKeys = checked
        ? new Set(currentResultItems.map((item, index) => getItemKey(item, index)))
        : new Set();
      renderResultCards(currentResultItems);
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
    };

    const closePreview = () => {
      previewModal.hidden = true;
      previewIndex = -1;
      previewImage.src = '';
      previewImage.alt = '预览图片';
      previewTitle.textContent = '图片预览';
      previewType.textContent = '预览';
      document.body.style.overflow = '';
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
        return;
      }

      const platform = getPlatformLabel();
      const sellingText = sellingInput.value.trim();
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
        const kindLabel = item.kind === 'reference' ? '原图' : '生成图';
        return `
          <article class="result-card${selectedClass}${referenceClass}" data-item-key="${itemKey}">
            <div class="result-image${hasImageClass}">
              <label class="card-check" aria-label="选择图片">
                <input type="checkbox" data-role="select-item" data-key="${itemKey}" ${isSelected ? 'checked' : ''}>
              </label>
              <div class="overlay-chip">
                <span class="result-no">${String(item.sort || index + 1).padStart(2, '0')}</span>
                <span class="overlay-type">${escapeHtml(item.type_tag || item.type || 'Board')}</span>
              </div>
              ${imageUrl ? `<img src="${imageUrl}" alt="${escapeHtml(item.title || item.type || '生成结果')}" loading="lazy" data-role="preview-image" data-index="${index}">` : '<div class="image-shape"></div>'}
            </div>
            <div class="result-body">
              <div class="result-topline">
                <div class="card-title">${escapeHtml(item.title || '')}</div>
                <span class="card-kind">${escapeHtml(kindLabel)}</span>
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
    };

    const resetResultStatus = () => {
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
      taskOutputCount.textContent = '00';
      taskSelectedCount.textContent = '00';
      taskSelectAll.checked = false;
      taskSelectAll.disabled = true;
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
      resultStatusMessage.textContent = message || '';
      resultStatusMessage.className = `result-status-message${type ? ` ${type}` : ''}`;
    };

    navItems.forEach((item) => {
      item.addEventListener('click', () => {
        setMode(item.dataset.mode);
      });
    });

    aplusModulesGrid.addEventListener('click', (event) => {
      const card = event.target.closest('[data-module]');
      if (!card) {
        return;
      }
      toggleAplusModule(card.dataset.module);
    });

    styleResultsGrid.addEventListener('click', (event) => {
      const styleCard = event.target.closest('[data-role="select-style"]');
      if (!styleCard) {
        return;
      }
      selectStyleCard(Number(styleCard.dataset.index));
    });

    taskSelectAll.addEventListener('change', (event) => {
      setAllSelections(event.target.checked);
    });

    selectAllBtn.addEventListener('click', () => {
      const shouldSelectAll = selectedResultKeys.size !== currentResultItems.length;
      setAllSelections(shouldSelectAll);
    });

    downloadSelectedBtn.addEventListener('click', () => {
      const selectedItems = getSelectedItems();
      if (!selectedItems.length) {
        setResultStatus('请先勾选至少 1 张图片后再批量下载。', 'error');
        return;
      }
      selectedItems.forEach((item) => {
        triggerDownload(item);
      });
      setResultStatus(`已开始下载 ${selectedItems.length} 张图片`, 'success');
    });

    generateTitlesBtn.addEventListener('click', () => {
      renderTitleSuggestions();
    });

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
        if (triggerDownload(item)) {
          setResultStatus(`已开始下载：${item.title || item.type || '图片'}`, 'success');
        }
      }
    });

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

    previewBackdrop.addEventListener('click', closePreview);
    previewCloseBtn.addEventListener('click', closePreview);
    previewDownloadBtn.addEventListener('click', () => {
      if (previewIndex >= 0) {
        triggerDownload(currentResultItems[previewIndex]);
      }
    });
    previewPrevBtn.addEventListener('click', () => showPreviewOffset(-1));
    previewNextBtn.addEventListener('click', () => showPreviewOffset(1));

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

    moreBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      if (moreMenu.hidden) {
        openMoreMenu();
        return;
      }
      closeMoreMenu();
    });

    moreOptions.forEach((option) => {
      option.addEventListener('click', () => {
        setSelectedOutputCount(Number(option.dataset.count));
        closeMoreMenu();
      });
    });

    document.addEventListener('click', (event) => {
      if (!moreActions.contains(event.target)) {
        closeMoreMenu();
      }
    });

    renderAplusModuleCards();
    syncOutputCountSummary();
    resetResultState();
    setMode(currentMode);

    aiWriteBtn.addEventListener('click', async () => {
      const originalText = sellingInput.value;
      const formData = new FormData();
      formData.append('selling_text', originalText);

      Array.from(fileInput.files).slice(0, 3).forEach((file) => {
        formData.append('images', file);
      });

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
        sellingMessage.textContent = 'AI 文案已生成';
        sellingMessage.className = 'field-message success';
      } catch (error) {
        sellingInput.value = originalText;
        sellingMessage.textContent = error.message || '生成失败，请稍后重试';
        sellingMessage.className = 'field-message error';
      } finally {
        aiWriteBtn.disabled = false;
      }
    });

    styleBtn.addEventListener('click', async () => {
      const formData = new FormData();
      formData.append('selling_text', sellingInput.value.trim());
      formData.append('platform', getPlatformLabel());

      Array.from(fileInput.files).slice(0, 3).forEach((file) => {
        formData.append('images', file);
      });

      currentStyleResults = [];
      selectedStyleIndex = -1;
      styleBtn.disabled = true;
      setStyleButtonLabel(getStyleLoadingLabel());
      styleResultsMessage.textContent = `${getStyleLoadingLabel()}，请稍候…`;
      styleResultsMessage.className = 'style-results-message';
      styleResultsGrid.innerHTML = '';

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
      } catch (error) {
        currentStyleResults = [];
        selectedStyleIndex = -1;
        styleResultsGrid.innerHTML = '';
        styleResultsMessage.textContent = error.message || '风格分析失败，请稍后重试';
        styleResultsMessage.className = 'style-results-message error';
        setStyleButtonLabel(defaultStyleBtnLabel);
      } finally {
        styleBtn.disabled = false;
      }
    });

    generateBtn.addEventListener('click', async () => {
      const formData = new FormData();
      const selectedStyle = getSelectedStyle();
      const config = getCurrentModeConfig();
      const endpoint = currentMode === 'aplus' ? '/api/generate-aplus' : '/api/generate-suite';
      formData.append('selling_text', sellingInput.value.trim());
      formData.append('platform', getPlatformLabel());
      formData.append('country', getCountryReference());
      formData.append('text_type', getTextType());
      formData.append('image_size_ratio', getImageSizeRatio());
      if (currentMode === 'aplus') {
        if (!selectedAplusModules.size) {
          setResultStatus('请至少选择 1 个 A+ 模块后再生成。', 'error');
          return;
        }
        formData.append('selected_modules', JSON.stringify(Array.from(selectedAplusModules)));
      } else {
        formData.append('output_count', String(selectedOutputCount));
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

      Array.from(fileInput.files).slice(0, 3).forEach((file) => {
        formData.append('images', file);
      });

      resetResultStatus();
      resetResultState();
      resultMeta.textContent = selectedStyle?.title
        ? config.selectedPrefix.replace('{style}', selectedStyle.title)
        : config.initialResultMeta;
      generateBtn.disabled = true;
      updateGenerateButtonLabel(config.planLoadingLabel);
      setResultStatus(selectedStyle?.title ? config.selectedPrefix.replace('{style}', selectedStyle.title) : config.defaultPrefix);
      showResultView();

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
      } catch (error) {
        resetResultState();
        resultMeta.textContent = '生成失败后可修改卖点、平台或素材后重试。';
        setResultStatus(error.message || config.errorFallback, 'error');
      } finally {
        generateBtn.disabled = false;
        updateGenerateButtonLabel(config.generateBtnLabel);
      }
    });

    uploadBtn.addEventListener('click', () => {
      fileInput.click();
    });

    fileInput.addEventListener('change', (event) => {
      const files = Array.from(event.target.files).slice(0, 3);
      thumbs.innerHTML = '';

      if (!files.length) {
        thumbs.innerHTML = emptyThumbsMarkup;
        return;
      }

      files.forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const item = document.createElement('div');
          item.className = 'thumb';
          item.style.backgroundImage = `linear-gradient(180deg, transparent 0%, transparent 58%, rgba(17, 17, 17, 0.82) 100%), url(${e.target.result})`;
          item.style.backgroundSize = 'cover';
          item.style.backgroundPosition = 'center';
          item.style.color = '#fff';
          item.innerHTML = `<span>素材 ${index + 1}</span>`;
          thumbs.appendChild(item);
        };
        reader.readAsDataURL(file);
      });
    });
  