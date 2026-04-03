import base64
import json
import mimetypes
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, url_for
from openai import APIError, APIStatusError, OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

app = Flask(__name__, static_folder=None)

SYSTEM_PROMPT = (
    '你是电商商品图识别与商品卖点文案专家。'
    '你必须同时参考用户提供的图片内容与已有文案，输出适合商品详情/作图使用的中文商品文案。'
    '如果图片中某些参数无法确认，可以使用“约”“预估”“图中可见”等保守表达，禁止编造明显精确但无依据的数据。'
)

USER_PROMPT_TEMPLATE = """请结合以下信息，为该商品生成新的中文文案：

用户当前文案：
{selling_text}

要求：
1. 必须优先参考图片中可见内容，多张图片需要综合分析。
2. 同时吸收用户当前文案里的有效信息，但不要机械复述。
3. 只输出以下 5 段，不要添加前言、解释、备注、Markdown 代码块：
商品名称：
核心卖点：
适用人群：
期望场景：
规格参数：
4. 核心卖点尽量清晰、具体、适合电商展示。
5. 如果图片无法确认某项规格，请使用保守表达，不要虚构精确参数。
"""

STYLE_ANALYSIS_SYSTEM_PROMPT = (
    '你是多平台电商商品视觉策略分析专家，擅长根据商品图、核心卖点与目标平台，'
    '为不同平台的主图/辅图生成可执行的视觉风格方向。'
    '你必须输出适合前端直接渲染的 JSON，不要返回任何额外说明。'
)

STYLE_ANALYSIS_USER_PROMPT_TEMPLATE = """请结合当前商品图片与核心卖点，分析适合 {platform} 电商场景的视觉方向。

目标平台：
{platform}

核心卖点：
{selling_text}

输出要求：
1. 仅返回 JSON，不要代码块、不要前言、不要解释。
2. 返回 4 个明显不同的风格方案，避免只是同义改写。
3. 每个风格都必须包含：
   - title：简短风格标题
   - reasoning：一句适合直接展示在卡片上的简短理由
   - colors：恰好 3 个可直接用于前端的十六进制颜色值，例如 #F5C028
4. 风格必须明确贴合 {platform} 的商品主图/辅图策略，不是泛视觉概念。
5. 本次请尽量给出与常见默认答案不同的组合，方便用户重复点击时获得新方向。
6. 请严格按以下 JSON 结构返回：
{{"styles":[{{"title":"","reasoning":"","colors":["#000000","#FFFFFF","#CCCCCC"]}}]}}
"""

SUITE_PLAN_SYSTEM_PROMPT = (
    '你是资深电商商品套图策划专家，擅长根据商品图、卖点、平台与固定图类型结构，'
    '产出可直接进入图生图执行阶段的套图规划 JSON。'
    '你必须只返回 JSON，不允许返回代码块、解释、说明文字。'
)

SUITE_PLAN_USER_PROMPT_TEMPLATE = """请根据参考商品图、平台和卖点，输出本次爆款套图的结构化规划 JSON。

目标平台：
{platform}

国家参考：
{country}

说明文字种类：
{text_type}

图片尺寸比例参考：
{image_size_ratio}

用户当前核心关键词/卖点：
{selling_text}

风格参考：
{style_reference}

本次输出张数：
{output_count}

后端固定图类型顺序（必须保留顺序，不要改数量）：
{type_list}

可用图类型说明：
{type_details}

输出要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 顶层结构必须为：
{{
  "summary": "",
  "output_count": {output_count},
  "items": [
    {{
      "sort": 1,
      "type": "",
      "title": "",
      "keywords": ["", "", ""],
      "prompt": ""
    }}
  ]
}}
3. summary 用一句中文概括本次套图策略。
4. items 长度必须严格等于 {output_count}，sort 必须从 1 开始递增。
5. type 必须严格使用后端给定的图类型，不得自创新 type。
6. title 适合直接作为单张卡片标题，简洁明确。
7. keywords 必须是 3-6 个短语，便于前端展示。
8. prompt 必须是适合图生图的中文指令，需明确：构图重点、场景/背景、文案层级、视觉风格、商品主体保持一致、不要偏离参考商品。
9. 如果用户卖点为空，也必须结合图片可见特征完成规划，但禁止虚构无法确认的精确参数。
10. 每张图都要贴合 {platform} 平台的电商展示逻辑，且彼此分工明确、避免重复。
11. 说明文字种类、图片尺寸比例、国家参考都必须体现在 summary 与每张图的 prompt 中；如果某些卖点或场景与地区强相关，必须优先参考国家信息。
12. 如果说明文字种类为“无文字”，prompt 中必须明确不要在图片中生成任何标题、卖点文案或说明文字；否则应按指定文字种类组织画面文案语言。
13. 如果提供了风格参考，必须优先吸收该风格的视觉气质、色彩倾向、版式氛围与信息层级，并把它们自然融入 summary 与每张图的 prompt；但平台规则、国家参考、文字类型、尺寸比例、商品主体与卖点约束始终优先。
"""

