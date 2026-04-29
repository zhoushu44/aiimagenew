# AI Image New

一个基于 Flask 的 AI 图片生成与会员支付项目，包含 Supabase 登录、积分、会员套餐、ZPay 支付、支付回调、订阅续期和前端账号面板。

## 功能概览

- Flask 2.x 后端服务
- Supabase Auth 登录与后端 session 同步
- httpOnly Cookie 登录态
- 积分余额、注册奖励、每日奖励
- AI 图片生成与图片编辑
- 生成任务支持刷新恢复、状态轮询和失败自动返还积分
- VIP 套餐配置从 Supabase 表读取
- ZPay 支付创建接口
- ZPay 支付成功回调验签
- 一次性购买和订阅购买
- 订阅到期时间自动叠加
- 会员状态在账号面板展示
- FRP 内网穿透支持支付平台回调本地服务

## 目录说明

```text
.
├── app.py                         # Flask 主应用
├── auth.html                      # 登录/注册页面
├── index.html                     # 首页
├── suite.html                     # 工作台页面
├── requirements.txt               # Python 依赖
├── .env                           # 本地环境变量，不要提交到公开仓库
├── static/
│   ├── js/
│   │   ├── shared-topbar.js        # 顶部栏、登录弹窗、账号面板、VIP 支付弹窗
│   │   └── workspace.js            # 工作台交互
│   └── ...
├── supabase/
│   └── migrations/                # Supabase 表结构迁移 SQL
└── test-tools/
    └── frpc/
        ├── frpc-built.exe          # 测试用 frpc 客户端
        └── frpc.toml               # 测试用 FRP 客户端配置
```

## 环境要求

- Windows / macOS / Linux
- Python 3.10+
- pip
- 可访问 Supabase 项目
- 可访问 ZPay 支付网关
- 如需本地接收支付回调，需要公网地址或 FRP 内网穿透

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动项目

```bash
python app.py
```

默认监听：

```text
http://127.0.0.1:5078
```

如果 `.env` 配置了 `HOST` 和 `PORT`，会以 `.env` 为准。

## .env 配置完整版

项目从 `.env` 读取配置。当前 `.env` 已按模块分组：

```env
# Flask
HOST=0.0.0.0
PORT=5078
FLASK_DEBUG=false

# OpenAI-compatible image generation provider
OPENAI_API_KEY=你的 OpenAI 兼容接口 Key
OPENAI_BASE_URL=https://api.example.com/v1
OPENAI_MODEL=gpt-5.4-mini

# Volcengine Ark image generation
ARK_API_KEY=你的火山 Ark Key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_IMAGE_MODEL=doubao-seedream-5-0-260128
ARK_IMAGE_SIZE=2048x2048
ARK_IMAGE_QUALITY=
ARK_IMAGE_WATERMARK=false
ARK_SEQUENTIAL_IMAGE_GENERATION=auto
ARK_SEQUENTIAL_MAX_IMAGES=1

# Mode 2 image edit / text-to-image
MODE2_OPENAI_API_KEY=你的图片编辑 Key
MODE2_OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
MODE2_IMAGE_EDIT_MODEL=doubao-seedream-5-0-260128
MODE2_TEXT2IMAGE_MODEL=doubao-seedream-5-0-260128
MODE2_DEFAULT_RATIO=1:1
MODE2_DEFAULT_RESOLUTION=2048x2048
MODE2_DEFAULT_SAMPLE_STRENGTH=0.65
MODE2_ALLOWED_IMAGE_HOSTS=

# Supabase
SUPABASE_URL=https://你的项目.supabase.opentrust.net
SUPABASE_ANON_KEY=你的 anon key
SUPABASE_SERVICE_ROLE_KEY=你的 service role key
SUPABASE_SETTINGS_SCOPE=global
SUPABASE_SETTINGS_ALLOWED_EMAIL=
SUPABASE_SETTINGS_ALLOWED_EMAILS=

# Points
POINTS_SIGNUP_BONUS=100
POINTS_DAILY_FREE=10
POINTS_IMAGE_GENERATION_COST=1
GENERATION_TASK_TTL_SECONDS=7200
GENERATION_TASK_POLL_RETENTION_SECONDS=86400
GENERATION_TASK_WORKERS=2

# ZPay
ZPAY_PID=你的商户 PID
ZPAY_KEY=你的 ZPay 密钥
ZPAY_GATEWAY=https://zpayz.cn/submit.php
ZPAY_NOTIFY_URL=http://你的公网地址/api/pay/notify
ZPAY_RETURN_URL=http://你的公网地址/
ZPAY_DEFAULT_CHANNEL=alipay
SUBSCRIPTION_PRODUCT_DAYS_JSON={"plan_2":30,"plan_3":90}
```

