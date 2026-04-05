import base64
import binascii
import io
import json
import mimetypes
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory, url_for
from openai import APIError, APIStatusError, OpenAI
from werkzeug.exceptions import RequestEntityTooLarge

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

app = Flask(__name__, static_folder=str(BASE_DIR / 'static'), static_url_path='/static')

MAX_IMAGE_UPLOADS = 3
ALLOWED_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
IMAGE_SIGNATURES = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/webp': [b'RIFF'],
    'image/gif': [b'GIF87a', b'GIF89a'],
    'image/bmp': [b'BM'],
}
UPLOAD_MAX_BYTES = max(int((os.getenv('UPLOAD_MAX_BYTES') or str(15 * 1024 * 1024)).strip() or 0), 1)
UPLOAD_MAX_FILE_BYTES = max(int((os.getenv('UPLOAD_MAX_FILE_BYTES') or str(8 * 1024 * 1024)).strip() or 0), 1)
GENERATED_SUITE_RETENTION_DAYS = max(int((os.getenv('GENERATED_SUITE_RETENTION_DAYS') or '7').strip() or 0), 0)
GENERATED_SUITE_RETENTION_COUNT = max(int((os.getenv('GENERATED_SUITE_RETENTION_COUNT') or '20').strip() or 0), 0)
GENERATED_SUITES_DIR = BASE_DIR / 'generated-suites'
app.config['MAX_CONTENT_LENGTH'] = UPLOAD_MAX_BYTES

SYSTEM_PROMPT = (
    '你是电商商品图识别与商品卖点文案专家。'
    '你必须同时参考用户提供的图片内容与已有文案，输出适合商品详情/作图使用的中文商品文案。'
    '如果图片中某些参数无法确认，可以使用“约”“预估”“图中可见”等保守表达，禁止编造明显精确但无依据的数据。'
)

PRODUCT_JSON_SYSTEM_PROMPT = (
    '你是电商商品信息结构化提取专家。'
    '你必须严格根据商品图片与已有卖点文案，提取后续生图保持商品一致性所需的商品主体 JSON。'
    '你只能输出合法 JSON，不要输出代码块、解释或额外文字。'
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

PRODUCT_JSON_USER_PROMPT_TEMPLATE = """请结合当前商品图片与卖点信息，提取后续生图保持商品一致性所需的结构化商品 JSON。

用户当前文案：
{selling_text}

要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 只能提取图片中明确可见，或文案中明确给出的商品信息；不确定就写空字符串、空数组，或使用“图中可见”“未明确”。
3. 输出内容服务于后续商品一致性生图，必须优先锁定商品主体，而不是营销文案。
4. 顶层结构必须为：
{{
  "product_name": "",
  "category": "",
  "core_subject": "",
  "selling_points": [""],
  "visible_attributes": {{
    "color": "",
    "material": "",
    "pattern": "",
    "shape": "",
    "structure": "",
    "craft_details": [""]
  }},
  "specs": {{
    "size": "",
    "capacity": "",
    "weight": "",
    "applicable_people": "",
    "usage_scene": ""
  }},
  "consistency_rules": [""]
}}
5. consistency_rules 至少返回 4 条，明确说明生图时哪些主体特征必须保持一致，例如颜色、材质、轮廓、结构、比例、关键细节、图案位置、品牌位等。
6. selling_points 最多返回 6 条，craft_details 最多返回 6 条。
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

FASHION_SCENE_PLAN_SYSTEM_PROMPT = (
    '你是服饰穿搭视觉策划专家，擅长围绕服装主体一致性、模特外观、镜头语言与场景氛围，'
    '为前端生成可直接渲染的场景推荐 JSON。你必须只输出合法 JSON，不要附加解释。'
)

FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE = """请基于当前服装商品图与模特参考，为服饰穿搭生成推荐场景方案。

目标平台：
{platform}

国家参考：
{country}

文字类型：
{text_type}

输出比例：
{image_size_ratio}

核心卖点：
{selling_text}

风格参考：
{style_reference}

要求：
1. 商品图用于锁定服饰主体、颜色、材质、版型、图案与细节一致性，不得替换商品主体。
2. 模特参考图只用于锁定人物外观、穿着承载对象、姿态方向与镜头气质。
3. 需要输出 3 组推荐场景，每组 2 个姿态方案。
4. 场景描述要适合电商服饰穿戴图，避免过于复杂或喧宾夺主的背景。
5. 每个 pose 都要清楚区分姿态、构图与镜头感，便于前端让用户继续选择景别和视角。
6. scene_prompt 与 pose.scene_prompt 都必须是可直接用于后续生图拼接的中文短句，突出服装一致性优先。
7. 只返回如下 JSON 结构，不要返回 Markdown：
{{
  "summary": "整体推荐说明",
  "scene_prompt": "适用于整组候选的总场景提示",
  "scene_groups": [
    {{
      "id": "scene-group-1",
      "title": "场景组标题",
      "description": "场景组说明",
      "scene_prompt": "该场景组提示词短句",
      "poses": [
        {{
          "id": "pose-1",
          "title": "姿态标题",
          "description": "姿态说明",
          "scene_prompt": "该姿态提示词短句"
        }}
      ]
    }}
  ]
}}
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

商品主体结构化信息：
{product_json}

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
14. 每张图的 prompt 都必须把“参考商品图中的主体款式、颜色、材质、结构、比例、边缘轮廓、关键细节、品牌位与可见设计元素保持一致”作为最高优先级，不允许只保留大致品类。
15. 风格变化只能发生在构图、背景、光线、文案排版与氛围上，不能把参考图商品改成另一种外观、另一种材质表现、另一种颜色体系或另一种结构。
16. 如果参考图已经体现了明确的摄影风格、打光方式、背景纯度、镜头距离或版式密度，prompt 必须优先延续这些可见特征，再做当前图类型需要的局部变化。
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

商品主体结构化信息：
{product_json}

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


def get_optional_int_env(name: str, default: int) -> int:
    value = get_optional_env(name, str(default))
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f'环境变量 {name} 必须为整数') from exc


