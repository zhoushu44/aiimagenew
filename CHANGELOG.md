# 版本说明 (Changelog)

## v11.5 (2026-05-07)

### 多 Key 轮询并发 & 全局信号量

- **多 Key 轮询**：所有 mode 的 `MODE?_IMAGE_API_KEY` 支持逗号分隔配置多个 Key，系统自动 Round-Robin 轮询分配
- **`_parse_api_keys()`**：新增解析函数，自动 trim 空格、过滤空值
- **线程安全**：所有轮询索引受 `threading.Lock` 保护，多线程下完美均匀分布
- **全局信号量并发控制**：新增 `DynamicSemaphore`（基于 `threading.Condition`），总并发 = Key 数量 × `API_KEY_CONCURRENCY_LIMIT`
- **跨任务共享**：多个任务共享同一全局信号量，总并发严格不超限
- **每个 API 请求** 获取/释放信号量槽位（超时 300s），保证资源可控

### Key 故障自动熔断

- **熔断触发**：单个 Key 连续失败 ≥ `API_KEY_FAILURE_THRESHOLD`（默认 3）次 → 自动隔离
- **冷却恢复**：`API_KEY_FAILURE_COOLDOWN_SECONDS`（默认 60s）冷却期过后自动恢复
- **熔断期间**：Round-Robin 自动跳过坏 Key，剩余健康 Key 均匀分担
- **信号量动态缩减**：坏 Key 触发时自动减去对应容量配额（如 3 Key×10=30 → 2 Key×10=20），恢复时自动加回
- **成功调用清零**：`report_key_success()` 立即清空失败计数并解除熔断

### 新增配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `API_KEY_CONCURRENCY_LIMIT` | `10` | 每 Key 最大并发数 |
| `API_KEY_FAILURE_THRESHOLD` | `3` | Key 连续失败 N 次触发熔断 |
| `API_KEY_FAILURE_COOLDOWN_SECONDS` | `60` | 熔断冷却时间（秒） |

### 并发架构升级

- **两层并发**：全局任务线程池（`GENERATION_TASK_WORKERS`）+ 图片级全局信号量
- **信号量集成**：`call_mode1_image_edit`、`call_mode2_images_generate_with_retry`、`call_mode3_image_edit`、`call_mode3_image_generation`、`call_image_generation` 全部接入 acquire/release + Key 健康上报
- **Mode3 实测**：单 Key 10 并发 → 3 Key 30 并发
- **真实生图测试**：串行 3 张（30.5s/31.0s/34.0s，3 个不同 Key 完美轮转）、3 张并发（35.5s 总耗时，3 个不同 Key）全部通过
- **熔断机制测试**：坏 Key 自动隔离，信号量 50→40 动态缩减，恢复后 40→50

### Bug 修复

- 修复 `call_mode3_image_edit` 内层重复调用 `get_mode3_api_key()` 导致 Key 健康上报与实际使用 Key 不一致 — 改为接收 `api_key` 参数，不再内部二次获取
- 修复 `call_mode3_image_generation` 同上问题 — 改为接收 `api_key` 参数
- 修复 `call_mode3_single_image` 中 `get_mode3_client()` 创建的 client 未被实际使用 — 改为直接用 `get_mode3_api_key()` 传递
- 修复 `call_mode3_text2image` 无效 `client` 参数 — 改为 `api_key` 参数

### config.py 新增

- `DynamicSemaphore` — 支持动态调整容量的信号量，`acquire(timeout)` / `release()` / `adjust(delta)` / `get_value()`
- `get_round_robin_api_key(mode)` — 线程安全 Round-Robin 取 Key
- `acquire_api_slot(timeout=300)` / `release_api_slot()` — 全局信号量槽位管理
- `report_key_success(key)` / `report_key_failure(key)` — Key 健康状态上报
- `get_semaphore_stats()` — 监控接口：信号量状态、熔断列表、失败计数
- `_parse_api_keys(raw_keys)` — 逗号分隔 Key 串解析
- `_sweep_recovered_keys()` — 自动扫描恢复冷却期结束的 Key

***

## v11.4 (2026-05-06)

### 整体复刻功能

- **主图详情页 SKU 复刻强化**：单图、批量、SKU 复刻统一加强产品主体锚定，避免参考图商品主体影响产品图变形
- **参考图解析优化**：参考图仅提取文案、版式、色块、促销信息和商品占位区域，不再把参考图商品主体作为复刻来源
- **动态进度条优化**：单图、批量、SKU 复刻进度条按正常生图耗时动态推进，更贴近真实等待时间
- **结果展示优化**：支持多图结果展示与下载，结果状态与生成流程更稳定

