# AI Image New

基于 Flask + Gunicorn 的 AI 图片生成与会员支付项目，支持 Supabase 登录、积分、会员套餐、ZPay 支付、支付回调、订阅续期和前端账号面板。

## 功能概览

- Flask 2.x 后端，Docker 生产镜像使用 Gunicorn 启动（`app:app`）
- Supabase Auth 登录与后端 session 同步（httpOnly Cookie）
- 积分系统：注册奖励、每日签到、按量消费、失败自动退款
- AI 图片生成：3 种 App Mode（mode1/mode2/mode3），支持文生图/图生图
- 套图（Suite）生成：6 张电商详情页套图，LLM 规划 + 并行生成
- A+ 详情页生成：结构化电商 A+ 模块图文
- 服饰穿搭（Fashion）：AI 模特生成、场景规划、成图质检
- 生成任务持久化：支持刷新恢复、状态轮询、失败自动返还积分
- 任务链路耗时打点：后端生成、图片存储、前端轮询、渲染和图片加载均可拆分排查
- LLM Chat 双模式：Ark 直连为主，自动 fallback 到备选接口
- ZPay 支付：创建订单、异步回调验签、一次性/订阅购买
- 订阅续期自动叠加，会员状态实时展示
- COS/CDN 图片存储，自动生成公网 URL
- 配置支持 `.env` + 本地 `config.json`（Settings 页面实时编辑）

## 目录结构

```text
.
├── app.py                    # Flask 主应用（3044 行）
├── config.py                 # 全局配置与环境变量
├── supabase_client.py        # Supabase REST 操作（积分、支付、用户、任务）
├── utils.py                  # 通用工具函数
├── image_utils.py            # 图片处理、编解码、保存、上传
├── prompts.py                # 所有 LLM System/User Prompt 模板
├── points_rules.py           # 积分规则定义与计价
├── cos_utils.py              # 腾讯云 COS 上传/管理
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 镜像构建
├── .dockerignore             # 排除 .env 等敏感文件
│
├── pages/                    # 前端 HTML 页面
│   ├── landing.html          # 首页
│   ├── auth.html             # 登录/注册页面
│   ├── suite.html            # 套图工作台
│   ├── aplus.html            # A+ 详情页工作台
│   ├── fashion.html          # 服饰穿搭工作台
│   └── settings.html         # 配置管理页面
│
├── generation/               # AI 生图模块
│   ├── __init__.py           # 统一导出
│   ├── modes.py              # mode1/2/3 客户端、并行/重试、图片编解码
│   ├── planning.py           # LLM Chat、JSON 修复、Suite/Fashion/A+ 规划
│   ├── suite.py              # 套图并行生成编排
│   └── aplus.py              # A+ 模块生成编排
│
├── static/
│   ├── css/
│   │   ├── landing.css       # 首页样式
│   │   └── workspace.css     # 工作台样式
│   └── js/
│       ├── shared-topbar.js  # 顶部栏、登录弹窗、账号面板、VIP 支付
│       └── workspace.js      # 工作台交互逻辑
│
├── supabase/
│   └── migrations/           # 数据库迁移 SQL
│
└── .github/
    └── workflows/
        └── docker-publish.yml # GitHub Action 自动构建推送镜像
```

## 环境要求

- Python 3.10+
- pip
- 可访问 Supabase 项目
- 可访问 ZPay 支付网关（可选）
- 需要公网地址或 FRP 内网穿透来接收支付回调（可选）

## 安装与启动

```bash
pip install -r requirements.txt
python app.py
```

本地开发可直接使用 `python app.py` 启动 Flask 开发服务，默认监听 `http://127.0.0.1:5078`。可通过 `.env` 中 `HOST` / `PORT` 配置。

生产/Docker 镜像已加入 Gunicorn，并通过 `app:app` 启动：

```bash
gunicorn -w 4 -b 0.0.0.0:5078 --timeout 300 --access-logfile - app:app
```

