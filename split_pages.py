from pathlib import Path
import re

root = Path("C:/Users/zs/Desktop/aiimagenew")
text = (root / "index.html").read_text(encoding="utf-8")

nav_template = """<aside class=\"side-nav\" aria-label=\"功能导航\">
          <a class=\"nav-item{suite_active}\" href=\"/suite\" data-mode=\"suite\" data-nav-link=\"true\" aria-pressed=\"{suite_pressed}\">
            <span class=\"nav-item-index\">01</span>
            <span class=\"nav-item-label\">商品套图</span>
          </a>
          <a class=\"nav-item{aplus_active}\" href=\"/aplus\" data-mode=\"aplus\" data-nav-link=\"true\" aria-pressed=\"{aplus_pressed}\">
            <span class=\"nav-item-index\">02</span>
            <span class=\"nav-item-label\">A+详情页</span>
          </a>
          <a class=\"nav-item{fashion_active}\" href=\"/fashion\" data-mode=\"fashion\" data-nav-link=\"true\" aria-pressed=\"{fashion_pressed}\">
            <span class=\"nav-item-index\">03</span>
            <span class=\"nav-item-label\">服饰穿戴</span>
          </a>
        </aside>"""

fashion_config = """      fashion: {
        title: 'AI服饰穿戴',
        description: '上传服饰商品图后，系统会按穿搭展示、模特氛围、卖点层级与平台展示逻辑生成更适合服装类商品的视觉方案，适合做穿搭套图与展示页素材。',
        note: 'Editorial Styling / Model Story / Outfit Focus / Fashion Contrast',
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
"""

