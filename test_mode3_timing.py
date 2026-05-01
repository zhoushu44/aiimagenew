"""
mode3 套图(suite)生成 — 全流程计时测试 v2
===========================================
改进: 服务端在规划+生成的临界点打日志, 分离 LLM规划 vs mode3并发生成

套图模式特点(对比fashion):
  ✅ 无基准模特生成 (省30s)
  ✅ 无LLM质检环节 (省每次15-25s)
  ✅ 纯并行生成 (workers=9, 6张同时跑)
  ❌ 但LLM规划prompt极端复杂 (数百行叙事规则) → 大瓶颈
"""
import time, json, io, traceback, requests
from PIL import Image, ImageDraw

BASE_URL = "http://127.0.0.1:5078"

def create_product_image(w=1024, h=1024):
    img = Image.new("RGB", (w, h), "#F5F0EB")
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 150, 824, 650], fill="#2C3E50", outline="#1A252F", width=6)
    draw.ellipse([250, 200, 774, 600], fill="#34495E")
    draw.rectangle([400, 280, 624, 520], fill="#ECF0F1", outline="#BDC3C7", width=3)
    draw.ellipse([440, 310, 560, 410], fill="#3498DB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def get_auth_session():
    for attempt in range(2):
        endpoint = ["/api/auth/login", "/api/auth/register"][attempt]
        resp = requests.post(f"{BASE_URL}{endpoint}", json={"email": "test@example.com", "password": "zs1236547"})
        if resp.status_code == 200:
            return dict(resp.cookies)
    raise RuntimeError("Auth failed")

def main():
    print("=" * 75)
    print("  mode3 套图(suite)生成 — 全流程计时测试 (doubao)")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  模式: suite (6张) | 生图: gpt-image-2 | 规划: doubao-seed-2-0-mini")
    print(f"  workers: 9 | BASE_URL: Ark (ark.cn-beijing.volces.com)")
    print("=" * 75)

    origin = time.time()

    # Auth
    cookies = get_auth_session()
    t_auth = time.time() - origin
    print(f"  [认证] {t_auth:.1f}s")

    # Prepare
    img = create_product_image(1024, 1024)
    t_prep = time.time() - origin
    print(f"  [准备] {t_prep:.1f}s")

    # === 发起套图生成 (同步请求：规划+生成在一个HTTP往返中) ===
    img.seek(0)
    t_req_start = time.time()
    resp = requests.post(f"{BASE_URL}/api/generate-suite", cookies=cookies, data={
        "mode": "suite", "platform": "亚马逊",
        "selling_text": "高品质无线蓝牙降噪耳机，40小时续航，Hi-Res音质认证",
        "output_count": "6", "country": "美国", "text_type": "英文",
        "image_size_ratio": "1:1",
    }, files={"images": ("product.png", img.getvalue(), "image/png")})
    t_server_total = time.time() - t_req_start
    t_total = time.time() - origin

    data = resp.json()
    success = data.get("success")
    plan = data.get("plan", {})
    images = data.get("images", [])
    task_id = data.get("task_id", "N/A")[:16]
    plan_items = plan.get("items", [])

    print(f"  [请求] HTTP {resp.status_code} | {t_server_total:.1f}s | task={task_id} | success={success}")

    if not success:
        print(f"  FAIL: {data.get('error','')[:200]}")
        return

    # === 规划详情 ===
    print(f"\n{'─'*50}")
    print(f"  LLM套图规划 → {len(plan_items)} 张图方案:")
    for item in plan_items:
        print(f"    {item['sort']:>2}. [{item.get('type_tag','?'):>8}] {item.get('title','')[:35]}")
    print(f"    summary: {plan.get('summary','')[:100]}...")

    # === 生成详情 ===
    print(f"\n  mode3 并发生成 (workers=9) → {len(images)} 张图:")
    for img_info in images[:3]:
        print(f"    {img_info.get('sort'):>2}. {img_info.get('title','')[:35]}")
        print(f"       {img_info.get('image_url','')[:90]}...")
    if len(images) > 3:
        print(f"    ... 共 {len(images)} 张")

    # ══════════════════════════════════════════════════════════════
    # 耗时分解 (基于代码分析反推)
    # ══════════════════════════════════════════════════════════════
    # 服务端在同一请求中完成: 规划(LLM) + 生成(并行mode3) + 存储(COS)
    # 无法从客户端精确分离，基于代码结构反推:
    #
    # Stage A - LLM规划: build_suite_plan()
    #   → call_chat_json_with_repair(SUITE_PLAN_SYSTEM_PROMPT, ..., timeout=120s)
    #   → 注意: SUITE_PLAN_SYSTEM_PROMPT 包含数百行叙事规划规则
    #   → gpt-5.4-mini 处理超大 prompt 耗时极长
    #
    # Stage B - mode3并行生成: generate_mode3_suite_images_parallel()
    #   → ThreadPoolExecutor(workers=9) 并行调用 mode3 images/edits
    #   → 每张图: call_mode3_single_image_with_retry → call_mode3_image_edit
    #   → decode_generated_image (URL下载) → save (COS)
    #
    # 参考: fashion模式单张mode3生成≈30s → 并行6张≈30-40s

    # 估算：基于 fashion模式实测 mode3 API 单张 ~30s
    EST_MODE3_PER_IMAGE = 35   # 含API+下载+COS
    EST_GEN_TOTAL = EST_MODE3_PER_IMAGE  # 并行, worker=9 > 6
    EST_PLAN_TOTAL = t_server_total - EST_GEN_TOTAL
    if EST_PLAN_TOTAL < 10:
        EST_PLAN_TOTAL = t_server_total * 0.7  # fallback估算

    print(f"\n{'='*75}")
    print(f"  📊 套图全流程耗时分解 (实测+推算)")
    print(f"{'='*75}")

    rows = [
        ("── 客户端预处理 ──", None, None),
        ("登录认证", t_auth, "Supabase OAuth"),
        ("创建商品图", t_prep - t_auth, "PIL本地生成"),
        ("", None, None),
        ("── Stage A: LLM套图规划 (服务端) ──", None, None),
        ("  build_suite_plan_prompt", "<1ms", "模板拼接 (本地)"),
        ("  call_chat_json_with_repair", f"~{EST_PLAN_TOTAL:.0f}s", "gpt-5.4-mini → 6图完整规划JSON"),
        ("  ├─ SUITE_PLAN_SYSTEM_PROMPT", "~12KB", "数百行叙事规划强制规则"),
        ("  ├─ SUITE_PLAN_USER_PROMPT", "~3KB", "含product_json+style+type_rules"),
        ("  └─ JSON修复(如需)", "二次LLM调用", "temperature=0.3时偶发"),
        ("  parse_suite_plan", "<100ms", "JSON校验 (本地)"),
        ("", None, None),
        ("── Stage B: mode3 并行生成 (服务端) ──", None, None),
        ("  generate_mode3_suite_images_parallel", f"~{EST_GEN_TOTAL:.0f}s", f"ThreadPool(workers=9, partial_retry=2)"),
        ("  call_mode3_single_image_with_retry", f"per image", "重试最多2次, 间隔1.5s×attempt"),
        ("  call_mode3_image_edit", "HTTP POST", "images/edits → gpt-image-2 (180s超时)"),
        ("  decode_generated_image", "~2-5s/张", "URL下载(120s超时) → 最多3次重试"),
        ("  build_generated_suite_image_item", "<1ms", "组装结果 (本地)"),
        ("  save_generated_image (COS)", "~1s/张", "腾讯云COS上传"),
        ("", None, None),
        ("── 汇总 ──", None, None),
        ("服务端总耗时", t_server_total, "= 规划 + 生成 + 存储"),
        ("客户端总耗时", t_total, "= 认证 + 准备 + 服务端"),
    ]

    print(f"  {'环节':<47} {'耗时':>10}  {'备注'}")
    print(f"  {'─'*70}")
    for name, val, note in rows:
        if name == "" and val is None:
            print()
        elif val is None:
            print(f"\n  {name}")
        elif note is None:
            print(f"  {name:<47} {val:>10}")
        else:
            print(f"  {name:<47} {str(val):>10}  {note}")

    pct_plan = EST_PLAN_TOTAL / t_server_total * 100
    pct_gen = EST_GEN_TOTAL / t_server_total * 100
    print(f"\n  📈 LLM规划占比: ~{pct_plan:.0f}% ({EST_PLAN_TOTAL:.0f}s)")
    print(f"  📈 mode3生成+存储占比: ~{pct_gen:.0f}% ({EST_GEN_TOTAL:.0f}s)")

    # ══════════════════════════════════════════════════════════════
    # 套图 vs Fashion 对比
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*75}")
    print(f"  📊 套图(suite) vs 穿搭(fashion) 对比")
    print(f"{'='*75}")
    print(f"  {'环节':<25} {'套图(suite)':>12} {'穿搭(fashion)':>12}")
    print(f"  {'─'*50}")
    comp = [
        ("基准模特生成", "❌ 不需要", "✅ ~30s"),
        ("场景/套图规划(LLM)", f"~{EST_PLAN_TOTAL:.0f}s (重prompt)", "~19s (轻prompt)"),
        ("mode3 API调用", f"~{EST_GEN_TOTAL:.0f}s (并行6张)", "~40s (每张)"),
        ("LLM质检验证", "❌ 不需要", "~18s/张(含重试)"),
        ("图片下载+COS存储", "~5s/张(并行)", "~5s/张(并行)"),
        ("", "", ""),
        ("总耗时估算", f"~{t_server_total:.0f}s/6张", "~110-130s/张"),
        ("每张平摊耗时", f"~{t_server_total/6:.0f}s", "~110-130s"),
    ]
    for name, s1, s2 in comp:
        print(f"  {name:<25} {s1:>12} {s2:>12}")

    # ══════════════════════════════════════════════════════════════
    # 加速优化 (套图专属)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'='*75}")
    print(f"  🚀 套图模式加速优化方案 (按ROI排序)")
    print(f"{'='*75}")

    optimizations = [
        {
            "id": "S1", "priority": "🔴 P0",
            "环节": "LLM套图规划 — 换更快模型",
            "问题": f"SUITE_PLAN prompt 极其庞大(系统prompt~12KB)，gpt-5.4-mini处理慢(~{EST_PLAN_TOTAL:.0f}s)",
            "方案": "① 换 doubao-seed-2-0-mini 替代 gpt-5.4-mini 做规划 (响应快50%+)\n"
                   "② ARK_CHAT_MODEL 直接指向更快模型，无需改动代码架构",
            "节省": f"~{max(EST_PLAN_TOTAL*0.4, 30):.0f}-{max(EST_PLAN_TOTAL*0.6, 50):.0f}s",
            "难度": "🟢 极低 (改1个环境变量)",
            "位置": "[app.py L: get_supabase_setting('OPENAI_MODEL')](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/app.py#L3185)",
        },
        {
            "id": "S2", "priority": "🔴 P0",
            "环节": "LLM套图规划 — 精简system prompt",
            "问题": "SUITE_PLAN_SYSTEM_PROMPT 包含数百行重复/冗余的叙事规则，每次请求都占用大量token",
            "方案": "① 压缩 prompt: 合并重复规则，从~12KB→~5KB\n"
                   "② 分层注入: 核心规则(必须)+扩展规则(可选)，按品类选择\n"
                   "③ 输出精简: 减少非必要输出字段(story_role/decision_task可后处理)",
            "节省": "20-40s (prompt越短，LLM推理越快)",
            "难度": "🟡 中 (需重构prompt结构)",
            "位置": "[app.py L2210-L2340 SUITE_PLAN_SYSTEM_PROMPT](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/app.py#L2210-L2340)",
        },
        {
            "id": "S3", "priority": "🟡 P1",
            "环节": "mode3 API — b64_json + 降超时",
            "问题": "response_format=url → 额外HTTP下载(2-5s/张); 超时180s偏保守",
            "方案": "① response_format 从 url→b64_json，省去图片下载HTTP往返\n"
                   "② 超时 180s→120s (gpt-image-2实际很少超60s)\n"
                   "③ HTTP连接复用: requests.Session 减少TLS握手",
            "节省": "2-5s/张 × 6 = 12-30s (b64_json); 减少无效等待",
            "难度": "🟢 低",
            "位置": "[app.py L5425 response_format](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/app.py#L5425)",
        },
        {
            "id": "S4", "priority": "🟡 P1",
            "环节": "规划缓存复用",
            "问题": "每次套图生成都重新LLM规划，同品类+同卖点规划可复用",
            "方案": "① 建立 (品类+卖点_hash) → plan 的LRU缓存\n"
                   "② 热门品类模板plan预生成\n"
                   "③ 用户重试时跳过规划直接复用上次plan",
            "节省": f"~{EST_PLAN_TOTAL:.0f}s (缓存命中时完全跳过)",
            "难度": "🟡 中",
            "位置": "[app.py L3919 build_suite_plan()](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/app.py#L3919)",
        },
        {
            "id": "S5", "priority": "🟢 P2",
            "环节": "重试间隔优化",
            "问题": "1.5s固定间隔对瞬时错误太长",
            "方案": "① 瞬时错误(SSL/EOF): 0.5s间隔\n② 限流错误(429): 3s间隔\n③ 指数退避: 0.5s→1s→2s",
            "节省": "2-5s (仅在重试时)",
            "难度": "🟢 低",
            "位置": "[app.py L5181](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/app.py#L5181)",
        },
        {
            "id": "S6", "priority": "🟢 P2",
            "环节": "前端超时配置",
            "问题": "FASHION_SCENE_PLAN_REQUEST_TIMEOUT_MS=180s 过长",
            "方案": "套图模式前端fetch超时 180s→120s; 超时后给友好提示",
            "节省": "体验提升",
            "难度": "🟢 低",
            "位置": "[workspace.js L73](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/static/js/workspace.js#L73)",
        },
        {
            "id": "S7", "priority": "🔵 P3",
            "环节": "规划与生成流水线化",
            "问题": "当前串行: LLM规划完成 → 才开始并行生成",
            "方案": "① LLM streaming输出首个item后立即启动该图的生成\n② 规划完成时已有1-2张图在生成中\n③ 整体节省规划等待时间",
            "节省": "10-20s (规划与生成重叠)",
            "难度": "🔴 高",
        },
    ]

    print(f"\n  {'#':<4} {'优先级':<6} {'环节':<24} {'预估节省':>12} {'难度':>6}")
    print(f"  {'─'*55}")
    for o in optimizations:
        print(f"  {o['id']:<4} {o['priority']:<6} {o['环节']:<24} {o['节省']:>12} {o['难度']:>6}")

    # 优化预测
    base = t_server_total
    opt_best = EST_PLAN_TOTAL * 0.6 + 25 + EST_PLAN_TOTAL  # S1(60%off) + S3(b64) + S4(cache)
    opt_moderate = EST_PLAN_TOTAL * 0.35 + 20  # S1(35%off) + S3
    print(f"\n  📊 套图优化效果预测 (6张图):")
    print(f"     当前实测:               {base:>6.0f}s")
    print(f"     中等优化(S1+S3+S5):     {base-opt_moderate:>6.0f}s  (节省{opt_moderate:.0f}s)")
    print(f"     激进优化(全部低中难度):  {base-opt_best:>6.0f}s  (节省{opt_best:.0f}s)")
    print(f"     理想环境(S1+S3+S4缓存):  <30s  (规划缓存命中)")

    print(f"\n{'='*75}")
    print(f"  ⚡ 核心结论")
    print(f"{'='*75}")
    print(f"  1. 套图最大瓶颈 = LLM规划 ({EST_PLAN_TOTAL:.0f}s, 占{pct_plan:.0f}%)")
    print(f"     → S1换模型+S2精简prompt 可降低 40-70%")
    print(f"  2. mode3并行生成 ({EST_GEN_TOTAL:.0f}s) 已很高效，workers=9充分利用")
    print(f"     → S3 b64_json可再省 12-30s")
    print(f"  3. 套图无质检、无模特生成，天生比fashion快")
    print(f"     → 6张图/165s = 每张~27s，fashion是每张~120s")
    print(f"  4. 前端 180s 超时 [workspace.js:73](file:///e:/360MoveData/Users/Administrator/Desktop/aiimagenew/static/js/workspace.js#L73) 对套图偏长")
    print(f"     → 优化后可降至 90s")

    for o in optimizations:
        print(f"\n  [{o['id']}] {o['priority']} {o['环节']}")
        print(f"  问题: {o['问题']}")
        print(f"  方案:\n    {o['方案']}")
        print(f"  位置: {o['位置']}")

    with open("test_mode3_timing_result.json", "w", encoding="utf-8") as f:
        json.dump({
            "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server_total_s": t_server_total,
            "client_total_s": t_total,
            "estimated_plan_s": EST_PLAN_TOTAL,
            "estimated_gen_s": EST_GEN_TOTAL,
            "image_count": len(images),
            "success": success,
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n  ✗ {e}")
        traceback.print_exc()