## 关键配置说明

### Flask

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `HOST` | 否 | Flask 监听地址，本地调试可用 `127.0.0.1`，FRP 穿透建议 `0.0.0.0` |
| `PORT` | 否 | Flask 监听端口，当前项目默认使用 `5078` |
| `FLASK_DEBUG` | 否 | 是否开启调试模式，生产环境建议 `false` |

### AI 模型

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 是 | OpenAI 兼容接口密钥 |
| `OPENAI_BASE_URL` | 是 | OpenAI 兼容接口地址 |
| `OPENAI_MODEL` | 是 | 文生图/文本生成使用的模型名 |
| `ARK_API_KEY` | 是 | 火山 Ark 图片生成接口密钥 |
| `ARK_BASE_URL` | 否 | Ark 接口地址，默认 `https://ark.cn-beijing.volces.com/api/v3` |
| `ARK_IMAGE_MODEL` | 是 | Ark 图片生成模型 |
| `ARK_IMAGE_SIZE` | 否 | 默认图片尺寸 |
| `ARK_IMAGE_QUALITY` | 否 | 图片质量参数，留空则不传 |
| `ARK_IMAGE_WATERMARK` | 否 | 是否开启水印 |
| `ARK_SEQUENTIAL_IMAGE_GENERATION` | 否 | 多图顺序生成策略，默认 `auto` |
| `ARK_SEQUENTIAL_MAX_IMAGES` | 否 | 顺序生成最大图片数 |

### Mode2 图片编辑

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `MODE2_OPENAI_API_KEY` | 是 | 图片编辑接口密钥 |
| `MODE2_OPENAI_BASE_URL` | 是 | 图片编辑接口地址 |
| `MODE2_IMAGE_EDIT_MODEL` | 是 | 图片编辑模型 |
| `MODE2_TEXT2IMAGE_MODEL` | 是 | 文生图模型 |
| `MODE2_DEFAULT_RATIO` | 否 | 默认比例，例如 `1:1` |
| `MODE2_DEFAULT_RESOLUTION` | 否 | 默认分辨率，例如 `2048x2048` |
| `MODE2_DEFAULT_SAMPLE_STRENGTH` | 否 | 参考图强度，默认 `0.65` |
| `MODE2_ALLOWED_IMAGE_HOSTS` | 否 | 允许远程参考图的域名白名单，多个用英文逗号分隔 |

### Supabase

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `SUPABASE_URL` | 是 | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | 是 | 前端登录用 anon key，可公开，但仍建议由后端注入页面配置 |
| `SUPABASE_SERVICE_ROLE_KEY` | 是 | 后端管理员 key，只能放后端 `.env`，严禁写入前端 JS |
| `SUPABASE_SETTINGS_SCOPE` | 否 | 后台配置表 scope，默认 `global` |
| `SUPABASE_SETTINGS_ALLOWED_EMAIL` | 否 | 允许访问配置管理的单个邮箱 |
| `SUPABASE_SETTINGS_ALLOWED_EMAILS` | 否 | 允许访问配置管理的多个邮箱，英文逗号分隔 |

### 积分与生成任务

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `POINTS_SIGNUP_BONUS` | 否 | 注册赠送积分 |
| `POINTS_DAILY_FREE` | 否 | 每日免费积分 |
| `POINTS_IMAGE_GENERATION_COST` | 否 | 生成图片消耗积分 |
| `GENERATION_TASK_TTL_SECONDS` | 否 | 内存生成任务清理时间，默认 `7200` 秒，最小 `300` 秒 |
| `GENERATION_TASK_POLL_RETENTION_SECONDS` | 否 | 前端可轮询恢复的任务保留时间，默认 `86400` 秒，最小 `3600` 秒 |
| `GENERATION_TASK_WORKERS` | 否 | 后端生成任务线程数，默认 `2` |