HEX_COLOR_PATTERN = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
SAFE_NAME_PATTERN = re.compile(r'[^0-9a-zA-Z\u4e00-\u9fff_-]+')

SUITE_TYPE_META = {
    '首屏主视觉图': {
        'tag': 'Hero',
        'detail': '首图担当，突出主体识别度、平台主图逻辑与强视觉记忆点。',
    },
    '核心卖点图': {
        'tag': 'Selling',
        'detail': '聚焦 1-3 个核心卖点，用主副标题和信息分层强化转化。',
    },
    '使用场景图': {
        'tag': 'Scene',
        'detail': '展示真实使用环境，让用户快速理解商品用途和适用情境。',
    },
    '商品细节图': {
        'tag': 'Detail',
        'detail': '放大展示材质、结构、做工、关键部件等细节。',
    },
    '参数图': {
        'tag': 'Specs',
        'detail': '承载尺寸、规格、适配信息、容量等参数型信息。',
    },
    '配件/售后图': {
        'tag': 'Support',
        'detail': '展示包装清单、附赠配件、售后承诺或服务亮点。',
    },
    '场景氛围图': {
        'tag': 'Mood',
        'detail': '强调氛围感、生活方式与审美调性，提升点击欲望。',
    },
    '图标卖点图': {
        'tag': 'Icons',
        'detail': '通过图标、短词和模块化布局快速说明多个卖点。',
    },
    '品牌故事图': {
        'tag': 'Brand',
        'detail': '通过品牌感叙事、理念与调性，补足认知与信任。',
    },
    '多角度图': {
        'tag': 'Angles',
        'detail': '展示产品多角度、多面信息或组合视角，补充完整认知。',
    },
}

SUITE_TYPE_RULES = {
    6: ['首屏主视觉图', '核心卖点图', '使用场景图', '商品细节图', '参数图', '配件/售后图'],
    7: ['首屏主视觉图', '核心卖点图', '使用场景图', '场景氛围图', '商品细节图', '参数图', '配件/售后图'],
    8: ['首屏主视觉图', '使用场景图', '场景氛围图', '核心卖点图', '图标卖点图', '商品细节图', '参数图', '配件/售后图'],
    9: ['首屏主视觉图', '使用场景图', '场景氛围图', '品牌故事图', '核心卖点图', '图标卖点图', '商品细节图', '参数图', '配件/售后图'],
    10: ['首屏主视觉图', '使用场景图', '场景氛围图', '品牌故事图', '核心卖点图', '图标卖点图', '商品细节图', '多角度图', '参数图', '配件/售后图'],
}

APLUS_PLAN_SYSTEM_PROMPT = (
    '你是资深电商 A+ 详情页策划专家，擅长根据商品图、卖点、平台与指定模块结构，'
    '产出可直接进入图生图执行阶段的 A+ 页面模块规划 JSON。'
    '你必须只返回 JSON，不允许返回代码块、解释、说明文字。'
)

