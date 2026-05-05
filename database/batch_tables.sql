-- 批量任务表
CREATE TABLE IF NOT EXISTS batch_tasks (
    batch_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    gen_type VARCHAR(20) NOT NULL,
    platform VARCHAR(50),
    country VARCHAR(50),
    text_type VARCHAR(20),
    ratio VARCHAR(10),
    selling_points TEXT,
    prompt_config JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    estimated_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    cancel_reason VARCHAR(255)
);

-- 批量任务项表
CREATE TABLE IF NOT EXISTS batch_task_items (
    task_id VARCHAR(64) PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL REFERENCES batch_tasks(batch_id) ON DELETE CASCADE,
    task_index INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    current_step VARCHAR(100),
    input_images JSONB,
    result_images JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE
);

-- 批量任务图片表
CREATE TABLE IF NOT EXISTS batch_task_images (
    image_id VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    task_id VARCHAR(64) NOT NULL REFERENCES batch_task_items(task_id) ON DELETE CASCADE,
    image_type VARCHAR(20) NOT NULL,
    scene_type VARCHAR(50),
    url VARCHAR(500) NOT NULL,
    thumbnail_url VARCHAR(500),
    file_name VARCHAR(255),
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_batch_user_id ON batch_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_tasks(status);
CREATE INDEX IF NOT EXISTS idx_batch_created_at ON batch_tasks(created_at);

CREATE INDEX IF NOT EXISTS idx_task_batch_id ON batch_task_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_task_status ON batch_task_items(status);

CREATE INDEX IF NOT EXISTS idx_image_task_id ON batch_task_images(task_id);
CREATE INDEX IF NOT EXISTS idx_image_type ON batch_task_images(image_type);

-- 添加注释
COMMENT ON TABLE batch_tasks IS '批量任务表';
COMMENT ON TABLE batch_task_items IS '批量任务项表';
COMMENT ON TABLE batch_task_images IS '批量任务图片表';

COMMENT ON COLUMN batch_tasks.batch_id IS '批次ID';
COMMENT ON COLUMN batch_tasks.user_id IS '用户ID';
COMMENT ON COLUMN batch_tasks.gen_type IS '生成类型：suite/aplus/fashion';
COMMENT ON COLUMN batch_tasks.status IS '状态：pending/processing/completed/failed/cancelled';

COMMENT ON COLUMN batch_task_items.task_id IS '任务ID';
COMMENT ON COLUMN batch_task_items.task_index IS '任务序号';
COMMENT ON COLUMN batch_task_items.status IS '状态：pending/processing/completed/failed/cancelled';
COMMENT ON COLUMN batch_task_items.progress IS '进度百分比 0-100';

COMMENT ON COLUMN batch_task_images.image_type IS '图片类型：input/output';
COMMENT ON COLUMN batch_task_images.scene_type IS '场景类型：hero/usage/detail等';
