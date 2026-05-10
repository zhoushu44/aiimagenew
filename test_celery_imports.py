#!/usr/bin/env python3
"""测试 Celery 任务模块导入是否正常"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

print("=" * 60)
print("测试 Celery 任务模块导入")
print("=" * 60)

# 测试1: 导入 celery_app
print("\n[1/3] 测试导入 celery_app...")
try:
    from celery_app import celery_app
    print("✅ celery_app 导入成功")
except Exception as e:
    print(f"❌ celery_app 导入失败: {e}")
    sys.exit(1)

# 测试2: 导入 celery_tasks
print("\n[2/3] 测试导入 celery_tasks...")
try:
    import celery_tasks
    print("✅ celery_tasks 导入成功")
except Exception as e:
    print(f"❌ celery_tasks 导入失败: {e}")
    sys.exit(1)

# 测试3: 导入 app 模块中的函数
print("\n[3/3] 测试导入 app 模块中的函数...")
try:
    from app import (
        run_generation_task,
        run_replicate_generation_task,
        run_fashion_model_task,
        run_mode_image_task,
        run_aplus_task,
        run_zip_task,
        run_ai_write_task,
        run_style_analysis_task,
    )
    print("✅ app 模块函数导入成功")
    print("   - run_generation_task")
    print("   - run_replicate_generation_task")
    print("   - run_fashion_model_task")
    print("   - run_mode_image_task")
    print("   - run_aplus_task")
    print("   - run_zip_task")
    print("   - run_ai_write_task")
    print("   - run_style_analysis_task")
except Exception as e:
    print(f"❌ app 模块函数导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
print("\n修复说明：")
print("1. 已在 Dockerfile 中添加 PYTHONPATH=/app 环境变量")
print("2. 这将确保 Celery worker 能够正确导入 app 模块")
print("\n下一步操作：")
print("1. 重新构建 Docker 镜像: docker build -t aiimagenew .")
print("2. 重启容器")
print("3. 验证 Celery worker 是否正常工作")