## Docker 镜像发布

通过 GitHub Action 自动构建并推送 Docker 镜像，**不需要本地手动执行**。

| 触发条件 | 标签 |
|----------|------|
| 推送到 `main` 分支 | `10.0` + `latest` |
| GitHub Actions 手动触发 | `10.0` + `latest` |

- 构建平台：`linux/amd64` + `linux/arm64`
- 镜像内使用 Gunicorn 运行 Flask 应用：`gunicorn -w 4 -b 0.0.0.0:5078 --timeout 300 --access-logfile - app:app`
- 宝塔 Docker 部署时如果容器 `command` 被手动设置为 `python app.py`，需要改为上面的 Gunicorn 命令，否则仍会启动 Flask 开发服务器
- `.dockerignore` 已排除 `.env` 和 `.env.*`
- 工作流文件：[docker-publish.yml](.github/workflows/docker-publish.yml)

### 宝塔 Docker 部署检查

容器启动命令应为：

```bash
gunicorn -w 4 -b 0.0.0.0:5078 --timeout 300 --access-logfile - app:app
```

正确启动日志应包含：

```text
[INFO] Starting gunicorn
[INFO] Listening at: http://0.0.0.0:5078
[INFO] Booting worker with pid: ...
```

如果日志仍出现 `WARNING: This is a development server.`，说明容器仍在运行 `python app.py`，Gunicorn 生产启动方式未生效。

推荐 Nginx 反代到本机容器端口：

```nginx
proxy_pass http://127.0.0.1:5078;
proxy_connect_timeout 60s;
proxy_send_timeout 600s;
proxy_read_timeout 600s;
send_timeout 600s;
proxy_buffering off;
```

GitHub 仓库需要配置 Secrets：
- `DOCKER_HUB_USERNAME` — Docker Hub 用户名
- `DOCKER_HUB_TOKEN` — Docker Hub Access Token

---

## .env 配置参考

### Flask

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `5078` | 监听端口 |
| `FLASK_DEBUG` | `false` | 调试模式 |
| `APP_MODE` | `mode1` | 生图模式：`mode1` / `mode2` / `mode3`（可在 Settings 页面切换） |
| `UPLOAD_MAX_BYTES` | `15728640` | 上传总大小限制（15MB），可以在 Settings 页面调整 |
| `UPLOAD_MAX_FILE_BYTES` | `8388608` | 单张图片大小限制（8MB） |
| `GENERATED_SUITE_RETENTION_DAYS` | `7` | 生成图片保留天数 |
| `GENERATED_SUITE_RETENTION_COUNT` | `20` | 最多保留的任务目录数 |

### OpenAI 兼容接口（Chat / 套图规划 / 风格分析）

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `OPENAI_API_KEY` | 是 | 接口密钥 |
| `OPENAI_BASE_URL` | 是 | 接口地址 |
| `OPENAI_MODEL` | 是 | 模型名 |
| `CHAT_FALLBACK_TO_ARK` | 否 | 主接口失败时自动切 Ark（默认 `auto`） |
| `ARK_CHAT_API_KEY` | 否 | 备选 Ark Chat 密钥 |
| `ARK_CHAT_BASE_URL` | 否 | 备选 Ark Chat 地址 |
| `ARK_CHAT_MODEL` | 否 | 备选 Ark Chat 模型 |
| `SUITE_PLAN_TIMEOUT_SECONDS` | 否 | 套图规划超时秒数（默认 `180`，最小 `60`） |

### Mode1 图片生成（Ark 豆包）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MODE1_IMAGE_API_KEY` | — | API 密钥 |
| `MODE1_IMAGE_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | 接口地址 |
| `MODE1_IMAGE_MODEL` | `doubao-seedream-5-0-260128` | 生图模型 |

### Mode2 图片生成（即梦）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MODE2_IMAGE_API_KEY` | `any-value` | API 密钥 |
| `MODE2_IMAGE_BASE_URL` | — | 接口地址 |
| `MODE2_IMAGE_MODEL` | `jimeng-4.6` | 生图模型 |
| `MODE2_SAMPLE_STRENGTH` | `0.65` | 参考图强度 |
| `MODE2_ALLOWED_IMAGE_HOSTS` | — | 远程图片域名白名单 |

