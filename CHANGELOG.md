# 版本说明 (Changelog)

## v10.2 (2026-05-03)

### AI 帮写性能优化：并发 + 先返回卖点

- **AI 帮写改为并发执行**：卖点文案生成与商品结构化提取（product_json）同时启动，不再串行等待
- **卖点先展示**：卖点生成完成后立即写入任务结果，前端轮询时先回填卖点文案，product_json 在后台继续生成
- **前端静默补齐**：product_json 完成后静默写入 `currentProductJson`，用户无感知，后续 A+/生图正常复用
- **实测提速**：串行 23s → 并发 8.88s，总耗时节省 61.4%；首屏等待从 12.77s 降到 6.46s

### A+ 图片生成 Bug 修复

- 修复 `generation/aplus.py` 中 `save_generated_image` 返回 4 个值但只解包 3 个导致的 `too many values to unpack (expected 3)` 错误
- 修复后首屏主视觉、使用场景图等 A+ 模块可正常生成

### 后端新增

- `update_generation_task_partial_result`：支持在任务未最终完成时写入中间结果
- `pollGenericTaskResult` 新增 `onProgress` 回调：前端可在任务运行中读取部分结果

### Docker

- 镜像标签 10.1 → 10.2
- GitHub Action 自动打 `10.2` + `latest` 双标签
- 推送仍由 GitHub Action 自动完成，本地不执行 Docker 推送操作
- `.dockerignore` 继续排除 `.env` 和 `.env.*`

***

## v10.1 (2026-05-02)

### 生成任务异步链路增强

- 重接口继续接入统一 generation task 任务体系，减少长耗时请求阻塞 Web worker
- 支持任务完成时间字段持久化：`created_at_ts`、`updated_at_ts`、`completed_at`、`completed_at_ts`
- Supabase `generation_tasks` 表新增 `trace` JSONB 字段，用于保存任务链路事件

### 完整耗时打点

- 后端记录 `task_created`、`task_running`、`task_result_ready`、`task_succeeded`、`task_polled`
- 图片存储记录 `image_storage_started`、`image_cos_upload_started`、`image_cos_upload_completed`、`image_cos_upload_failed`、`image_local_write_started`、`image_local_write_completed`、`image_storage_completed`
- 前端记录 `frontend_poll_received`、`frontend_success_received`、`frontend_result_render_start`、`frontend_result_render_done`、`image_loaded`
- 新增后端 summary 日志：`Generation task trace summary succeeded/polled_succeeded`
- 新增前端控制台摘要：`render_done_summary`、`image_loaded_summary`
- 支持精确拆分“生成完成”和“页面显示完成”的延迟来源

### 验证

- 已完成真实 fashion-model 同步生图测试
- 已完成 `async_task: true` 异步真实生图测试，并轮询到 `succeeded`
- 已验证任务结果包含完成时间、存储 trace 和任务 trace

### Docker

- 镜像标签 10.0 → 10.1
- GitHub Action 自动打 `10.1` + `latest` 双标签
- 推送仍由 GitHub Action 自动完成，本地不执行 Docker 推送操作
- `.dockerignore` 继续排除 `.env` 和 `.env.*`

***

## v10.0 (2026-05-02)

### 生产运行方式升级

- Docker 镜像已加入 Gunicorn，生产容器不再依赖 Flask 开发服务器启动
- 镜像默认使用 `gunicorn -w 4 -b 0.0.0.0:5078 --timeout 300 --access-logfile - app:app` 运行 Flask 应用
- `requirements.txt` 新增 `gunicorn` 依赖，Docker 构建时自动安装

### Docker

- 镜像标签 9.9 → 10.0
- GitHub Action 自动打 `10.0` + `latest` 双标签
- 推送仍由 GitHub Action 自动完成，本地不执行 Docker 推送操作
- `.dockerignore` 继续排除 `.env` 和 `.env.*`

***

## v9.9 (2026-05-02)

### 多用户性能优化

- **Supabase Session 缓存**：5 分钟缓存（`_SESSION_CACHE`），命中缓存直接返回，减少 99% 的 token 验证 API 调用
- **静态文件缓存**：`Cache-Control: public, max-age=3600`，浏览器缓存 1 小时，消除重复下载
- **后台任务清理**：生成任务清理从每次请求触发改为后台线程每 10 分钟定时执行，消除 O(n) 开销

### 生成任务超时保护

- 新增 `_run_with_timeout` 函数，生成任务 10 分钟超时自动 fail + 积分退款
- 任务再也不永久卡在 running 状态占用 worker

