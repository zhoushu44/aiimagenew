import base64
import importlib.util
import os
from datetime import datetime
from pathlib import Path

APP_PATH = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/app.py')
DEFAULT_PRODUCT_PATH = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/1.png')
DEFAULT_MODEL_PATH = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/generated-suites/307c91a48f604ed6abdefc5a83e07110/01-fashion-model.png')
PROMPT = (
    '请生成1张服饰穿搭图。产品穿在模特身上，必须清晰可见真人模特完整上身展示该商品。'
    '严格使用提供的模特图作为最终出镜人物，保持同一张脸、发型、气质与身形特征。'
    '严格使用提供的商品图作为服饰主体，保持款式、颜色、结构、材质、logo位置与细节一致。'
    '禁止只生成衣服，禁止平铺挂拍，禁止无头模特，禁止新增任何可见文字。'
    '背景简洁，突出模特穿着商品的真实电商展示效果。'
)


def load_module():
    spec = importlib.util.spec_from_file_location('fashion_app_single_test', APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_payload(path: Path, mime_type: str):
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode('utf-8')
    return {
        'filename': path.name,
        'mime_type': mime_type,
        'bytes': data,
        'base64': encoded,
        'data_url': f'data:{mime_type};base64,{encoded}',
    }


def resolve_input_path(env_name: str, fallback: Path):
    raw = str(os.environ.get(env_name, '')).strip()
    return Path(raw) if raw else fallback


module = load_module()
product_path = resolve_input_path('FASHION_TEST_PRODUCT_PATH', DEFAULT_PRODUCT_PATH)
model_path = resolve_input_path('FASHION_TEST_MODEL_PATH', DEFAULT_MODEL_PATH)
product_payload = build_payload(product_path, 'image/png')
model_payload = build_payload(model_path, 'image/png')
image_payloads = [model_payload, product_payload]

generated_items = module.call_image_generation(
    module.get_ark_client(),
    PROMPT,
    image_payloads,
    '1:1',
    '无文字',
    '中国',
    None,
    'fashion-look',
    max_images=1,
)

generated_item = generated_items[0]
image_bytes, mime_type = module.decode_generated_image(generated_item)
task_id = f"single-fashion-manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

with module.app.test_request_context():
    download_name, relative_path, image_url = module.save_generated_image(
        task_id,
        1,
        'fashion-look',
        image_bytes,
        mime_type,
    )

print('product_path=', product_path.as_posix())
print('model_path=', model_path.as_posix())
print('task_id=', task_id)
print('download_name=', download_name)
print('relative_path=', relative_path)
print('image_url=', image_url)
print('saved_file=', (module.GENERATED_SUITES_DIR / relative_path).as_posix())
