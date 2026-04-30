# Mode3 图生图说明

## 当前结论

mode3 的真正图生图接口使用 OpenAI-compatible 的 multipart 图片编辑接口：

```text
POST {MODE3_OPENAI_BASE_URL}/images/edits
```

当前默认 base URL：

```text
https://code.ciyuanapi.xyz/v1
```

最终请求地址：

```text
https://code.ciyuanapi.xyz/v1/images/edits
```

## 配置项

```env
APP_MODE=mode3
MODE3_OPENAI_API_KEY=你的_key
MODE3_OPENAI_BASE_URL=https://code.ciyuanapi.xyz/v1
MODE3_IMAGE_MODEL=gpt-image-2
MODE3_IMAGE_EDIT_SIZE=2048x2048
MODE3_IMAGE_QUALITY=
MODE3_IMAGE_WATERMARK=false
MODE3_TIMEOUT_SECONDS=180
MODE3_RETRY_ATTEMPTS=2
MODE3_RETRY_DELAY_SECONDS=1.5
MODE3_PARALLEL_WORKERS=9
MODE3_PARTIAL_RETRY_ATTEMPTS=2
MODE3_SEQUENTIAL_GENERATION=off
MODE3_SUITE_BATCH_SIZE=1
```

说明：

- `APP_MODE=mode3`：全局应用模式，控制套图、A+ 等走 mode3 链路。可通过 settings 管理页面实时切换，保存后自动刷新 `config.json` 缓存。
- `MODE3_OPENAI_API_KEY`：mode3 图生图接口鉴权 key。
- `MODE3_OPENAI_BASE_URL`：接口域名，代码会自动拼接 `/images/edits`。
- `MODE3_IMAGE_MODEL`：当前使用 `gpt-image-2`。
- `MODE3_IMAGE_EDIT_SIZE`：图生图尺寸，当前建议 `2048x2048`。
- `MODE3_IMAGE_QUALITY`：可选，不填则不传。
- `MODE3_IMAGE_WATERMARK`：默认不加水印。
- `MODE3_TIMEOUT_SECONDS`：单次接口请求超时时间，默认 `180`，最小 `30`。
- `MODE3_RETRY_ATTEMPTS`：单张图生成失败后的重试次数，默认 `2`。
- `MODE3_RETRY_DELAY_SECONDS`：重试间隔秒数，默认 `1.5`。
- `MODE3_PARALLEL_WORKERS`：套图并发线程数，默认 `9`，最小 `1`。mode3 套图（8-9 张）会按这个数量并发生成，总耗时接近单张耗时而非累加。
- `MODE3_PARTIAL_RETRY_ATTEMPTS`：套图部分图片失败后的补图重试次数，默认 `2`。
- `MODE3_SEQUENTIAL_GENERATION`：`off` 强制并行，`on` 强制串行，`auto` 自动（>1 张图时并行）。

## 请求格式

mode3 图生图现在使用 `multipart/form-data` 上传本地图片文件，不再把图片塞到 `extra_body.image`。

核心字段：

```text
model=gpt-image-2
prompt=提示词
size=2048x2048
response_format=url
image=@本地图片文件
```

Python 直连示例：

```python
from pathlib import Path
import requests

api_key = '你的_key'
base_url = 'https://code.ciyuanapi.xyz/v1'
url = f'{base_url}/images/edits'
image_path = Path('1.png')

headers = {
    'Authorization': f'Bearer {api_key}',
}

data = {
    'model': 'gpt-image-2',
    'prompt': '基于输入图片生成新图，保持商品主体一致。',
    'size': '2048x2048',
    'response_format': 'url',
}

with image_path.open('rb') as image_file:
    files = {
        'image': (image_path.name, image_file, 'image/png'),
    }
    response = requests.post(url, headers=headers, data=data, files=files, timeout=180)

response.raise_for_status()
print(response.json())
```

## 返回格式

实测接口返回 JSON：

```json
{
  "data": [
    {
      "url": "https://.../image.png",
      "b64_json": "",
      "revised_prompt": "..."
    }
  ],
  "created": 1777455352
}
```