def get_optional_bool_env(name: str, default: bool = False) -> bool:
    value = get_optional_env(name, '1' if default else '0').lower()
    return value in {'1', 'true', 'yes', 'on'}


def sanitize_filename_part(value: str, fallback: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub('-', (value or '').strip()).strip('-_')
    return cleaned[:40] or fallback


def build_task_name(platform: str, mode: str, count: int) -> str:
    if mode == 'aplus':
        mode_label = 'A+详情页'
        count_label = '模块'
    elif mode == 'fashion':
        mode_label = '服饰穿搭'
        count_label = '张'
    else:
        mode_label = '爆款套图'
        count_label = '张'
    return f'{platform}{mode_label}-{count}{count_label}-{datetime.now().strftime("%m%d-%H%M%S")}'


def build_generated_at() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def guess_extension(mime_type: str, fallback: str = '.png') -> str:
    extension = mimetypes.guess_extension(mime_type or '')
    if extension == '.jpe':
        extension = '.jpg'
    return extension or fallback


def sniff_image_mime_type(content: bytes):
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        return 'image/webp'

    for mime_type, signatures in IMAGE_SIGNATURES.items():
        if any(content.startswith(signature) for signature in signatures):
            return mime_type
    return None


def validate_image_file(file_storage, content: bytes):
    filename = file_storage.filename or '未命名文件'
    extension = Path(filename).suffix.lower()
    declared_mime_type = (file_storage.mimetype or '').split(';', 1)[0].strip().lower()
    detected_mime_type = sniff_image_mime_type(content)

    if not content:
        raise ValueError(f'图片 {filename} 内容为空')
    if len(content) > UPLOAD_MAX_FILE_BYTES:
        raise ValueError(f'图片 {filename} 超过单张大小限制（{UPLOAD_MAX_FILE_BYTES // (1024 * 1024)}MB）')
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f'图片 {filename} 格式不受支持，仅支持 JPG、PNG、WEBP、GIF、BMP')
    if declared_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError(f'图片 {filename} MIME 类型不受支持：{declared_mime_type or "未知类型"}')
    if not detected_mime_type:
        raise ValueError(f'图片 {filename} 不是有效的图片文件')
    if detected_mime_type != declared_mime_type:
        raise ValueError(f'图片 {filename} 文件内容与类型声明不一致')

    return detected_mime_type


