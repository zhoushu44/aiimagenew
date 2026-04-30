# VIP 功能教程与介绍

本文档用于说明项目中的 VIP 会员功能，包括功能入口、套餐配置、支付流程、订阅续期、积分赠送、数据库表和常见排查方法。

## 1. 功能概览

VIP 功能主要包含以下能力：

- 用户登录后可在顶部账号面板中打开 VIP 开通弹窗
- 前端从 Supabase 的 `vip_plan_config` 表读取套餐配置
- 套餐支持一次性购买和订阅购买两种类型
- 购买时通过后端接口创建 ZPay 支付订单
- 支付成功后由 ZPay 回调后端接口完成订单确认
- 订阅套餐会更新用户的 `user_profiles.subscribe_expire`
- 套餐可配置赠送积分，支付成功后会给用户发放积分
- 账号面板会根据 `subscribe_expire` 判断会员是否有效

核心链路是：

```text
用户登录 -> 打开 VIP 弹窗 -> 选择套餐 -> 创建支付订单 -> 跳转 ZPay 支付 -> ZPay 回调后端 -> 更新订单和权益 -> 用户获得会员/积分
```

## 2. 用户侧使用流程

### 2.1 登录账号

用户需要先登录账号。未登录时点击开通 VIP，会先弹出登录窗口。

登录成功后，前端会同步 Supabase session 到后端 httpOnly Cookie，后端接口再通过 Cookie 判断用户身份。

### 2.2 打开会员中心

页面顶部账号入口会打开账号面板，账号面板中有“开通VIP”按钮。

点击后会打开 VIP 套餐弹窗，弹窗展示：

- 当前登录账号
- VIP 权益视觉说明
- 套餐卡片
- 价格
- 赠送积分
- 支付按钮

### 2.3 选择套餐并支付

用户选择套餐后点击“立即购买”或“立即订阅”。

前端会调用：

```http
POST /api/pay/create
```

后端会校验：

- 用户是否登录
- 请求里的 `user_id` 是否和当前登录用户一致
- `product_id` 是否是有效套餐
- 前端提交金额是否和 Supabase 套餐配置一致
- 支付类型是否有效

校验通过后，后端创建订单并返回 ZPay 支付链接，浏览器跳转到支付页面。

## 3. 套餐配置说明

VIP 套餐由 Supabase 表 `vip_plan_config` 提供，前端和后端都会读取这张表。

### 3.1 套餐编号

当前支持 3 个套餐：

```text
plan_1
plan_2
plan_3
```

前端会按 `plan_1`、`plan_2`、`plan_3` 的顺序构建套餐卡片。

### 3.2 常用字段

`vip_plan_config` 建议包含以下字段：

| 字段 | 说明 |
| --- | --- |
| `config_key` | 配置标识，默认使用 `default` |
| `plan_name_1` | 套餐 1 名称 |
| `discount_price_1` | 套餐 1 实付价格 |
| `original_price_1` | 套餐 1 原价，可为空 |
| `price_note_1` | 套餐 1 价格说明，例如 `/月` |
| `points_1` | 套餐 1 支付成功后赠送积分 |
| `pay_type_1` | 套餐 1 支付类型，支持 `one_time` 或 `subscribe` |
| `validity_days_1` | 套餐 1 订阅天数 |
| `badge_1` | 套餐 1 角标，例如 `推荐` |
| `trial_text_1` | 套餐 1 试用或补充文案 |

套餐 2 和套餐 3 使用相同规则，只需要把字段后缀改为 `_2`、`_3`。

例如：

```text
plan_name_2
discount_price_2
points_2
pay_type_2
validity_days_2
```

### 3.3 支付类型

`pay_type_x` 支持两种值：

| 值 | 含义 |
| --- | --- |
| `one_time` | 一次性购买，只发放积分或一次性权益，不更新会员到期时间 |
| `subscribe` | 订阅会员，支付成功后更新 `subscribe_expire` |

如果 `pay_type_x` 没有配置，系统会根据套餐天数字段判断：

- 有 `validity_days_x`、`duration_days_x` 或 `subscription_days_x` 且大于 0：按订阅处理
- 没有有效天数：按一次性购买处理

### 3.4 默认选中套餐

可以通过以下字段指定默认选中的套餐：

```text
default_plan
default_plan_key
default_product_id
selected_plan
recommended_plan
```

字段值填写 `plan_1`、`plan_2` 或 `plan_3`。

如果没有配置默认套餐，前端会默认选中第一个有效套餐。

## 4. 后端环境变量

VIP 支付依赖 ZPay 和 Supabase 后端配置。

### 4.1 ZPay 配置

`.env` 中需要配置：

```env
ZPAY_PID=你的商户PID
ZPAY_KEY=你的ZPay密钥
ZPAY_GATEWAY=https://zpayz.cn/submit.php
ZPAY_NOTIFY_URL=http://你的公网地址/api/pay/notify
ZPAY_RETURN_URL=http://你的公网地址/
ZPAY_DEFAULT_CHANNEL=alipay
```

