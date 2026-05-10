# GitHub Action Docker 镜像自动构建和推送说明

## 📋 配置概览

GitHub Action 已配置为自动构建并推送 Docker 镜像到 Docker Hub，镜像会同时打上两个标签：
- `12.2` - 版本标签
- `latest` - 最新版本标签

## 🔄 工作流程

### 触发条件

GitHub Action 会在以下情况自动触发：

1. **推送到 main 分支**
   ```yaml
   on:
     push:
       branches:
         - main
   ```

2. **手动触发**
   - 在 GitHub 仓库页面 → Actions → "Build and Push Docker Image" → Run workflow

### 构建流程

```
代码推送到 main 分支
    ↓
GitHub Action 自动触发
    ↓
检出代码
    ↓
设置 QEMU (支持多架构)
    ↓
设置 Docker Buildx
    ↓
登录 Docker Hub (使用 Secrets)
    ↓
构建 Docker 镜像
    ↓
推送镜像到 Docker Hub
    ├─ username/aiimagenew:12.2
    └─ username/aiimagenew:latest
```

## 📦 镜像标签说明

### 版本标签 (12.2)

- **用途**: 固定版本，用于生产环境部署
- **特点**: 永久保留，不会改变
- **拉取命令**: `docker pull username/aiimagenew:12.2`

### 最新标签 (latest)

- **用途**: 最新版本，用于测试和开发
- **特点**: 每次构建都会更新
- **拉取命令**: `docker pull username/aiimagenew:latest`

## 🔐 必需的 GitHub Secrets

在 GitHub 仓库设置中配置以下 Secrets：

**路径**: Settings → Secrets and variables → Actions → New repository secret

| Secret 名称 | 说明 | 获取方式 |
|-----------|------|---------|
| `DOCKER_HUB_USERNAME` | Docker Hub 用户名 | Docker Hub 个人主页 |
| `DOCKER_HUB_TOKEN` | Docker Hub 访问令牌 | Docker Hub → Account Settings → Security → New Access Token |

### 创建 Docker Hub Token

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 点击右上角头像 → Account Settings
3. 选择 Security → New Access Token
4. 设置权限：
   - Read, Write, Delete (推荐)
   - 或至少 Read, Write
5. 复制生成的 Token（只显示一次）
6. 在 GitHub Secrets 中添加 `DOCKER_HUB_TOKEN`

## 🏗️ 构建配置

### 支持的架构

```yaml
platforms: linux/amd64,linux/arm64
```

- **linux/amd64**: 标准 x86_64 架构（大多数服务器）
- **linux/arm64**: ARM64 架构（如 AWS Graviton、Apple Silicon）

### .dockerignore 配置

以下文件和目录会被排除在镜像构建之外：

```
.env              # 环境变量文件（敏感信息）
.env.*            # 所有环境变量文件
node_modules      # Node.js 依赖
.git              # Git 仓库
.gitignore        # Git 忽略配置
.github           # GitHub 配置
.trae             # Trae 配置
supabase          # Supabase 迁移文件
README.md         # 说明文档
```

**重要**: `.env` 文件已被排除，确保敏感信息不会泄露到镜像中。

## 📝 使用方法

### 方法一：自动触发（推荐）

```bash
# 1. 修改代码
vim app.py

# 2. 提交更改
git add .
git commit -m "Update to version 12.2"

# 3. 推送到 main 分支
git push origin main

# 4. GitHub Action 自动构建并推送
# 访问 https://github.com/your-username/your-repo/actions 查看进度
```

### 方法二：手动触发

1. 访问 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 选择 "Build and Push Docker Image"
4. 点击 "Run workflow"
5. 选择分支（默认 main）
6. 点击 "Run workflow"

## 🔍 验证构建

### 1. 检查 GitHub Action 状态

访问 Actions 页面查看构建状态：
- ✅ 绿色对勾：构建成功
- ❌ 红色叉号：构建失败
- 🟡 黄色圆圈：正在构建

### 2. 检查 Docker Hub

访问 Docker Hub 仓库页面：
- 查看 Tags 标签页
- 应该看到 `12.2` 和 `latest` 两个标签
- 检查镜像大小和架构支持

### 3. 拉取并测试镜像

```bash
# 拉取镜像
docker pull username/aiimagenew:12.2

# 查看镜像信息
docker images username/aiimagenew

# 运行容器测试
docker run -d \
  --name aiimagenew-test \
  -p 5078:5078 \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=your_password \
  -e OPENAI_API_KEY=your_api_key \
  -e OPENAI_BASE_URL=your_base_url \
  -e OPENAI_MODEL=your_model \
  username/aiimagenew:12.2

# 查看容器日志
docker logs aiimagenew-test

# 测试访问
curl http://localhost:5078

# 停止并删除容器
docker stop aiimagenew-test
docker rm aiimagenew-test
```