def cleanup_generated_suites(active_task_id: str | None = None):
    if not GENERATED_SUITES_DIR.exists():
        return

    task_dirs = [path for path in GENERATED_SUITES_DIR.iterdir() if path.is_dir()]
    if not task_dirs:
        return

    now = datetime.now()
    removable_dirs = []
    for path in task_dirs:
        if active_task_id and path.name == active_task_id:
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        removable_dirs.append((path, modified_at))

    if GENERATED_SUITE_RETENTION_DAYS > 0:
        expire_before = now - timedelta(days=GENERATED_SUITE_RETENTION_DAYS)
        for path, modified_at in removable_dirs:
            if modified_at < expire_before and path.exists():
                shutil.rmtree(path, ignore_errors=True)

    if GENERATED_SUITE_RETENTION_COUNT > 0:
        survivors = []
        for path in GENERATED_SUITES_DIR.iterdir():
            if not path.is_dir():
                continue
            if active_task_id and path.name == active_task_id:
                continue
            survivors.append((path, path.stat().st_mtime))
        survivors.sort(key=lambda item: item[1], reverse=True)
        for path, _ in survivors[GENERATED_SUITE_RETENTION_COUNT:]:
            shutil.rmtree(path, ignore_errors=True)


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
    mime_type = validate_image_file(file_storage, content)
    filename = file_storage.filename or 'image'
    encoded = base64.b64encode(content).decode('utf-8')
    return {
        'filename': filename,
        'mime_type': mime_type,
        'bytes': content,
        'base64': encoded,
        'data_url': f'data:{mime_type};base64,{encoded}',
    }




def parse_string_list(value: str, field_label: str):
    raw = (value or '').strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f'{field_label} 参数格式异常') from exc

    if not isinstance(parsed, list):
        raise ValueError(f'{field_label} 参数必须为数组')

    return [str(item).strip() for item in parsed if str(item).strip()]


def get_image_payloads_from_request(field_name: str = 'images', limit: int = MAX_IMAGE_UPLOADS):
    image_files = request.files.getlist(field_name)
    if len(image_files) > limit:
        raise ValueError(f'最多仅支持上传 {limit} 张图片')

    payloads = []
    for image_file in image_files:
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


PRODUCT_JSON_FALLBACK = {
    'product_name': '',
    'category': '',
    'core_subject': '',
    'selling_points': [],
    'visible_attributes': {
        'color': '',
        'material': '',
        'pattern': '',
        'shape': '',
        'structure': '',
        'craft_details': [],
    },
    'specs': {
        'size': '',
        'capacity': '',
        'weight': '',
        'applicable_people': '',
        'usage_scene': '',
    },
    'consistency_rules': [],
}


PRODUCT_JSON_PROMPT_TEMPLATE = (
    '商品主体结构化信息（用于保持商品一致性，若为空则代表暂未提取）：\n{product_json_text}\n\n'
    '执行要求：\n'
    '1. 后续所有规划与生图都必须优先遵守以上商品结构化信息。\n'
    '2. 尤其要锁定商品主体、颜色、材质、轮廓、结构比例、图案位置、工艺细节与品牌位，不得偏离。\n'
    '3. 若结构化信息中的某些字段为空，只能依据参考图可见信息保守补足，不能擅自改造成另一种商品。'
)


def normalize_product_json(raw_value):
    payload = raw_value if isinstance(raw_value, dict) else {}
    visible_attributes = payload.get('visible_attributes') if isinstance(payload.get('visible_attributes'), dict) else {}
    specs = payload.get('specs') if isinstance(payload.get('specs'), dict) else {}

    selling_points_raw = payload.get('selling_points') if isinstance(payload.get('selling_points'), list) else []
    craft_details_raw = visible_attributes.get('craft_details') if isinstance(visible_attributes.get('craft_details'), list) else []
    consistency_rules_raw = payload.get('consistency_rules') if isinstance(payload.get('consistency_rules'), list) else []

    selling_points = [str(item).strip() for item in selling_points_raw if str(item).strip()][:6]
    craft_details = [str(item).strip() for item in craft_details_raw if str(item).strip()][:6]
    consistency_rules = [str(item).strip() for item in consistency_rules_raw if str(item).strip()]

    return {
        'product_name': str(payload.get('product_name', '')).strip(),
        'category': str(payload.get('category', '')).strip(),
        'core_subject': str(payload.get('core_subject', '')).strip(),
        'selling_points': selling_points,
        'visible_attributes': {
            'color': str(visible_attributes.get('color', '')).strip(),
            'material': str(visible_attributes.get('material', '')).strip(),
            'pattern': str(visible_attributes.get('pattern', '')).strip(),
            'shape': str(visible_attributes.get('shape', '')).strip(),
            'structure': str(visible_attributes.get('structure', '')).strip(),
            'craft_details': craft_details,
        },
        'specs': {
            'size': str(specs.get('size', '')).strip(),
            'capacity': str(specs.get('capacity', '')).strip(),
            'weight': str(specs.get('weight', '')).strip(),
            'applicable_people': str(specs.get('applicable_people', '')).strip(),
            'usage_scene': str(specs.get('usage_scene', '')).strip(),
        },
        'consistency_rules': consistency_rules,
    }



def parse_product_json(text: str):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'商品结构化信息格式异常：{exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息格式异常：顶层必须为对象')
    return normalize_product_json(payload)



