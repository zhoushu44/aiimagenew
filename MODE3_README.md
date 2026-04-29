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
MODE3_SUITE_BATCH_SIZE=1
```

说明：

- `MODE3_OPENAI_API_KEY`：mode3 图生图接口鉴权 key。
- `MODE3_OPENAI_BASE_URL`：接口域名，代码会自动拼接 `/images/edits`。
- `MODE3_IMAGE_MODEL`：当前使用 `gpt-image-2`。
- `MODE3_IMAGE_EDIT_SIZE`：图生图尺寸，当前建议 `2048x2048`。
- `MODE3_IMAGE_QUALITY`：可选，不填则不传。
- `MODE3_IMAGE_WATERMARK`：默认不加水印。
- `MODE3_TIMEOUT_SECONDS`：接口请求超时时间。
- `MODE3_SUITE_BATCH_SIZE`：建议为 `1`，逐张生成更利于商品一致性。

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
- 后端 `decode_generated_image()` 已支持 URL 下载，所以现有保存流程可以继续使用。

## 代码位置

主要改动在 `app.py`：

- `get_mode3_api_key()`：读取 mode3 key。
- `get_mode3_base_url()`：读取 mode3 base URL。
- `get_mode3_image_edit_size()`：读取图生图尺寸，默认 `1024x1024`。
- `call_mode3_image_edit()`：调用 `/images/edits`，使用 multipart 文件上传。
- `decode_generated_image()`：支持接口返回 URL 后下载图片。

## 当前生成链路

当 `APP_MODE=mode3` 且用户上传了商品图或参考图：

```text
前端上传图片
  -> Flask 读取为 image_payloads
  -> call_mode3_single_image()
  -> call_mode3_image_edit()
  -> POST /images/edits multipart
  -> 返回图片 URL
  -> decode_generated_image() 下载 URL
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
