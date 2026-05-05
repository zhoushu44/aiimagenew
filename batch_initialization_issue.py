"""
批量任务页面初始化问题分析
"""

print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    批量任务页面初始化问题分析                        ║
╚══════════════════════════════════════════════════════════════════════╝

🔍 问题现象:

页面打开/刷新时:
• select 显示: "商品套图" (正确)
• sceneTypeConfig (场景类型): 显示 ❌ (错误，应该隐藏)
• sceneNotesField (补充说明): 显示 ❌ (错误，应该隐藏)

来回切换后:
• 显示正常

══════════════════════════════════════════════════════════════════════

📋 问题原因:

HTML 初始状态:
```html
<div id="sceneTypeConfig">
  <!-- 场景类型配置，默认显示 -->
</div>

<label id="sceneNotesField">
  <!-- 补充说明，默认显示 -->
</label>
```

JavaScript 初始化:
```javascript
// 页面加载时没有调用 toggleConfigByGenType
// 导致初始显示状态不正确
```

toggleConfigByGenType 函数逻辑:
```javascript
function toggleConfigByGenType(genType) {
  // 商品套图时隐藏场景类型配置
  if (sceneTypeConfig) {
    sceneTypeConfig.hidden = genType === 'suite';  // true (隐藏)
  }
  
  // A+详情页时隐藏补充说明字段
  if (sceneNotesField) {
    sceneNotesField.hidden = genType === 'aplus';  // false (显示)
  }
}
```

问题:
• 页面加载时，HTML 元素默认都是显示的
• JavaScript 没有在初始化时调用 toggleConfigByGenType
• 导致初始显示状态与实际选择的生成类型不匹配

══════════════════════════════════════════════════════════════════════

✅ 解决方案:

方案 1: 在页面加载时调用初始化函数 (推荐)

```javascript
// 页面加载完成后立即初始化
document.addEventListener('DOMContentLoaded', () => {
  // 初始化显示状态
  toggleConfigByGenType(batchGenType.value);
  
  // ... 其他初始化代码 ...
});
```

方案 2: 在 HTML 中设置正确的初始 hidden 状态

```html
<!-- 商品套图时应该隐藏 -->
<div id="sceneTypeConfig" hidden>
  <!-- 场景类型配置 -->
</div>

<!-- 商品套图时应该显示 -->
<label id="sceneNotesField">
  <!-- 补充说明 -->
</label>
```

方案 3: 在 JavaScript 变量定义后立即调用

```javascript
const batchGenType = document.getElementById('batchGenType');
const sceneTypeConfig = document.getElementById('sceneTypeConfig');
const sceneNotesField = document.getElementById('sceneNotesField');

// 立即初始化显示状态
toggleConfigByGenType(batchGenType.value);
```

══════════════════════════════════════════════════════════════════════

🎯 推荐方案: 方案 1 + 方案 3 结合

原因:
1. 页面加载时立即初始化，确保显示状态正确
2. 在变量定义后立即调用，逻辑清晰
3. 不需要修改 HTML，保持代码整洁

实现步骤:
1. 在 JavaScript 变量定义完成后
2. 立即调用 toggleConfigByGenType(batchGenType.value)
3. 初始化所有相关元素的显示状态

══════════════════════════════════════════════════════════════════════

📝 正确的初始化逻辑:

页面加载流程:
1. HTML 渲染完成
   • select 默认选中 "商品套图"
   • 所有元素默认显示

2. JavaScript 执行
   • 获取 DOM 元素引用
   • 定义 toggleConfigByGenType 函数
   • ✅ 立即调用 toggleConfigByGenType('suite')
   • sceneTypeConfig.hidden = true (隐藏)
   • sceneNotesField.hidden = false (显示)

3. 用户看到正确的初始状态
   • 商品套图选中
   • 场景类型隐藏 ✅
   • 补充说明显示 ✅

══════════════════════════════════════════════════════════════════════

🔧 代码修改位置:

文件: pages/batch.html
位置: JavaScript 部分，在变量定义和函数定义之后

当前代码:
```javascript
const batchOutputCountField = document.getElementById('batchOutputCountField');

let taskCounter = 0;
// ... 其他代码 ...

function toggleConfigByGenType(genType) {
  // ... 函数实现 ...
}

batchGenType.addEventListener('change', () => {
  toggleConfigByGenType(batchGenType.value);
});
```

修改后:
```javascript
const batchOutputCountField = document.getElementById('batchOutputCountField');

let taskCounter = 0;
// ... 其他代码 ...

function toggleConfigByGenType(genType) {
  // ... 函数实现 ...
}

// ✅ 初始化显示状态
toggleConfigByGenType(batchGenType.value);

batchGenType.addEventListener('change', () => {
  toggleConfigByGenType(batchGenType.value);
});
```

══════════════════════════════════════════════════════════════════════

📊 修改后的行为:

页面加载时:
• select: "商品套图" (选中)
• sceneTypeConfig: 隐藏 ✅ (正确)
• sceneNotesField: 显示 ✅ (正确)
• batchOutputCountField: 显示 ✅ (正确)

切换到 A+详情页:
• sceneTypeConfig: 显示 ✅
• sceneNotesField: 隐藏 ✅
• batchOutputCountField: 隐藏 ✅

切换到服饰穿戴:
• sceneTypeConfig: 隐藏 ✅
• sceneNotesField: 隐藏 ✅
• batchOutputCountField: 隐藏 ✅

切换回商品套图:
• sceneTypeConfig: 隐藏 ✅
• sceneNotesField: 显示 ✅
• batchOutputCountField: 显示 ✅

══════════════════════════════════════════════════════════════════════

✅ 总结:

问题: 页面初始化时显示状态不正确

原因: JavaScript 没有在页面加载时调用初始化函数

解决: 在变量定义后立即调用 toggleConfigByGenType(batchGenType.value)

效果: 页面加载时立即显示正确的初始状态

══════════════════════════════════════════════════════════════════════
""")
