"""
张数选择器显示问题修复报告
"""

print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    张数选择器显示问题修复报告                        ║
╚══════════════════════════════════════════════════════════════════════╝

🔍 问题分析:

原因:
张数选择器原本放在 sceneTypeConfig 内部，但是 sceneTypeConfig 在"商品套图"
模式下被隐藏了，导致张数选择器也被隐藏。

代码逻辑冲突:
```javascript
// 商品套图时隐藏场景类型配置
if (sceneTypeConfig) {
  sceneTypeConfig.hidden = genType === 'suite';  // 隐藏整个 sceneTypeConfig
}

// 只在商品套图时显示张数选择器
if (batchMoreActions) {
  batchMoreActions.hidden = genType !== 'suite';  // 无效，因为父元素已隐藏
}
```

结果: 当选择"商品套图"时，sceneTypeConfig 被隐藏，张数选择器也随之隐藏。

══════════════════════════════════════════════════════════════════════

✅ 解决方案:

1. 将张数选择器移到 sceneTypeConfig 外面
   • 创建独立的 div: batchOutputCountField
   • 包含"输出数量"标签和张数选择器

2. 更新 JavaScript 代码
   • 添加对 batchOutputCountField 的引用
   • 在 toggleConfigByGenType 中控制其显示/隐藏

══════════════════════════════════════════════════════════════════════

📝 代码修改详情:

修改 1: HTML 结构调整

修改前:
```html
<div id="sceneTypeConfig">
  <div class="field">
    <div style="display: flex; ...">
      <span class="field-label">场景类型</span>
      <div class="more-actions" id="batchMoreActions">
        <!-- 张数选择器 -->
      </div>
    </div>
    <div class="checkbox-group" id="batchSceneTypes">
      <!-- 场景类型复选框 -->
    </div>
  </div>
</div>
```

修改后:
```html
<!-- 独立的输出数量选择器 -->
<div class="field" id="batchOutputCountField" style="margin-top: 12px;">
  <div style="display: flex; align-items: center; justify-content: space-between;">
    <span class="field-label">输出数量</span>
    <div class="more-actions" id="batchMoreActions">
      <button class="more-btn" id="batchMoreBtn">…(6张)</button>
      <div class="more-menu" id="batchMoreMenu" hidden>
        <!-- 6-10张选项 -->
      </div>
    </div>
  </div>
</div>

<!-- 场景类型配置 -->
<div id="sceneTypeConfig">
  <div class="field" style="margin-top: 12px;">
    <span class="field-label">场景类型</span>
    <div class="checkbox-group" id="batchSceneTypes">
      <!-- 场景类型复选框 -->
    </div>
  </div>
</div>
```

修改 2: JavaScript 逻辑更新

添加变量引用:
```javascript
const batchOutputCountField = document.getElementById('batchOutputCountField');
```

更新显示逻辑:
```javascript
function toggleConfigByGenType(genType) {
  // ... 其他逻辑 ...

  // 只在商品套图时显示输出数量选择器
  if (batchOutputCountField) {
    batchOutputCountField.hidden = genType !== 'suite';
  }
}
```

══════════════════════════════════════════════════════════════════════

🎯 修复后的行为:

生成类型: 商品套图 (suite)
• batchOutputCountField.hidden = false ✅ 显示
• sceneTypeConfig.hidden = true (隐藏场景类型配置)

生成类型: A+详情页 (aplus)
• batchOutputCountField.hidden = true ❌ 隐藏
• sceneTypeConfig.hidden = false (显示场景类型配置)

生成类型: 服饰穿戴 (fashion)
• batchOutputCountField.hidden = true ❌ 隐藏
• sceneTypeConfig.hidden = true (隐藏场景类型配置)

══════════════════════════════════════════════════════════════════════

✅ 修复完成:

• 张数选择器现在独立于 sceneTypeConfig
• 只在"商品套图"模式下显示
• 与 /suite 页面的行为一致
• 解决了显示冲突问题

══════════════════════════════════════════════════════════════════════

🧪 测试建议:

1. 刷新页面 http://127.0.0.1:5078/batch
2. 默认选择"商品套图"
3. 应该看到"输出数量"字段和张数选择器 ✅
4. 切换到"A+详情页"
5. "输出数量"字段应该隐藏 ❌
6. 切换回"商品套图"
7. "输出数量"字段应该重新显示 ✅

══════════════════════════════════════════════════════════════════════
""")
