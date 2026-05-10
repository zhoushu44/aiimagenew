# GitHub Action 自动构建 Docker 镜像说明

## 配置概览

### 1. GitHub Action Workflow

**文件位置**: `.github/workflows/docker-publish.yml`

**触发条件**:
- 推送到 `main` 分支时自动触发
- 手动触发（workflow_dispatch）

**构建平台**:
- linux/amd64
- linux/arm64

**镜像标签**:
- `11.9` (版本标签)
- `latest` (最新标签)

### 2. .dockerignore 配置

**文件位置**: `.dockerignore`

**排除内容**:
```
.env           # 环境变量文件（重要：不包含在镜像中）
.env.*         # 所有环境变量文件
node_modules   # Node.js 依赖
.git           # Git 仓库
.gitignore     # Git 忽略文件
.github        # GitHub 配置
.trae          # Trae 配置
supabase       # Supabase 配置
README.md      # 说明文档
```

**重要**: `.env` 文件已被排除，不会包含在 Docker 镜像中，确保敏感信息不会泄露。

### 3. Dockerfile 配置

**基础镜像**: `python:3.11-slim`

**环境变量**:
```bash
HOST=0.0.0.0
PORT=5078
CELERY_WORKER_POOL=prefork
CELERY_WORKER_CONCURRENCY=30
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_TASK_TIME_LIMIT=1200
CELERY_TASK_SOFT_TIME_LIMIT=900
GUNICORN_WORKERS=8
GUNICORN_TIMEOUT=300
GUNICORN_MAX_REQUESTS=500
GUNICORN_MAX_REQUESTS_JITTER=50
```

**暴露端口**: 5078

**启动命令**: `/app/start.sh`

## 使用方法

### 1. 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets:

**Settings → Secrets and variables → Actions → New repository secret**

1. `DOCKER_HUB_USERNAME`: Docker Hub 用户名
2. `DOCKER_HUB_TOKEN`: Docker Hub Access Token

**获取 Docker Hub Access Token**:
1. 登录 Docker Hub
2. 进入 Account Settings → Security
3. 点击 "New Access Token"
4. 选择 "Read, Write, Delete" 权限
5. 复制生成的 Token

### 2. 推送代码触发构建

```bash
# 方式1: 推送到 main 分支
git add .
git commit -m "Update to version 11.9"
git push origin main

# 方式2: 手动触发
# GitHub → Actions → Build and Push Docker Image → Run workflow
```

### 3. 查看构建状态

1. 进入 GitHub 仓库
2. 点击 "Actions" 标签
3. 查看构建进度和日志

### 4. 拉取镜像

构建完成后，可以从 Docker Hub 拉取镜像:

```bash
# 拉取指定版本
docker pull YOUR_USERNAME/aiimagenew:11.9

# 拉取最新版本
docker pull YOUR_USERNAME/aiimagenew:latest
```

## 工作流程

```
本地开发
    ↓
git push origin main
    ↓
GitHub Action 触发
    ↓
检出代码
    ↓
设置 QEMU (多平台支持)
    ↓
设置 Docker Buildx
    ↓
登录 Docker Hub
    ↓
构建 Docker 镜像
    ├─ 平台: linux/amd64, linux/arm64
    ├─ 标签: 11.9, latest
    └─ 排除: .env 等敏感文件
    ↓
推送到 Docker Hub
    ├─ YOUR_USERNAME/aiimagenew:11.9
    └─ YOUR_USERNAME/aiimagenew:latest
    ↓
完成
```

## 本地操作

### 本地构建（不推送）

```bash
# 构建镜像
docker build -t aiimagenew:local .

# 运行容器
docker run -d \
  --name aiimagenew \
  -p 5078:5078 \
  --env-file .env \
  aiimagenew:local
```

### 本地测试

```bash
# 构建并运行
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 版本管理

### 更新版本标签

修改 `.github/workflows/docker-publish.yml`:

```yaml
tags: |
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:11.10  # 更新版本号
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:latest
```

### 版本命名规范

- **主版本号**: 重大更新（如 12.0）
- **次版本号**: 功能更新（如 11.9）
- **修订号**: Bug修复（如 11.9.1）

## 安全注意事项

### 1. .env 文件处理

✅ **已配置**: `.dockerignore` 排除 `.env` 文件

**重要**: 
- `.env` 文件不会包含在镜像中
- 运行容器时需要挂载或传入环境变量
- 敏感信息不会泄露到镜像层

### 2. 运行时配置

```bash
# 方式1: 使用 --env-file
docker run -d \
  --name aiimagenew \
  -p 5078:5078 \
  --env-file .env \
  YOUR_USERNAME/aiimagenew:11.9

# 方式2: 使用 -e 传入环境变量
docker run -d \
  --name aiimagenew \
  -p 5078:5078 \
  -e OPENAI_API_KEY=sk-xxx \
  -e ARK_CHAT_API_KEY=xxx \
  YOUR_USERNAME/aiimagenew:11.9

# 方式3: 使用 docker-compose
# docker-compose.yml 中配置 env_file
```

### 3. Secrets 管理

✅ **GitHub Secrets**: 敏感信息存储在 GitHub Secrets 中
✅ **Docker Hub Token**: 使用 Access Token 而非密码
✅ **.env 排除**: 环境变量文件不包含在镜像中

## 故障排查

### 1. 构建失败

**检查项**:
- GitHub Secrets 是否正确配置
- Docker Hub Token 是否有效
- Dockerfile 语法是否正确
- 依赖是否安装成功

**查看日志**:
- GitHub → Actions → 点击失败的构建 → 查看详细日志

### 2. 推送失败

**可能原因**:
- Docker Hub 用户名错误
- Docker Hub Token 权限不足
- 网络连接问题

**解决方法**:
- 检查 Secrets 配置
- 重新生成 Docker Hub Token
- 重试构建

### 3. 镜像拉取失败

**可能原因**:
- 镜像不存在
- 镜像为私有
- 网络问题

**解决方法**:
```bash
# 登录 Docker Hub
docker login

# 拉取镜像
docker pull YOUR_USERNAME/aiimagenew:11.9
```

## 最佳实践

### 1. 版本控制

- ✅ 每次更新都打上新版本标签
- ✅ `latest` 标签始终指向最新版本
- ✅ 保留历史版本标签

### 2. 安全管理

- ✅ 不在镜像中包含敏感信息
- ✅ 使用 GitHub Secrets 管理凭证
- ✅ 定期更新 Docker Hub Token

### 3. 构建优化

- ✅ 使用多阶段构建减小镜像大小
- ✅ 利用缓存加速构建
- ✅ 多平台支持（amd64/arm64）

### 4. 测试验证

- ✅ 本地测试通过后再推送
- ✅ 检查构建日志
- ✅ 验证镜像功能

## 示例配置

### docker-compose.yml

```yaml
version: '3.8'

services:
  aiimagenew:
    image: YOUR_USERNAME/aiimagenew:11.9
    container_name: aiimagenew
    restart: unless-stopped
    ports:
      - "5078:5078"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

## 总结

✅ **配置完成**:
- GitHub Action 自动构建和推送
- 镜像标签: `11.9` 和 `latest`
- .dockerignore 排除 `.env` 文件
- 多平台支持（amd64/arm64）

✅ **安全保证**:
- 敏感信息不包含在镜像中
- GitHub Secrets 管理凭证
- Docker Hub Token 认证

✅ **使用简单**:
- 推送代码自动构建
- 本地不执行推送操作
- 自动打标签和推送

---

**下一步**: 推送代码到 GitHub，触发自动构建！