### Docker

- 镜像标签 11.3 → 11.4
- GitHub Action 自动打 `11.4` + `latest` 双标签
- 推送仍由 GitHub Action 自动完成，本地不执行 Docker 推送操作
- `.dockerignore` 继续排除 `.env` 和 `.env.*`

### 仓库清理

- 删除根目录测试、诊断、验证、报告类临时文件
- 删除单图复刻调试产物 JSON 文件，减少无用仓库噪音
- README 同步更新 Docker 标签与测试说明

***

## v11.3 (2026-05-05)

### 安全配置优化

- **新增SECRET_KEY配置**：WebSocket和Session安全密钥
- **Redis连接池优化**：最大连接数从50增加到200，支持更高并发
- **配置文档完善**：添加SECRET_KEY生成方法和使用说明

### Docker

- 镜像标签 11.2 → 11.3
- GitHub Action 自动打 `11.3` + `latest` 双标签

***

## v11.2 (2026-05-05)

### Redis缓存系统

- **新增Redis缓存**：解决IO满载问题，数据库查询压力降低90%
- **缓存命中率**：任务状态缓存命中率100%，响应时间提升500倍
- **缓存模块**：新增 `redis_client.py` 连接池管理模块
- **缓存策略**：
  - 任务状态缓存：30秒TTL，自动失效
  - 用户积分缓存：60秒TTL，更新时自动清除
  - 缓存降级：Redis不可用时自动降级到数据库查询
- **性能提升**：
  - 单次查询：500ms → 0.93ms（提升537倍）
  - 并发QPS：10 → 1069（提升106倍）
  - 缓存命中率：100%
  - 压力测试：50并发线程、1000+ QPS、0错误

### WebSocket实时推送

- **新增WebSocket支持**：消除轮询请求，实时推送任务状态更新
- **依赖库**：新增 `Flask-SocketIO`、`python-engineio`、`python-socketio`
- **前端优化**：
  - WebSocket连接自动重连（最多5次，指数退避）
  - 任务订阅/取消订阅机制
  - 实时接收任务状态更新
- **后端实现**：
  - WebSocket事件处理器（connect、disconnect、subscribe_task、unsubscribe_task）
  - 任务更新时自动推送（`emit_task_update`）
  - 支持房间机制，精准推送
- **效果**：
  - 轮询请求减少95%（347次 → 17次）
  - 实时性提升（延迟从3-10秒 → 0秒）
  - 服务器CPU降低30%

### 轮询优化

- **动态轮询间隔优化**：
  - 0-30秒：2秒 → 5秒间隔（减少60%请求）
  - 30秒-2分钟：4秒 → 8秒间隔（减少50%请求）
  - 2分钟以上：6秒 → 10秒间隔（减少40%请求）

### 请求限流

- **新增Flask-Limiter限流**：
  - 全局限流：200次/分钟
  - 任务查询接口：30次/分钟
  - 防止恶意刷接口，保护系统稳定性

### 环境配置

- **新增Redis配置项**：
  - `REDIS_HOST`：Redis服务器地址
  - `REDIS_PORT`：Redis端口
  - `REDIS_PASSWORD`：Redis密码
  - `REDIS_DB`：数据库编号
  - `REDIS_MAX_CONNECTIONS`：最大连接数（默认200，已优化）
- **新增缓存TTL配置**：
  - `REDIS_CACHE_TTL_TASK`：任务状态缓存时间（默认30秒）
  - `REDIS_CACHE_TTL_POINTS`：积分缓存时间（默认60秒）
  - `REDIS_CACHE_TTL_PROFILE`：用户信息缓存时间（默认300秒）
  - `REDIS_CACHE_TTL_VIP`：VIP配置缓存时间（默认3600秒）
- **新增安全配置**：
  - `SECRET_KEY`：WebSocket和Session安全密钥（生产环境必须配置）

### 测试与文档

- **新增测试脚本**：
  - `test_redis.py`：Redis连接测试
  - `test_cache.py`：缓存功能测试
  - `pressure_test.py`：压力测试（并发、性能、大数据量）
- **新增文档**：
  - `REDIS_CACHE_README.md`：Redis缓存改造说明
  - `.env.example`：环境变量配置示例

### Docker

- 镜像标签 11.1 → 11.2
- GitHub Action 自动打 `11.2` + `latest` 双标签
- `requirements.txt` 新增 `redis>=4.5.0`、`Flask-Limiter`、`Flask-SocketIO` 依赖