### ZPay

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `ZPAY_PID` | 是 | ZPay 商户 ID |
| `ZPAY_KEY` | 是 | ZPay 签名密钥，只能放后端 |
| `ZPAY_GATEWAY` | 是 | ZPay 支付提交地址 |
| `ZPAY_NOTIFY_URL` | 是 | 支付平台异步回调地址，必须公网可访问 |
| `ZPAY_RETURN_URL` | 是 | 用户支付完成后浏览器跳回地址 |
| `ZPAY_DEFAULT_CHANNEL` | 否 | 默认支付通道，当前为 `alipay` |
| `SUBSCRIPTION_PRODUCT_DAYS_JSON` | 是 | 订阅套餐天数配置，例如 `{"plan_2":30,"plan_3":90}` |

## 前端 Key 安全说明

项目已经清理了前端硬编码 Supabase key：

- [shared-topbar.js](file:///c:/Users/zs/Desktop/aiimagenew/static/js/shared-topbar.js) 不再写死 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`
- [auth.html](file:///c:/Users/zs/Desktop/aiimagenew/auth.html) 不再写死 `SUPABASE_URL` 和 `SUPABASE_ANON_KEY`
- 后端会在渲染 HTML 时注入：

```html
<script>window.AI_IMAGE_CONFIG = { ... };</script>
```

前端只会拿到：

- `supabaseUrl`
- `supabaseAnonKey`

不会拿到：

- `SUPABASE_SERVICE_ROLE_KEY`
- `ZPAY_KEY`
- `OPENAI_API_KEY`
- `ARK_API_KEY`

注意：Supabase anon key 本身允许在浏览器使用，但要配合 RLS 策略和后端接口权限控制。service role key 永远不要暴露给浏览器。

## Supabase 后台配置

### 必需表

项目依赖以下表或迁移：

- `user_profiles`
- `user_points_balances`
- `user_points_transactions`
- `api_settings`
- `vip_plan_config`
- `zpay_transactions`
- `generation_tasks`

迁移 SQL 位于：

```text
supabase/migrations/
```

### 会员字段

`user_profiles` 需要包含：

```sql
subscribe_expire timestamptz
```

该字段用于判断用户会员是否有效。后端现在会判断：

```text
subscribe_expire > 当前时间
```

只有到期时间大于当前时间，才会返回 `membership_active = true`。

### 生成任务表

`generation_tasks` 用于保存用户生成任务状态，支持页面刷新后恢复生成结果。核心字段包括：

- `id`：生成任务 ID
- `user_id`：任务所属用户
- `mode`：生成模式，例如 `suite`、`fashion`
- `request_id`：积分扣减请求 ID，用于失败后返还积分
- `status`：任务状态，取值 `pending`、`running`、`succeeded`、`failed`
- `result`：生成成功后的结果 JSON
- `error` / `details`：失败原因
- `spend_record`：本次扣分记录
- `refunded` / `refund_error`：自动退款结果

相关接口：

```http
GET /api/generation-tasks/<task_id>
POST /api/generation-tasks/<task_id>/cancel
```

注意：当前生成任务会写入 Supabase，并保留进程内缓存兜底。若线上容器在生成中被强制重启，正在运行的线程会中断；要做到完全任务续跑，需要额外接入队列 Worker 或定时重试机制。

### 支付订单表

`zpay_transactions` 用于存储支付订单，核心字段包括：

- `out_trade_no`
- `user_id`
- `amount`
- `status`
- `type`
- `product_id`
- `trade_no`
- `subscribe_start`
- `subscribe_expire`
- `created_at`
- `updated_at`

支付状态：

- `pending`：已创建，未支付或未成功回调
- `success`：支付成功并已处理权益

### VIP 套餐配置

前端 VIP 弹窗会从 Supabase 的 `vip_plan_config` 表读取套餐配置。常见字段包括：

- `config_key`
- `title_1` / `title_2` / `title_3`
- `discount_price_1` / `discount_price_2` / `discount_price_3`
- `origin_price_1` / `origin_price_2` / `origin_price_3`
- `trial_1` / `trial_2` / `trial_3`
- `points_1` / `points_2` / `points_3`

默认读取：

```text
config_key = default
```

## 支付链路说明

### 创建订单

接口：

```http
POST /api/pay/create
```

要求：

- 用户必须已登录
- 后端从 httpOnly Cookie 中读取 session
- 请求参数包括套餐、金额、支付类型

后端会：

1. 校验登录态
2. 校验 `product_id`、`amount`、`pay_type`
3. 生成唯一 `out_trade_no`
4. 写入 `zpay_transactions`，状态为 `pending`
5. 使用 `ZPAY_KEY` 生成签名
6. 返回 ZPay 支付链接

### 支付回调

接口：

```http
GET/POST /api/pay/notify
```

支付平台回调后，后端会：

1. 解析回调参数
2. 使用 `ZPAY_KEY` 验签
3. 查询订单
4. 校验金额一致
5. 防重复处理，订单已成功则直接返回 `success`
6. 更新订单状态为 `success`
7. 订阅订单更新 `user_profiles.subscribe_expire`
8. 返回字符串 `success`

### 订阅续期规则

订阅订单会自动叠加：

- 首次开通：从当前时间开始加套餐天数
- 已过期：从当前时间开始加套餐天数
- 未过期：从原到期时间继续叠加套餐天数

套餐天数来自：

```env
SUBSCRIPTION_PRODUCT_DAYS_JSON={"plan_2":30,"plan_3":90}
```

## FRP 内网穿透测试配置

FRPC 只用于本地测试支付回调，已单独放在测试工具目录，不属于正式业务代码。

如果本地开发要接收 ZPay 回调，需要公网地址转发到本机 Flask。

当前 FRP 客户端测试配置：

```text
test-tools/frpc/frpc.toml
```

示例：

```toml
serverAddr = "8.163.52.51"
serverPort = 7000

auth.method = "token"
auth.token = "你的 frps token"

[[proxies]]
name = "aiimagenew-pay"
type = "tcp"
localIP = "127.0.0.1"
localPort = 5078
remotePort = 60009
```

启动：

```powershell
.\test-tools\frpc\frpc-built.exe -c .\test-tools\frpc\frpc.toml
```

对应 `.env`：

```env
ZPAY_NOTIFY_URL=http://8.163.52.51:60009/api/pay/notify
ZPAY_RETURN_URL=http://8.163.52.51:60009/
```

## 登录与 session-sync

前端登录成功后会调用：

```http
POST /api/auth/session-sync
```

后端会把 Supabase session 写入 httpOnly Cookie。之后受保护接口通过后端 Cookie 判断登录态。

退出登录时调用：

```http
POST /api/auth/logout
```

后端会清理 Cookie，前端会清理 Supabase 本地 session。

## 本地验证命令

### Python 语法检查

```bash
python -m py_compile app.py
```

### Flask 应用导入检查

```bash
python -c "from app import app; print('routes', len(list(app.url_map.iter_rules())))"
```

### 前端 JS 语法检查

```bash
node --check static/js/shared-topbar.js
node --check static/js/workspace.js
```

## 常见问题

### 支付成功但订单仍是 pending

重点检查：

1. `ZPAY_NOTIFY_URL` 是否公网可访问
2. FRP 是否正在运行
3. Flask 是否监听在 `PORT=5078`
4. `/api/pay/notify` 是否被登录守卫拦截
5. `ZPAY_KEY` 是否和支付平台一致
6. 回调金额是否和订单金额一致

### 支付后跳回登录页

重点检查：

1. 登录后是否成功调用 `/api/auth/session-sync`
2. 浏览器是否保留 Cookie
3. `ZPAY_RETURN_URL` 是否跳回正确页面
4. 前端是否能读取当前 Supabase session

### 会员已过期但仍显示已开通

当前版本已修复。后端会判断 `subscribe_expire` 是否大于当前时间，只有未过期才返回 `membership_active=true`。

### 生成过程中刷新页面后看不到结果

当前版本已修复。套图和服饰生成会先创建 `generation_tasks` 任务，前端保存 `task_id` 并轮询任务状态；刷新页面后会自动恢复未完成任务，生成成功后重新渲染结果。

如果线上仍无法恢复，重点检查：

1. Supabase 是否已执行 `20260429_create_generation_tasks.sql`
2. `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY` 是否正确
3. `/api/generation-tasks/<task_id>` 是否返回 401/403/404
4. 容器是否在生成中被重启或强杀

### 前端提示 Supabase 配置缺失

检查 `.env`：

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
```

并确认页面是通过 Flask 返回的，不是直接用浏览器打开本地 HTML 文件。

## 清理说明

本项目已清理：

- 临时图片文件
- 临时 base64 文件
- 旧 SQL 辅助 Python 脚本
- FRP 源码克隆目录
- 运行日志
- Python pycache
- 无用 `/api/execute-sql` 路由
- 前端硬编码 Supabase URL 和 anon key

保留为独立测试工具：

- `test-tools/frpc/frpc-built.exe`
- `test-tools/frpc/frpc.toml`

这两个文件仅用于本地支付回调穿透测试，不属于正式业务代码。
