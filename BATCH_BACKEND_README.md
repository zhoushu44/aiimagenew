# 批量任务后端实现说明

## 已完成的功能

### 1. 数据库模型 ✅
- 创建了 `batch_models.py` 文件，包含所有数据库操作函数
- 创建了 `database/batch_tables.sql` 文件，包含数据库表创建语句

### 2. API接口 ✅
已实现以下API接口：

#### POST /api/batch/create
创建批量任务
- 接收配置和图片文件
- 创建批次记录和任务记录
- 返回批次ID

#### GET /api/batch/{batch_id}/progress
查询任务进度
- 返回批次状态和所有任务的进度

#### POST /api/batch/{batch_id}/cancel
取消批次任务
- 更新批次和任务状态为cancelled

### 3. 文件上传处理 ✅
- 支持多文件上传
- 使用FormData格式传输
- 文件命名格式：`images_{taskId}_{imageIndex}`

## 需要继续完善的功能

### 1. 任务队列和异步处理
需要实现：
- 使用Celery或Redis队列
- 异步处理任务
- 实时更新进度

**建议实现方式：**
```python
# 创建 batch_worker.py
from celery import Celery
from batch_models import update_task_progress, update_task_result

celery_app = Celery('batch_worker', broker='redis://localhost:6379/0')

@celery_app.task
def process_batch_task(batch_id, task_id, config, input_images):
    # 更新进度：开始处理
    update_task_progress(task_id, 20, '分析图片中', 'processing')
    
    # 调用AI生成服务
    update_task_progress(task_id, 40, '生成提示词')
    
    # 生成图片
    update_task_progress(task_id, 60, 'AI处理中')
    
    # 保存结果
    update_task_progress(task_id, 80, '优化结果')
    
    # 完成
    update_task_result(task_id, result_images, 'completed')
```

### 2. AI生成服务集成
需要实现：
- 根据gen_type调用不同的生成服务
- 商品套图生成
- A+详情页生成
- 服饰穿戴生成

**建议实现方式：**
```python
# 创建 batch_generation.py
from generation import generate_suite_images, generate_aplus_images

def generate_batch_images(gen_type, config, input_images):
    if gen_type == 'suite':
        return generate_suite_images(config, input_images)
    elif gen_type == 'aplus':
        return generate_aplus_images(config, input_images)
    elif gen_type == 'fashion':
        return generate_fashion_images(config, input_images)
```

### 3. 图片存储
需要实现：
- 上传图片到对象存储（OSS/COS）
- 生成缩略图
- 返回图片URL

### 4. 前端集成
需要修改 `pages/batch.html`：
- 实现真实的API调用
- 实现进度轮询
- 实现取消功能

**示例代码：**
```javascript
// 创建批量任务
async function createBatchTask() {
    const formData = new FormData();
    formData.append('config', JSON.stringify(config));
    formData.append('tasks', JSON.stringify(tasks));
    
    // 添加图片文件
    pendingImages.forEach((img, index) => {
        formData.append(`images_1_${index}`, img.file);
    });
    
    const response = await fetch('/api/batch/create', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    return result.data.batchId;
}

// 轮询进度
async function pollProgress(batchId) {
    const response = await fetch(`/api/batch/${batchId}/progress`);
    const result = await response.json();
    
    // 更新UI
    updateProgressUI(result.data);
    
    // 如果未完成，继续轮询
    if (result.data.status !== 'completed') {
        setTimeout(() => pollProgress(batchId), 2000);
    }
}
```

## 数据库表创建

在Supabase中执行以下SQL：
```bash
psql -f database/batch_tables.sql
```

或者在Supabase Dashboard的SQL Editor中执行 `batch_tables.sql` 文件内容。

## 测试API

### 1. 创建批量任务
```bash
curl -X POST http://localhost:5078/api/batch/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "config={\"genType\":\"suite\",\"platform\":\"亚马逊\"}" \
  -F "tasks=[{\"taskId\":1,\"imageCount\":2}]" \
  -F "images_1_0=@/path/to/image1.jpg" \
  -F "images_1_1=@/path/to/image2.jpg"
```

### 2. 查询进度
```bash
curl http://localhost:5078/api/batch/batch_20260504_123456/progress \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. 取消任务
```bash
curl -X POST http://localhost:5078/api/batch/batch_20260504_123456/cancel \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 下一步工作

1. **安装依赖**
   ```bash
   pip install celery redis
   ```

2. **启动Redis**
   ```bash
   redis-server
   ```

3. **启动Celery Worker**
   ```bash
   celery -A batch_worker worker --loglevel=info
   ```

4. **修改前端代码**
   - 实现真实的API调用
   - 实现进度轮询
   - 实现取消功能

5. **测试完整流程**
   - 上传图片
   - 创建任务
   - 查看进度
   - 获取结果

## 注意事项

1. **安全性**
   - 验证用户权限
   - 限制文件大小
   - 防止重复提交

2. **性能优化**
   - 使用异步处理
   - 图片压缩
   - CDN加速

3. **错误处理**
   - 记录错误日志
   - 失败重试机制
   - 用户友好的错误提示

## 联系方式

如有问题，请联系开发团队。