def parse_product_json_payload(raw_value: str):
    normalized_raw = (raw_value or '').strip()
    if not normalized_raw:
        return None
    try:
        payload = json.loads(normalized_raw)
    except json.JSONDecodeError as exc:
        raise ValueError('商品结构化信息参数格式异常') from exc
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息参数格式异常：顶层必须为对象')
    return normalize_product_json(payload)



def serialize_product_json(product_json) -> str:
    normalized = normalize_product_json(product_json or PRODUCT_JSON_FALLBACK)
    return json.dumps(normalized, ensure_ascii=False, indent=2)



def build_product_json_prompt_text(product_json) -> str:
    if not product_json:
        return '未提供结构化商品信息。'
    return PRODUCT_JSON_PROMPT_TEMPLATE.format(product_json_text=serialize_product_json(product_json))



def build_suite_plan_prompt(platform: str, selling_text: str, output_count: int, type_rules, country: str, text_type: str, image_size_ratio: str, selected_style=None, mode: str = 'suite', product_json=None):
    type_list = '\n'.join(f'{index + 1}. {item}' for index, item in enumerate(type_rules))
    type_details = '\n'.join(
        f'- {name}：{SUITE_TYPE_META[name]["detail"]}'
        for name in type_rules
    )
    prompt_template = SUITE_PLAN_USER_PROMPT_TEMPLATE
    if mode == 'fashion':
        prompt_template = (
            SUITE_PLAN_USER_PROMPT_TEMPLATE
            + '\n14. 当前为服饰穿搭场景：商品图用于锁定服饰主体、颜色、材质、版型与细节一致性；如同时提供穿搭参考图，则只用于吸收模特姿态、穿搭方式、镜头语言、氛围与版式方向，不得替换商品主体本身。\n'
            + '15. 服饰场景下，prompt 必须优先保证商品主体与商品图一致，其次再融合参考图里的姿态、氛围与构图灵感。'
        )
    product_json_text = build_product_json_prompt_text(product_json)
    return prompt_template.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        style_reference=build_style_reference_text(selected_style),
        product_json=product_json_text,
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




def build_suite_plan(platform: str, selling_text: str, output_count: int, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None, mode: str = 'suite', product_json=None):
    _, type_rules = get_suite_type_rules(output_count)
    response_text = call_chat_completion(
        SUITE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_suite_plan_prompt(platform, selling_text, output_count, type_rules, country, text_type, image_size_ratio, selected_style, mode, product_json),
            image_payloads,
        ),
        temperature=0.8,
    )
    return parse_suite_plan(response_text, output_count, type_rules)



def parse_fashion_scene_plan(text: str):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'场景规划结果格式异常：{exc}') from exc

    summary = str(payload.get('summary', '')).strip()
    scene_prompt = str(payload.get('scene_prompt', '')).strip()
    scene_groups = payload.get('scene_groups')

    if not summary:
        raise ValueError('场景规划结果格式异常：summary 不能为空')
    if not scene_prompt:
        raise ValueError('场景规划结果格式异常：scene_prompt 不能为空')
    if not isinstance(scene_groups, list) or len(scene_groups) < 1:
        raise ValueError('场景规划结果格式异常：scene_groups 不能为空')

    normalized_groups = []
    for group_index, group in enumerate(scene_groups, start=1):
        if not isinstance(group, dict):
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组必须为对象')

        group_id = str(group.get('id', '')).strip() or f'scene-group-{group_index}'
        title = str(group.get('title', '')).strip()
        description = str(group.get('description', '')).strip()
        group_scene_prompt = str(group.get('scene_prompt', '')).strip()
        poses = group.get('poses')

        if not title:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 title 不能为空')
        if not description:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 description 不能为空')
        if not group_scene_prompt:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 scene_prompt 不能为空')
        if not isinstance(poses, list) or len(poses) < 1:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 poses 不能为空')

        normalized_poses = []
        for pose_index, pose in enumerate(poses, start=1):
            if not isinstance(pose, dict):
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态必须为对象')

            pose_id = str(pose.get('id', '')).strip() or f'{group_id}-pose-{pose_index}'
            pose_title = str(pose.get('title', '')).strip()
            pose_description = str(pose.get('description', '')).strip()
            pose_scene_prompt = str(pose.get('scene_prompt', '')).strip()

            if not pose_title:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 title 不能为空')
            if not pose_description:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 description 不能为空')
            if not pose_scene_prompt:
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态 scene_prompt 不能为空')

            normalized_poses.append(
                {
                    'id': pose_id,
                    'title': pose_title,
                    'description': pose_description,
                    'scene_prompt': pose_scene_prompt,
                }
            )

        normalized_groups.append(
            {
                'id': group_id,
                'title': title,
                'description': description,
                'scene_prompt': group_scene_prompt,
                'poses': normalized_poses,
            }
        )

    return {
        'summary': summary,
        'scene_prompt': scene_prompt,
        'scene_groups': normalized_groups,
    }