说明：

- `ZPAY_PID` 是商户 ID
- `ZPAY_KEY` 用于后端签名和回调验签，不能暴露到前端
- `ZPAY_GATEWAY` 是支付提交地址
- `ZPAY_NOTIFY_URL` 是异步回调地址，必须能被 ZPay 服务器访问
- `ZPAY_RETURN_URL` 是用户支付完成后浏览器跳回的地址
- `ZPAY_DEFAULT_CHANNEL` 当前一般使用 `alipay`

### 4.2 Supabase 配置

`.env` 中还需要有：

```env
SUPABASE_URL=你的Supabase项目地址
SUPABASE_ANON_KEY=你的Supabase匿名key
SUPABASE_SERVICE_ROLE_KEY=你的Supabase服务端key
```

其中：

- `SUPABASE_ANON_KEY` 可用于前端初始化 Supabase 客户端
- `SUPABASE_SERVICE_ROLE_KEY` 只能放在后端，用于写订单、更新会员、发放积分

## 5. 数据库表说明

VIP 功能主要涉及以下表。

### 5.1 vip_plan_config

用于保存 VIP 套餐配置。

前端读取该表展示套餐；后端读取该表校验价格、支付类型、赠送积分和订阅天数。

最关键的是：前端展示价格和后端实际收款价格都来自这张表，这样可以避免用户篡改前端金额。

### 5.2 zpay_transactions

用于保存支付订单。

创建订单时写入一条 `pending` 记录；ZPay 回调成功后更新为支付成功状态。

核心字段包括：

| 字段 | 说明 |
| --- | --- |
| `out_trade_no` | 本站订单号 |
| `user_id` | 用户 ID |
| `amount` | 支付金额 |
| `status` | 支付状态 |
| `type` | 订单类型，可能是 `one_time` 或 `subscription` |
| `product_id` | 套餐 ID，例如 `plan_2` |
| `trade_no` | ZPay 平台订单号 |
| `subscribe_start` | 订阅开始时间 |
| `subscribe_expire` | 订阅到期时间 |

### 5.3 user_profiles

用于保存用户扩展信息，其中 `subscribe_expire` 是会员判断的核心字段。

```sql
subscribe_expire timestamptz
```

后端判断会员有效的规则是：

```text
subscribe_expire > 当前时间
```

只要该字段晚于当前时间，用户就会被视为会员有效。

### 5.4 user_points_balances

用于保存用户积分余额。

如果套餐配置了 `points_x`，支付成功后会尝试给用户发放对应积分。

## 6. 支付创建流程

用户点击支付按钮后，前端会调用：

```http
POST /api/pay/create
Content-Type: application/json
```

请求体示例：

```json
{
  "user_id": "当前登录用户ID",
  "product_id": "plan_2",
  "amount": "29.90",
  "pay_type": "subscribe"
}
```

后端实际不会盲信前端传来的金额和支付类型，而是会重新读取 `vip_plan_config`，并以数据库配置为准。

后端处理步骤：

1. 从 Cookie 中读取登录态
2. 校验 `user_id` 是否匹配当前用户
3. 校验套餐 ID 是否有效
4. 读取 `vip_plan_config` 中的套餐信息
5. 校验前端金额是否等于后端配置金额
6. 判断订单类型是一次性购买还是订阅
7. 如果是订阅，计算开始时间和到期时间
8. 写入 `zpay_transactions`
9. 生成 ZPay 签名
10. 返回支付链接

返回成功后，前端会跳转到 `payment_url`。

## 7. 支付回调流程

ZPay 支付成功后，会请求：

```http
GET/POST /api/pay/notify
```

后端会执行：

1. 读取回调参数
2. 使用 `ZPAY_KEY` 验证签名
3. 检查 `out_trade_no`
4. 检查支付状态是否成功
5. 查询本地订单
6. 校验回调金额和订单金额一致
7. 如果订单已经处理过，直接返回 `success`
8. 更新订单为支付成功
9. 发放套餐积分
10. 如果是订阅订单，更新 `user_profiles.subscribe_expire`
11. 返回字符串 `success`

ZPay 平台一般要求回调接口返回 `success` 才认为通知处理成功。

## 8. 订阅续期规则

订阅套餐会自动叠加时间。

规则如下：

| 当前状态 | 计算方式 |
| --- | --- |
| 从未开通过会员 | 从当前时间开始加套餐天数 |
| 会员已过期 | 从当前时间开始加套餐天数 |
| 会员未过期 | 从原到期时间继续叠加套餐天数 |

示例：

```text
当前时间：2026-04-30
用户会员到期：2026-05-10
购买 30 天套餐后，新到期时间：2026-06-09
```

这样可以避免用户提前续费时损失剩余会员时间。

## 9. 积分赠送规则

如果套餐中配置了：

```text
points_1
points_2
points_3
```

支付成功后，后端会根据购买的套餐发放积分。

例如：

```text
points_2 = 300
```

