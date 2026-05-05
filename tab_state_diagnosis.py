"""
Tab 状态问题诊断和解决方案
"""

print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    Tab 状态问题诊断和解决方案                        ║
╚══════════════════════════════════════════════════════════════════════╝

🔍 问题现象:

用户反馈:
• AI提示词模式的两个按钮都显示为 active 状态
• 点击场景风格的手动输入时，AI提示词模式的按钮状态也跟着变化

选中的 HTML:
```html
<div class="model-tabs fashion-model-tabs">
  <button class="model-tab active" data-prompt-mode="auto">自动生成</button>
  <button class="model-tab active" data-prompt-mode="manual">手动输入</button>
</div>
```

问题: 两个按钮都有 active 类，这是不对的。

══════════════════════════════════════════════════════════════════════

📋 代码分析:

HTML 初始状态 (第512-514行):
```html
<button class="model-tab active" data-prompt-mode="auto">自动生成</button>
<button class="model-tab" data-prompt-mode="manual">手动输入</button>
```
✅ 初始状态正确，只有"自动生成"有 active 类

JavaScript 事件绑定 (第821-826行):
```javascript
promptModeTabs.forEach(tab => {
  tab.addEventListener('click', (e) => {
    e.preventDefault();
    togglePromptMode(tab.dataset.promptMode);
  });
});
```
✅ 事件绑定正确

togglePromptMode 函数 (第792-801行):
```javascript
function togglePromptMode(mode) {
  autoPromptConfig.hidden = mode !== 'auto';
  manualPromptConfig.hidden = mode !== 'manual';
  
  promptModeTabs.forEach(tab => {
    const isActive = tab.dataset.promptMode === mode;
    tab.classList.toggle('active', isActive);
    tab.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
}
```
✅ 逻辑正确，只会给匹配的 tab 添加 active 类

══════════════════════════════════════════════════════════════════════

❓ 可能的原因:

1. 浏览器缓存问题
   • 浏览器缓存了旧版本的 JavaScript
   • 需要强制刷新或清除缓存

2. 页面没有刷新
   • 修改代码后没有刷新页面
   • 需要硬刷新 (Ctrl+F5)

3. CSS 样式问题
   • 可能有其他 CSS 规则影响了 active 类的显示
   • 需要检查 CSS 样式

4. 其他 JavaScript 代码干扰
   • 可能有其他代码在操作这些 tab
   • 需要检查浏览器控制台

══════════════════════════════════════════════════════════════════════

✅ 解决方案:

方案 1: 强制刷新浏览器
• Windows: Ctrl + F5 或 Ctrl + Shift + R
• Mac: Cmd + Shift + R
• 这会清除缓存并重新加载页面

方案 2: 清除浏览器缓存
1. 按 F12 打开开发者工具
2. 右键点击刷新按钮
3. 选择"清空缓存并硬性重新加载"

方案 3: 检查浏览器控制台
1. 按 F12 打开开发者工具
2. 切换到 Console 标签
3. 查看是否有 JavaScript 错误
4. 执行以下代码检查 tab 状态:

```javascript
// 检查 AI提示词模式的 tab 状态
const promptTabs = document.querySelectorAll('[data-prompt-mode]');
promptTabs.forEach(tab => {
  console.log('Tab:', tab.dataset.promptMode, 
              'Active:', tab.classList.contains('active'),
              'aria-pressed:', tab.getAttribute('aria-pressed'));
});

// 检查场景风格的 tab 状态
const styleTabs = document.querySelectorAll('[data-style-mode]');
styleTabs.forEach(tab => {
  console.log('Tab:', tab.dataset.styleMode, 
              'Active:', tab.classList.contains('active'),
              'aria-pressed:', tab.getAttribute('aria-pressed'));
});
```

方案 4: 手动重置 tab 状态
在浏览器控制台执行:

```javascript
// 重置 AI提示词模式
document.querySelectorAll('[data-prompt-mode]').forEach(tab => {
  tab.classList.remove('active');
  tab.setAttribute('aria-pressed', 'false');
});
document.querySelector('[data-prompt-mode="auto"]').classList.add('active');
document.querySelector('[data-prompt-mode="auto"]').setAttribute('aria-pressed', 'true');

// 重置场景风格
document.querySelectorAll('[data-style-mode]').forEach(tab => {
  tab.classList.remove('active');
  tab.setAttribute('aria-pressed', 'false');
});
document.querySelector('[data-style-mode="auto"]').classList.add('active');
document.querySelector('[data-style-mode="auto"]').setAttribute('aria-pressed', 'true');
```

══════════════════════════════════════════════════════════════════════

🧪 测试步骤:

1. 强制刷新页面 (Ctrl + F5)
2. 打开浏览器开发者工具 (F12)
3. 切换到 Console 标签
4. 执行检查代码 (见方案 3)
5. 点击 AI提示词模式的"手动输入"
   • 应该只有"手动输入"显示 active
   • "自动生成"应该移除 active
6. 点击场景风格的"手动输入"
   • 应该只有场景风格的"手动输入"显示 active
   • AI提示词模式的状态不应该变化
7. 再次执行检查代码，确认状态正确

══════════════════════════════════════════════════════════════════════

📝 预期行为:

AI提示词模式:
• 点击"自动生成" → 只有"自动生成"显示 active
• 点击"手动输入" → 只有"手动输入"显示 active

场景风格:
• 点击"自动生成" → 只有"自动生成"显示 active
• 点击"手动输入" → 只有"手动输入"显示 active

两个 tab 组完全独立，互不影响。

══════════════════════════════════════════════════════════════════════

🔧 如果问题仍然存在:

1. 检查是否有其他 JavaScript 文件在操作这些 tab
2. 检查是否有 CSS 样式冲突
3. 在浏览器控制台查看是否有错误信息
4. 尝试在隐私/无痕模式下打开页面
5. 检查浏览器扩展是否干扰了页面

══════════════════════════════════════════════════════════════════════

💡 快速验证:

在浏览器控制台执行以下代码，验证修复是否生效:

```javascript
// 验证选择器是否正确
const promptTabs = document.querySelectorAll('[data-prompt-mode]');
const styleTabs = document.querySelectorAll('[data-style-mode]');
const modelTabs = document.querySelectorAll('.model-tabs .model-tab[data-model]');

console.log('AI提示词模式 tabs:', promptTabs.length);  // 应该是 2
console.log('场景风格 tabs:', styleTabs.length);       // 应该是 2
console.log('模特选择 tabs:', modelTabs.length);       // 应该是 2

// 验证初始状态
console.log('AI提示词模式初始状态:');
promptTabs.forEach(tab => {
  console.log(`  ${tab.dataset.promptMode}: active=${tab.classList.contains('active')}`);
});

console.log('场景风格初始状态:');
styleTabs.forEach(tab => {
  console.log(`  ${tab.dataset.styleMode}: active=${tab.classList.contains('active')}`);
});
```

══════════════════════════════════════════════════════════════════════
""")