APLUS_PLAN_USER_PROMPT_TEMPLATE = """请根据参考商品图、平台和卖点，输出本次 A+详情页模块的结构化规划 JSON。

目标平台：
{platform}

国家参考：
{country}

说明文字种类：
{text_type}

图片尺寸比例参考：
{image_size_ratio}

用户当前核心关键词/卖点：
{selling_text}

风格参考：
{style_reference}

本次选中的 A+ 模块顺序（必须保留顺序，不要改数量）：
{module_list}

可用模块说明：
{module_details}

输出要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 顶层结构必须为：
{{
  "summary": "",
  "module_count": {module_count},
  "items": [
    {{
      "sort": 1,
      "type": "",
      "title": "",
      "keywords": ["", "", ""],
      "prompt": ""
    }}
  ]
}}
3. summary 用一句中文概括本次 A+ 页面模块策略，体现模块结构、信息层级、平台语境，以及从首屏到转化说明的内容编排。
4. items 长度必须严格等于 {module_count}，sort 必须从 1 开始递增。
5. type 必须严格使用后端给定的模块名称，不得自创新 type。
6. title 适合直接作为单个模块卡片标题，简洁明确。
7. keywords 必须是 3-6 个短语，便于前端展示。
8. prompt 必须是适合图生图的中文指令，需明确：该模块的版式目标、信息层级、构图重点、文案位置或禁文要求、视觉风格、商品主体保持一致、不要偏离参考商品。
9. 这是 A+ 详情页模块规划，不是普通套图；模块之间必须承担不同的信息职责，并严格匹配本次选中的模块语义，例如：首屏主视觉负责第一屏吸引与核心价值、使用场景图负责真实使用展示、效果对比图负责前后差异表达、详细规格/参数表负责数据化说明、售后保障图负责质保退换与服务承诺。
10. 如果用户卖点为空，也必须结合图片可见特征完成规划，但禁止虚构无法确认的精确参数。
11. 每个模块都要贴合 {platform} 平台的 A+ 内容表达逻辑，且彼此分工明确、避免重复。
12. 说明文字种类、图片尺寸比例、国家参考都必须体现在 summary 与每个模块的 prompt 中；如果某些卖点或场景与地区强相关，必须优先参考国家信息。
13. 如果说明文字种类为“无文字”，prompt 中必须明确不要在图片中生成任何标题、卖点文案或说明文字；否则应按指定文字种类组织模块文案语言。
14. 如果提供了风格参考，必须优先吸收该风格的视觉气质、色彩倾向、版式氛围与信息层级，并把它们自然融入 summary 与每个模块的 prompt；但平台规则、国家参考、文字类型、尺寸比例、商品主体与卖点约束始终优先。
15. 选中的模块可能来自以下 16 类标准模块：首屏主视觉、使用场景图、场景氛围图、品牌故事图、效果对比图、工艺制作图、系列展示图、售后保障图、核心卖点图、多角度图、商品细节图、尺寸/容量/尺码图、详细规格/参数表、配件/赠品图、商品成分图、使用建议图。只有被选中的模块才可出现在 items 中。
16. 对于“尺寸/容量/尺码图”“详细规格/参数表”“商品成分图”这类强信息模块，如图片或文案无法确认精确数据，必须使用保守表达，如“尺寸示意”“参数信息以实物为准”“图中可见材质/成分线索”，禁止编造具体数值。
17. 对于“配件/赠品图”“售后保障图”“效果对比图”这类容易误导的模块，如缺少依据，不要虚构额外赠品、售后政策或夸张功效，应采用克制、可信的表达。
"""

APLUS_MODULE_META = {
    'hero_value': {
        'name': '首屏主视觉',
        'tag': 'Hero',
        'detail': '页面开场主视觉，突出商品主体、品牌识别与核心价值主张。',
    },
    'usage_scene': {
        'name': '使用场景图',
        'tag': 'Scene',
        'detail': '呈现真实使用场景，让用户快速理解商品用途、对象与使用方式。',
    },
    'mood_scene': {
        'name': '场景氛围图',
        'tag': 'Mood',
        'detail': '展示生活方式与情绪氛围，强化审美调性与场景代入感。',
    },
    'brand_story': {
        'name': '品牌故事图',
        'tag': 'Brand',
        'detail': '传达品牌理念、品牌调性、信任背书与故事化表达。',
    },
    'effect_compare': {
        'name': '效果对比图',
        'tag': 'Compare',
        'detail': '用于展示使用前后、升级前后或不同状态下的变化对比。',
    },
    'craft_process': {
        'name': '工艺制作图',
        'tag': 'Craft',
        'detail': '展示工艺制作过程、制造标准、做工流程与品质细节。',
    },
    'series_showcase': {
        'name': '系列展示图',
        'tag': 'Series',
        'detail': '展示多色、多规格、多 SKU 或系列化组合陈列。',
    },
    'after_sales': {
        'name': '售后保障图',
        'tag': 'Support',
        'detail': '说明质保、退换、客服响应、物流或服务承诺等保障信息。',
    },
    'core_selling': {
        'name': '核心卖点图',
        'tag': 'Selling',
        'detail': '聚焦关键差异点与竞争优势，用模块化布局突出转化信息。',
    },
    'multi_angle': {
        'name': '多角度图',
        'tag': 'Angles',
        'detail': '从多个角度呈现外观、轮廓、结构与整体形态。',
    },
    'detail_zoom': {
        'name': '商品细节图',
        'tag': 'Detail',
        'detail': '放大材质、纹理、接口、缝线、边角等局部细节与工艺。',
    },
    'size_capacity': {
        'name': '尺寸/容量/尺码图',
        'tag': 'Size',
        'detail': '展示尺寸、容量、尺码或适配范围等规格信息。',
    },
    'spec_table': {
        'name': '详细规格/参数表',
        'tag': 'Specs',
        'detail': '用表格或信息板形式承载更完整的商品参数与数据说明。',
    },
    'accessories_gifts': {
        'name': '配件/赠品图',
        'tag': 'Bundle',
        'detail': '明确收货包含的配件、赠品、包装内容与清单信息。',
    },
    'ingredients_materials': {
        'name': '商品成分图',
        'tag': 'Formula',
        'detail': '展示配方、材质、面料、成分构成或核心用料信息。',
    },
    'usage_tips': {
        'name': '使用建议图',
        'tag': 'Tips',
        'detail': '说明使用方法、注意事项、禁忌提醒与更佳使用建议。',
    },
}