def build_fashion_scene_plan_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    return FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE.format(
        platform=platform,
        country=country or '中国',
        text_type=text_type or '中文',
        image_size_ratio=image_size_ratio or '1:1',
        selling_text=selling_text or '（未填写）',
        style_reference=build_style_reference_text(selected_style),
    )



def build_fashion_scene_plan(platform: str, selling_text: str, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    response_text = call_chat_completion(
        FASHION_SCENE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_fashion_scene_plan_prompt(platform, selling_text, country, text_type, image_size_ratio, selected_style),
            image_payloads,
        ),
        temperature=0.85,
    )
    return parse_fashion_scene_plan(response_text)



def parse_json_string_list(raw_value: str, field_label: str):
    try:
        parsed = json.loads((raw_value or '').strip() or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError(f'{field_label}参数格式异常') from exc

    if not isinstance(parsed, list):
        raise ValueError(f'{field_label}参数格式异常')

    normalized = []
    seen = set()
    for item in parsed:
        value = str(item or '').strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized



def parse_fashion_scene_plan_payload(raw_value: str):
    normalized = (raw_value or '').strip()
    if not normalized:
        raise ValueError('场景规划数据不能为空，请重新生成推荐场景')

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError('场景规划数据格式异常，请重新生成推荐场景') from exc

    return parse_fashion_scene_plan(json.dumps(payload, ensure_ascii=False))



def find_fashion_scene_selection(scene_groups, scene_group_id: str, pose_id: str):
    selected_group = None
    selected_pose = None

    for group in scene_groups:
        if group.get('id') != scene_group_id:
            continue
        selected_group = group
        for pose in group.get('poses') or []:
            if pose.get('id') == pose_id:
                selected_pose = pose
                break
        break

    if not selected_group:
        raise ValueError('请选择有效的场景组')
    if not selected_pose:
        raise ValueError('请选择有效的姿态方案')

    return selected_group, selected_pose



def build_fashion_generation_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style, scene_plan: dict, selected_group: dict, selected_pose: dict, shot_sizes, view_angles):
    shot_text = '、'.join(shot_sizes) if shot_sizes else '未指定'
    angle_text = '、'.join(view_angles) if view_angles else '未指定'
    style_reference = build_style_reference_text(selected_style)
    scene_summary = str(scene_plan.get('summary', '')).strip() or '未提供'
    scene_prompt = str(scene_plan.get('scene_prompt', '')).strip() or ''
    group_prompt = str(selected_group.get('scene_prompt', '')).strip() or ''
    pose_prompt = str(selected_pose.get('scene_prompt', '')).strip() or ''

    text_rule = '画面中不要生成任何标题、卖点文案或说明文字。' if (text_type or '中文') == '无文字' else f'若需要文字表达，使用{text_type or "中文"}组织极少量且自然的电商表达。'

    return (
        f'请生成 1 张服饰穿戴图，严格围绕商品图与模特参考完成最终画面。\n\n'
        f'目标平台：{platform}\n'
        f'国家参考：{country or "中国"}\n'
        f'说明文字种类：{text_type or "中文"}\n'
        f'图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'核心卖点：{selling_text or "（未填写）"}\n'
        f'风格参考：\n{style_reference}\n\n'
        f'场景规划摘要：{scene_summary}\n'
        f'整组场景提示：{scene_prompt or "未提供"}\n'
        f'已选场景组：{selected_group.get("title", "未命名场景组")}\n'
        f'场景组说明：{selected_group.get("description", "未提供")}\n'
        f'场景组提示：{group_prompt or "未提供"}\n'
        f'已选姿态：{selected_pose.get("title", "未命名姿态")}\n'
        f'姿态说明：{selected_pose.get("description", "未提供")}\n'
        f'姿态提示：{pose_prompt or "未提供"}\n'
        f'镜头景别：{shot_text}\n'
        f'视角选择：{angle_text}\n\n'
        f'执行要求：\n'
        f'1. 商品图用于严格锁定服饰主体，必须保持款式、颜色、材质、版型、图案与细节一致，不得替换商品本身。\n'
        f'2. 模特参考图只用于锁定人物外观、体态、穿着承载对象与人物气质，不得改变商品主体。\n'
        f'3. 画面必须体现已选场景组、姿态、镜头景别与视角信息，背景简洁，服务于服装展示。\n'
        f'4. 优先输出适合电商服饰穿戴展示的完整成图，突出服装上身效果、版型、面料垂感与搭配氛围。\n'
        f'5. {text_rule}\n'
        f'6. 若卖点、场景氛围、生活方式表达与地区有关，优先参考国家信息。'
    )


