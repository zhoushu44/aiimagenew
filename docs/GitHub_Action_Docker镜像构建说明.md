# GitHub Action Docker 镜像构建说明

## 📋 配置概述

本项目使用 GitHub Action 自动构建和推送 Docker 镜像到 Docker Hub。

## 🏷️ 镜像标签策略

### 当前配置
- **版本标签**: `12.3`
- **最新标签**: `latest`

### 完整镜像地址
```
<DOCKER_HUB_USERNAME>/aiimagenew:12.3
<DOCKER_HUB_USERNAME>/aiimagenew:latest
```

## 🚀 触发条件

### 自动触发
- **触发分支**: `main`
- **触发事件**: Push 到 main 分支

### 手动触发
- **方式**: GitHub Action 界面手动运行
- **权限**: 需要仓库写权限

## 🔧 构建配置

### 平台支持
- `linux/amd64` - 64位 Intel/AMD 处理器
- `linux/arm64` - 64位 ARM 处理器（如 Apple M1/M2）

### 构建优化
- **缓存**: 使用 GitHub Actions 缓存加速构建
- **多平台**: 使用 QEMU 模拟器和 Buildx 构建多平台镜像

## 🔐 安全配置

### Docker Hub 认证
需要在 GitHub 仓库的 Secrets 中配置：

1. **DOCKER_HUB_USERNAME**: Docker Hub 用户名
2. **DOCKER_HUB_TOKEN**: Docker Hub 访问令牌

### 敏感文件排除
`.dockerignore` 文件确保以下内容不会被打包到镜像中：

```
.env
.env.*
node_modules
.git
.gitignore
.github
.trae
supabase
README.md
```

**重要**: `.env` 文件已被排除，确保敏感信息不会泄露。

## 📝 使用说明

### 本地开发
本地开发时，**不需要**执行任何 Docker 推送操作。

### 发布新版本
1. 更新 `.github/workflows/docker-publish.yml` 中的版本号
2. 提交并推送到 `main` 分支
3. GitHub Action 自动构建并推送镜像

### 版本号更新示例
```yaml
tags: |
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:12.4  # 更新版本号
  ${{ secrets.DOCKER_HUB_USERNAME }}/aiimagenew:latest
```

## 🔄 工作流程

### 构建流程
1. **Checkout** - 检出代码
2. **Setup QEMU** - 设置多平台模拟器
3. **Setup Buildx** - 设置 Docker Buildx
4. **Login** - 登录 Docker Hub
5. **Build & Push** - 构建并推送镜像

### 推送结果
- ✅ 镜像自动推送到 Docker Hub
- ✅ 同时打上版本标签和 latest 标签
- ✅ 支持多平台架构

## 📊 构建状态

### 查看构建日志
1. 访问 GitHub 仓库
2. 点击 "Actions" 标签
3. 选择对应的 workflow 运行记录

### 构建时间
- **首次构建**: 约 10-15 分钟
- **缓存构建**: 约 3-5 分钟

## 🛠️ 故障排除

### 构建失败
1. 检查 Docker Hub 凭证是否正确
2. 检查 `.dockerignore` 配置
3. 查看 GitHub Action 日志

### 推送失败
1. 验证 Docker Hub Token 是否有效
2. 检查 Docker Hub 用户名是否正确
3. 确认 Docker Hub 仓库权限

## 📋 检查清单

### 发布前检查
- [ ] 更新版本号
- [ ] 测试代码功能
- [ ] 检查敏感文件排除
- [ ] 验证 Docker Hub 凭证

### 发布后验证
- [ ] 检查 GitHub Action 状态
- [ ] 验证 Docker Hub 镜像
- [ ] 测试拉取镜像
- [ ] 验证多平台支持

## 🎯 最佳实践

### 版本管理
- 使用语义化版本号（如 12.3）
- 保持 `latest` 标签指向最新稳定版本
- 考虑使用 Git 标签自动生成版本号

### 安全建议
- 定期更新 Docker Hub Token
- 使用最小权限原则
- 定期检查 `.dockerignore` 配置

### 性能优化
- 利用 GitHub Actions 缓存
- 优化 Dockerfile 层级
- 使用多阶段构建

## 📚 相关文档

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker Buildx 文档](https://docs.docker.com/buildx/working-with-buildx/)
- [Docker Hub 文档](https://docs.docker.com/docker-hub/)

---

**更新时间**: 2026-05-10  
**配置版本**: v12.3  
**维护人**: AI Assistant