### Mode3 图片生成（gpt-image-2）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MODE3_IMAGE_API_KEY` | — | API 密钥 |
| `MODE3_IMAGE_BASE_URL` | `https://code.ciyuanapi.xyz/v1` | 接口地址 |
| `MODE3_IMAGE_MODEL` | `gpt-image-2` | 生图模型 |

以上均支持 fallback 到 `IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`（通用配置），即只需要在对应 mode 不同时才写 `MODE?_` 前缀。

### 并行生成（所有 mode 通用）

`PARALLEL_WORKERS`、`RETRY_ATTEMPTS`、`RETRY_DELAY_SECONDS`、`PARTIAL_RETRY_ATTEMPTS`、`SEQUENTIAL_GENERATION`、`TIMEOUT_SECONDS` 对所有 mode 生效。如需单独覆盖，在对应 env var 前加 `MODE1_`/`MODE2_`/`MODE3_` 前缀，优先级：`MODE3_PARALLEL_WORKERS` > `PARALLEL_WORKERS` > 默认值 3。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `PARALLEL_WORKERS` | `3` | 并发线程数 |
| `RETRY_ATTEMPTS` | `2` | 单张重试次数 |
| `RETRY_DELAY_SECONDS` | `0.5` | 重试间隔秒数 |
| `PARTIAL_RETRY_ATTEMPTS` | `2` | 部分失败补图轮次 |
| `SEQUENTIAL_GENERATION` | `auto` | 串行/并行策略 |
| `TIMEOUT_SECONDS` | `180` | 单次请求超时秒数 |

### 服饰成图质检

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS` | `3` | 成图质检最大重试次数 |

### Supabase

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `SUPABASE_URL` | 是 | 项目 URL（也可用 `SUPABASE_PROJECT_URL`） |
| `SUPABASE_ANON_KEY` | 是 | 前端 anon key（也可用 `SUPABASE_PUBLISHABLE_KEY`） |
| `SUPABASE_SERVICE_ROLE_KEY` | 是 | 后端 service role key，严禁暴露（也可用 `SUPABASE_SERVICE_KEY`） |

### 积分

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `POINTS_SIGNUP_BONUS` | `100` | 注册奖励 |
| `POINTS_DAILY_FREE` | `10` | 每日签到 |
| `POINTS_RULE_SUITE` | `{"key":"suite","label":"套图","unit_cost":4,"minimum_cost":4,"metric":"output_count"}` | 套图积分规则 |
| `POINTS_RULE_MODE2` | `{"key":"mode2","label":"AI 生图","unit_cost":4,"minimum_cost":4,"metric":"output_count"}` | mode2 规则 |
| `POINTS_RULE_APLUS` | `{"key":"aplus","label":"A+ 模块","unit_cost":4,"minimum_cost":4,"metric":"selected_modules_count"}` | A+ 规则 |
| `POINTS_RULE_FASHION` | `{"key":"fashion","label":"服饰场景","unit_cost":4,"minimum_cost":4,"metric":"selected_scene_count"}` | 服饰规则 |
| `GENERATION_TASK_TTL_SECONDS` | `7200` | 任务内存 TTL |
| `GENERATION_TASK_POLL_RETENTION_SECONDS` | `86400` | 轮询保留时间 |
| `GENERATION_TASK_WORKERS` | `2` | 异步任务线程数 |

#### 积分规则 JSON 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | string | 规则标识 |
| `label` | string | 前端名称 |
| `unit_cost` | int | 每单位消耗积分 |
| `minimum_cost` | int | 最低消耗 |
| `metric` | string | 计数方式 |

积分读取优先级：Supabase `api_settings` 表 → `.env` → 代码默认值。

### ZPay

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `ZPAY_PID` | 是 | 商户 ID |
| `ZPAY_KEY` | 是 | 签名密钥 |
| `ZPAY_GATEWAY` | 是 | 支付提交地址 |
| `ZPAY_NOTIFY_URL` | 是 | 异步回调地址（公网可达） |
| `ZPAY_RETURN_URL` | 是 | 支付完成跳转地址 |
| `ZPAY_DEFAULT_CHANNEL` | 否 | 默认通道（`alipay`） |

### COS

| 配置项 | 必填 | 说明 |
|--------|------|------|
| `COS_SECRET_ID` | 否 | 腾讯云 SecretId |
| `COS_SECRET_KEY` | 否 | 腾讯云 SecretKey |
| `COS_REGION` | 否 | 地域（如 `ap-guangzhou`） |
| `COS_BUCKET` | 否 | **存储桶名**（纯名称，不含域名，如 `aiimg-1234567890`） |
| `COS_CDN_DOMAIN` | 否 | CDN 域名（不带协议头，如 `cdn.example.com`） |

> **注意**：`COS_BUCKET` 填腾讯云控制台的纯桶名，不要填域名。CDN 加速域名填在 `COS_CDN_DOMAIN`。COS 配置支持 `.env` 和 Settings 页面 `config.json` 两种方式，`cos_utils` 优先读环境变量，其次读取 `config.json` 的 `LOCAL_CONFIG`。

### 管理员

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ADMIN_PASSWORD` | — | 管理员登录密码 |
| `ADMIN_ALLOWED_PHONE` | — | 允许登录管理后台的手机号 |