注意：

- 当前实测 `b64_json` 为空。
- 实际图片需要从 `data[0].url` 下载。
- 后端 `decode_generated_image()` 已支持 URL 下载，且自带重试（最多 3 次），覆盖 SSL/EOF/连接断流等网络错误。

## 套图并发生成

当 `APP_MODE=mode3` 时，套图（suite）生成不再逐张串行，而是按每张规划图各自的 prompt 并发生成：

```text
generate_suite_images()
  -> APP_MODE=mode3 时走 generate_mode3_suite_images_parallel()
  -> 每张图调用 call_mode3_single_image_with_retry()
  -> POST /images/edits multipart（并发 N 个请求，N ≤ MODE3_PARALLEL_WORKERS）
  -> 失败的图按 MODE3_PARTIAL_RETRY_ATTEMPTS 补图重试
  -> 全部完成后按 sort 排序输出
```

实测数据（`MODE3_PARALLEL_WORKERS=9`，`MODE3_RETRY_ATTEMPTS=2`）：

| 张数 | 总耗时 | 相比旧串行 |
|------|--------|-----------|
| 3 张 | ~48 秒 | 原来需 3× 累加 |
| 9 张 | ~56 秒 | 原来需 6-10 分钟 |

## 断流与下载重试

高并发下 API 服务商可能出现 SSL EOF、连接断流等瞬时网络错误，已做三层防护：

1. **API 调用层**：`is_retryable_mode3_error()` 识别 SSL/EOF/连接池等错误为可重试，`call_mode3_single_image_with_retry()` 按 `MODE3_RETRY_ATTEMPTS` 重试。
2. **套图批量层**：`generate_mode3_suite_images_parallel()` 按 `MODE3_PARTIAL_RETRY_ATTEMPTS` 对失败的图补图重试。
3. **图片下载层**：`_download_image_url_with_retry()` 下载 API 返回的图片 URL 时最多重试 3 次。

## 代码位置

主要改动在 `app.py`：

- `get_mode3_api_key()`：读取 mode3 key。
- `get_mode3_base_url()`：读取 mode3 base URL。
- `get_mode3_image_edit_size()`：读取图生图尺寸，默认 `2048x2048`。
- `call_mode3_image_edit()`：调用 `/images/edits`，使用 multipart 文件上传。
- `decode_generated_image()`：支持接口返回 URL 后下载图片，含 `_download_image_url_with_retry()` 重试。
- `is_retryable_mode3_error()`：判断 mode3 错误是否可重试，含 SSL/EOF/连接池等。
- `call_mode3_single_image_with_retry()`：单张图带重试生成。
- `call_mode3_images_parallel_with_partial_retry()`：多张相同 prompt 并发 + 部分重试。
- `build_generated_suite_image_item()`：图片保存 + 结果结构构建。
- `generate_mode3_suite_images_parallel()`：套图每张独立 prompt 并发 + 补图重试。
- `generate_suite_images()`：入口函数，mode3 时走并行路径。

## 当前生成链路

当 `APP_MODE=mode3` 且用户上传了商品图或参考图：

```text
前端上传图片
  -> Flask 读取为 image_payloads
  -> call_mode3_single_image()
  -> call_mode3_image_edit()
  -> POST /images/edits multipart
  -> 返回图片 URL
  -> decode_generated_image() → _download_image_url_with_retry() 下载 URL
  -> 保存到 generated-suites
```

- mode3 文生图也统一走 `/images/edits`：后端会自动生成空白 2k 底图，再以 multipart 方式上传。

## 一致性建议

为了尽量提高商品一致性：

1. 商品图尽量清晰、主体完整、不要太小。
2. 每次图生图建议只生成 1 张，避免批量并发造成漂移。
3. prompt 中明确写：不得重新设计商品、不得改变颜色体系、不得改变 logo/文字位置。
4. 如果要复杂场景，例如人物手持、咖啡店、多个商品，建议分阶段测试：
   - 先只换背景；
   - 再加手持；
   - 再加人物；
   - 最后再加多个商品。
