-- Seed all known API settings with descriptions and defaults
insert into public.api_settings (scope, setting_key, setting_value, description)
values
  ('global', 'HOST', '0.0.0.0', '服务启动地址'),
  ('global', 'PORT', '5078', '服务启动端口'),
  ('global', 'FLASK_DEBUG', 'false', '是否开启调试模式'),
  ('global', 'UPLOAD_MAX_BYTES', '15728640', '上传请求最大字节数'),
  ('global', 'UPLOAD_MAX_FILE_BYTES', '8388608', '单文件上传最大字节数'),
  ('global', 'GENERATED_SUITE_RETENTION_DAYS', '7', '生成结果保留天数'),
  ('global', 'GENERATED_SUITE_RETENTION_COUNT', '20', '生成结果保留数量上限'),
  ('global', 'POINTS_SIGNUP_BONUS', '100', '新用户注册赠送积分'),
  ('global', 'POINTS_DAILY_FREE', '10', '每日免费领取积分'),
  ('global', 'MODE2_ALLOWED_IMAGE_HOSTS', '', '允许远程参考图片的域名白名单'),
  ('global', 'OPENAI_API_KEY', '', 'OpenAI 接口密钥'),
  ('global', 'OPENAI_BASE_URL', 'https://api.nofx.online/v1', 'OpenAI 接口地址'),
  ('global', 'OPENAI_MODEL', 'gpt-5.4-mini', 'OpenAI 聊天模型'),
  ('global', 'ARK_API_KEY', '', 'ARK 接口密钥'),
  ('global', 'ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3', 'ARK 接口地址'),
  ('global', 'ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128', 'ARK 生图模型'),
  ('global', 'ARK_IMAGE_SIZE', '2048x2048', 'ARK 生图默认尺寸'),
  ('global', 'ARK_IMAGE_QUALITY', '', 'ARK 生图质量参数'),
  ('global', 'ARK_IMAGE_WATERMARK', 'false', 'ARK 生图是否加水印'),
  ('global', 'ARK_SEQUENTIAL_IMAGE_GENERATION', 'auto', 'ARK 生图顺序生成模式'),
  ('global', 'ARK_SEQUENTIAL_MAX_IMAGES', '1', 'ARK 顺序生图最大张数'),
  ('global', 'MODE2_OPENAI_API_KEY', '', 'MODE2 接口密钥'),
  ('global', 'MODE2_OPENAI_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3', 'MODE2 接口地址'),
  ('global', 'MODE2_IMAGE_EDIT_MODEL', 'doubao-seedream-5-0-260128', 'MODE2 修图模型'),
  ('global', 'MODE2_TEXT2IMAGE_MODEL', 'doubao-seedream-5-0-260128', 'MODE2 文生图模型'),
  ('global', 'MODE2_DEFAULT_RATIO', '1:1', 'MODE2 默认画幅比例'),
  ('global', 'MODE2_DEFAULT_RESOLUTION', '2048x2048', 'MODE2 默认分辨率'),
  ('global', 'MODE2_DEFAULT_SAMPLE_STRENGTH', '0.65', 'MODE2 默认参考强度')
on conflict (scope, setting_key) do update
set setting_value = excluded.setting_value,
    description = excluded.description;