---

## API 路由一览

```
  GET    /                                          landing 首页
  GET    /suite           /aplus       /fashion     工作台页面
  GET    /settings        /auth         /logout      页面 / 登录入口

  GET    /api/app-mode                               当前模式查询
  POST   /api/auth/login    /register                邮箱密码登录/注册
  POST   /api/auth/session  /session-sync /logout    Session 管理
  POST   /api/admin/login   /session /logout         管理员
  GET    /api/points/balance /rules                  积分查询
  POST   /api/points/daily-claim /quote /spend /refund  积分操作
  POST   /api/generate-suite     /aplus    /fashion-model  套图/A+/模特
  POST   /api/generate-mode{1,2,3}-text2image        单图文生图
  POST   /api/generate-mode{1,2,3}-image-edit        单图图生图
  POST   /api/style-analysis                         风格分析
  POST   /api/ai-write                               文案生成
  POST   /api/download-zip                           批量下载
  GET    /api/generation-tasks/<id>                  任务查询
  POST   /api/generation-tasks/<id>/cancel           任务取消
  POST   /api/pay/create                             创建支付
  GET|POST /api/pay/notify                           支付回调
  GET|PATCH|POST /api/settings*                      配置管理
```

---

## 前端 Key 安全

- 后端渲染 HTML 时注入 `window.AI_IMAGE_CONFIG = { supabaseUrl, supabaseAnonKey }`
- 前端 JS 不再硬编码任何 Key
- `SUPABASE_SERVICE_ROLE_KEY`、`ZPAY_KEY`、各 `API_KEY` 永远不在浏览器出现

---

## Supabase 数据库

### 必需表

| 表名 | 作用 |
|------|------|
| `user_points_balances` | 积分余额 |
| `user_points_transactions` | 积分流水 |
| `user_profiles` | 用户扩展（管理员、会员到期） |
| `zpay_transactions` | ZPay 订单 |
| `vip_plan_config` | VIP 套餐配置 |
| `generation_tasks` | 生成任务持久化 |

迁移 SQL 位于 `supabase/migrations/`。

### 会员套餐配置

套餐配置从 Supabase `vip_plan_config` 表读取（`config_key = 'default'` 行）：