IMAGE_SIZE_RATIO_MAP = {
    '1:1': '2048x2048',
    '3:4': '1728x2304',
    '9:16': '1440x2560',
    '16:9': '2560x1440',
}


def normalize_platform_label(platform: str) -> str:
    value = (platform or '').strip()
    if not value:
        return '亚马逊'
    if value == '速卖通速卖通':
        return '速卖通'
    return value


def get_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise ValueError(f'缺少环境变量：{name}')
    return value


def get_optional_env(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def sanitize_filename_part(value: str, fallback: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub('-', (value or '').strip()).strip('-_')
    return cleaned[:40] or fallback


def build_task_name(platform: str, mode: str, count: int) -> str:
    mode_label = 'A+详情页' if mode == 'aplus' else '爆款套图'
    count_label = '模块' if mode == 'aplus' else '张'
    return f'{platform}{mode_label}-{count}{count_label}-{datetime.now().strftime("%m%d-%H%M%S")}'


def build_generated_at() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def guess_extension(mime_type: str, fallback: str = '.png') -> str:
    extension = mimetypes.guess_extension(mime_type or '')
    if extension == '.jpe':
        extension = '.jpg'
    return extension or fallback


def resolve_image_size(image_size_ratio: str) -> str:
    ratio = (image_size_ratio or '').strip()
    if ratio in IMAGE_SIZE_RATIO_MAP:
        return IMAGE_SIZE_RATIO_MAP[ratio]
    return get_optional_env('ARK_IMAGE_SIZE', '2048x2048')


def file_to_data_url(file_storage) -> str:
    content = file_storage.read()
    if not content:
        raise ValueError(f'图片 {file_storage.filename or "未命名文件"} 内容为空')

    mime_type = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or '')[0] or 'application/octet-stream'
    encoded = base64.b64encode(content).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


def create_image_payload(file_storage):
    content = file_storage.read()
    if not content:
        raise ValueError(f'图片 {file_storage.filename or "未命名文件"} 内容为空')

    mime_type = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or '')[0] or 'application/octet-stream'
    filename = file_storage.filename or 'image'
    encoded = base64.b64encode(content).decode('utf-8')
    return {
        'filename': filename,
        'mime_type': mime_type,
        'bytes': content,
        'base64': encoded,
        'data_url': f'data:{mime_type};base64,{encoded}',
    }


def get_image_payloads_from_request(limit: int = 3):
    payloads = []
    for image_file in request.files.getlist('images')[:limit]:
        payloads.append(create_image_payload(image_file))
    return payloads


def build_multimodal_content(prompt_text: str, image_files):
    content = [{'type': 'text', 'text': prompt_text}]

    for image_file in image_files:
        if isinstance(image_file, dict):
            image_url = image_file.get('data_url')
        else:
            image_url = file_to_data_url(image_file)
        content.append(
            {
                'type': 'image_url',
                'image_url': {'url': image_url},
            }
        )

    return content


