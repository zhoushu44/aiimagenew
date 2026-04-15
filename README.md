# AI 电商视觉控制台

一个基于 Flask + Supabase 的 AI 电商视觉工作台，支持登录、权限控制、全局配置和图片生成。

## 项目目标

这个项目的核心目标是把“登录、配置、生成、权限”全部收敛到同一个控制台里：

- 用户通过 `/auth` 登录或注册
- 登录后进入业务工作台
- 管理员或白名单邮箱可以进入 `/settings`
- 所有全局配置统一保存在 `public.api_settings`
- `APP_MODE` 作为全局开关控制后端走 `mode1` 或 `mode2`
- 图片生成结果会通过后端保存并返回给前端

## 核心功能

- **登录 / 注册**：通过 `/auth` 使用 Supabase 账号登录
- **安全跳转**：支持 `next` 参数，但只允许站内相对路径
- **权限控制**：`/settings` 仅允许白名单邮箱或管理员进入
- **全局配置**：配置保存在 `public.api_settings`
- **模式切换**：通过 `APP_MODE` 在 `mode1 / mode2` 间切换生图逻辑
- **图片生成**：支持商品套图、A+ 详情页、服饰模特等生成流程
- **Docker 发布**：GitHub Actions 在 `main` 分支推送时自动构建并发布镜像

## 访问流程

```text
用户打开网站
   |
   v
访问 /auth 登录页
   |
   v
Supabase 登录 / 注册
   |
   v
后端写入 session cookie
   |
   v
登录成功后跳转到工作台
   |
   +-----------------------------+
   |                             |
   v                             v
访问业务页                    访问 /settings
(/suite /aplus /fashion)         |
   |                             v
   |                        检查权限
   |                    (邮箱 allowlist / is_admin)
   |                             |
   |                    +--------+--------+
   |                    |                 |
   |                    v                 v
   |                允许进入         拒绝访问
   |
   v
读取 APP_MODE
   |
   +-----------------------------+
   |                             |
   v                             v
mode1                         mode2
   |                             |
   v                             v
走 ARK 生成链路            走 mode2 接口链路
   |                             |
   v                             v
生成图片 / 保存结果 / 返回前端
```

## 模式说明

### mode1

- 作为默认模式
- 走通用多图生成流程
- 适合商品套图、A+ 详情页等常规生成任务

### mode2

- 作为另一套后端生成模式
- 走专用接口链路
- 不对应单独页面，只是后端模式开关

## 设置页说明

`/settings` 页面会从 Supabase 读取 `api_settings`，可以直接修改：

- `APP_MODE`
- 模型相关配置
- 生成参数
- 积分相关配置

保存后会立即刷新 settings cache。页面里 `APP_MODE` 会以 `mode1 / mode2` 下拉框展示，避免手动输入错误。

## 权限逻辑

`/settings` 的访问控制采用“双重判断”：

1. **邮箱白名单**
   - 通过环境变量 `SUPABASE_SETTINGS_ALLOWED_EMAILS`
   - 或单个邮箱变量 `SUPABASE_SETTINGS_ALLOWED_EMAIL`
2. **管理员标记**
   - 从 `public.user_profiles.is_admin` 读取
   - 只要值为 `true`，即可进入设置页

后端会同时保护：

- 页面路由 `/settings`
- 配置接口 `/api/settings`
- 刷新接口 `/api/settings/refresh`

如果没有登录，接口会返回 `401`，页面会跳转到 `/auth`。
如果已登录但没有权限，页面会返回 `403`，接口会返回 `403`。

## Supabase 配置表

全局设置统一存放在：

- `public.api_settings`

当前项目会读取的关键项包括：

- `APP_MODE`
- `HOST`
- `PORT`
- `FLASK_DEBUG`
- 模型相关配置
- 生成相关参数
- 积分相关参数

当设置页保存配置后，后端会立即刷新 settings cache，使新配置马上生效。

## 管理员表

管理员状态存放在：

- `public.user_profiles`

其中：

- `user_id` 对应 `auth.users.id`
- `is_admin = true` 表示该账号拥有设置页权限

## Docker 发布

GitHub Actions 会在 `main` 分支 push 时自动：

- 拉取代码
- 登录 Docker Hub
- 构建镜像
- 同时发布两个标签：`4.1` 和 `latest`

本地不需要执行推送操作。

## 目录说明

- `app.py`：Flask 主程序，负责认证、权限、配置读取、生成路由
- `auth.html`：登录 / 注册页面
- `settings.html`：设置页面
- `Dockerfile`：容器构建文件
- `.github/workflows/docker-publish.yml`：镜像构建与推送流程
- `supabase/migrations/`：数据库迁移与初始化脚本

## 备注

- `/auth` 支持安全的 `next` 跳转
- `/mode2` 独立页面已删除，mode2 只作为后端生成模式存在
- 管理员标记由 `public.user_profiles.is_admin` 控制，值为 `true` 即可进入设置页