```sql
insert into public.vip_plan_config (config_key, recommended_plan,
  plan_name_1, discount_price_1, points_1, pay_type_1,
  plan_name_2, discount_price_2, points_2, pay_type_2, validity_days_2, badge_2,
  plan_name_3, discount_price_3, points_3, pay_type_3, validity_days_3, badge_3)
values ('default', 'plan_2',
  '体验包', '9.90', 100, 'one_time',
  '月度会员', '29.90', 300, 'subscribe', 30, '推荐',
  '季度会员', '79.90', 1000, 'subscribe', 90, '超值')
on conflict (config_key) do update set ... ;
```

---

## 支付链路

1. **创建订单** `POST /api/pay/create`：校验登录态 → 校验套餐 → 写入 `zpay_transactions` → 签名 → 返回支付链接
2. **支付回调** `GET|POST /api/pay/notify`：验签 → 查询订单 → 校验金额 → 防重 → 更新状态 → 发放积分/延长会员
3. **订阅续期**：未过期从原到期日叠加，已过期从当前时间开始

---

## Mode3 技术参考

Mode3 使用 OpenAI-compatible 的 multipart `images/edits` 接口：

```
POST {MODE3_OPENAI_BASE_URL}/images/edits
```

请求格式 `multipart/form-data`，返回 `{ data: [{ url: "..." }] }`。

套图性能基准（6 张，mode3 并行）：

| 阶段 | 耗时 | 说明 |
|------|------|------|
| LLM 套图规划 | ~86s | doubao-seed-2-0-mini，prompt ~2.6KB |
| mode3 并行生成 | ~35s | 9 workers，单张 ~30s |
| **总计** | **~121s** | 每张平摊 ~20s |

---

## 近期更新

### 2026-05-02 · v10.0

- **生产启动方式升级**：Docker 镜像加入 Gunicorn，使用 `gunicorn -w 4 -b 0.0.0.0:5078 --timeout 300 --access-logfile - app:app` 运行 Flask 应用
- **宝塔 Docker 部署确认**：容器 `command` 需要使用 Gunicorn 命令，线上日志已确认出现 `Starting gunicorn`、`Booting worker`，不再使用 Flask 开发服务器
- **Docker 镜像标签**：9.9 → 10.0，GitHub Action 自动打 `10.0` + `latest` 双标签

### 2026-05-02 · v9.9

- **多用户性能优化**：Supabase 会话缓存 5 分钟（减少 99% token 验证请求），静态文件浏览器缓存 1 小时，生成任务清理改为后台定时（每 10 分钟），彻底消除多用户场景下的 IO 瓶颈
- **生成任务超时保护**：新增 10 分钟超时自动 fail + 积分退款，任务再也不永久卡在 running 状态占用 worker
- **Worker 线程提升**：默认从 2 增至 4，支持 `GENERATION_TASK_WORKERS` 环境变量自定义
- **前端轮询优化**：任务轮询 2.5s→3s，总超时 30min→12min
- **Docker 镜像标签**：9.8 → 9.9，自动打 `9.9` + `latest` 双标签

### 2026-05-02 · v9.8

- **Flask 多线程**：`app.run()` 新增 `threaded=True`，AI 帮写等长耗时请求不再阻塞其他用户的页面加载和 API 调用
- **Chat HTTP 重试优化**：主 API 调用不再对 HTTP 错误码（503 等）做自动重试，失败立刻走 fallback，节省 4-6s 额外延迟
- **SSE/流式兼容 + Fallback 完善**：新增 SSE 流式格式解析支持，扩展 fallback token（新增 model_not_found / JSONDecodeError 等），通用 API 兼容性大幅提升
- **OpenAI 直连 Ark**：支持将 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 直接配置为 Ark 豆包的密钥和端点，不走 fallback 直连调用
- **Docker 镜像标签**：9.7 → 9.8，自动打 `9.8` + `latest` 双标签

### 2026-05-02 · v9.7

