# GitHub Action Docker 镜像构建配置修改说明

## ✅ 已完成的修改

### 1. 修改 GitHub Action 配置

**文件**: `.github/workflows/docker-publish.yml`

**修改内容**:
```yaml
# 修改前
tags: |
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:12.1
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:latest

# 修改后
tags: |
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:12.2
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:latest
```

### 2. 确认 .dockerignore 配置

**文件**: `.dockerignore`

**已排除的文件**:
```
.env          # ✅ 环境变量文件（敏感信息）
.env.*        # ✅ 所有环境变量文件
node_modules  # Node.js 依赖
.git          # Git 仓库
.gitignore    # Git 忽略配置
.github       # GitHub 配置
.trae         # Trae 配置
supabase      # Supabase 迁移文件
README.md     # 说明文档
```

## 📋 配置说明

### 镜像标签

构建完成后，Docker Hub 上会有两个标签：

| 标签 | 用途 | 特点 |
|-----|------|------|
| `12.2` | 固定版本 | 永久保留，用于生产环境 |
| `latest` | 最新版本 | 每次构建更新，用于测试环境 |

### 触发方式

1. **自动触发**: 推送代码到 `main` 分支
2. **手动触发**: GitHub Actions 页面手动运行

### 构建架构

支持多架构构建：
- `linux/amd64` - 标准 x86_64 架构
- `linux/arm64` - ARM64 架构

## 🚀 使用方法

### 推送代码自动构建

```bash
# 1. 提交代码
git add .
git commit -m "Update to version 12.2"

# 2. 推送到 main 分支
git push origin main

# 3. GitHub Action 自动构建并推送
# 访问 https://github.com/your-username/your-repo/actions 查看进度
```

### 拉取镜像

```bash
# 拉取固定版本
docker pull username/aiimagenew:12.2

# 或拉取最新版本
docker pull username/aiimagenew:latest
```

### 运行容器

```bash
docker run -d \
  --name aiimagenew \
  -p 5078:5078 \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=your_password \
  -e OPENAI_API_KEY=your_api_key \
  -e OPENAI_BASE_URL=your_base_url \
  -e OPENAI_MODEL=your_model \
  username/aiimagenew:12.2
```

## ⚠️ 重要提示

### 1. 本地不执行推送

- ✅ 所有构建和推送由 GitHub Action 自动完成
- ✅ 本地只需要提交代码到 GitHub
- ✅ 无需本地执行 `docker push`

### 2. 敏感信息保护

- ✅ `.env` 文件已被 `.dockerignore` 排除
- ✅ 环境变量通过容器运行时传入
- ✅ 不会泄露到镜像中

### 3. GitHub Secrets 配置

确保已在 GitHub 仓库中配置以下 Secrets：

- `DOCKER_HUB_USERNAME` - Docker Hub 用户名
- `DOCKER_HUB_TOKEN` - Docker Hub 访问令牌

**配置路径**: Settings → Secrets and variables → Actions

## 📊 验证步骤

### 1. 检查 GitHub Action

推送代码后，访问 Actions 页面：
- ✅ 应该看到 "Build and Push Docker Image" workflow 正在运行
- ✅ 等待构建完成（通常 5-15 分钟）

### 2. 检查 Docker Hub

访问 Docker Hub 仓库页面：
- ✅ 应该看到 `12.2` 和 `latest` 两个标签
- ✅ 检查镜像大小和架构支持

### 3. 测试镜像

```bash
# 拉取镜像
docker pull username/aiimagenew:12.2

# 运行容器
docker run -d --name test -p 5078:5078 username/aiimagenew:12.2

# 查看日志
docker logs test

# 测试访问
curl http://localhost:5078
```

## 📁 相关文件

| 文件 | 说明 |
|-----|------|
| `.github/workflows/docker-publish.yml` | GitHub Action 配置文件 |
| `.dockerignore` | Docker 构建排除文件 |
| `Dockerfile` | Docker 镜像构建文件 |
| `docs/GitHub_Action_Docker镜像自动构建说明.md` | 详细使用文档 |

## 🎯 下一步

1. **提交修改到 GitHub**
   ```bash
   git add .
   git commit -m "Update Docker image version to 12.2"
   git push origin main
   ```

2. **等待 GitHub Action 构建**
   - 访问 Actions 页面查看进度
   - 等待构建完成

3. **验证镜像**
   - 在 Docker Hub 查看新镜像
   - 拉取并测试镜像

---

**修改时间**: 2026-05-10  
**版本**: 12.2  
**状态**: ✅ 已完成