def call_chat_completion(system_prompt: str, user_content, temperature: float = 0.7):
    api_key = get_env('OPENAI_API_KEY')
    base_url = get_env('OPENAI_BASE_URL').rstrip('/')
    model = get_env('OPENAI_MODEL')

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
        'temperature': temperature,
    }

    response = requests.post(
        f'{base_url}/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = response.text.strip()
        raise RuntimeError(
            json.dumps(
                {
                    'error': f'模型接口调用失败（HTTP {response.status_code}）',
                    'details': error_payload,
                },
                ensure_ascii=False,
            )
        )

    data = response.json()
    text = ((data.get('choices') or [{}])[0].get('message') or {}).get('content', '')
    if isinstance(text, list):
        text = ''.join(part.get('text', '') for part in text if isinstance(part, dict))
    text = (text or '').strip()
    if not text:
        raise ValueError('模型接口未返回内容')
    return text


def parse_runtime_error(exc: RuntimeError):
    try:
        payload = json.loads(str(exc))
    except ValueError:
        return {'success': False, 'error': str(exc)}, 502
    return {'success': False, **payload}, 502


def parse_ark_exception(exc: Exception):
    status_code = 502
    details = None

    if isinstance(exc, APIStatusError):
        status_code = exc.status_code or 502
        details = exc.response.text if getattr(exc, 'response', None) else None
    elif isinstance(exc, APIError):
        details = str(exc)
    else:
        details = str(exc)

    return {
        'success': False,
        'error': '图像生成接口调用失败',
        'details': details,
    }, status_code


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


def normalize_hex_color(value: str) -> str:
    color = (value or '').strip()
    if not color:
        raise ValueError('颜色值为空')
    if not color.startswith('#'):
        color = f'#{color}'
    if not HEX_COLOR_PATTERN.fullmatch(color):
        raise ValueError(f'颜色值格式非法：{value}')
    if len(color) == 4:
        color = '#' + ''.join(ch * 2 for ch in color[1:])
    return color.upper()


def parse_style_analysis(text: str):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'风格分析结果格式异常：{exc}') from exc

    styles = payload.get('styles')
    if not isinstance(styles, list) or len(styles) != 4:
        raise ValueError('风格分析结果格式异常：styles 必须为长度 4 的数组')

    normalized_styles = []
    for item in styles:
        if not isinstance(item, dict):
            raise ValueError('风格分析结果格式异常：单个风格必须为对象')

        title = str(item.get('title', '')).strip()
        reasoning = str(item.get('reasoning', '')).strip()
        colors = item.get('colors')

        if not title or not reasoning:
            raise ValueError('风格分析结果格式异常：title 和 reasoning 不能为空')
        if not isinstance(colors, list) or len(colors) != 3:
            raise ValueError('风格分析结果格式异常：colors 必须包含 3 个颜色值')

        normalized_styles.append(
            {
                'title': title,
                'reasoning': reasoning,
                'colors': [normalize_hex_color(color) for color in colors],
            }
        )

    return normalized_styles


def get_suite_type_rules(output_count: int):
    try:
        count = int(output_count)
    except (TypeError, ValueError) as exc:
        raise ValueError('输出数量必须为 6-10 之间的整数') from exc

    if count not in SUITE_TYPE_RULES:
        raise ValueError('输出数量必须为 6-10 之间的整数')
    return count, SUITE_TYPE_RULES[count]