- **积分发放修复**：修复 `grant_payment_points_once` 中错误从 `points_rules` 导入不存在的函数，导致支付回调积分永远不到账的严重 Bug；调整执行顺序为先发积分再标记订单 paid，并对重试回调补发积分
- **COS 配置增强**：新增 `config.json` 兜底读取链路，Docker 中无 `.env` 时自动从 Settings 页面写入的 `config.json` 读取 COS 密钥；恢复 `load_dotenv` 确保本地 `.env` 正常加载
- **COS 桶名校验**：`COS_BUCKET` 必须填腾讯云控制台的纯桶名（如 `aiimg-1234567890`），不能填 CDN 域名
- **Docker 镜像标签**：9.6 → 9.7，自动打 `9.7` + `latest` 双标签

### 2026-05-02 · v9.6

- **COS 图片存储优化**：COS 客户端改为运行时懒加载，每次通过 `os.getenv()` 实时读取配置，避免 Settings 页面修改后不生效的问题
- **Chat Fallback 增强**：新增 401 / authentication_error / auth_unavailable / token is expired 等认证类错误 token，主接口 Key 过期时自动切换到 Ark Chat 备用接口
- **AI 帮写按钮修复**：页面初始化时自动启用按钮，不再出现加载后 disabled 的情况
- **Docker 镜像标签**：9.5 → 9.6，自动打 `9.6` + `latest` 双标签
- **VIP 系统文档**：补充完整的 Supabase 建表 SQL、AI 提示词配置、积分规则与支付链路教程

### 2026-05-01 · v9.5

- **代码重构**：`app.py` 从 7326 行降至 3044 行（-58%），提取 `supabase_client.py`（887 行）和 `generation/` 包（2570 行）
- `generation/modes.py`：mode1/2/3 客户端工厂、单图/并行生成、重试逻辑
- `generation/planning.py`：LLM Chat、JSON 修复、Suite/Fashion/A+ 规划函数
- `generation/suite.py` + `generation/aplus.py`：套图/A+ 并行编排
- `app.logger` → 可注入 `logging.Logger`，所有模块独立日志
- HTML 页面归入 `pages/` 目录
- 删除 4 个旧测试文件，项目更整洁
- **Docker 镜像 9.5 + latest**
- 重构后全部 42 个路由回归测试通过，认证/积分/生图全链路正常

### 2026-05-01 · v9.4

- LLM 全模式切 doubao-seed-2-0-mini（Ark 直连），成本 ¥0.008/套
- 套图规划 prompt 精简 63%（7KB→2.6KB），规划耗时 -34s
- 重试间隔全局减半（1.5s→0.5s）
- b64_json 回退到 url（b64 反慢 17s）
- 套图三轮优化：165s→121s（-27%）

### 2026-04-30

- mode3 套图并发生成（9 workers，9 张图 ~1 分钟）
- 三层断流重试（API 层 + 补图层 + 下载层）
- A+ 模块 524 自动回退 Ark Chat
- Supabase JSONB 查询编码修复

---

## 本地验证

```bash
# Python 语法检查
python -m py_compile app.py

# 全部模块导入
python -c "import app; print(len(list(app.app.url_map.iter_rules())), 'routes')"

# COS 连通性
python -c "import cos_utils; print(cos_utils.is_cos_enabled())"
```

---

## 常见问题

### 支付回调不生效
1. `ZPAY_NOTIFY_URL` 是否公网可达
2. `ZPAY_KEY` 是否正确
3. `/api/pay/notify` 是否返回 `fail`（查看服务端日志中的 ZPAY 日志）

### 生成后刷新页面看不到结果
1. Supabase 是否执行了 `generation_tasks` 建表 SQL
2. `SUPABASE_SERVICE_ROLE_KEY` 是否正确
3. `/api/generation-tasks/<task_id>` 返回 401/404 表示未登录或任务过期

### 前端提示 Supabase 配置缺失
确保页面通过 Flask 返回（`http://127.0.0.1:5078/`），不是直接双击 HTML 文件。
