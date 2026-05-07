(() => {
  const MAX_PRODUCTS = 6;
  const MAX_BATCH_IMAGES = 20;
  const MAX_SKU_PRODUCTS = 20;
  const PROGRESS_SETTINGS = {
    single: { baseMs: 25000, itemMs: 75000, ceiling: 92 },
    batch: { baseMs: 30000, itemMs: 70000, ceiling: 94 },
    sku: { baseMs: 30000, itemMs: 75000, ceiling: 94 },
  };

  const state = {
    currentTab: 'single',
    referenceImage: null,
    productImages: [],
    batchImages: [],
    skuImage: null,
    skuProducts: [],
    editingSkuIndex: null,
    isGenerating: false,
    generatedImageUrl: null,
    generatedImages: [],
    selectedSize: '1:1',
    selectedCount: '1',
    generationProgressTimer: null,
    generationStartedAt: 0,
    generationEstimatedMs: 0,
    generationProgress: 0,
  };

  const elements = {
    tabs: null,
    referencePreview: null,
    referenceInput: null,
    productGrid: null,
    productInput: null,
    productUploadBtn: null,
    productCount: null,
    promptInput: null,
    generateBtn: null,
    introView: null,
    resultView: null,
    resultPreview: null,
    regenerateBtn: null,
    downloadResultBtn: null,
    resultStatusMessage: null,
    generationProgressBar: null,
    previewModal: null,
    previewImage: null,
    previewCloseBtn: null,
    previewDownloadBtn: null,
    previewBackdrop: null,
    sizeSelect: null,
    countSelect: null,
    singleUploadArea: null,
    batchUploadArea: null,
    batchDropzone: null,
    batchInput: null,
    batchUploadCount: null,
    batchPreviewGrid: null,
    skuUploadArea: null,
    skuPreview: null,
    skuInput: null,
    productSection: null,
    skuProductSection: null,
    skuProductUploadArea: null,
    skuProductListArea: null,
    skuProductDropzone: null,
    skuProductInput: null,
    skuProductCount: null,
    skuProductListCount: null,
    skuProductGrid: null,
    skuEditModal: null,
    skuEditBackdrop: null,
    skuEditTitle: null,
    skuEditTextarea: null,
    skuEditCloseBtn: null,
    skuEditCancelBtn: null,
    skuEditConfirmBtn: null,
    promptLabel: null,
  };

  function initElements() {
    elements.tabs = document.querySelectorAll('.replicate-tab');
    elements.referencePreview = document.getElementById('referencePreview');
    elements.referenceInput = document.getElementById('referenceInput');
    elements.productGrid = document.getElementById('productGrid');
    elements.productInput = document.getElementById('productInput');
    elements.productUploadBtn = document.getElementById('productUploadBtn');
    elements.productCount = document.getElementById('productCount');
    elements.promptInput = document.getElementById('promptInput');
    elements.generateBtn = document.getElementById('generateBtn');
    elements.introView = document.getElementById('introView');
    elements.resultView = document.getElementById('resultView');
    elements.resultPreview = document.getElementById('resultPreview');
    elements.regenerateBtn = document.getElementById('regenerateBtn');
    elements.downloadResultBtn = document.getElementById('downloadResultBtn');
    elements.resultStatusMessage = document.getElementById('resultStatusMessage');
    elements.generationProgressBar = document.getElementById('generationProgressBar');
    elements.previewModal = document.getElementById('previewModal');
    elements.previewImage = document.getElementById('previewImage');
    elements.previewCloseBtn = document.getElementById('previewCloseBtn');
    elements.previewDownloadBtn = document.getElementById('previewDownloadBtn');
    elements.previewBackdrop = document.getElementById('previewBackdrop');
    elements.sizeSelect = document.getElementById('modelSelect');
    elements.countSelect = document.getElementById('sizeSelect');
    elements.singleUploadArea = document.getElementById('singleUploadArea');
    elements.batchUploadArea = document.getElementById('batchUploadArea');
    elements.batchDropzone = document.getElementById('batchDropzone');
    elements.batchInput = document.getElementById('batchInput');
    elements.batchUploadCount = document.getElementById('batchUploadCount');
    elements.batchPreviewGrid = document.getElementById('batchPreviewGrid');
    elements.skuUploadArea = document.getElementById('skuUploadArea');
    elements.skuPreview = document.getElementById('skuPreview');
    elements.skuInput = document.getElementById('skuInput');
    elements.productSection = document.getElementById('productSection');
    elements.skuProductSection = document.getElementById('skuProductSection');
    elements.skuProductUploadArea = document.getElementById('skuProductUploadArea');
    elements.skuProductListArea = document.getElementById('skuProductListArea');
    elements.skuProductDropzone = document.getElementById('skuProductDropzone');
    elements.skuProductInput = document.getElementById('skuProductInput');
    elements.skuProductCount = document.getElementById('skuProductCount');
    elements.skuProductListCount = document.getElementById('skuProductListCount');
    elements.skuProductGrid = document.getElementById('skuProductGrid');
    elements.skuEditModal = document.getElementById('skuEditModal');
    elements.skuEditBackdrop = document.getElementById('skuEditBackdrop');
    elements.skuEditTitle = document.getElementById('skuEditTitle');
    elements.skuEditTextarea = document.getElementById('skuEditTextarea');
    elements.skuEditCloseBtn = document.getElementById('skuEditCloseBtn');
    elements.skuEditCancelBtn = document.getElementById('skuEditCancelBtn');
    elements.skuEditConfirmBtn = document.getElementById('skuEditConfirmBtn');
    elements.promptLabel = document.getElementById('promptLabel');
  }

  function updateProductCount() {
    if (elements.productCount) {
      elements.productCount.textContent = `${state.productImages.length}/${MAX_PRODUCTS}`;
    }
  }

  function updateGenerateButton() {
    if (elements.generateBtn) {
      let hasReference = false;
      let hasProducts = false;
      
      if (state.currentTab === 'single') {
        hasReference = state.referenceImage !== null;
        hasProducts = state.productImages.length > 0;
      } else if (state.currentTab === 'batch') {
        hasReference = state.batchImages.length > 0;
        hasProducts = state.productImages.length > 0;
      } else if (state.currentTab === 'sku') {
        hasReference = state.skuImage !== null;
        hasProducts = state.skuProducts.length > 0;
      }
      
      elements.generateBtn.disabled = !hasReference || !hasProducts || state.isGenerating;
    }
  }

  function updateRegenerateButton() {
    if (elements.regenerateBtn) {
      elements.regenerateBtn.disabled = state.isGenerating || !(state.generatedImages && state.generatedImages.length > 0);
    }
  }

  function handleTabClick(event) {
    const tab = event.currentTarget;
    const tabType = tab.dataset.tab;

    if (tabType === state.currentTab) return;

    state.currentTab = tabType;

    elements.tabs.forEach(t => {
      t.classList.toggle('active', t.dataset.tab === tabType);
    });

    if (tabType === 'single') {
      elements.singleUploadArea?.removeAttribute('hidden');
      elements.batchUploadArea?.setAttribute('hidden', '');
      elements.skuUploadArea?.setAttribute('hidden', '');
      elements.productSection?.removeAttribute('hidden');
      elements.skuProductSection?.setAttribute('hidden', '');
      elements.promptLabel?.removeAttribute('hidden');
    } else if (tabType === 'batch') {
      elements.singleUploadArea?.setAttribute('hidden', '');
      elements.batchUploadArea?.removeAttribute('hidden');
      elements.skuUploadArea?.setAttribute('hidden', '');
      elements.productSection?.removeAttribute('hidden');
      elements.skuProductSection?.setAttribute('hidden', '');
      elements.promptLabel?.removeAttribute('hidden');
    } else if (tabType === 'sku') {
      elements.singleUploadArea?.setAttribute('hidden', '');
      elements.batchUploadArea?.setAttribute('hidden', '');
      elements.skuUploadArea?.removeAttribute('hidden');
      elements.productSection?.setAttribute('hidden', '');
      elements.skuProductSection?.removeAttribute('hidden');
      elements.promptLabel?.setAttribute('hidden', '');
    }

    updateGenerateButton();

    console.log('Tab switched to:', tabType);
  }

  function handleReferenceUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      state.referenceImage = {
        file,
        dataUrl: e.target.result,
      };

      elements.referencePreview.innerHTML = `
        <img src="${e.target.result}" alt="参考图">
        <button class="reference-delete-btn" type="button" title="删除">×</button>
      `;
      elements.referencePreview.classList.add('has-image');

      const deleteBtn = elements.referencePreview.querySelector('.reference-delete-btn');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          deleteReferenceImage();
        });
      }

      updateGenerateButton();
    };
    reader.readAsDataURL(file);
  }

  function deleteReferenceImage() {
    state.referenceImage = null;
    elements.referencePreview.innerHTML = `
      <div class="preview-placeholder">
        <div class="placeholder-icon">◆</div>
        <div class="placeholder-text">上传参考图</div>
        <div class="placeholder-hint">上传具有明确风格的参考图</div>
      </div>
    `;
    elements.referencePreview.classList.remove('has-image');
    
    updateGenerateButton();
  }

  function handleReferencePreviewClick() {
    if (state.referenceImage) {
      return;
    }
    elements.referenceInput?.click();
  }

  function createProductItem(imageData, index) {
    const item = document.createElement('div');
    item.className = 'product-item';
    item.innerHTML = `
      <img src="${imageData.dataUrl}" alt="产品图 ${index + 1}">
      <button class="product-delete-btn" type="button" data-index="${index}">×</button>
    `;

    const deleteBtn = item.querySelector('.product-delete-btn');
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteProduct(index);
    });

    return item;
  }

  function renderProductGrid() {
    if (!elements.productGrid) return;

    elements.productGrid.innerHTML = '';
    state.productImages.forEach((imageData, index) => {
      const item = createProductItem(imageData, index);
      elements.productGrid.appendChild(item);
    });

    updateProductCount();
    updateGenerateButton();
    updateRegenerateButton();
  }

  function handleProductUpload(event) {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    const remainingSlots = MAX_PRODUCTS - state.productImages.length;
    const filesToAdd = files.slice(0, remainingSlots);

    filesToAdd.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        state.productImages.push({
          file,
          dataUrl: e.target.result,
        });
        renderProductGrid();
      };
      reader.readAsDataURL(file);
    });
  }

  function deleteProduct(index) {
    if (index < 0 || index >= state.productImages.length) return;

    state.productImages.splice(index, 1);
    renderProductGrid();
  }

  function handleProductUploadClick() {
    if (state.productImages.length >= MAX_PRODUCTS) {
      alert(`最多只能上传 ${MAX_PRODUCTS} 张产品图`);
      return;
    }
    elements.productInput?.click();
  }

  function showIntroView() {
    elements.introView?.classList.add('active');
    elements.resultView?.classList.remove('active');
  }

  function showResultView() {
    elements.introView?.classList.remove('active');
    elements.resultView?.classList.add('active');
  }

  function setGenerationProgress(progress, text) {
    if (!elements.generationProgressBar) return;

    const fill = elements.generationProgressBar.querySelector('.progress-bar-fill');
    const textEl = elements.generationProgressBar.querySelector('.progress-bar-text');
    const percentEl = elements.generationProgressBar.querySelector('.progress-bar-percent');

    state.generationProgress = Math.max(0, Math.min(100, Number(progress) || 0));

    if (fill) {
      fill.style.width = `${state.generationProgress}%`;
    }
    if (textEl && text) {
      textEl.textContent = text;
    }
    if (percentEl) {
      percentEl.textContent = `${Math.round(state.generationProgress)}%`;
    }
  }

  function stopGenerationProgress() {
    if (state.generationProgressTimer) {
      window.clearInterval(state.generationProgressTimer);
      state.generationProgressTimer = null;
    }
  }

  function startGenerationProgress() {
    stopGenerationProgress();
    const settings = PROGRESS_SETTINGS[state.currentTab] || PROGRESS_SETTINGS.single;
    const itemCount = state.currentTab === 'batch'
      ? Math.max(1, state.batchImages.length)
      : (state.currentTab === 'sku' ? Math.max(1, state.skuProducts.length) : Math.max(1, Number(state.selectedCount) || 1));
    state.generationStartedAt = Date.now();
    state.generationEstimatedMs = settings.baseMs + itemCount * settings.itemMs;
    setGenerationProgress(3, '正在生成...');
    state.generationProgressTimer = window.setInterval(() => {
      if (!state.isGenerating) {
        stopGenerationProgress();
        return;
      }

      const settings = PROGRESS_SETTINGS[state.currentTab] || PROGRESS_SETTINGS.single;
      const elapsed = Date.now() - state.generationStartedAt;
      const ratio = Math.min(1, elapsed / Math.max(1, state.generationEstimatedMs));
      const easedRatio = 1 - Math.pow(1 - ratio, 2.4);
      const targetProgress = Math.min(settings.ceiling, 3 + easedRatio * (settings.ceiling - 3));
      const nextProgress = Math.max(state.generationProgress, targetProgress);
      setGenerationProgress(nextProgress);
    }, 800);
  }

  function completeGenerationProgress() {
    stopGenerationProgress();
    setGenerationProgress(100, '生成完成');
  }

  function showGeneratingState() {
    state.isGenerating = true;
    state.generatedImageUrl = null;
    state.generatedImages = [];
    updateGenerateButton();
    updateRegenerateButton();

    showResultView();

    if (elements.generationProgressBar) {
      elements.generationProgressBar.hidden = false;
    }

    startGenerationProgress();

    if (elements.resultPreview) {
      elements.resultPreview.innerHTML = `
        <div class="result-placeholder">
          <div class="placeholder-icon" style="animation: spin 1s linear infinite;">✦</div>
          <div class="placeholder-text">正在生成...</div>
          <div class="placeholder-hint">AI 正在为您复刻主图，请稍候</div>
        </div>
      `;
      elements.resultPreview.classList.remove('has-image');
    }
  }

  function showResult(imageUrl) {
    showResults([{ url: imageUrl }]);
  }

  function showResults(images) {
    completeGenerationProgress();
    state.isGenerating = false;
    state.generatedImageUrl = images.length > 0 ? images[0].url : null;
    state.generatedImages = images;
    updateGenerateButton();
    updateRegenerateButton();

    if (elements.resultStatusMessage) {
      const countText = images.length > 1 ? `生成完成，共 ${images.length} 张结果` : '生成完成';
      elements.resultStatusMessage.textContent = countText;
      elements.resultStatusMessage.className = 'result-status-message is-success';
    }

    if (elements.generationProgressBar) {
      window.setTimeout(() => {
        if (!state.isGenerating && elements.generationProgressBar) {
          elements.generationProgressBar.hidden = true;
        }
      }, 600);
    }

    if (elements.resultPreview) {
      if (images.length === 1) {
        elements.resultPreview.innerHTML = `
          <img src="${images[0].url}" alt="生成结果">
        `;
        elements.resultPreview.classList.add('has-image');
        const img = elements.resultPreview.querySelector('img');
        if (img) {
          img.addEventListener('click', () => openPreviewModal(images[0].url));
        }
      } else {
        let gridHtml = '<div class="result-image-grid">';
        images.forEach((img, index) => {
          let label = `#${index + 1}`;
          if (img.sku_info) {
            label = img.sku_info;
          } else if (img.batch_reference_index !== undefined) {
            label = `参考图${img.batch_reference_index + 1}`;
          }
          gridHtml += `
            <div class="result-image-item" data-index="${index}">
              <img src="${img.url}" alt="结果 ${index + 1}">
              <div class="result-image-label">${label}</div>
            </div>
          `;
        });
        gridHtml += '</div>';
        elements.resultPreview.innerHTML = gridHtml;
        elements.resultPreview.classList.add('has-image');
        elements.resultPreview.querySelectorAll('.result-image-item img').forEach((imgEl, idx) => {
          imgEl.addEventListener('click', () => openPreviewModal(images[idx].url));
        });
      }
    }
  }

  function showResultError(message) {
    stopGenerationProgress();
    state.isGenerating = false;
    state.generatedImageUrl = null;
    state.generatedImages = [];
    updateGenerateButton();
    updateRegenerateButton();

    if (elements.resultStatusMessage) {
      elements.resultStatusMessage.textContent = message || '生成失败';
      elements.resultStatusMessage.className = 'result-status-message is-error';
    }

    if (elements.generationProgressBar) {
      elements.generationProgressBar.hidden = true;
    }

    if (elements.resultPreview) {
      elements.resultPreview.innerHTML = `
        <div class="result-placeholder">
          <div class="placeholder-icon" style="color: var(--danger);">✗</div>
          <div class="placeholder-text">生成失败</div>
          <div class="placeholder-hint">${message || '请检查图片后重试'}</div>
        </div>
      `;
      elements.resultPreview.classList.remove('has-image');
    }
  }

  function openPreviewModal(imageUrl) {
    if (!elements.previewModal || !elements.previewImage) return;

    elements.previewImage.src = imageUrl;
    elements.previewModal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closePreviewModal() {
    if (!elements.previewModal) return;

    elements.previewModal.hidden = true;
    document.body.style.overflow = '';
  }

  async function handleGenerate() {
    let hasReference = false;
    let hasProducts = false;
    
    if (state.currentTab === 'single') {
      hasReference = state.referenceImage !== null;
      hasProducts = state.productImages.length > 0;
    } else if (state.currentTab === 'batch') {
      hasReference = state.batchImages.length > 0;
      hasProducts = state.productImages.length > 0;
    } else if (state.currentTab === 'sku') {
      hasReference = state.skuImage !== null;
      hasProducts = state.skuProducts.length > 0;
    }
    
    if (!hasReference || !hasProducts) {
      if (state.currentTab === 'sku') {
        alert('请先上传SKU图片和SKU产品图');
      } else {
        alert('请先上传参考设计图和至少一张产品素材图');
      }
      return;
    }

    showGeneratingState();

    try {
      const formData = new FormData();
      
      if (state.currentTab === 'single') {
        if (state.referenceImage?.file) {
          formData.append('reference_image', state.referenceImage.file);
        }
        state.productImages.forEach((img, index) => {
          if (img.file) {
            formData.append('product_images', img.file);
          }
        });
      } else if (state.currentTab === 'batch') {
        state.batchImages.forEach((img, index) => {
          if (img.file) {
            formData.append('reference_image', img.file);
          }
        });
        state.productImages.forEach((img, index) => {
          if (img.file) {
            formData.append('product_images', img.file);
          }
        });
      } else if (state.currentTab === 'sku') {
        if (state.skuImage?.file) {
          formData.append('reference_image', state.skuImage.file);
        }
        state.skuProducts.forEach((product, index) => {
          if (product.file) {
            formData.append('product_images', product.file);
          }
          if (product.info) {
            formData.append(`sku_info_${index}`, product.info);
          }
        });
      }
      
      const prompt = elements.promptInput?.value || '';
      formData.append('replicate_mode', state.currentTab);
      formData.append('prompt', prompt);
      formData.append('image_size_ratio', state.selectedSize);
      formData.append('output_count', state.selectedCount);
      formData.append('async_task', '1');
      
      console.log('Sending request with:', {
        mode: state.currentTab,
        prompt,
        image_size_ratio: state.selectedSize,
        output_count: state.selectedCount,
      });

      const response = await fetch('/api/generate-replicate', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error || '生成失败，请稍后重试');
      }

      if (result.async_task && result.task_id) {
        await pollTaskResult(result.task_id);
      } else if (result.images && result.images.length > 0) {
        if (result.images.length === 1) {
          showResult(result.images[0].url);
        } else {
          showResults(result.images);
        }
      } else {
        throw new Error('未返回生成结果');
      }

    } catch (error) {
      console.error('Generate error:', error);
      showResultError(error.message || '生成过程中发生错误');
    }
  }

  async function pollTaskResult(taskId) {
    const maxAttempts = 120;
    const intervalMs = 2000;
    
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const response = await fetch(`/api/generation-tasks/${taskId}`);
        const result = await response.json();
        
        if (!response.ok || !result.success) {
          throw new Error(result.error || '任务查询失败');
        }
        
        const task = result.task;
        
        if (task?.status === 'succeeded' && task?.result?.images?.length > 0) {
          if (task.result.images.length === 1) {
            showResult(task.result.images[0].url);
          } else {
            showResults(task.result.images);
          }
          return;
        }
        
        if (task?.status === 'failed') {
          throw new Error(task.error || '生成任务失败');
        }
        
        await new Promise(resolve => setTimeout(resolve, intervalMs));
      } catch (error) {
        console.error('Poll error:', error);
        throw error;
      }
    }
    
    throw new Error('生成超时，请稍后重试');
  }

  function handleRegenerate() {
    if (!state.generatedImages || state.generatedImages.length === 0) {
      alert('请先生成结果');
      return;
    }

    handleGenerate();
  }

  function handleDownloadResult() {
    if (!state.generatedImageUrl && (!state.generatedImages || state.generatedImages.length === 0)) {
      alert('没有可下载的结果');
      return;
    }

    if (state.generatedImages && state.generatedImages.length > 1) {
      state.generatedImages.forEach((img, index) => {
        const link = document.createElement('a');
        link.href = img.url;
        link.download = `replicate-result-${index + 1}-${Date.now()}.png`;
        link.click();
      });
    } else {
      const link = document.createElement('a');
      link.href = state.generatedImageUrl;
      link.download = `replicate-result-${Date.now()}.png`;
      link.click();
    }
  }

  function handleModelSelect(event) {
    state.selectedSize = event.target.value;
    console.log('Size selected:', state.selectedSize);
  }

  function handleSizeSelect(event) {
    state.selectedCount = event.target.value;
    console.log('Count selected:', state.selectedCount);
  }

  function updateBatchUploadCount() {
    if (elements.batchUploadCount) {
      elements.batchUploadCount.textContent = `${state.batchImages.length}/${MAX_BATCH_IMAGES} 张`;
    }
  }

  function createBatchPreviewItem(imageData, index) {
    const item = document.createElement('div');
    item.className = 'batch-preview-item';
    item.innerHTML = `
      <img src="${imageData.dataUrl}" alt="批量图片 ${index + 1}">
      <div class="batch-preview-item-number">${index + 1}</div>
      <button class="batch-preview-item-delete" type="button" data-index="${index}">×</button>
    `;

    const deleteBtn = item.querySelector('.batch-preview-item-delete');
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteBatchImage(index);
    });

    return item;
  }

  function renderBatchPreviewGrid() {
    if (!elements.batchPreviewGrid) return;

    elements.batchPreviewGrid.innerHTML = '';

    state.batchImages.forEach((imageData, index) => {
      const item = createBatchPreviewItem(imageData, index);
      elements.batchPreviewGrid.appendChild(item);
    });

    updateBatchUploadCount();
    updateGenerateButton();
  }

  function handleBatchUpload(files) {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const remainingSlots = MAX_BATCH_IMAGES - state.batchImages.length;
    const filesToAdd = fileArray.slice(0, remainingSlots);

    filesToAdd.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        state.batchImages.push({
          file,
          dataUrl: e.target.result,
        });
        renderBatchPreviewGrid();
      };
      reader.readAsDataURL(file);
    });
  }

  function deleteBatchImage(index) {
    if (index < 0 || index >= state.batchImages.length) return;

    state.batchImages.splice(index, 1);
    renderBatchPreviewGrid();
  }

  function handleBatchDropzoneClick() {
    if (state.batchImages.length >= MAX_BATCH_IMAGES) {
      alert(`最多只能上传 ${MAX_BATCH_IMAGES} 张图片`);
      return;
    }
    elements.batchInput?.click();
  }

  function handleBatchInputChange(event) {
    handleBatchUpload(event.target.files || []);
    event.target.value = '';
  }

  function handleBatchDropzoneDragover(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.batchDropzone?.classList.add('dragover');
  }

  function handleBatchDropzoneDragleave(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.batchDropzone?.classList.remove('dragover');
  }

  function handleBatchDropzoneDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.batchDropzone?.classList.remove('dragover');

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      handleBatchUpload(files);
    }
  }

  function handleSkuUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      state.skuImage = {
        file,
        dataUrl: e.target.result,
      };

      elements.skuPreview.innerHTML = `
        <img src="${e.target.result}" alt="SKU图片">
        <button class="reference-delete-btn" type="button" title="删除">×</button>
      `;
      elements.skuPreview.classList.add('has-image');

      const deleteBtn = elements.skuPreview.querySelector('.reference-delete-btn');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          deleteSkuImage();
        });
      }

      updateGenerateButton();
    };
    reader.readAsDataURL(file);
  }

  function deleteSkuImage() {
    state.skuImage = null;
    
    elements.skuPreview.innerHTML = `
      <div class="preview-placeholder">
        <div class="placeholder-icon">◆</div>
        <div class="placeholder-text">上传SKU图片</div>
        <div class="placeholder-hint">上传需要替换的SKU图片</div>
      </div>
    `;
    elements.skuPreview.classList.remove('has-image');
    updateGenerateButton();
  }

  function createSkuProductItem(product, index) {
    const item = document.createElement('div');
    item.className = 'sku-product-item';
    item.innerHTML = `
      <img src="${product.dataUrl}" alt="SKU产品 ${index + 1}">
      <div class="sku-product-actions">
        <button class="sku-product-edit" type="button" data-index="${index}">编辑信息</button>
        <button class="sku-product-delete" type="button" data-index="${index}">删除</button>
      </div>
      <div class="sku-product-info">${product.info || '未填写SKU信息'}</div>
    `;

    item.querySelector('.sku-product-edit')?.addEventListener('click', () => openSkuEditModal(index));
    item.querySelector('.sku-product-delete')?.addEventListener('click', () => deleteSkuProduct(index));
    return item;
  }

  function renderSkuProductGrid() {
    if (!elements.skuProductGrid) return;

    elements.skuProductGrid.innerHTML = '';
    state.skuProducts.forEach((product, index) => {
      const item = createSkuProductItem(product, index);
      elements.skuProductGrid.appendChild(item);
    });

    if (elements.skuProductCount) {
      elements.skuProductCount.textContent = `${state.skuProducts.length}/${MAX_SKU_PRODUCTS}`;
    }
    if (elements.skuProductListCount) {
      elements.skuProductListCount.textContent = String(state.skuProducts.length);
    }
    updateGenerateButton();
    updateRegenerateButton();
  }

  function handleSkuProductUpload(files) {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) return;

    const remainingSlots = MAX_SKU_PRODUCTS - state.skuProducts.length;
    const filesToAdd = fileArray.slice(0, remainingSlots);

    filesToAdd.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        state.skuProducts.push({
          file,
          dataUrl: e.target.result,
          info: '',
        });
        renderSkuProductGrid();
      };
      reader.readAsDataURL(file);
    });
  }

  function deleteSkuProduct(index) {
    if (index < 0 || index >= state.skuProducts.length) return;
    state.skuProducts.splice(index, 1);
    renderSkuProductGrid();
  }

  function openSkuEditModal(index) {
    const product = state.skuProducts[index];
    if (!product || !elements.skuEditModal || !elements.skuEditTextarea) return;

    state.editingSkuIndex = index;
    elements.skuEditTextarea.value = product.info || '';
    elements.skuEditModal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeSkuEditModal() {
    if (!elements.skuEditModal) return;
    elements.skuEditModal.hidden = true;
    document.body.style.overflow = '';
    state.editingSkuIndex = null;
  }

  function confirmSkuEdit() {
    if (state.editingSkuIndex === null) return;
    const product = state.skuProducts[state.editingSkuIndex];
    if (!product || !elements.skuEditTextarea) return;

    product.info = elements.skuEditTextarea.value.trim();
    renderSkuProductGrid();
    closeSkuEditModal();
  }

  function bindEvents() {
    elements.tabs?.forEach(tab => tab.addEventListener('click', handleTabClick));
    elements.referencePreview?.addEventListener('click', handleReferencePreviewClick);
    elements.referenceInput?.addEventListener('change', handleReferenceUpload);
    elements.productUploadBtn?.addEventListener('click', handleProductUploadClick);
    elements.productInput?.addEventListener('change', handleProductUpload);
    elements.generateBtn?.addEventListener('click', handleGenerate);
    elements.regenerateBtn?.addEventListener('click', handleRegenerate);
    elements.downloadResultBtn?.addEventListener('click', handleDownloadResult);
    elements.sizeSelect?.addEventListener('change', handleModelSelect);
    elements.countSelect?.addEventListener('change', handleSizeSelect);
    elements.batchDropzone?.addEventListener('click', handleBatchDropzoneClick);
    elements.batchInput?.addEventListener('change', handleBatchInputChange);
    elements.batchDropzone?.addEventListener('dragover', handleBatchDropzoneDragover);
    elements.batchDropzone?.addEventListener('dragleave', handleBatchDropzoneDragleave);
    elements.batchDropzone?.addEventListener('drop', handleBatchDropzoneDrop);
    elements.skuInput?.addEventListener('change', handleSkuUpload);
    elements.skuProductDropzone?.addEventListener('click', () => elements.skuProductInput?.click());
    elements.skuProductInput?.addEventListener('change', (event) => {
      handleSkuProductUpload(event.target.files || []);
      event.target.value = '';
    });
    elements.skuEditCloseBtn?.addEventListener('click', closeSkuEditModal);
    elements.skuEditCancelBtn?.addEventListener('click', closeSkuEditModal);
    elements.skuEditConfirmBtn?.addEventListener('click', confirmSkuEdit);
    elements.previewCloseBtn?.addEventListener('click', closePreviewModal);
    elements.previewBackdrop?.addEventListener('click', closePreviewModal);
    elements.previewDownloadBtn?.addEventListener('click', () => {
      if (!elements.previewImage?.src) return;
      const link = document.createElement('a');
      link.href = elements.previewImage.src;
      link.download = `replicate-preview-${Date.now()}.png`;
      link.click();
    });
  }

  function init() {
    initElements();
    bindEvents();
    updateGenerateButton();
    updateRegenerateButton();
    renderProductGrid();
    renderBatchPreviewGrid();
    renderSkuProductGrid();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