## 🚀 部署到生产环境

### 使用固定版本标签（推荐）

```bash
# 拉取固定版本
docker pull username/aiimagenew:12.2

# 启动容器
docker run -d \
  --name aiimagenew-prod \
  -p 5078:5078 \
  --restart unless-stopped \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=your_password \
  -e OPENAI_API_KEY=your_api_key \
  -e OPENAI_BASE_URL=your_base_url \
  -e OPENAI_MODEL=your_model \
  username/aiimagenew:12.2
```

### 使用 latest 标签（测试环境）

```bash
# 拉取最新版本
docker pull username/aiimagenew:latest

# 启动容器
docker run -d \
  --name aiimagenew-dev \
  -p 5078:5078 \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=your_password \
  -e OPENAI_API_KEY=your_api_key \
  -e OPENAI_BASE_URL=your_base_url \
  -e OPENAI_MODEL=your_model \
  username/aiimagenew:latest
```

## 🔄 版本更新流程

### 更新到新版本

1. **修改代码**
   ```bash
   vim app.py
   ```

2. **更新版本标签**
   ```yaml
   # .github/workflows/docker-publish.yml
   tags: |
     ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:12.3  # ← 更新版本号
     ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:latest
   ```

3. **提交并推送**
   ```bash
   git add .
   git commit -m "Release version 12.3"
   git push origin main
   ```

4. **等待构建完成**
   - 访问 Actions 页面查看进度
   - 构建成功后，新镜像会自动推送到 Docker Hub

5. **部署新版本**
   ```bash
   # 拉取新版本
   docker pull username/aiimagenew:12.3
   
   # 停止旧容器
   docker stop aiimagenew-prod
   docker rm aiimagenew-prod
   
   # 启动新容器
   docker run -d \
     --name aiimagenew-prod \
     -p 5078:5078 \
     --restart unless-stopped \
     -e ... \
     username/aiimagenew:12.3
   ```

## ⚠️ 注意事项

### 1. 敏感信息保护

- ✅ `.env` 文件已被 `.dockerignore` 排除
- ✅ 环境变量通过容器运行时传入
- ✅ Secrets 存储在 GitHub 中，不会泄露

### 2. 版本管理

- **固定版本标签** (`12.2`) 用于生产环境
- **latest 标签** 用于测试和开发
- 每次更新版本时，同时更新 `latest`

### 3. 构建时间

- 多架构构建（amd64 + arm64）需要较长时间
- 通常需要 5-15 分钟
- 可以在 Actions 页面查看实时进度

### 4. 镜像大小

- 基础镜像：python:3.11-slim
- 预期镜像大小：500MB - 1GB
- 取决于依赖包数量

## 🐛 故障排查

### 构建失败

**检查项：**
1. Docker Hub Secrets 是否正确配置
2. Docker Hub Token 是否过期
3. 代码是否有语法错误
4. 依赖包是否正确安装

**查看日志：**
- Actions → 选择失败的 workflow → 查看详细日志

### 推送失败

**可能原因：**
1. Docker Hub 用户名或 Token 错误
2. Docker Hub 仓库权限不足
3. 网络连接问题

**解决方法：**
```bash
# 本地测试登录
echo $DOCKER_HUB_TOKEN | docker login -u $DOCKER_HUB_USERNAME --password-stdin

# 本地测试构建
docker build -t username/aiimagenew:test .

# 本地测试推送
docker push username/aiimagenew:test
```

### 镜像拉取失败

**可能原因：**
1. 镜像不存在
2. 权限不足（私有仓库）
3. 网络连接问题

**解决方法：**
```bash
# 登录 Docker Hub
docker login

# 拉取镜像
docker pull username/aiimagenew:12.2
```

## 📊 最佳实践

### 1. 版本标签策略

- 使用语义化版本号（如 12.2）
- 每次重大更新递增主版本号
- 每次功能更新递增次版本号
- 每次修复更新递增修订号

### 2. 分支管理

- `main` 分支：生产代码，自动构建
- `develop` 分支：开发代码，手动构建
- 功能分支：测试代码，不构建

### 3. 安全最佳实践

- ✅ 使用 GitHub Secrets 存储敏感信息
- ✅ 使用 Docker Hub Access Token 而非密码
- ✅ 定期更新 Token
- ✅ 使用最小权限原则

### 4. 性能优化

- 使用 Docker layer cache
- 优化 .dockerignore 减少构建上下文
- 使用多阶段构建减小镜像大小

## 📚 相关文档

- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Docker Hub 官方文档](https://docs.docker.com/docker-hub/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)

---

**最后更新**: 2026-05-10  
**版本**: 12.2  
**维护者**: AI Assistant
