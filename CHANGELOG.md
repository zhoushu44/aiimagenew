# 版本说明 (Changelog)

## v9.6 (2026-05-02)

### COS 图片存储优化
- COS 客户端改为**运行时懒加载**，每次调用 `os.getenv()` 实时读取 `.env` 配置
- 避免 Settings 页面修改后 COS 配置不生效的问题
- 新增 `get_cos_url_prefix()` 函数替代旧的模块级 `COS_URL_PREFIX` 常量
- `/generated/<path>` 路由和 ZIP 下载接口同步使用动态前缀

### Chat Fallback 增强
- 新增 401 认证类错误 token：`401`, `authentication_error`, `auth_unavailable`, `token is expired`, `Invalid API Key`, `Incorrect API key`, `invalid_api_key`
- 主接口 `OPENAI_API_KEY` 过期或失效时，自动切换到 Ark Chat (`ARK_CHAT_API_KEY` + `ARK_CHAT_MODEL`) 备用接口
- 用户无感知切换，不影响文案生成、风格分析、套图规划等功能

### AI 帮写按钮修复
- 页面初始化时自动启用 `aiWriteBtn`（`disabled = false`）
- 不再出现页面加载后按钮持续 disabled 的情况

### VIP 系统文档
- 补充 `vip_plan_config` 和 `zpay_transactions` 完整的建表 SQL
- 全部 AI 提示词（商品文案、风格分析、套图规划、A+ 规划、服饰质检）配置说明
- 积分规则配置与定价说明
- 完整支付链路文档

### Docker
- 镜像标签 9.5 → 9.6
- GitHub Action 自动打 `9.6` + `latest` 双标签
- 平台：`linux/amd64` + `linux/arm64`

---

## v9.5 (2026-05-01)

### 代码重构
- `app.py` 从 7326 行降至 3044 行（-58%）
- 提取 `supabase_client.py`（积分/支付/用户/任务，887 行）
- 提取 `generation/` 包（2570 行）：
  - `modes.py`：mode1/2/3 客户端工厂、单图/并行生成、重试逻辑
  - `planning.py`：LLM Chat、JSON 修复、Suite/Fashion/A+ 规划函数
  - `suite.py` + `aplus.py`：套图/A+ 并行编排
- `app.logger` → 可注入 `logging.Logger`，所有模块独立日志

### 前端整理
- HTML 页面归入 `pages/` 目录
- `static/js/` 和 `static/css/` 目录结构不变

### 代码清理
- 删除 4 个旧测试文件

### 验证
- 全部 42 个路由回归测试通过
- 认证/积分/生图全链路正常
- Docker 镜像 9.5 + latest

---

## v9.4 (2026-05-01)

### LLM 优化
- 全模式切 doubao-seed-2-0-mini（Ark 直连），成本 ¥0.008/套
- 套图规划 prompt 精简 63%（7KB→2.6KB），规划耗时 -34s
- 重试间隔全局减半（1.5s→0.5s）

### 生成优化
- b64_json 回退到 url（b64 反慢 17s）
- 套图三轮优化：165s→121s（-27%）

---

## v9.3 (2026-04-30)

### 新增功能
- mode3 套图并发生成（9 workers，9 张图 ~1 分钟）
- 三层断流重试（API 层 + 补图层 + 下载层）
- A+ 模块 524 自动回退 Ark Chat
- Supabase JSONB 查询编码修复

---

## Docker 镜像标签历史

| 版本 | 标签 | 日期 |
|---|---|---|
| v9.6 | `9.6`, `latest` | 2026-05-02 |
| v9.5 | `9.5`, `latest` | 2026-05-01 |
| v9.4 | `9.4` | 2026-05-01 |
| v9.3 | `9.3` | 2026-04-30 |