### Worker 优化

- 默认 worker 线程从 2 增至 4（`GENERATION_TASK_WORKERS` 环境变量可调）
- 前端轮询：2.5s→3s，总超时 30min→12min

### Docker

- 镜像标签 9.8 → 9.9
- GitHub Action 自动打 `9.9` + `latest` 双标签

***

## v9.8 (2026-05-02)

### Flask 多线程

- `app.run()` 新增 `threaded=True`，AI 帮写等长耗时请求不再阻塞其他用户的页面加载和 API 调用
- 解决生产环境 AI 帮写时整个服务器响应卡顿的问题

### Chat HTTP 重试优化

- `_run_chat_completion_http` 使用独立 session，HTTP 错误码（503 等）不做自动重试（`status_forcelist=frozenset()`）
- 主 API 失败立刻抛异常走 fallback，节省 4-6s 额外延迟

### SSE/流式兼容 + Fallback 完善

- 新增 SSE 流式格式（`Content-Type: text/event-stream`）解析支持
- Fallback token 扩展：新增 `model_not_found`、`No available channel`、`new_api_error`、`Expecting value`、`JSONDecodeError`
- 主 API 返回非 JSON 格式时自动 fallback，通用兼容性大幅提升

### OpenAI 直连 Ark

- 支持将 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 直接配置为 Ark 豆包的密钥和端点
- 走标准 OpenAI-compatible 协议直连调用，不走 fallback，响应更快
- 测试通过：AI 帮写 \~8s，风格分析 \~15s

### Docker

- 镜像标签 9.7 → 9.8
- GitHub Action 自动打 `9.8` + `latest` 双标签

***

## v9.7 (2026-05-02)

### 积分发放修复 (Critical Bugfix)

- 修复 `grant_payment_points_once` 中 `from points_rules import get_payment_points_amount` 和 `from points_rules import add_user_points` 错误导入——这两个函数在 `app.py` 而非 `points_rules.py`，导致支付回调积分永远不到账
- 调整 `process_success_payment` 执行顺序：先发积分 (`grant_payment_points_once`) 再标记订单 paid (`update_payment_order`)，避免先改状态后崩溃
- 回调重试时对已 paid 订单仍然补发积分（幂等安全，按 `order_no` 去重）

### COS 配置增强

- 新增 `_read_cos_env()` 函数：优先 `os.getenv()` 读环境变量，其次读取 `config.LOCAL_CONFIG`（`config.json`）兜底
- 恢复 `load_dotenv(Path(__file__).resolve().parent / '.env')`，确保本地 `.env` 正常加载
- Docker 中无 `.env` 时自动从 Settings 页面写入的 `config.json` 读取 COS 密钥
- COS 全链路上传/删除测试通过

### COS 桶名校验

- `COS_BUCKET` 必须填腾讯云控制台的纯桶名（如 `aiimg-1234567890`），不能填 CDN 域名，否则报 `bucket format is illegal`

### Docker

- 镜像标签 9.6 → 9.7
- GitHub Action 自动打 `9.7` + `latest` 双标签

***

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

***

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

***

## v9.4 (2026-05-01)

### LLM 优化

- 全模式切 doubao-seed-2-0-mini（Ark 直连），成本 ¥0.008/套
- 套图规划 prompt 精简 63%（7KB→2.6KB），规划耗时 -34s
- 重试间隔全局减半（1.5s→0.5s）

### 生成优化

- b64\_json 回退到 url（b64 反慢 17s）
- 套图三轮优化：165s→121s（-27%）

***

## v9.3 (2026-04-30)

### 新增功能

- mode3 套图并发生成（9 workers，9 张图 \~1 分钟）
- 三层断流重试（API 层 + 补图层 + 下载层）
- A+ 模块 524 自动回退 Ark Chat
- Supabase JSONB 查询编码修复

***

## Docker 镜像标签历史

| 版本    | 标签               | 日期         |
| ----- | ---------------- | ---------- |
| v10.1 | `10.1`, `latest` | 2026-05-02 |
| v10.0 | `10.0`, `latest` | 2026-05-02 |
| v9.9  | `9.9`, `latest`  | 2026-05-02 |
| v9.8  | `9.8`, `latest`  | 2026-05-02 |
| v9.7 | `9.7`, `latest` | 2026-05-02 |
| v9.6 | `9.6`, `latest` | 2026-05-02 |
| v9.5 | `9.5`, `latest` | 2026-05-01 |
| v9.4 | `9.4`           | 2026-05-01 |
| v9.3 | `9.3`           | 2026-04-30 |