用户购买 `plan_2` 后，会赠送 300 积分。

积分发放一般会记录到积分余额和积分流水中，便于后续排查。

## 10. 本地调试教程

### 10.1 启动 Flask 服务

```bash
python app.py
```

或使用项目 README 中指定的启动方式。

### 10.2 配置公网回调地址

支付平台回调必须能访问本地后端。

本地开发时可以使用 FRP、ngrok 或其他内网穿透工具，把公网地址转发到 Flask 服务端口。

`.env` 示例：

```env
ZPAY_NOTIFY_URL=http://公网地址/api/pay/notify
ZPAY_RETURN_URL=http://公网地址/
```

### 10.3 配置套餐数据

在 Supabase 的 `vip_plan_config` 表中确认存在 `config_key = default` 的配置行。

至少需要配置套餐名称和价格，例如：

```text
plan_name_1 = 基础体验包
discount_price_1 = 9.90
points_1 = 100
pay_type_1 = one_time

plan_name_2 = 月度会员
discount_price_2 = 29.90
points_2 = 300
pay_type_2 = subscribe
validity_days_2 = 30

plan_name_3 = 季度会员
discount_price_3 = 79.90
points_3 = 1000
pay_type_3 = subscribe
validity_days_3 = 90
```

### 10.4 前端验证

1. 打开网站
2. 登录账号
3. 打开账号面板
4. 点击“开通VIP”
5. 确认套餐是否正常展示
6. 点击支付按钮
7. 确认是否跳转到 ZPay 支付页
8. 完成支付后检查订单和会员状态

### 10.5 数据库验证

支付前检查：

```text
zpay_transactions 是否新增 pending 订单
```

支付后检查：

```text
zpay_transactions.status 是否变为 paid 或 success
user_profiles.subscribe_expire 是否更新
user_points_balances.balance 是否增加
```

## 11. 常见问题排查

### 11.1 VIP 弹窗提示套餐加载失败

重点检查：

1. Supabase 前端 key 是否正确
2. `vip_plan_config` 表是否存在
3. 是否存在 `config_key = default` 的记录
4. 套餐是否至少配置了 `plan_name_x` 和 `discount_price_x`
5. RLS 策略是否允许前端读取套餐配置

### 11.2 点击支付后提示金额不一致

说明前端传入金额和后端从 `vip_plan_config` 读取到的金额不一致。

处理方法：

1. 刷新页面重新加载套餐
2. 检查 Supabase 中 `discount_price_x` 是否是正确金额
3. 确认没有多个环境连接到不同 Supabase 项目
4. 确认前端展示和后端服务使用的是同一个 Supabase 配置

### 11.3 支付成功但会员没有生效

重点检查：

1. `ZPAY_NOTIFY_URL` 是否公网可访问
2. ZPay 是否成功请求 `/api/pay/notify`
3. 后端日志是否出现验签失败
4. `ZPAY_KEY` 是否和平台后台一致
5. 回调金额是否和订单金额一致
6. `zpay_transactions` 订单状态是否更新
7. `user_profiles.subscribe_expire` 是否写入
8. 订单 `type` 是否是 `subscription`

### 11.4 支付成功但积分没有增加

重点检查：

1. 对应套餐的 `points_x` 是否大于 0
2. 用户积分余额记录是否存在
3. 后端日志是否有积分发放失败信息
4. 是否重复回调导致已处理过同一订单

### 11.5 回调接口返回 fail

常见原因：

- 签名验证失败
- 缺少 `out_trade_no`
- 支付状态不是成功状态
- 本地找不到订单
- 回调金额和订单金额不一致

建议先查看后端日志中的 `ZPAY notify received` 记录。

## 12. 安全注意事项

- `ZPAY_KEY` 只能保存在后端 `.env` 中
- `SUPABASE_SERVICE_ROLE_KEY` 只能保存在后端，不能暴露给浏览器
- 前端传来的金额、套餐和用户 ID 都不能直接信任
- 支付回调必须验签
- 支付成功处理必须防重复，避免重复发放积分或重复延长会员
- Supabase RLS 要控制好前端可读写权限

## 13. 运营配置建议

推荐把套餐设计成清晰的三档：

| 套餐 | 建议用途 |
| --- | --- |
| `plan_1` | 低价体验包或积分包 |
| `plan_2` | 月度会员主推套餐 |
| `plan_3` | 季度或年度高价值套餐 |

配置建议：

- 主推套餐设置 `badge_x = 推荐`
- 订阅套餐设置明确的 `validity_days_x`
- 赠送积分用 `points_x` 明确展示
- 前端展示价格和后端校验价格统一使用 `discount_price_x`
- 每次改价后先用测试账号完整走一遍支付流程

## 14. 相关文件位置

- 后端支付、会员、积分逻辑：`app.py`
- 前端账号面板和 VIP 弹窗：`static/js/shared-topbar.js`
- Supabase 表结构说明：`supabase_readme.md`
- 项目总说明：`README.md`

