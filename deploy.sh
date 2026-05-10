#!/bin/bash
# Docker 镜像重新构建和部署脚本

set -e

echo "============================================================"
echo "AI Image New - Docker 部署脚本"
echo "============================================================"

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker"
    exit 1
fi

echo ""
echo "步骤 1/4: 停止现有容器..."
echo "------------------------------------------------------------"
CONTAINERS=$(docker ps -a --filter "ancestor=aiimagenew" --format "{{.ID}}")
if [ -n "$CONTAINERS" ]; then
    echo "找到容器: $CONTAINERS"
    docker stop $CONTAINERS || true
    docker rm $CONTAINERS || true
    echo "✅ 容器已停止并删除"
else
    echo "未找到现有容器"
fi

echo ""
echo "步骤 2/4: 删除旧镜像..."
echo "------------------------------------------------------------"
if docker images | grep -q "aiimagenew"; then
    docker rmi aiimagenew || true
    echo "✅ 旧镜像已删除"
else
    echo "未找到旧镜像"
fi

echo ""
echo "步骤 3/4: 构建新镜像..."
echo "------------------------------------------------------------"
docker build -t aiimagenew .
echo "✅ 新镜像构建完成"

echo ""
echo "步骤 4/4: 启动容器..."
echo "------------------------------------------------------------"
echo "请确保以下环境变量已设置："
echo "  - REDIS_HOST"
echo "  - REDIS_PORT"
echo "  - REDIS_PASSWORD"
echo "  - 其他必要的环境变量"
echo ""
echo "启动命令示例："
echo "docker run -d \\"
echo "  --name aiimagenew \\"
echo "  -p 5078:5078 \\"
echo "  -e REDIS_HOST=your_redis_host \\"
echo "  -e REDIS_PORT=6379 \\"
echo "  -e REDIS_PASSWORD=your_password \\"
echo "  -e OPENAI_API_KEY=your_api_key \\"
echo "  -e OPENAI_BASE_URL=your_base_url \\"
echo "  -e OPENAI_MODEL=your_model \\"
echo "  aiimagenew"
echo ""
echo "============================================================"
echo "✅ 部署脚本执行完成"
echo "============================================================"