def parse_selected_modules(modules_raw: str):
    try:
        parsed = json.loads((modules_raw or '').strip() or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError('A+ 模块参数格式异常') from exc

    if not isinstance(parsed, list) or not parsed:
        raise ValueError('请至少选择 1 个 A+ 模块')

    selected_keys = []
    seen = set()
    for item in parsed:
        key = str(item or '').strip()
        if not key or key in seen:
            continue
        if key not in APLUS_MODULE_META:
            raise ValueError(f'A+ 模块参数非法：{key}')
        selected_keys.append(key)
        seen.add(key)

    if not selected_keys:
        raise ValueError('请至少选择 1 个 A+ 模块')
    return selected_keys



def parse_selected_style(title: str, reasoning: str, colors_raw: str):
    normalized_title = (title or '').strip()
    normalized_reasoning = (reasoning or '').strip()
    raw_colors = (colors_raw or '').strip()

    if not normalized_title and not normalized_reasoning and not raw_colors:
        return None

    if not normalized_title or not normalized_reasoning:
        raise ValueError('所选风格参数不完整，请重新选择风格后再试')

    try:
        parsed_colors = json.loads(raw_colors or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError('所选风格颜色参数格式异常') from exc

    if not isinstance(parsed_colors, list) or len(parsed_colors) != 3:
        raise ValueError('所选风格颜色参数必须包含 3 个颜色值')

    return {
        'title': normalized_title,
        'reasoning': normalized_reasoning,
        'colors': [normalize_hex_color(color) for color in parsed_colors],
    }


def build_style_reference_text(selected_style) -> str:
    if not selected_style:
        return '未指定风格，请基于平台、卖点、国家、文字类型、尺寸比例与参考图自行规划。'

    color_list = ' / '.join(selected_style.get('colors') or []) or '未提供颜色'
    return (
        f'已选风格标题：{selected_style.get("title", "") or "未命名风格"}\n'
        f'风格说明：{selected_style.get("reasoning", "") or "未提供"}\n'
        f'参考配色：{color_list}'
    )



def build_suite_plan_prompt(platform: str, selling_text: str, output_count: int, type_rules, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    type_list = '\n'.join(f'{index + 1}. {item}' for index, item in enumerate(type_rules))
    type_details = '\n'.join(
        f'- {name}：{SUITE_TYPE_META[name]["detail"]}'
        for name in type_rules
    )
    return SUITE_PLAN_USER_PROMPT_TEMPLATE.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        style_reference=build_style_reference_text(selected_style),
        output_count=output_count,
        type_list=type_list,
        type_details=type_details,
    )


def parse_suite_plan(text: str, expected_output_count: int, allowed_types):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'套图规划结果格式异常：{exc}') from exc

    summary = str(payload.get('summary', '')).strip()
    output_count = payload.get('output_count')
    items = payload.get('items')

    if not summary:
        raise ValueError('套图规划结果格式异常：summary 不能为空')
    if output_count != expected_output_count:
        raise ValueError('套图规划结果格式异常：output_count 与请求不一致')
    if not isinstance(items, list) or len(items) != expected_output_count:
        raise ValueError('套图规划结果格式异常：items 数量与输出张数不一致')

    normalized_items = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError('套图规划结果格式异常：单个套图项必须为对象')

        sort = item.get('sort')
        image_type = str(item.get('type', '')).strip()
        title = str(item.get('title', '')).strip()
        prompt = str(item.get('prompt', '')).strip()
        keywords = item.get('keywords')

        if sort != index:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 sort 非法')
        if image_type not in allowed_types:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 type 非法')
        if not title:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 title 不能为空')
        if not prompt:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 prompt 不能为空')
        if not isinstance(keywords, list) or not (3 <= len(keywords) <= 6):
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 keywords 数量必须为 3-6 个')

        normalized_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
        if len(normalized_keywords) < 3:
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 keywords 不能为空')

        normalized_items.append(
            {
                'sort': sort,
                'type': image_type,
                'title': title,
                'keywords': normalized_keywords,
                'prompt': prompt,
                'type_tag': SUITE_TYPE_META.get(image_type, {}).get('tag', 'Board'),
            }
        )

    return {
        'summary': summary,
        'output_count': expected_output_count,
        'items': normalized_items,
    }


def build_suite_plan(platform: str, selling_text: str, output_count: int, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    _, type_rules = get_suite_type_rules(output_count)
    response_text = call_chat_completion(
        SUITE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_suite_plan_prompt(platform, selling_text, output_count, type_rules, country, text_type, image_size_ratio, selected_style),
            image_payloads,
        ),
        temperature=0.8,
    )
    return parse_suite_plan(response_text, output_count, set(type_rules))


def build_aplus_plan_prompt(platform: str, selling_text: str, selected_module_keys, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    module_names = [APLUS_MODULE_META[key]['name'] for key in selected_module_keys]
    module_list = '\n'.join(f'{index + 1}. {name}' for index, name in enumerate(module_names))
    module_details = '\n'.join(
        f'- {APLUS_MODULE_META[key]["name"]}：{APLUS_MODULE_META[key]["detail"]}'
        for key in selected_module_keys
    )
    return APLUS_PLAN_USER_PROMPT_TEMPLATE.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        style_reference=build_style_reference_text(selected_style),
        module_list=module_list,
        module_details=module_details,
        module_count=len(selected_module_keys),
    )


def parse_aplus_plan(text: str, selected_module_keys):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'A+ 规划结果格式异常：{exc}') from exc

    summary = str(payload.get('summary', '')).strip()
    module_count = payload.get('module_count')
    items = payload.get('items')
    expected_types = [APLUS_MODULE_META[key]['name'] for key in selected_module_keys]

    if not summary:
        raise ValueError('A+ 规划结果格式异常：summary 不能为空')
    if module_count != len(expected_types):
        raise ValueError('A+ 规划结果格式异常：module_count 与请求不一致')
    if not isinstance(items, list) or len(items) != len(expected_types):
        raise ValueError('A+ 规划结果格式异常：items 数量与模块数量不一致')

    normalized_items = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError('A+ 规划结果格式异常：单个模块项必须为对象')

        sort = item.get('sort')
        module_type = str(item.get('type', '')).strip()
        title = str(item.get('title', '')).strip()
        prompt = str(item.get('prompt', '')).strip()
        keywords = item.get('keywords')
        expected_type = expected_types[index - 1]

        if sort != index:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 sort 非法')
        if module_type != expected_type:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 type 必须为 {expected_type}')
        if not title:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 title 不能为空')
        if not prompt:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 prompt 不能为空')
        if not isinstance(keywords, list) or not (3 <= len(keywords) <= 6):
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 keywords 数量必须为 3-6 个')

        normalized_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()]
        if len(normalized_keywords) < 3:
            raise ValueError(f'A+ 规划结果格式异常：第 {index} 项 keywords 不能为空')

        meta = APLUS_MODULE_META[selected_module_keys[index - 1]]
        normalized_items.append(
            {
                'sort': sort,
                'type': module_type,
                'title': title,
                'keywords': normalized_keywords,
                'prompt': prompt,
                'type_tag': meta.get('tag', 'Module'),
            }
        )

    return {
        'summary': summary,
        'module_count': len(expected_types),
        'items': normalized_items,
    }