landing_html = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>AI电商视觉工作台</title>
  <style>
    :root {
      --bg: #f3f1ec;
      --surface: rgba(255, 253, 248, 0.88);
      --panel: #fffdf8;
      --fg: #111111;
      --muted: #5e5a54;
      --accent: #d72828;
      --border: #111111;
      --shadow: 0 24px 60px rgba(17, 17, 17, 0.08);
      --font: Inter, \"Helvetica Neue\", Arial, \"PingFang SC\", \"Microsoft YaHei\", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--font);
      color: var(--fg);
      background:
        linear-gradient(rgba(17,17,17,0.08) 1px, transparent 1px),
        linear-gradient(90deg, rgba(17,17,17,0.08) 1px, transparent 1px),
        var(--bg);
      background-size: 28px 28px, 28px 28px, auto;
    }
    .shell {
      width: min(1280px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 18px 20px;
      border: 3px solid var(--border);
      background: rgba(248, 246, 241, 0.94);
      backdrop-filter: blur(8px);
    }
    .eyebrow, .bullet, .meta {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .logo {
      font-size: clamp(28px, 5vw, 64px);
      line-height: 0.92;
      font-weight: 900;
      letter-spacing: -0.08em;
      text-transform: uppercase;
      margin-top: 8px;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 24px;
      margin-top: 24px;
    }
    .hero-main, .hero-side, .module-card, .note-panel {
      border: 3px solid var(--border);
      background: var(--surface);
      box-shadow: var(--shadow);
    }
    .hero-main {
      padding: 28px;
      display: grid;
      gap: 20px;
      min-height: 420px;
      align-content: space-between;
    }
    .hero-side {
      padding: 24px;
      display: grid;
      gap: 18px;
      align-content: start;
    }
    .hero-copy {
      max-width: 820px;
      font-size: clamp(18px, 2.2vw, 26px);
      line-height: 1.5;
      color: #24211d;
    }
    .hero-title {
      font-size: clamp(48px, 9vw, 116px);
      line-height: 0.88;
      letter-spacing: -0.08em;
      font-weight: 900;
      max-width: 860px;
      text-transform: uppercase;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 56px;
      padding: 0 22px;
      border: 3px solid var(--border);
      text-decoration: none;
      color: var(--fg);
      font-weight: 800;
      letter-spacing: 0.04em;
      background: var(--panel);
    }
    .btn.primary { background: var(--accent); color: #fff; }
    .btn:hover { transform: translate(-2px, -2px); box-shadow: 8px 8px 0 var(--border); }
    .modules {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 24px;
      margin-top: 24px;
    }
    .module-card {
      padding: 24px;
      display: grid;
      gap: 18px;
      min-height: 380px;
      align-content: space-between;
    }
    .module-no {
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0.2em;
      color: var(--accent);
    }
    .module-title {
      font-size: 36px;
      line-height: 0.96;
      font-weight: 900;
      letter-spacing: -0.06em;
    }
    .module-desc {
      font-size: 18px;
      line-height: 1.65;
      color: #2f2b27;
    }
    .module-points {
      display: grid;
      gap: 10px;
      padding: 0;
      margin: 0;
      list-style: none;
    }
    .module-points li {
      display: flex;
      gap: 10px;
      line-height: 1.55;
      color: #282521;
    }
    .bullet { min-width: 52px; }
    .note-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 24px;
      margin-top: 24px;
    }
    .note-panel { padding: 20px; }
    .meta { margin-bottom: 10px; }
    @media (max-width: 980px) {
      .hero, .modules, .note-grid { grid-template-columns: 1fr; }
      .shell { width: min(100vw - 24px, 1280px); }
      .hero-title { font-size: clamp(42px, 16vw, 88px); }
    }
  </style>
</head>
<body>
  <div class=\"shell\">
    <header class=\"topbar\">
      <div>
        <div class=\"eyebrow\">AI Commerce Visual Workspace</div>
        <div class=\"logo\">Three Modules<br>One Workflow</div>
      </div>
      <a class=\"btn primary\" href=\"/suite\">进入工作台</a>
    </header>

    <section class=\"hero\">
      <div class=\"hero-main\">
        <div>
          <div class=\"eyebrow\">Swiss Grid / Editorial Commerce / Product System</div>
          <div class=\"hero-title\">AI 电商视觉生成工作台</div>
        </div>
        <div class=\"hero-copy\">把原来的单页操作拆成三个独立模块：首页只负责分发入口，侧边导航进入不同页面继续工作。商品套图、A+详情页、服饰穿戴各自保留独立任务语义，但沿用统一的上传、卖点分析、风格分析与结果管理体验。</div>
        <div class=\"hero-actions\">
          <a class=\"btn primary\" href=\"/suite\">商品套图</a>
          <a class=\"btn\" href=\"/aplus\">A+详情页</a>
          <a class=\"btn\" href=\"/fashion\">服饰穿戴</a>
        </div>
      </div>
      <aside class=\"hero-side\">
        <div>
          <div class=\"meta\">output system</div>
          <div>统一保留上传素材、AI 帮写、风格分析、结果筛选、预览和下载能力。</div>
        </div>
        <div>
          <div class=\"meta\">navigation</div>
          <div>侧边导航改为真实页面切换，不再只是单页内模式切换。</div>
        </div>
        <div>
          <div class=\"meta\">design direction</div>
          <div>延续当前项目的海报式对比、硬边框、红色强调和编辑排版节奏。</div>
        </div>
      </aside>
    </section>

    <section class=\"modules\">
      <article class=\"module-card\">
        <div>
          <div class=\"module-no\">01</div>
          <div class=\"module-title\">商品套图</div>
        </div>
        <div class=\"module-desc\">适合常规商品主图、卖点图、场景图、细节图、参数图等整套电商图像输出。</div>
        <ul class=\"module-points\">
          <li><span class=\"bullet\">Hero</span><span>按平台和输出张数自动规划整套图像结构。</span></li>
          <li><span class=\"bullet\">Style</span><span>生成多组可选风格作为后续出图参考。</span></li>
          <li><span class=\"bullet\">Result</span><span>支持任务结果筛选、批量下载与标题建议。</span></li>
        </ul>
        <a class=\"btn primary\" href=\"/suite\">进入商品套图</a>
      </article>
      <article class=\"module-card\">
        <div>
          <div class=\"module-no\">02</div>
          <div class=\"module-title\">A+详情页</div>
        </div>
        <div class=\"module-desc\">适合按模块组织详情页视觉内容，覆盖主视觉、卖点分栏、细节放大、品牌故事、参数信息等结构。</div>
        <ul class=\"module-points\">
          <li><span class=\"bullet\">Module</span><span>按 A+ 模块选择生成内容，更适合详情页排版。</span></li>
          <li><span class=\"bullet\">Logic</span><span>保留原有模块选择和顺序输出能力。</span></li>
          <li><span class=\"bullet\">Preview</span><span>结果视图继续支持逐张查看和下载。</span></li>
        </ul>
        <a class=\"btn primary\" href=\"/aplus\">进入A+详情页</a>
      </article>
      <article class=\"module-card\">
        <div>
          <div class=\"module-no\">03</div>
          <div class=\"module-title\">服饰穿戴</div>
        </div>
        <div class=\"module-desc\">面向服装、穿搭、模特展示等场景，以穿搭叙事、氛围和材质表达组织结果。</div>
        <ul class=\"module-points\">
          <li><span class=\"bullet\">Look</span><span>强调穿搭展示、模特氛围和服装主体统一性。</span></li>
          <li><span class=\"bullet\">Flow</span><span>沿用套图生成链路，但文案和界面语义改为服饰场景。</span></li>
          <li><span class=\"bullet\">Ready</span><span>适合作为服装商品图、穿搭素材和展示图入口。</span></li>
        </ul>
        <a class=\"btn primary\" href=\"/fashion\">进入服饰穿戴</a>
      </article>
    </section>

    <section class=\"note-grid\">
      <div class=\"note-panel\">
        <div class=\"meta\">01 / structure</div>
        <div>首页只做分发，实际工作都在独立页面里完成。</div>
      </div>
      <div class=\"note-panel\">
        <div class=\"meta\">02 / consistency</div>
        <div>三个模块共用相同的视觉系统，保留一致操作手感。</div>
      </div>
      <div class=\"note-panel\">
        <div class=\"meta\">03 / compatibility</div>
        <div>继续兼容现有 Flask API 与上传 FormData 结构。</div>
      </div>
    </section>
  </div>
</body>
</html>
"""

def build_nav(active: str) -> str:
    return nav_template.format(
        suite_active=" active" if active == "suite" else "",
        aplus_active=" active" if active == "aplus" else "",
        fashion_active=" active" if active == "fashion" else "",
        suite_pressed="true" if active == "suite" else "false",
        aplus_pressed="true" if active == "aplus" else "false",
        fashion_pressed="true" if active == "fashion" else "false",
    )

def build_page(mode: str, title: str) -> str:
    page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", text, count=1)
    page = page.replace("<body>", f"<body data-page-mode=\"{mode}\">", 1)
    page = re.sub(r"<aside class=\"side-nav\"[\s\S]*?</aside>", build_nav(mode), page, count=1)
    page = page.replace(
        "      },\n    };\n    const defaultStyleBtnLabel",
        "      },\n" + fashion_config + "    };\n    const defaultStyleBtnLabel",
        1,
    )
    page = page.replace(
        "let currentMode = 'suite';",
        "const PAGE_MODE = document.body.dataset.pageMode || 'suite';\n    let currentMode = PAGE_MODE;",
        1,
    )
    page = page.replace(
        "    const getCurrentModeConfig = () => modeConfig[currentMode] || modeConfig.suite;\n",
        "    const getCurrentModeConfig = () => modeConfig[currentMode] || modeConfig.suite;\n    const modePlanLabelMap = { suite: '套图', aplus: 'A+ 模块', fashion: '服饰穿搭图' };\n",
        1,
    )
    page = page.replace(
        "      currentMode = mode === 'aplus' ? 'aplus' : 'suite';",
        "      currentMode = ['suite', 'aplus', 'fashion'].includes(mode) ? mode : PAGE_MODE;",
        1,
    )
    page = page.replace(
        "      moreActions.hidden = currentMode !== 'suite';",
        "      moreActions.hidden = currentMode === 'aplus';",
        1,
    )
    page = page.replace(
        "          : `选择后会把该风格作为${currentMode === 'aplus' ? 'A+ 模块' : '套图'}规划参考。`;",
        "          : `选择后会把该风格作为${modePlanLabelMap[currentMode] || '套图'}规划参考。`;",
        1,
    )
    return page

(root / "landing.html").write_text(landing_html, encoding="utf-8")
(root / "suite.html").write_text(build_page("suite", "AI商品套图"), encoding="utf-8")
(root / "aplus.html").write_text(build_page("aplus", "AI A+详情页"), encoding="utf-8")
(root / "fashion.html").write_text(build_page("fashion", "AI服饰穿戴"), encoding="utf-8")
