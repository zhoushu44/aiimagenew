# Celery 模块导入错误修复说明

## 问题描述

从日志中可以看到以下错误：

```
ModuleNotFoundError: No module named 'app'
File "/app/celery_tasks.py", line 155, in run_ai_write_task_celery
    from app import run_ai_write_task
```

**错误原因：**
- Celery worker 在执行任务时无法找到 `app` 模块
- Python 模块搜索路径中没有包含 `/app` 目录

## 修复方案

已在 `Dockerfile` 中添加 `PYTHONPATH=/app` 环境变量：

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \  # ← 新增
    HOST=0.0.0.0 \
    ...
```

## 部署步骤

### 方法一：使用部署脚本（推荐）

```bash
# 1. 赋予执行权限
chmod +x deploy.sh

# 2. 运行部署脚本
./deploy.sh

# 3. 根据提示启动容器（需要设置环境变量）
```

### 方法二：手动部署

```bash
# 1. 停止并删除现有容器
docker stop $(docker ps -a -q --filter "ancestor=aiimagenew")
docker rm $(docker ps -a -q --filter "ancestor=aiimagenew")

# 2. 删除旧镜像
docker rmi aiimagenew

# 3. 构建新镜像
docker build -t aiimagenew .

# 4. 启动容器（替换环境变量为实际值）
docker run -d \
  --name aiimagenew \
  -p 5078:5078 \
  -e REDIS_HOST=your_redis_host \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD=your_password \
  -e OPENAI_API_KEY=your_api_key \
  -e OPENAI_BASE_URL=your_base_url \
  -e OPENAI_MODEL=your_model \
  aiimagenew
```

## 验证修复

### 1. 检查容器日志

```bash
docker logs aiimagenew
```

应该看到类似以下输出：

```
[2026-05-10 XX:XX:XX +0000] [1] [INFO] Starting gunicorn 26.0.0
[2026-05-10 XX:XX:XX +0000] [1] [INFO] Listening at: http://0.0.0.0:5078 (1)
...
[2026-05-10 XX:XX:XX,XXX: INFO/MainProcess] celery@xxx ready.
```

### 2. 检查 Celery worker 状态

```bash
docker exec -it aiimagenew celery -A celery_app.celery_app inspect active
```

### 3. 测试功能

访问 `http://localhost:5078/suite` 并测试：
- ✅ AI 帮写功能
- ✅ 风格分析功能
- ✅ 主图生成功能

## 预期结果

修复后，日志中不应该再出现 `ModuleNotFoundError: No module named 'app'` 错误。

成功的日志应该显示：

```
[2026-05-10 XX:XX:XX,XXX: INFO/MainProcess] Task generation.run_ai_write_task[xxx] received
[2026-05-10 XX:XX:XX,XXX: INFO/MainProcess] Task generation.run_style_analysis_task[xxx] received
```

而不是：

```
[2026-05-10 XX:XX:XX,XXX: ERROR/ForkPoolWorker-16] Task generation.run_ai_write_task[xxx] raised unexpected: ModuleNotFoundError("No module named 'app'")
```

## 故障排查

如果问题仍然存在，请检查：

1. **确认 PYTHONPATH 环境变量已设置**

   ```bash
   docker exec -it aiimagenew env | grep PYTHONPATH
   ```

   应该输出：`PYTHONPATH=/app`

2. **确认 app.py 文件存在**

   ```bash
   docker exec -it aiimagenew ls -la /app/app.py
   ```

3. **确认 Python 路径**

   ```bash
   docker exec -it aiimagenew python -c "import sys; print('\n'.join(sys.path))"
   ```

   应该包含 `/app`

## 联系支持

如果问题仍未解决，请提供：
- 完整的错误日志
- Docker 版本信息
- 环境变量配置（隐藏敏感信息）