def build_aplus_plan(platform: str, selling_text: str, selected_module_keys, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    response_text = call_chat_completion(
        APLUS_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_aplus_plan_prompt(platform, selling_text, selected_module_keys, country, text_type, image_size_ratio, selected_style),
            image_payloads,
        ),
        temperature=0.8,
    )
    return parse_aplus_plan(response_text, selected_module_keys)


def get_ark_client() -> OpenAI:
    return OpenAI(
        api_key=get_env('ARK_API_KEY'),
        base_url=get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3').rstrip('/'),
    )


def pick_image_data_entry(data):
    if not isinstance(data, list) or not data:
        raise ValueError('图像生成接口未返回图片数据')
    first_item = data[0]
    if not isinstance(first_item, dict):
        raise ValueError('图像生成接口返回格式异常')
    return first_item


def decode_generated_image(item: dict):
    if item.get('b64_json'):
        return base64.b64decode(item['b64_json']), 'image/png'

    if item.get('url'):
        response = requests.get(item['url'], timeout=120)
        response.raise_for_status()
        mime_type = response.headers.get('Content-Type', 'image/png').split(';', 1)[0].strip()
        return response.content, mime_type

    raise ValueError('图像生成接口未返回可用图片内容')


def save_generated_image(task_id: str, sort: int, image_type: str, image_bytes: bytes, mime_type: str):
    output_dir = BASE_DIR / 'generated-suites' / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    filename = f'{sort:02d}-{sanitize_filename_part(image_type, "image")}{extension}'
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(BASE_DIR).as_posix()
    return filename, relative_path, url_for('serve_generated_file', path=relative_path)


def save_reference_image(task_id: str, sort: int, filename: str, image_bytes: bytes, mime_type: str):
    output_dir = BASE_DIR / 'generated-suites' / task_id / 'references'
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    source_stem = Path(filename or 'reference').stem
    safe_stem = sanitize_filename_part(source_stem, f'reference-{sort:02d}')
    output_name = f'{sort:02d}-{safe_stem}{extension}'
    output_path = output_dir / output_name
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(BASE_DIR).as_posix()
    return output_name, relative_path, url_for('serve_generated_file', path=relative_path)