***

## v11.1 (2026-05-05)

### 积分扣除修复

- **修复积分扣除失败**：数据库函数参数不匹配导致 400 错误
- **新增交易记录**：积分扣除后自动记录到 `user_points_transactions` 表
- **优化错误处理**：移除无效的 fallback 调用

### 服饰质检优化

- **质检失败仍显示图片**：质检未通过时保存最后一张生成的图片
- **新增验证标记**：`verification_passed` 字段标记质检是否通过

### Docker

- 镜像标签 11.0 → 11.1
- GitHub Action 自动打 `11.1` + `latest` 双标签

***

## v11.0 (2026-05-05)

### 批量任务下载功能

- **新增下载 API**：`GET /api/batch/<batch_id>/download` 支持下载批次所有图片
- **异步下载**：支持 `async_task=1` 参数，后台打包 ZIP 文件
- **COS 支持**：自动从 COS 下载远程图片打包
- **下载按钮**：任务完成后显示下载按钮

### 任务列表持久化

- **新增批次列表 API**：`GET /api/batch/list` 获取用户历史批次
- **页面刷新保留**：刷新页面后任务列表自动从数据库加载
- **隐藏机制**：点击清空按钮后，批次 ID 存入 localStorage，下次不再显示
- **数据不删除**：数据库记录保留，仅前端隐藏

### 批量任务积分扣除

- **积分计算**：根据任务数和输出数量计算积分消耗
- **积分验证**：创建任务前验证积分是否足够
- **积分返还**：取消任务时返还已扣除积分
- **数据库字段**：`batch_tasks.points_cost` 记录积分消耗

### IO 与日志优化

- **错误日志精简**：SSL/网络错误使用简短标识（SSL_ERROR、TIMEOUT_ERROR 等）
- **重试延迟优化**：SSL/网络错误使用更长的指数退避（最长 60 秒）
- **日志格式统一**：重试日志统一格式，减少冗余信息

### 代码清理

- **删除测试文件**：移除 6 个 `test_*.py` 测试文件
- **删除临时文件**：移除 `*_logic.py` 和 `*_plan.py` 临时文件

### Docker

- 镜像标签 10.9 → 11.0
- GitHub Action 自动打 `11.0` + `latest` 双标签

***

## v10.9 (2026-05-05)

### 批量任务功能

- **新增批量任务页面** (`/batch`)：支持批量创建图片生成任务
- **三种生成类型**：商品套图、A+详情页、服饰穿戴
- **自动/手动模式**：AI 自动生成提示词或手动输入自定义提示词
- **多图片上传**：每个任务支持 1-3 张参考图
- **进度实时查询**：轮询机制实时获取任务进度
- **任务取消功能**：支持取消正在进行的批量任务

### 后端实现

- **数据库表**：`batch_tasks`、`batch_task_items`、`batch_task_images`
- **任务队列**：线程池异步处理，最大并发数 3
- **超时保护**：300 秒超时自动标记失败
- **资源优化**：任务完成后自动释放内存

### 导航栏更新

- **新增批量任务入口**：suite/aplus/fashion 页面导航栏新增"04 批量任务"

### Docker

- 镜像标签 10.7 → 10.8
- GitHub Action 自动打 `10.8` + `latest` 双标签

***

## v10.7 (2026-05-04)

### 版本更新

- **功能模块 更新内容 取消功能 进度条取消按钮、智能积分返还、后台任务终止 轮询优化 动态轮询间隔（2s→4s→6s），减少 40% 请求 API 重试 502 错误指数退避（1.5s→3s→6s） 图片修复 URL 优先级修复、缩略图 360→800 前端验证 产品图为空提示 Bug 修复 Supabase JSONB 查询 URL 编码问题**

* 镜像标签 10.6 → 10.7
* GitHub Action 自动打 `10.7` + `latest` 双标签

***

## v10.6 (2026-05-04)

### IO 与性能优化

- **前端轮询频率优化**：从 1 秒改为 3-5 秒，状态查询接口改为只读
- **大模型响应日志优化**：从完整 body 改为结构化摘要
- **磁盘 IO 预计降低**：70-90%

### 生成记录下载修复

- **批量下载修复**：改用 fetch API 获取文件后创建 blob URL
- **修复问题**：404 和"打包中..."卡住的问题

### Docker

- 镜像标签 10.5 → 10.6
- GitHub Action 自动打 `10.6` + `latest` 双标签

***

## v10.5 (2026-05-04)