def build_aplus_plan_prompt(platform: str, selling_text: str, selected_module_keys, country: str, text_type: str, image_size_ratio: str, selected_style=None, product_json=None):
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
        product_json=build_product_json_prompt_text(product_json),
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


def build_aplus_plan(platform: str, selling_text: str, selected_module_keys, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None, product_json=None):
    response_text = call_chat_completion(
        APLUS_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_aplus_plan_prompt(platform, selling_text, selected_module_keys, country, text_type, image_size_ratio, selected_style, product_json),
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
    cleanup_generated_suites(active_task_id=task_id)
    output_dir = GENERATED_SUITES_DIR / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    filename = f'{sort:02d}-{sanitize_filename_part(image_type, "image")}{extension}'
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    return filename, relative_path, url_for('serve_generated_file', path=relative_path)


def save_reference_image(task_id: str, sort: int, filename: str, image_bytes: bytes, mime_type: str):
    cleanup_generated_suites(active_task_id=task_id)
    output_dir = GENERATED_SUITES_DIR / task_id / 'references'
    output_dir.mkdir(parents=True, exist_ok=True)
    extension = guess_extension(mime_type)
    source_stem = Path(filename or 'reference').stem
    safe_stem = sanitize_filename_part(source_stem, f'reference-{sort:02d}')
    output_name = f'{sort:02d}-{safe_stem}{extension}'
    output_path = output_dir / output_name
    output_path.write_bytes(image_bytes)
    relative_path = output_path.relative_to(GENERATED_SUITES_DIR).as_posix()
    return output_name, relative_path, url_for('serve_generated_file', path=relative_path)


def build_reference_images(task_id: str, image_payloads, source: str = 'product', start_sort: int = 1):
    reference_images = []
    source_meta = {
        'product': {'type': '商品原图', 'type_tag': 'Prod', 'reference_source': 'product'},
        'fashion_reference': {'type': '穿搭参考图', 'type_tag': 'Look', 'reference_source': 'fashion_reference'},
    }
    meta = source_meta.get(source, source_meta['product'])

    for offset, payload in enumerate(image_payloads):
        sort = start_sort + offset
        download_name, relative_path, image_url = save_reference_image(
            task_id,
            sort,
            payload.get('filename', ''),
            payload.get('bytes', b''),
            payload.get('mime_type', 'image/png'),
        )
        original_name = Path(payload.get('filename') or f'{meta["type"]} {sort}').stem.strip()
        title = original_name or f'{meta["type"]} {sort}'
        reference_images.append(
            {
                'sort': sort,
                'kind': 'reference',
                'type': meta['type'],
                'type_tag': meta['type_tag'],
                'reference_source': meta['reference_source'],
                'title': title,
                'keywords': [],
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
            }
        )

    return reference_images


def call_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None):
    model = get_env('ARK_IMAGE_MODEL')
    size = resolve_image_size(image_size_ratio)
    quality = get_optional_env('ARK_IMAGE_QUALITY', '')
    product_json_text = build_product_json_prompt_text(product_json)
    enriched_prompt = (
        f'{prompt}\n\n'
        f'商品主体结构化信息：\n{product_json_text}\n\n'
        f'额外执行约束：\n'
        f'- 图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'- 说明文字种类：{text_type or "中文"}\n'
        f'- 国家参考：{country or "中国"}\n'
        f'- 若提供了结构化商品信息，必须把其中的商品名称、核心主体、可见属性、规格线索与 consistency_rules 视为最终生图约束，优先保持商品主体一致。\n'
        f'- 若提供了参考商品图，必须把参考图视为主体锚点，优先复用其商品外观、颜色关系、材质质感、结构比例、边缘轮廓、关键细节与整体摄影气质。\n'
        f'- 除非 prompt 明确要求改变场景或版式，否则不要随意改变参考图的背景基调、打光方向、镜头距离、俯仰角、陈列方式与主视觉风格。\n'
        f'- 所有创意变化都应建立在商品主体与参考图风格高度一致的前提下，禁止生成与参考图差异过大的新商品、新材质观感或新色系。\n'
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


def generate_suite_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
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
            product_json,
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



def generate_aplus_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
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
            product_json,
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


@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(_exc):
    return jsonify({'success': False, 'error': f'上传内容过大，请控制在 {UPLOAD_MAX_BYTES // (1024 * 1024)}MB 以内'}), 413


@app.get('/')
def index():
    return send_from_directory(BASE_DIR, 'landing.html')


@app.get('/suite')
def suite_page():
    return send_from_directory(BASE_DIR, 'suite.html')


@app.get('/aplus')
def aplus_page():
    return send_from_directory(BASE_DIR, 'aplus.html')


@app.get('/fashion')
def fashion_page():
    return send_from_directory(BASE_DIR, 'fashion.html')


@app.get('/generated/<path:path>')
def serve_generated_file(path: str):
    return send_from_directory(GENERATED_SUITES_DIR, path)


@app.post('/api/download-zip')
def download_zip():
    try:
        payload = request.get_json(silent=True) or {}
        image_paths = payload.get('image_paths')
        if not isinstance(image_paths, list) or not image_paths:
            return jsonify({'success': False, 'error': '请至少选择 1 张图片后再下载'}), 400

        zip_buffer = io.BytesIO()
        used_names = set()

        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for index, raw_path in enumerate(image_paths, start=1):
                relative_path = str(raw_path or '').strip().replace('\\', '/').lstrip('/')
                if not relative_path:
                    continue
                file_path = (GENERATED_SUITES_DIR / relative_path).resolve()
                try:
                    file_path.relative_to(GENERATED_SUITES_DIR.resolve())
                except ValueError:
                    continue
                if not file_path.is_file():
                    continue

                base_name = Path(relative_path).name or f'image-{index:02d}{file_path.suffix or ".png"}'
                stem = Path(base_name).stem or f'image-{index:02d}'
                suffix = Path(base_name).suffix or file_path.suffix or '.png'
                archive_name = f'{stem}{suffix}'
                duplicate_index = 2
                while archive_name in used_names:
                    archive_name = f'{stem}-{duplicate_index}{suffix}'
                    duplicate_index += 1
                used_names.add(archive_name)
                archive.write(file_path, arcname=archive_name)

        if not used_names:
            return jsonify({'success': False, 'error': '未找到可下载的图片文件'}), 404

        zip_buffer.seek(0)
        download_name = f'ai-images-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=download_name)
    except Exception as exc:
        return jsonify({'success': False, 'error': f'打包下载失败：{exc}'}), 500


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
        product_json = None
        if image_payloads or text:
            product_json_text = call_chat_completion(
                PRODUCT_JSON_SYSTEM_PROMPT,
                build_multimodal_content(
                    PRODUCT_JSON_USER_PROMPT_TEMPLATE.format(selling_text=text or selling_text or '（未填写）'),
                    image_payloads,
                ),
                temperature=0.2,
            )
            product_json = parse_product_json(product_json_text)

        return jsonify({'success': True, 'text': text, 'product_json': product_json})
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
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
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
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
        mode = (request.form.get('mode', 'suite') or 'suite').strip() or 'suite'
        image_payloads = get_image_payloads_from_request('images')
        fashion_reference_payloads = get_image_payloads_from_request('reference_images') if mode == 'fashion' else []
        country = request.form.get('country', '中国').strip() or '中国'
        text_type = request.form.get('text_type', '中文').strip() or '中文'
        image_size_ratio = request.form.get('image_size_ratio', '1:1').strip() or '1:1'
        product_json = parse_product_json_payload(request.form.get('product_json', ''))
        selected_style = parse_selected_style(
            request.form.get('selected_style_title', ''),
            request.form.get('selected_style_reasoning', ''),
            request.form.get('selected_style_colors', ''),
        )

        if not selling_text and not image_payloads:
            return jsonify({'success': False, 'error': '请至少提供核心卖点文案或上传 1 张图片'}), 400

        if mode == 'fashion':
            fashion_action = (request.form.get('fashion_action', 'generate') or 'generate').strip() or 'generate'
            planning_payloads = image_payloads + fashion_reference_payloads
            if not planning_payloads:
                return jsonify({'success': False, 'error': '请至少上传商品图或模特参考图'}), 400

            if fashion_action == 'scene_plan':
                scene_plan = build_fashion_scene_plan(
                    platform,
                    selling_text,
                    planning_payloads,
                    country,
                    text_type,
                    image_size_ratio,
                    selected_style,
                )
                return jsonify(
                    {
                        'success': True,
                        'mode': 'fashion',
                        'fashion_action': 'scene_plan',
                        'plan': scene_plan,
                        'selected_style': selected_style,
                    }
                )

            scene_plan = parse_fashion_scene_plan_payload(request.form.get('fashion_scene_plan', ''))
            scene_group_id = (request.form.get('fashion_scene_group_id', '') or '').strip()
            pose_id = (request.form.get('fashion_pose_id', '') or '').strip()
            shot_sizes = parse_json_string_list(request.form.get('fashion_shot_sizes', ''), '景别')
            view_angles = parse_json_string_list(request.form.get('fashion_view_angles', ''), '视角')

            if not scene_group_id:
                raise ValueError('请选择场景组')
            if not pose_id:
                raise ValueError('请选择姿态方案')
            if not shot_sizes:
                raise ValueError('请至少选择 1 个景别')
            if not view_angles:
                raise ValueError('请至少选择 1 个视角')

            selected_group, selected_pose = find_fashion_scene_selection(scene_plan.get('scene_groups') or [], scene_group_id, pose_id)
            final_prompt = build_fashion_generation_prompt(
                platform,
                selling_text,
                country,
                text_type,
                image_size_ratio,
                selected_style,
                scene_plan,
                selected_group,
                selected_pose,
                shot_sizes,
                view_angles,
            )

            task_id = uuid.uuid4().hex
            task_name = build_task_name(platform, 'fashion', 1)
            generated_at = build_generated_at()
            reference_images = build_reference_images(task_id, image_payloads, source='product')
            if fashion_reference_payloads:
                reference_images.extend(
                    build_reference_images(
                        task_id,
                        fashion_reference_payloads,
                        source='fashion_reference',
                        start_sort=len(reference_images) + 1,
                    )
                )

            generated_item = call_image_generation(
                get_ark_client(),
                final_prompt,
                planning_payloads,
                image_size_ratio,
                text_type,
                country,
                product_json,
            )
            image_bytes, mime_type = decode_generated_image(generated_item)
            download_name, relative_path, image_url = save_generated_image(task_id, 1, 'fashion-look', image_bytes, mime_type)
            images = [
                {
                    'sort': 1,
                    'kind': 'generated',
                    'type': '服饰穿搭图',
                    'type_tag': 'Look',
                    'title': selected_pose.get('title') or '服饰穿搭图',
                    'keywords': [*shot_sizes, *view_angles],
                    'prompt': final_prompt,
                    'image_url': image_url,
                    'image_path': relative_path,
                    'download_name': download_name,
                }
            ]

            return jsonify(
                {
                    'success': True,
                    'mode': 'fashion',
                    'fashion_action': 'generate',
                    'task_id': task_id,
                    'task_name': task_name,
                    'generated_at': generated_at,
                    'plan': scene_plan,
                    'selected_style': selected_style,
                    'reference_images': reference_images,
                    'images': images,
                    'fashion_selection': {
                        'scene_group_id': scene_group_id,
                        'pose_id': pose_id,
                        'shot_sizes': shot_sizes,
                        'view_angles': view_angles,
                    },
                }
            )

        output_count, _ = get_suite_type_rules(request.form.get('output_count', '8'))
        task_id = uuid.uuid4().hex
        task_name = build_task_name(platform, 'suite', output_count)
        generated_at = build_generated_at()
        reference_images = build_reference_images(task_id, image_payloads, source='product')
        planning_payloads = image_payloads + fashion_reference_payloads
        plan = build_suite_plan(
            platform,
            selling_text,
            output_count,
            planning_payloads,
            country,
            text_type,
            image_size_ratio,
            selected_style,
            mode,
            product_json,
        )
        images = generate_suite_images(plan, planning_payloads, task_id, image_size_ratio, text_type, country, product_json)

        return jsonify(
            {
                'success': True,
                'mode': mode,
                'task_id': task_id,
                'task_name': task_name,
                'generated_at': generated_at,
                'plan': plan,
                'selected_style': selected_style,
                'reference_images': reference_images,
                'images': images,
            }
        )
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
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
        product_json = parse_product_json_payload(request.form.get('product_json', ''))
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
        plan = build_aplus_plan(platform, selling_text, selected_modules, image_payloads, country, text_type, image_size_ratio, selected_style, product_json)
        images = generate_aplus_images(plan, image_payloads, task_id, image_size_ratio, text_type, country, product_json)

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
    except RequestEntityTooLarge as exc:
        return handle_request_entity_too_large(exc)
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
    host = get_optional_env('HOST', '0.0.0.0') or '0.0.0.0'
    port = get_optional_int_env('PORT', 5078)
    debug = get_optional_bool_env('FLASK_DEBUG', False)
    app.run(host=host, port=port, debug=debug)