def build_reference_images(task_id: str, image_payloads):
    reference_images = []

    for index, payload in enumerate(image_payloads, start=1):
        download_name, relative_path, image_url = save_reference_image(
            task_id,
            index,
            payload.get('filename', ''),
            payload.get('bytes', b''),
            payload.get('mime_type', 'image/png'),
        )
        original_name = Path(payload.get('filename') or f'原图 {index}').stem.strip()
        title = original_name or f'原图 {index}'
        reference_images.append(
            {
                'sort': index,
                'kind': 'reference',
                'type': '原图',
                'type_tag': 'Ref',
                'title': title,
                'keywords': [],
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return reference_images


def call_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str):
    model = get_env('ARK_IMAGE_MODEL')
    size = resolve_image_size(image_size_ratio)
    quality = get_optional_env('ARK_IMAGE_QUALITY', '')
    enriched_prompt = (
        f'{prompt}\n\n'
        f'额外执行约束：\n'
        f'- 图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'- 说明文字种类：{text_type or "中文"}\n'
        f'- 国家参考：{country or "中国"}\n'
        f'- 若卖点、生活方式、消费场景、节日氛围或合规表达与地区有关，优先按国家参考进行画面设计与文案表达。'
    )
    request_payload = {
        'model': model,
        'prompt': enriched_prompt,
        'size': size,
        'response_format': 'b64_json',
    }

    extra_body = {}
    if image_payloads:
        extra_body['reference_images'] = [payload['data_url'] for payload in image_payloads]
    if quality:
        extra_body['quality'] = quality
    if extra_body:
        request_payload['extra_body'] = extra_body

    response = client.images.generate(**request_payload)
    response_payload = response.model_dump()
    return pick_image_data_entry(response_payload.get('data'))


def generate_suite_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str):
    client = get_ark_client()
    images = []

    for item in plan['items']:
        generated_item = call_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
        )
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, item['sort'], item['type'], image_bytes, mime_type)
        images.append(
            {
                'sort': item['sort'],
                'kind': 'generated',
                'type': item['type'],
                'type_tag': item['type_tag'],
                'title': item['title'],
                'keywords': item['keywords'],
                'prompt': item['prompt'],
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return images



def generate_aplus_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str):
    client = get_ark_client()
    images = []

    for item in plan['items']:
        generated_item = call_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
        )
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, item['sort'], item['type'], image_bytes, mime_type)
        images.append(
            {
                'sort': item['sort'],
                'kind': 'generated',
                'type': item['type'],
                'type_tag': item['type_tag'],
                'title': item['title'],
                'keywords': item['keywords'],
                'prompt': item['prompt'],
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return images


@app.get('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.get('/generated/<path:path>')
def serve_generated_file(path: str):
    generated_root = BASE_DIR / 'generated-suites'
    return send_from_directory(generated_root, path)


@app.post('/api/ai-write')
def ai_write():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        image_payloads = get_image_payloads_from_request()

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        text = call_chat_completion(
            SYSTEM_PROMPT,
            build_multimodal_content(
                USER_PROMPT_TEMPLATE.format(selling_text=selling_text or '（未填写）'),
                image_payloads,
            ),
            temperature=0.7,
        )

        return jsonify({'success': True, 'text': text})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '模型接口请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'模型接口请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/style-analysis')
def style_analysis():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        platform = normalize_platform_label(request.form.get('platform', '亚马逊'))
        image_payloads = get_image_payloads_from_request()

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        response_text = call_chat_completion(
            STYLE_ANALYSIS_SYSTEM_PROMPT,
            build_multimodal_content(
                STYLE_ANALYSIS_USER_PROMPT_TEMPLATE.format(
                    platform=platform,
                    selling_text=selling_text or '（未填写）',
                ),
                image_payloads,
            ),
            temperature=1,
        )
        styles = parse_style_analysis(response_text)
        return jsonify({'success': True, 'styles': styles})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '模型接口请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'模型接口请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-suite')
def generate_suite():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        platform = normalize_platform_label(request.form.get('platform', '亚马逊'))
        output_count, _ = get_suite_type_rules(request.form.get('output_count', '8'))
        image_payloads = get_image_payloads_from_request()
        country = request.form.get('country', '中国').strip() or '中国'
        text_type = request.form.get('text_type', '中文').strip() or '中文'
        image_size_ratio = request.form.get('image_size_ratio', '1:1').strip() or '1:1'
        selected_style = parse_selected_style(
            request.form.get('selected_style_title', ''),
            request.form.get('selected_style_reasoning', ''),
            request.form.get('selected_style_colors', ''),
        )

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        task_id = uuid.uuid4().hex
        task_name = build_task_name(platform, 'suite', output_count)
        generated_at = build_generated_at()
        reference_images = build_reference_images(task_id, image_payloads)
        plan = build_suite_plan(platform, selling_text, output_count, image_payloads, country, text_type, image_size_ratio, selected_style)
        images = generate_suite_images(plan, image_payloads, task_id, image_size_ratio, text_type, country)

        return jsonify(
            {
                'success': True,
                'mode': 'suite',
                'task_id': task_id,
                'task_name': task_name,
                'generated_at': generated_at,
                'plan': plan,
                'selected_style': selected_style,
                'reference_images': reference_images,
                'images': images,
            }
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


@app.post('/api/generate-aplus')
def generate_aplus():
    try:
        selling_text = request.form.get('selling_text', '').strip()
        platform = normalize_platform_label(request.form.get('platform', '亚马逊'))
        image_payloads = get_image_payloads_from_request()
        country = request.form.get('country', '中国').strip() or '中国'
        text_type = request.form.get('text_type', '中文').strip() or '中文'
        image_size_ratio = request.form.get('image_size_ratio', '1:1').strip() or '1:1'
        selected_modules = parse_selected_modules(request.form.get('selected_modules', ''))
        selected_style = parse_selected_style(
            request.form.get('selected_style_title', ''),
            request.form.get('selected_style_reasoning', ''),
            request.form.get('selected_style_colors', ''),
        )

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        task_id = uuid.uuid4().hex
        task_name = build_task_name(platform, 'aplus', len(selected_modules))
        generated_at = build_generated_at()
        reference_images = build_reference_images(task_id, image_payloads)
        plan = build_aplus_plan(platform, selling_text, selected_modules, image_payloads, country, text_type, image_size_ratio, selected_style)
        images = generate_aplus_images(plan, image_payloads, task_id, image_size_ratio, text_type, country)

        return jsonify(
            {
                'success': True,
                'mode': 'aplus',
                'task_id': task_id,
                'task_name': task_name,
                'generated_at': generated_at,
                'plan': plan,
                'selected_style': selected_style,
                'reference_images': reference_images,
                'images': images,
            }
        )
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except RuntimeError as exc:
        payload, status_code = parse_runtime_error(exc)
        return jsonify(payload), status_code
    except (APIError, APIStatusError) as exc:
        payload, status_code = parse_ark_exception(exc)
        return jsonify(payload), status_code
    except requests.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except requests.RequestException as exc:
        return jsonify({'success': False, 'error': f'请求失败：{exc}'}), 502
    except Exception as exc:
        return jsonify({'success': False, 'error': f'服务端异常：{exc}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