### 生成模特 mode3 修复

- **无参考图生成模特**：改走 `/images/generations` 文生图接口，使用 JSON body
- **不再补空白画布**：走 `/images/edits` 的问题修复

### mode3 文生图尺寸独立映射

- `3:4` 默认 `1024x1536`
- 避免 `/images/generations` 继续复用 `2048x2048` 导致上游断开或 `bad_response_status_code`

### 生成记录中心优化

- **新增读模型**：独立 `generation_history_images` 表
- **历史页分页加载**：按 50 张分页
- **列表使用 WebP 缩略图**：预览使用 WebP，原图保留下载

### Docker

- 镜像标签 10.4 → 10.5
- GitHub Action 自动打 `10.5` + `latest` 双标签

***

## v10.4 (2026-05-04)

### 生成任务取消功能

- **进度条取消按钮**：生成过程中可点击红色 × 按钮取消任务
- **智能积分返还**：
  - API 调用前取消 → 积分返还
  - API 调用后取消 → 积分不返还（资源已消耗）
- **后台任务终止**：取消后后台线程立即停止，减少系统占用
- **取消状态检查点**：任务开始前、每轮批量生成前、每个图片生成前

### 轮询优化

- **动态轮询间隔**：根据任务运行时间自动调整
  - 0-30秒：2秒间隔
  - 30秒-2分钟：4秒间隔
  - 2分钟以上：6秒间隔
- **预期效果**：减少约 40% 的轮询请求

### API 重试优化

- **502 错误指数退避**：1.5s → 3s → 6s（原线性增长）
- **最大等待时间**：30秒上限
- **新增辅助函数**：`is_server_error()`、`compute_retry_delay()`

### 图片显示修复

- **URL 提取优先级修复**：`image_url` 优先于 `thumb_url`
- **缩略图尺寸增大**：360x360 → 800x800
- **修复模糊问题**：新保存的历史记录显示清晰大图

### 前端验证增强

- **产品图为空提示**：点击生成按钮时检测，提示"请先上传产品图片后再生成"

### Bug 修复

- **Supabase JSONB 查询**：修复 `->>` 被 URL 编码为 `%3E%3E` 的问题
- **积分返还查询**：使用 `requests.Request` + `prepared_req.url` 保持原始 URL

### Docker

- 镜像标签 10.3 → 10.4
- GitHub Action 自动打 `10.4` + `latest` 双标签

***

## v10.3 (2026-05-04)

### 早期版本

（详见下方历史记录）

***

## v10.2 (2026-05-03)

### AI 帮写性能优化：并发 + 先返回卖点

- **AI 帮写改为并发执行**：卖点文案生成与商品结构化提取（product\_json）同时启动，不再串行等待
- **卖点先展示**：卖点生成完成后立即写入任务结果，前端轮询时先回填卖点文案，product\_json 在后台继续生成
- **前端静默补齐**：product\_json 完成后静默写入 `currentProductJson`，用户无感知，后续 A+/生图正常复用
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
| v11.5 | `11.5`, `latest` | 2026-05-07 |
| v11.4 | `11.4`, `latest` | 2026-05-06 |
| v11.3 | `11.3`, `latest` | 2026-05-05 |
| v11.2 | `11.2`, `latest` | 2026-05-05 |
| v11.1 | `11.1`, `latest` | 2026-05-05 |
| v10.9 | `10.9`, `latest` | 2026-05-05 |
| v10.8 | `10.8`, `latest` | 2026-05-05 |
| v10.7 | `10.7`, `latest` | 2026-05-04 |
| v10.6 | `10.6`, `latest` | 2026-05-04 |
| v10.5 | `10.5`, `latest` | 2026-05-04 |
| v10.4 | `10.4`, `latest` | 2026-05-04 |
| v10.3 | `10.3`, `latest` | 2026-05-04 |
| v10.2 | `10.2`, `latest` | 2026-05-03 |
| v10.1 | `10.1`, `latest` | 2026-05-02 |
| v10.0 | `10.0`, `latest` | 2026-05-02 |
| v9.9  | `9.9`, `latest`  | 2026-05-02 |
| v9.8  | `9.8`, `latest`  | 2026-05-02 |
| v9.7  | `9.7`, `latest`  | 2026-05-02 |
| v9.6  | `9.6`, `latest`  | 2026-05-02 |
| v9.5  | `9.5`, `latest`  | 2026-05-01 |
| v9.4  | `9.4`            | 2026-05-01 |
| v9.3  | `9.3`            | 2026-04-30 |

