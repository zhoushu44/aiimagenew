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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
    '你是商品主体不可变特征结构化提取专家。'
    '你必须严格根据商品图片与已有卖点文案，只提取后续生图保持商品主体一致性所需的主体信息。'
    '禁止提取或总结光线、场景、背景、道具、人物/模特、手部、姿势、镜头语言、构图、氛围等非商品主体信息。'
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

PRODUCT_JSON_USER_PROMPT_TEMPLATE = """请结合当前商品图片与卖点信息，提取后续生图保持商品主体一致性所需的“不可变商品特征” JSON。

用户当前文案：
{selling_text}

要求：
1. 只返回 JSON，不要代码块，不要解释。
2. 只能提取图片中明确可见，或文案中明确给出的商品主体信息；不确定就写空字符串、空数组，不做臆测。
3. 该 JSON 只服务于锁定“商品主体是什么、哪些特征绝不能变”，不是营销摘要，也不是场景总结。
4. 严禁提取、概括或带入以下非商品主体信息：光线、打光、场景、背景、道具、人物/模特、手部、姿势、镜头语言、构图、氛围、情绪、文案排版、环境描述。
5. 输出结构必须适用于任意商品，不要偏向服装类；如果某些字段不适用，则保留空值或空数组。
6. must_keep 用于列出“后续所有图都必须保留的主体特征”；must_not_change 用于列出“不能漂移、不能弱化、不能替换的稳定主体信息”；forbidden_changes 用于列出“明确禁止出现的改动方向”。这三组规则必须只针对商品主体本身，不得写场景或镜头限制。
7. selling_points 仅用于提炼可在后续画面中表达的商品卖点，可引用用户文案里的重点，但不得覆盖主体一致性规则，也不得写成场景描述。
8. 所有字段都要尽量短句化、去修辞化、去营销化；优先写名词短语或硬规则短句，不要写大段完整描述。
9. structure 只写稳定结构组成，不要把颜色、氛围、场景、卖点解释混进去；优先写“门襟/开合方式、主体开口结构、连接结构、固定结构、主要分区、关键部件关系”。
10. consistency_rules、must_keep、must_not_change、forbidden_changes 必须写成可直接注入生图提示词的硬约束；每条只表达一个约束点，避免复合长句。
11. 若同一信息已在更具体字段中表达，不要在多个字段里重复展开；避免把同一句意思改写后重复出现在多个数组中。
12. 顶层结构必须为：
{{
  "product_name": "",
  "category": "",
  "core_subject": "",
  "subject_composition": {{
    "subject_count": "",
    "subject_units": [""],
    "assembly_form": ""
  }},
  "appearance": {{
    "primary_colors": [""],
    "secondary_colors": [""],
    "materials": [""],
    "textures_patterns": [""],
    "silhouette": "",
    "structure": "",
    "surface_finish": "",
    "craft_details": [""]
  }},
  "key_components": [""],
  "brand_identity": {{
    "brand_name": "",
    "logo_details": "",
    "text_markings": [""],
    "logo_positions": [""]
  }},
  "immutable_traits": [""],
  "consistency_rules": [""],
  "must_keep": [""],
  "must_not_change": [""],
  "forbidden_changes": [""],
  "selling_points": [""]
}}
13. consistency_rules 至少返回 4 条，必须明确哪些主体特征必须保持一致，例如主体品类、颜色体系、轮廓、结构、关键部件、logo/品牌位、稳定细节等。
14. must_keep、must_not_change、forbidden_changes 各至少返回 4 条，尽量短句化、硬规则化，便于直接注入后续生图提示词。
15. immutable_traits、key_components、craft_details、subject_units、textures_patterns、text_markings、logo_positions 最多各返回 6 条。
16. primary_colors、secondary_colors、materials 最多各返回 4 条；只写稳定且可见的主体特征。
17. consistency_rules、must_keep、must_not_change、forbidden_changes 最多各返回 8 条；selling_points 最多返回 6 条。
18. consistency_rules、must_keep、must_not_change、forbidden_changes 每条尽量控制在 6-16 个字，优先使用短规则，不要写解释句。
19. 禁止输出这类长句："主体必须保持为...不得变成..."、"颜色关系必须保持..."。改为更短的规则，例如："棒球领外套品类"、"深蓝衣身+浅蓝袖身"、"禁止改为拉链门襟"、"禁止删除双侧插袋"。
20. must_keep 只写需要保留的主体锚点；must_not_change 只写不能变化的稳定主体信息；forbidden_changes 只写明确禁止的改动方向。三者不要互相改写重复。
21. selling_points 只保留可视化卖点短语，例如“拼色层次清晰”“双侧插袋实用”；不要写完整营销句。
22. product_name、category、core_subject、silhouette、structure、logo_details 也必须尽量短，不要超过 18 个字；避免“经典、时尚、高级、氛围感”等修饰词。"""

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

FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT = (
    '你是服饰穿搭成图质检助手。'
    '你会收到 3 张图片，顺序固定为：第 1 张是待检查的生成结果，第 2 张是必须出镜的模特参考图，第 3 张是必须穿到模特身上的商品图。'
    '你必须严格检查：生成结果里是否真的出现了清晰可见的人体/模特、是否与参考模特保持同一人物身份、是否让该模特穿上了商品图中的同一件服饰、是否出现了任何新增可见文字。'
    '只允许输出合法 JSON，不要输出代码块、解释或额外文字。'
)

FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE = """请严格检查这 3 张图片（顺序固定：1=生成结果，2=模特参考，3=商品图），并返回 JSON：
{{
  "model_present": true,
  "same_model_identity": true,
  "wearing_product": true,
  "extra_text_present": false,
  "passed": true,
  "score": 0,
  "failed_checks": [""],
  "reason": ""
}}

判定要求：
1. model_present：只有当第 1 张图里明显出现真实模特/人体主体时才为 true；如果只是衣服平铺、挂拍、白底单品、无头模特、裁切到看不出人物身份，都必须为 false。
2. same_model_identity：只有当第 1 张图中的出镜人物，与第 2 张参考图是同一模特身份时才为 true；若换人、性别不符、脸型发型明显不一致、只剩身体看不出是否同一人，都为 false。
3. wearing_product：只有当第 1 张图中的模特，穿着第 3 张商品图里的同一件服饰主体，且款式、颜色、结构、图案、logo/字样位置总体一致时才为 true；若只是相似衣服、只保留部分特征、没真正穿到人身上，都为 false。
4. extra_text_present：只要第 1 张图出现任何新增可见文字、数字、水印、海报字、标签字、背景招牌字、字幕或角标，就为 true。商品原本自带且与商品图一致的 logo / 印花文字不算新增文字。
5. passed：只有当 model_present=true、same_model_identity=true、wearing_product=true、extra_text_present=false 时才为 true。
6. score：0-100，越高表示越符合要求。
7. failed_checks：从 ["model_present", "same_model_identity", "wearing_product", "extra_text_present"] 中返回未通过项；若都通过则返回空数组。
8. reason：用一句中文简洁说明判定依据，20-80 字。

务必保守判定；不确定时按失败处理。"""

FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS = 1

FASHION_SCENE_PLAN_SYSTEM_PROMPT = (
    '你是服饰穿搭视觉策划专家，擅长围绕服装主体一致性、模特外观、镜头语言与场景氛围，'
    '为前端生成可直接渲染的场景推荐 JSON。你必须只输出合法 JSON，不要附加解释。'
)

FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE = """请基于当前服装商品图与当前已选模特参考，为服饰穿搭生成推荐场景方案。

输出比例：
{image_size_ratio}

要求：
1. 商品图用于锁定服饰主体、颜色、材质、版型、图案与细节一致性，不得替换商品主体。
2. 当前已选模特参考图只用于锁定人物身份、外观、脸部特征、发型、肤感、体态比例与整体气质，后续最终成图必须继续沿用该模特，不得切换成其他人物。
3. 需要输出 4 组推荐场景，每组 4 个模块方案。
4. 场景描述要适合电商服饰穿搭图，避免过于复杂或喧宾夺主的背景。
5. 每个模块都要清楚区分姿态、构图与镜头感，便于前端做多选场景。
6. scene_prompt 与 poses.scene_prompt 都必须是可直接用于后续生图拼接的中文短句，突出服装一致性与模特一致性优先。
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
          "id": "module-1",
          "title": "模块标题",
          "description": "模块说明",
          "scene_prompt": "该模块提示词短句"
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
      "prompt": "",
      "scene_required": true,
      "scene_type": "",
      "camera_shot": "",
      "subject_angle": "",
      "human_presence": "",
      "action_type": "",
      "layout_anchor": "",
      "must_differ_from": [""]
    }}
  ]
}}
3. summary 用一句中文概括本次套图策略。
4. items 长度必须严格等于 {output_count}，sort 必须从 1 开始递增。
5. type 必须严格使用后端给定的图类型，不得自创新 type。
6. title 适合直接作为单张卡片标题，简洁明确。
7. keywords 必须是 3-6 个短语，便于前端展示。
8. prompt 必须是适合图生图的中文指令，需明确：构图重点、场景/背景、文案层级、视觉风格，以及商品主体保持一致的硬约束。
9. 如果用户卖点为空，也必须结合图片可见特征完成规划，但禁止虚构无法确认的精确参数。
10. 每张图都要贴合 {platform} 平台的电商展示逻辑，且彼此分工明确、避免重复。
11. 说明文字种类、图片尺寸比例、国家参考都必须体现在 summary 与每张图的 prompt 中；如果某些卖点或场景与地区强相关，必须优先参考国家信息。
12. 如果说明文字种类为“无文字”，prompt 中必须明确不要在图片中生成任何标题、卖点文案或说明文字；否则应按指定文字种类组织画面文案语言。
13. 如果提供了风格参考，必须优先吸收该风格的视觉气质、色彩倾向、版式氛围与信息层级，并把它们自然融入 summary 与每张图的 prompt；但平台规则、国家参考、文字类型、尺寸比例、商品主体与卖点约束始终优先。
14. product_json 只代表不可变商品特征，只能用于锁定商品主体本身；不得把场景、背景、光线、氛围、人物、姿势、镜头语言或文案排版写进该结构的解释中。
15. 每张图的 prompt 都必须优先执行 must_keep、must_not_change、forbidden_changes 与 consistency_rules；主体品类、主色/辅色、轮廓、结构、关键部件、logo/品牌位、稳定细节必须保持一致，不允许只保留大致品类。
16. selling_points 只能作为画面表达的卖点重点、标题重点或信息层级参考；不得覆盖主体一致性约束，不得推动商品变体化。
17. 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把参考图商品改成另一种外观、另一种材质表现、另一种结构、另一种颜色体系或另一种品牌识别。
18. 整套图必须在“主体一致”前提下，主动做出“展示差异”；至少首屏主视觉图、核心卖点图、商品细节图、参数图、配件/售后图之间，商品展示角度、人物姿势（如有）、商品摆位、景别和构图重心不能高度重复。
19. 除使用场景图外，其余图也不能只是同一参考姿势或同一商品朝向的简单复用加字；必须根据图类型职责主动改变展示方式，例如：主图偏主体识别与视觉记忆点，卖点图偏卖点对应视角，细节图偏局部放大或结构特写，参数图偏规整陈列或信息板式视角，售后图偏包装/配件/服务说明视角。
20. 如果画面中有人物或手部，它们只能服务于当前图类型的表达，且不同图中的人物动作、持握方式、身体朝向、商品相对位置应明显区分；如果无人，则不同图中的商品朝向、放置方式、远近景和版式骨架也必须明显区分。
21. 禁止把整套图做成同一姿势、同一摆位、同一镜头、同一版式的重复变体；每张图都要让用户一眼看出职责不同、展示方式不同，但商品主体仍是同一个。
22. 首屏主视觉图、核心卖点图、使用场景图三者必须强制分化：首屏主视觉图也必须使用有场景的画面，且必须是“大场景 + 单主体强聚焦”结构，场景只负责建立氛围与使用语境，不得喧宾夺主；核心卖点图也必须使用有场景的画面，并围绕一个核心卖点采用“场景内功能动作 / 局部卖点展示”结构重构视角，可做场景中的局部放大、半身持握、俯拍陈列或结构拆解感，不得继续沿用首图站姿/拿法；使用场景图必须明确放入真实使用动作或生活环境，人物姿势、商品相对位置、镜头距离必须与前两张明显不同。
23. 首屏主视觉图与核心卖点图都不得做成纯白底棚拍、纯色背景孤立陈列或脱离语境的空场展示图；首图必须优先使用完整环境、留出明确空间纵深，并把商品作为第一视觉中心，禁止把场景元素做得比商品更抢眼；卖点图必须让场景直接服务某一个卖点，优先出现操作关系、功能触发点、局部放大区域或利益点对应动作，禁止仅把首图换个背景后继续展示整件商品。若首图已经出现人物，则核心卖点图必须改为不同身体朝向、不同持握关系、不同镜头距离或不同构图重心中的至少两项，禁止与首图形成同姿势平替。
24. 使用场景图不得复用首屏主视觉图或核心卖点图的站位、朝向、裁切和商品位置；必须体现“正在使用”而不是“拿着展示”，优先采用操作中、接触中、桌面使用中、收纳取用中等动态关系。
25. 对于首屏主视觉图、核心卖点图、使用场景图，三张图的 prompt 必须直接写出各自禁止复用的对象：禁止同朝向、禁止同姿势、禁止同摆位、禁止同景别、禁止同版式骨架，避免模型只换背景和文案。
26. 每个 item 除自然语言 prompt 外，还必须补充结构化差异字段：scene_required、scene_type、camera_shot、subject_angle、human_presence、action_type、layout_anchor、must_differ_from。
27. scene_required 必须为 true 或 false；scene_type 填该图主要场景类型，如“大场景家居”“桌面操作”“纯净参数板式”“包装清单展示”；camera_shot 填景别或镜头策略，如“远景主视觉”“中景半身”“近景特写”“俯拍平铺”；subject_angle 填商品主体朝向或观察角度，如“正侧45度”“俯视”“平视正面”“局部切面”。
28. human_presence 只能填写“none”“hand-only”“model”；action_type 填该图主要动作关系，如“静态陈列”“收纳取用”“桌面操作”“局部拆解”“参数说明”；layout_anchor 填构图重心，如“主体居中放大”“左文右图”“右文左图”“下方信息栏”“局部放大角标”。
29. must_differ_from 必须列出当前图明确禁止复用的前序图类型，可填 1-3 个；尤其首屏主视觉图、核心卖点图、使用场景图三者之间必须互相写出差异化约束。
30. 这些结构化差异字段必须与 prompt 保持一致，不能互相矛盾；优先用它们明确区分场景类型、景别、主体朝向、人物参与方式、动作关系与版式骨架。
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
16. 对于“首屏主视觉”“核心卖点图”，默认优先做场景化表达，不要只做白底商品、悬浮 cutout 或纯信息板；应尽量把商品放进真实使用环境中，通过人物、动作、空间、氛围来体现第一眼吸引力与核心卖点。如果卖点里包含期望场景，必须优先写入 prompt；如果是服饰、鞋包、配饰类商品，优先让商品穿在/背在/佩戴在人物身上，在咖啡店、通勤、街头、办公室、居家等合理生活场景中展示。
17. 对于“尺寸/容量/尺码图”“详细规格/参数表”“商品成分图”这类强信息模块，如图片或文案无法确认精确数据，必须使用保守表达，如“尺寸示意”“参数信息以实物为准”“图中可见材质/成分线索”，禁止编造具体数值。
18. 对于“配件/赠品图”“售后保障图”“效果对比图”这类容易误导的模块，如缺少依据，不要虚构额外赠品、售后政策或夸张功效，应采用克制、可信的表达。
"""

APLUS_MODULE_META = {
    'hero_value': {
        'name': '首屏主视觉',
        'tag': 'Hero',
        'detail': '页面开场主视觉，优先采用真实场景化表达，突出商品主体、品牌识别与核心价值主张；服饰、鞋包、配饰类优先让商品穿在/背在/佩戴在人物身上。',
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
        'detail': '聚焦关键差异点与竞争优势，优先通过真实使用场景、人物状态与环境氛围来演绎卖点，不要退化为纯信息板；服饰、鞋包、配饰类优先展示上身/佩戴效果。',
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
        return f'{platform}{mode_label}-{count}{count_label}-{datetime.now().strftime("%m%d-%H%M%S")}'
    if mode == 'fashion':
        return f'服饰穿搭-{count}张-{datetime.now().strftime("%m%d-%H%M%S")}'
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
    if declared_mime_type and declared_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValueError(f'图片 {filename} MIME 类型不受支持：{declared_mime_type}')
    if not detected_mime_type:
        raise ValueError(f'图片 {filename} 不是有效的图片文件')

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


CHAT_COMPLETION_RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


def create_chat_completion_session():
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        allowed_methods=frozenset({'POST'}),
        status_forcelist=CHAT_COMPLETION_RETRYABLE_STATUS_CODES,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def call_chat_completion(system_prompt: str, user_content, temperature: float = 0.7, timeout_seconds: int = 60):
    client = OpenAI(
        api_key=get_env('OPENAI_API_KEY'),
        base_url=get_env('OPENAI_BASE_URL').rstrip('/'),
    )
    model = get_env('OPENAI_MODEL')

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
        temperature=temperature,
        timeout=timeout_seconds,
    )

    try:
        raw_response_text = response.model_dump_json(indent=2)
    except Exception:
        raw_response_text = str(response)
    app.logger.warning(
        'Chat completion response: model=%s body=%s',
        model,
        raw_response_text,
    )

    message = ((getattr(response, 'choices', None) or [None])[0] or {}).message
    text = getattr(message, 'content', '') if message else ''
    if isinstance(text, list):
        text = ''.join(part.text for part in text if getattr(part, 'text', None))
    elif text is None:
        text = ''
    text = str(text).strip() if text else ''

    if not text:
        fallback_fields = ['reasoning_content']
        for field in fallback_fields:
            fallback_text = getattr(message, field, '') if message else ''
            if isinstance(fallback_text, list):
                fallback_text = ''.join(part.text for part in fallback_text if getattr(part, 'text', None))
            elif fallback_text is None:
                fallback_text = ''
            fallback_text = str(fallback_text).strip() if fallback_text else ''
            if fallback_text:
                text = fallback_text
                break

    if not text:
        raise ValueError('模型接口未返回内容（已记录原始响应日志，便于排查）')
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

    app.logger.exception('ARK image generation failed: status=%s details=%s', status_code, details)

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
    'subject_composition': {
        'subject_count': '',
        'subject_units': [],
        'assembly_form': '',
    },
    'appearance': {
        'primary_colors': [],
        'secondary_colors': [],
        'materials': [],
        'textures_patterns': [],
        'silhouette': '',
        'structure': '',
        'surface_finish': '',
        'craft_details': [],
    },
    'key_components': [],
    'brand_identity': {
        'brand_name': '',
        'logo_details': '',
        'text_markings': [],
        'logo_positions': [],
    },
    'immutable_traits': [],
    'consistency_rules': [],
    'must_keep': [],
    'must_not_change': [],
    'forbidden_changes': [],
    'selling_points': [],
}


PRODUCT_JSON_PROMPT_TEMPLATE = (
    '不可变商品特征（仅用于锁定商品主体，若为空则代表暂未提取）：\n{product_json_text}\n\n'
    '执行要求：\n'
    '1. 上述结构只代表商品主体本身，不包含也不得反向推导场景、背景、光线、氛围、人物、姿势、镜头语言或文案排版。\n'
    '2. 后续所有规划与生图都必须优先遵守以上不可变商品特征，尤其优先执行 must_keep、must_not_change、forbidden_changes 与 consistency_rules。\n'
    '3. must_keep 代表每张图都必须保留的主体锚点；must_not_change 代表绝不允许漂移、弱化或替换的主体信息；forbidden_changes 代表明确禁止出现的变体方向。\n'
    '4. selling_points 仅用于补充画面表达重点、信息层级与卖点文案，不得覆盖或削弱主体一致性约束。\n'
    '5. 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把商品改成另一种外观、材质、结构或颜色体系。\n'
    '6. 若某些字段为空，只能依据参考图可见主体信息保守补足，不能臆测或改造成另一种商品。'
)


def normalize_product_json(raw_value):
    payload = raw_value if isinstance(raw_value, dict) else {}
    subject_composition = payload.get('subject_composition') if isinstance(payload.get('subject_composition'), dict) else {}
    appearance = payload.get('appearance') if isinstance(payload.get('appearance'), dict) else {}
    brand_identity = payload.get('brand_identity') if isinstance(payload.get('brand_identity'), dict) else {}
    visible_attributes = payload.get('visible_attributes') if isinstance(payload.get('visible_attributes'), dict) else {}

    def clean_list(value, limit=6):
        if not isinstance(value, list):
            return []
        normalized = []
        seen = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
            if limit and len(normalized) >= limit:
                break
        return normalized

    primary_colors = clean_list(appearance.get('primary_colors'), limit=4)
    secondary_colors = clean_list(appearance.get('secondary_colors'), limit=4)
    materials = clean_list(appearance.get('materials'), limit=4)
    textures_patterns = clean_list(appearance.get('textures_patterns'))
    craft_details = clean_list(appearance.get('craft_details'))
    key_components = clean_list(payload.get('key_components'))
    immutable_traits = clean_list(payload.get('immutable_traits'))
    consistency_rules = clean_list(payload.get('consistency_rules'), limit=8)
    must_keep = clean_list(payload.get('must_keep'), limit=8)
    must_not_change = clean_list(payload.get('must_not_change'), limit=8)
    forbidden_changes = clean_list(payload.get('forbidden_changes'), limit=8)
    selling_points = clean_list(payload.get('selling_points'))
    subject_units = clean_list(subject_composition.get('subject_units'))
    text_markings = clean_list(brand_identity.get('text_markings'))
    logo_positions = clean_list(brand_identity.get('logo_positions'))

    legacy_color = str(visible_attributes.get('color', '')).strip()
    legacy_material = str(visible_attributes.get('material', '')).strip()
    legacy_pattern = str(visible_attributes.get('pattern', '')).strip()
    legacy_shape = str(visible_attributes.get('shape', '')).strip()
    legacy_structure = str(visible_attributes.get('structure', '')).strip()
    legacy_craft_details = clean_list(visible_attributes.get('craft_details'))

    if not primary_colors and legacy_color:
        primary_colors = [legacy_color]
    if not materials and legacy_material:
        materials = [legacy_material]
    if not textures_patterns and legacy_pattern:
        textures_patterns = [legacy_pattern]
    if not craft_details and legacy_craft_details:
        craft_details = legacy_craft_details

    silhouette = str(appearance.get('silhouette', '')).strip() or legacy_shape
    structure = str(appearance.get('structure', '')).strip() or legacy_structure
    category = str(payload.get('category', '')).strip()
    core_subject = str(payload.get('core_subject', '')).strip()

    if not must_keep:
        must_keep = clean_list([
            category,
            core_subject,
            *primary_colors[:2],
            silhouette,
            *key_components[:2],
        ], limit=8)

    if not must_not_change:
        must_not_change = clean_list([
            structure,
            *materials[:2],
            *immutable_traits[:4],
            *logo_positions[:2],
        ], limit=8)

    if not forbidden_changes:
        auto_forbidden = []
        if category:
            auto_forbidden.append('禁止替换为其他商品品类或其他主体对象')
        if primary_colors:
            auto_forbidden.append('禁止把主体主色与辅色改成另一套明显不同的颜色体系')
        if materials:
            auto_forbidden.append('禁止把主体材质表现替换成另一种明显不同的材质')
        if structure or silhouette:
            auto_forbidden.append('禁止改变主体轮廓、结构比例或关键造型')
        if key_components:
            auto_forbidden.append('禁止删减、替换或新增会改变商品识别度的关键部件')
        if logo_positions or text_markings:
            auto_forbidden.append('禁止改动品牌标识、文字标记或 logo 位置')
        forbidden_changes = clean_list(auto_forbidden, limit=8)

    return {
        'product_name': str(payload.get('product_name', '')).strip(),
        'category': category,
        'core_subject': core_subject,
        'subject_composition': {
            'subject_count': str(subject_composition.get('subject_count', '')).strip(),
            'subject_units': subject_units,
            'assembly_form': str(subject_composition.get('assembly_form', '')).strip(),
        },
        'appearance': {
            'primary_colors': primary_colors,
            'secondary_colors': secondary_colors,
            'materials': materials,
            'textures_patterns': textures_patterns,
            'silhouette': silhouette,
            'structure': structure,
            'surface_finish': str(appearance.get('surface_finish', '')).strip(),
            'craft_details': craft_details,
        },
        'key_components': key_components,
        'brand_identity': {
            'brand_name': str(brand_identity.get('brand_name', '')).strip(),
            'logo_details': str(brand_identity.get('logo_details', '')).strip(),
            'text_markings': text_markings,
            'logo_positions': logo_positions,
        },
        'immutable_traits': immutable_traits,
        'consistency_rules': consistency_rules,
        'must_keep': must_keep,
        'must_not_change': must_not_change,
        'forbidden_changes': forbidden_changes,
        'selling_points': selling_points,
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
        return '未提供不可变商品特征。'
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
            + '\n18. 当前为服饰穿搭场景：商品图只用于锁定服饰主体的不可变特征，如品类、颜色、材质、版型、结构与稳定细节；如同时提供穿搭参考图，则只用于吸收模特姿态、穿搭方式、镜头语言、氛围与版式方向，不得替换商品主体本身。\n'
            + '19. 服饰场景下，prompt 必须优先保证商品主体与商品图一致，其次再融合参考图里的姿态、氛围与构图灵感。'
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

        scene_required_raw = item.get('scene_required')
        if not isinstance(scene_required_raw, bool):
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 scene_required 必须为布尔值')

        human_presence = normalize_plan_enum(item.get('human_presence'), {'none', 'hand-only', 'model'}, 'none')
        scene_type = normalize_plan_short_text(item.get('scene_type'), '未指定场景')
        camera_shot = normalize_plan_short_text(item.get('camera_shot'), '未指定景别')
        subject_angle = normalize_plan_short_text(item.get('subject_angle'), '未指定角度')
        action_type = normalize_plan_short_text(item.get('action_type'), '静态陈列')
        layout_anchor = normalize_plan_short_text(item.get('layout_anchor'), '主体居中放大')
        must_differ_from = normalize_plan_type_list(item.get('must_differ_from'), allowed_types)
        must_differ_from = [name for name in must_differ_from if name != image_type]

        normalized_items.append(
            {
                'sort': sort,
                'type': image_type,
                'title': title,
                'keywords': normalized_keywords,
                'prompt': prompt,
                'type_tag': SUITE_TYPE_META.get(image_type, {}).get('tag', 'Board'),
                'scene_required': scene_required_raw,
                'scene_type': scene_type,
                'camera_shot': camera_shot,
                'subject_angle': subject_angle,
                'human_presence': human_presence,
                'action_type': action_type,
                'layout_anchor': layout_anchor,
                'must_differ_from': must_differ_from,
            }
        )

    return {
        'summary': summary,
        'output_count': expected_output_count,
        'items': normalized_items,
    }




def normalize_plan_short_text(value: str, fallback: str = '') -> str:
    return str(value or '').strip() or fallback


def normalize_plan_enum(value: str, allowed_values, fallback: str) -> str:
    text = normalize_plan_short_text(value, fallback)
    return text if text in allowed_values else fallback


def normalize_plan_type_list(raw_value, allowed_types, limit=3):
    if not isinstance(raw_value, list):
        return []
    normalized = []
    seen = set()
    for item in raw_value:
        text = str(item or '').strip()
        if not text or text in seen or text not in allowed_types:
            continue
        normalized.append(text)
        seen.add(text)
        if limit and len(normalized) >= limit:
            break
    return normalized


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
    if not isinstance(scene_groups, list) or len(scene_groups) != 4:
        raise ValueError('场景规划结果格式异常：scene_groups 必须严格返回 4 组场景')

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
        if not isinstance(poses, list) or len(poses) != 4:
            raise ValueError(f'场景规划结果格式异常：第 {group_index} 组 poses 必须严格返回 4 个模块')

        normalized_poses = []
        for pose_index, pose in enumerate(poses, start=1):
            if not isinstance(pose, dict):
                raise ValueError(f'场景规划结果格式异常：第 {group_index} 组第 {pose_index} 个姿态必须为对象')

            raw_pose_id = str(pose.get('id', '')).strip()
            pose_id = raw_pose_id if raw_pose_id.startswith(f'{group_id}-') else f'{group_id}-pose-{pose_index}'
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


FASHION_DEFAULT_PLATFORM = '服饰穿搭'
FASHION_DEFAULT_COUNTRY = '中国'
FASHION_DEFAULT_TEXT_TYPE = '中文'
FASHION_DEFAULT_SELLING_TEXT = ''
FASHION_DEFAULT_SELECTED_STYLE = None



def build_fashion_scene_plan_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    return FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE.format(
        image_size_ratio=image_size_ratio or '1:1',
    )



FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS = 120


def build_fashion_scene_plan(platform: str, selling_text: str, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    response_text = call_chat_completion(
        FASHION_SCENE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(
            build_fashion_scene_plan_prompt(platform, selling_text, country, text_type, image_size_ratio, selected_style),
            image_payloads,
        ),
        temperature=0.85,
        timeout_seconds=FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS,
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



def parse_fashion_scene_selections(scene_groups, scene_group_ids, pose_ids):
    normalized_group_ids = []
    seen_group_ids = set()
    for scene_group_id in scene_group_ids or []:
        normalized_group_id = str(scene_group_id or '').strip()
        if not normalized_group_id or normalized_group_id in seen_group_ids:
            continue
        normalized_group_ids.append(normalized_group_id)
        seen_group_ids.add(normalized_group_id)

    normalized_pose_ids = []
    seen_pose_ids = set()
    for pose_id in pose_ids or []:
        normalized_pose_id = str(pose_id or '').strip()
        if not normalized_pose_id or normalized_pose_id in seen_pose_ids:
            continue
        normalized_pose_ids.append(normalized_pose_id)
        seen_pose_ids.add(normalized_pose_id)

    if not normalized_pose_ids:
        raise ValueError('请至少选择 1 个场景')

    normalized_entries = []
    matched_group_ids = set()

    for normalized_pose_id in normalized_pose_ids:
        matched_group = None
        matched_pose = None

        for group in scene_groups or []:
            for pose in group.get('poses') or []:
                if pose.get('id') == normalized_pose_id:
                    matched_group = group
                    matched_pose = pose
                    break
            if matched_group and matched_pose:
                break

        if not matched_group or not matched_pose:
            raise ValueError('请选择有效的姿态方案')

        matched_group_id = str(matched_group.get('id') or '').strip()
        if normalized_group_ids and matched_group_id not in seen_group_ids:
            raise ValueError('请选择有效的场景组')

        normalized_entries.append(
            {
                'scene_group_id': matched_group_id,
                'pose_id': normalized_pose_id,
                'group': matched_group,
                'pose': matched_pose,
            }
        )
        matched_group_ids.add(matched_group_id)

    unused_group_ids = [group_id for group_id in normalized_group_ids if group_id not in matched_group_ids]
    if unused_group_ids:
        raise ValueError('请选择有效的场景和姿态')

    return normalized_entries



def infer_fashion_pose_shot_size(selected_group: dict, selected_pose: dict) -> str:
    text = ' '.join(
        str(value or '').strip()
        for value in [
            selected_group.get('title'),
            selected_group.get('description'),
            selected_group.get('scene_prompt'),
            selected_pose.get('title'),
            selected_pose.get('description'),
            selected_pose.get('scene_prompt'),
        ]
        if str(value or '').strip()
    )
    if re.search(r'特写|近景|局部|细节|拉链|袖口|领口|纽扣|面料|纹理', text):
        return '特写'
    if re.search(r'半身|上半身|胸像', text):
        return '半身'
    if re.search(r'四分之三|3/4|七分身|中景', text):
        return '四分之三'
    if re.search(r'全身|全景|站立|直立|完整|通身|落地', text):
        return '全身'
    return '半身'



def infer_fashion_pose_view_angle(selected_group: dict, selected_pose: dict) -> str:
    text = ' '.join(
        str(value or '').strip()
        for value in [
            selected_group.get('title'),
            selected_group.get('description'),
            selected_group.get('scene_prompt'),
            selected_pose.get('title'),
            selected_pose.get('description'),
            selected_pose.get('scene_prompt'),
        ]
        if str(value or '').strip()
    )
    if re.search(r'3/4|四分之三|45度|斜侧|侧前方', text):
        return '3/4侧'
    if re.search(r'背面|背影|后背|背部', text):
        return '背面'
    if re.search(r'侧面|侧身|侧向', text):
        return '侧面'
    if re.search(r'正面|正向|正对', text):
        return '正面'
    return '正面'



def build_fashion_pose_camera_setting(selected_group: dict, selected_pose: dict, current_setting=None):
    setting = current_setting if isinstance(current_setting, dict) else {}
    shot_size = str(setting.get('shot_size') or '').strip() or infer_fashion_pose_shot_size(selected_group, selected_pose)
    view_angle = str(setting.get('view_angle') or '').strip() or infer_fashion_pose_view_angle(selected_group, selected_pose)
    return {
        'shot_size': shot_size,
        'view_angle': view_angle,
    }



def parse_fashion_pose_camera_settings(raw_value: str, selections):
    normalized = (raw_value or '').strip()
    if not normalized:
        return {
            str(selection.get('pose_id') or '').strip(): build_fashion_pose_camera_setting(
                selection.get('group') or {},
                selection.get('pose') or {},
            )
            for selection in (selections or [])
            if str(selection.get('pose_id') or '').strip()
        }

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError('场景镜头参数格式异常，请重新选择') from exc

    if not isinstance(payload, list):
        raise ValueError('场景镜头参数格式异常，请重新选择')

    selection_map = {
        str(selection.get('pose_id') or '').strip(): selection
        for selection in (selections or [])
        if str(selection.get('pose_id') or '').strip()
    }
    camera_settings = {}

    for item in payload:
        if not isinstance(item, dict):
            continue
        pose_id = str(item.get('pose_id') or '').strip()
        if not pose_id or pose_id not in selection_map:
            continue
        selection = selection_map[pose_id]
        camera_settings[pose_id] = build_fashion_pose_camera_setting(
            selection.get('group') or {},
            selection.get('pose') or {},
            {
                'shot_size': str(item.get('shot_size') or '').strip(),
                'view_angle': str(item.get('view_angle') or '').strip(),
            },
        )

    for selection in selections or []:
        pose_id = str(selection.get('pose_id') or '').strip()
        if pose_id and pose_id not in camera_settings:
            camera_settings[pose_id] = build_fashion_pose_camera_setting(
                selection.get('group') or {},
                selection.get('pose') or {},
            )

    return camera_settings



def parse_fashion_selected_model_payload(form):
    source = (form.get('fashion_selected_model_source', '') or '').strip()
    model_id = (form.get('fashion_selected_model_id', '') or '').strip()
    model_name = (form.get('fashion_selected_model_name', '') or '').strip()
    gender = (form.get('fashion_selected_model_gender', '') or '').strip()
    age = (form.get('fashion_selected_model_age', '') or '').strip()
    ethnicity = (form.get('fashion_selected_model_ethnicity', '') or '').strip()
    body_type = (form.get('fashion_selected_model_body_type', '') or '').strip()
    appearance_details = (form.get('fashion_selected_model_appearance_details', '') or '').strip()
    summary = (form.get('fashion_selected_model_summary', '') or '').strip()
    detail_text = (form.get('fashion_selected_model_detail_text', '') or '').strip()

    if not source:
        raise ValueError('缺少当前已选模特来源，请重新选择模特后再生成')
    if source not in {'ai', 'custom'}:
        raise ValueError('当前已选模特来源无效，请重新选择模特后再生成')
    if not model_id:
        raise ValueError('缺少当前已选模特 ID，请重新选择模特后再生成')

    selected_payloads = get_image_payloads_from_request('fashion_selected_model_image', limit=1)
    if not selected_payloads:
        raise ValueError('缺少当前已选模特图片，请重新选择模特后再生成')

    selected_payload = selected_payloads[0]
    filename = str(selected_payload.get('filename') or '').strip()
    if source == 'ai' and not filename:
        raise ValueError('AI 基准模特图片信息异常，请重新生成或重新选择后再试')
    if source == 'custom' and not filename:
        raise ValueError('自定义模特图片信息异常，请重新上传或重新选择后再试')

    return {
        'source': source,
        'id': model_id,
        'name': model_name,
        'gender': gender,
        'age': age,
        'ethnicity': ethnicity,
        'body_type': body_type,
        'appearance_details': appearance_details,
        'summary': summary,
        'detail_text': detail_text,
        'payload': selected_payload,
        'debug': {
            'source': source,
            'id': model_id,
            'name': model_name,
            'filename': filename,
            'mime_type': str(selected_payload.get('mime_type') or '').strip(),
            'byte_size': len(selected_payload.get('bytes') or b''),
            'gender': gender,
            'age': age,
            'ethnicity': ethnicity,
            'body_type': body_type,
        },
    }


def build_fashion_selected_model_identity_text(selected_model: dict):
    model_name = str((selected_model or {}).get('name') or '').strip()
    gender = str((selected_model or {}).get('gender') or '').strip()
    age = str((selected_model or {}).get('age') or '').strip()
    ethnicity = str((selected_model or {}).get('ethnicity') or '').strip()
    body_type = str((selected_model or {}).get('body_type') or '').strip()
    appearance_details = str((selected_model or {}).get('appearance_details') or '').strip()
    summary = str((selected_model or {}).get('summary') or '').strip()
    detail_text = str((selected_model or {}).get('detail_text') or '').strip()

    identity_parts = [value for value in [gender, age, ethnicity, body_type] if value]
    identity_summary = '、'.join(identity_parts) if identity_parts else '未提供'
    appearance_summary = appearance_details or detail_text or summary or '未提供'
    model_label = model_name or '当前已选模特'
    return (
        f'模特名称：{model_label}\n'
        f'模特身份标签：{identity_summary}\n'
        f'模特外观补充：{appearance_summary}'
    )


def build_fashion_generation_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style, selected_model: dict, scene_plan: dict, selected_group: dict, selected_pose: dict, shot_sizes, view_angles):
    shot_text = '、'.join(shot_sizes) if shot_sizes else '未指定'
    angle_text = '、'.join(view_angles) if view_angles else '未指定'
    scene_summary = str(scene_plan.get('summary', '')).strip() or '未提供'
    scene_prompt = str(scene_plan.get('scene_prompt', '')).strip() or ''
    group_prompt = str(selected_group.get('scene_prompt', '')).strip() or ''
    pose_prompt = str(selected_pose.get('scene_prompt', '')).strip() or ''
    selected_model_identity_text = build_fashion_selected_model_identity_text(selected_model)

    return (
        f'请生成 1 张服饰穿戴图。产品穿在模特身上，必须清晰可见真人模特完整上身展示该商品，不能只出衣服。\n\n'
        f'图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'当前已选模特身份锚点：\n{selected_model_identity_text}\n'
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
        f'1. 严格使用提供的模特图作为最终出镜人物，保持同一张脸、发型、气质、肤感与身形特征；禁止换人、禁止变性别、禁止混入其他模特特征。\n'
        f'2. 严格使用提供的商品图作为服饰主体，保持款式、颜色、结构、材质、版型、图案、logo 位置与细节一致；禁止替换商品本身。\n'
        f'3. 商品图只负责锁定衣服，模特图只负责锁定穿着者，二者必须同时生效；不能只参考商品图，也不能只参考模特图。\n'
        f'4. 最终人物必须与“当前已选模特身份锚点”一致；若场景、姿态、镜头与模特身份锚点冲突，必须优先服从模特身份锚点。\n'
        f'5. 画面必须体现已选场景组、姿态、镜头景别与视角信息，背景简洁，服务于服装展示，不得让背景喧宾夺主。\n'
        f'6. 必须输出适合电商展示的真人模特穿搭成图，禁止只生成衣服、禁止平铺挂拍、禁止无头模特、禁止把人物裁切到无法识别身份。\n'
        f'7. 优先突出模特穿着商品后的上身效果、版型、面料垂感与真实穿搭氛围，让人一眼看出“这是当前已选模特穿着当前商品图中的同一件服饰”。\n'
        f'8. 严禁生成任何新增可见文字元素：汉字、英文、数字、logo 文案、水印、字幕、角标、标签字样、吊牌字样、排版字、海报字、印刷覆盖字都不允许出现。\n'
        f'9. 若商品本体原始设计中自带品牌标识、logo、印花文字或标签细节，只能按商品图原样保留，不得新增、篡改、放大、改写或替换成新的文字内容。\n'
        f'10. 不要出现海报排版、广告字、背景标牌、店招、墙面文字、包装外额外字样、吊牌放大展示、字幕条、水印角标。'
    )



def build_fashion_generation_prompts(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style, selected_model: dict, scene_plan: dict, selections, pose_camera_settings):
    if not selections:
        raise ValueError('请至少选择 1 个场景')

    prompts = []
    for selection in selections:
        pose_id = str(selection.get('pose_id') or '').strip()
        camera_setting = pose_camera_settings.get(pose_id) or {}
        shot_size = str(camera_setting.get('shot_size') or '').strip()
        view_angle = str(camera_setting.get('view_angle') or '').strip()
        if not shot_size:
            raise ValueError('请为每个场景选择景别')
        if not view_angle:
            raise ValueError('请为每个场景选择视角')
        prompts.append(
            {
                'scene_group_id': selection['scene_group_id'],
                'pose_id': pose_id,
                'group': selection['group'],
                'pose': selection['pose'],
                'shot_size': shot_size,
                'view_angle': view_angle,
                'prompt': build_fashion_generation_prompt(
                    platform,
                    selling_text,
                    country,
                    text_type,
                    image_size_ratio,
                    selected_style,
                    selected_model,
                    scene_plan,
                    selection['group'],
                    selection['pose'],
                    [shot_size] if shot_size else [],
                    [view_angle] if view_angle else [],
                ),
            }
        )
    return prompts



def parse_fashion_output_verification(text: str):
    cleaned = strip_code_fences(text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f'服饰成图质检结果格式异常：{exc}') from exc

    if not isinstance(payload, dict):
        raise ValueError('服饰成图质检结果格式异常：返回值必须为对象')

    failed_checks = payload.get('failed_checks')
    if not isinstance(failed_checks, list):
        failed_checks = []
    normalized_failed_checks = []
    allowed_failed_checks = {'model_present', 'same_model_identity', 'wearing_product', 'extra_text_present'}
    for item in failed_checks:
        value = str(item or '').strip()
        if value in allowed_failed_checks and value not in normalized_failed_checks:
            normalized_failed_checks.append(value)

    reason = str(payload.get('reason', '')).strip()
    if not reason:
        raise ValueError('服饰成图质检结果格式异常：reason 不能为空')

    try:
        score = int(payload.get('score', 0))
    except (TypeError, ValueError):
        raise ValueError('服饰成图质检结果格式异常：score 必须为整数') from None
    score = max(0, min(score, 100))

    result = {
        'model_present': bool(payload.get('model_present')),
        'same_model_identity': bool(payload.get('same_model_identity')),
        'wearing_product': bool(payload.get('wearing_product')),
        'extra_text_present': bool(payload.get('extra_text_present')),
        'passed': bool(payload.get('passed')),
        'score': score,
        'failed_checks': normalized_failed_checks,
        'reason': reason,
    }

    expected_passed = (
        result['model_present']
        and result['same_model_identity']
        and result['wearing_product']
        and not result['extra_text_present']
    )
    result['passed'] = expected_passed

    if expected_passed:
        result['failed_checks'] = []
    else:
        computed_failed_checks = []
        if not result['model_present']:
            computed_failed_checks.append('model_present')
        if not result['same_model_identity']:
            computed_failed_checks.append('same_model_identity')
        if not result['wearing_product']:
            computed_failed_checks.append('wearing_product')
        if result['extra_text_present']:
            computed_failed_checks.append('extra_text_present')
        result['failed_checks'] = computed_failed_checks

    return result



def verify_fashion_generated_output(generated_payload: dict, selected_model_payload: dict, product_payloads):
    if not generated_payload:
        raise ValueError('缺少待质检的服饰生成结果')
    if not selected_model_payload:
        raise ValueError('缺少模特参考图，无法执行服饰成图质检')
    if not product_payloads:
        raise ValueError('缺少商品图，无法执行服饰成图质检')

    verification_payloads = [generated_payload, selected_model_payload, product_payloads[0]]
    response_text = call_chat_completion(
        FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT,
        build_multimodal_content(FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE, verification_payloads),
        temperature=0,
        timeout_seconds=90,
    )
    return parse_fashion_output_verification(response_text)



FASHION_MODEL_APPEARANCE_FALLBACK = '五官自然立体，肤质真实细腻，整体形象干净利落'


def get_request_value(payload: dict, form, key: str, default: str = '') -> str:
    if key in payload:
        return str(payload.get(key, default) or '').strip()
    return str(form.get(key, default) or '').strip()


def build_fashion_model_prompt(gender: str, age: str, ethnicity: str, body_type: str, appearance_details: str) -> str:
    normalized_gender = gender or '女'
    normalized_age = age or '青年'
    normalized_ethnicity = ethnicity or '欧美白人'
    normalized_body_type = body_type or '标准'
    normalized_details = appearance_details or FASHION_MODEL_APPEARANCE_FALLBACK
    identity_summary = '，'.join([
        normalized_gender,
        normalized_age,
        normalized_ethnicity,
        normalized_body_type,
    ])

    return (
        '请生成 1 张写实风格电商基准模特图，用于后续服饰穿搭展示与人物一致性锁定。\n\n'
        f'人物基础身份：{identity_summary}。\n'
        f'外貌细节：{normalized_details}。\n\n'
        '画面要求：\n'
        '1. 单人出镜，正面站立，自然表情，看向镜头，姿态放松。\n'
        '2. 以写实摄影质感呈现，电商棚拍风格，光线均匀柔和，背景简洁干净，适合作为电商展示基准模特。\n'
        '3. 人物整体形象真实自然，面部、皮肤、发型与体态细节清晰，保留真实质感。\n'
        '4. 构图优先完整展示人物穿搭承载状态，便于后续继续用于服饰上身生成。\n\n'
        '限制项：\n'
        '1. 不要多人，不要儿童陪衬，不要宠物。\n'
        '2. 不要复杂背景，不要街拍环境，不要凌乱道具。\n'
        '3. 不要夸张动作，不要大幅扭身，不要跳跃或戏剧化姿势。\n'
        '4. 不要卡通、插画、二次元、3D 渲染风。\n'
        '5. 不要畸形肢体、异常手指、面部崩坏或比例错误。\n'
        '6. 不要过度磨皮、过强滤镜、过分美颜或塑料皮肤。'
    )


def build_fashion_model_summary(gender: str, age: str, ethnicity: str, body_type: str) -> str:
    return ' · '.join([value for value in [gender, age, ethnicity, body_type] if value])


def build_fashion_model_response(task_id: str, model_id: str, gender: str, age: str, ethnicity: str, body_type: str, appearance_details: str, prompt: str, image_url: str, image_path: str, download_name: str):
    detail_text = appearance_details or FASHION_MODEL_APPEARANCE_FALLBACK
    summary = build_fashion_model_summary(gender, age, ethnicity, body_type)
    return {
        'id': model_id,
        'name': 'AI 基准模特',
        'summary': summary,
        'detailText': detail_text,
        'previewLabel': 'AI',
        'previewUrl': image_url,
        'createdAt': int(datetime.now().timestamp() * 1000),
        'task_id': task_id,
        'prompt': prompt,
        'gender': gender,
        'age': age,
        'ethnicity': ethnicity,
        'body_type': body_type,
        'appearance_details': appearance_details,
        'image_url': image_url,
        'image_path': image_path,
        'download_name': download_name,
    }


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
        image_bytes = base64.b64decode(item['b64_json'])
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or 'image/png'

    if item.get('url'):
        response = requests.get(item['url'], timeout=120)
        response.raise_for_status()
        image_bytes = response.content
        header_mime_type = response.headers.get('Content-Type', 'image/png').split(';', 1)[0].strip()
        detected_mime_type = sniff_image_mime_type(image_bytes)
        return image_bytes, detected_mime_type or header_mime_type or 'image/png'

    raise ValueError('图像生成接口未返回可用图片内容')



def collect_streamed_generated_images(events):
    generated_images = []
    usage = None

    for event in events:
        if event is None:
            continue

        event_type = getattr(event, 'type', '') or ''
        if event_type == 'image_generation.partial_succeeded':
            b64_json = getattr(event, 'b64_json', None)
            image_url = getattr(event, 'url', None)
            if b64_json:
                generated_images.append({'b64_json': b64_json})
            elif image_url:
                generated_images.append({'url': image_url})
        elif event_type == 'image_generation.completed':
            usage = getattr(event, 'usage', None)

    if not generated_images:
        raise ValueError('流式图像生成未返回可用图片内容')

    if usage is not None:
        for item in generated_images:
            item['usage'] = usage

    return generated_images


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


def build_plan_control_prompt(item: dict, all_types) -> str:
    scene_required = bool(item.get('scene_required'))
    scene_type = str(item.get('scene_type', '')).strip() or '未指定场景'
    camera_shot = str(item.get('camera_shot', '')).strip() or '未指定景别'
    subject_angle = str(item.get('subject_angle', '')).strip() or '未指定角度'
    human_presence = str(item.get('human_presence', '')).strip() or 'none'
    action_type = str(item.get('action_type', '')).strip() or '静态陈列'
    layout_anchor = str(item.get('layout_anchor', '')).strip() or '主体居中放大'
    must_differ_from = [
        str(name).strip()
        for name in (item.get('must_differ_from') or [])
        if str(name).strip() and str(name).strip() in all_types and str(name).strip() != item.get('type')
    ]
    human_presence_map = {
        'none': '本图不应出现人物或手部，只通过商品自身展示完成表达。',
        'hand-only': '本图仅允许出现手部或局部操作关系，禁止出现完整人物主体。',
        'model': '本图允许出现人物/模特，但人物只能服务商品表达，不能抢夺主体。',
    }
    scene_rule = '必须使用明确场景，且场景类型需与下述规划一致。' if scene_required else '优先采用非场景或弱场景表达，不要强塞生活化环境。'
    differ_rule = '、'.join(must_differ_from) if must_differ_from else '无指定前序图'
    return (
        '结构化差异控制：\n'
        f'- scene_required：{"true" if scene_required else "false"}。{scene_rule}\n'
        f'- scene_type：{scene_type}。\n'
        f'- camera_shot：{camera_shot}。\n'
        f'- subject_angle：{subject_angle}。\n'
        f'- human_presence：{human_presence}。{human_presence_map.get(human_presence, human_presence_map["none"])}\n'
        f'- action_type：{action_type}。\n'
        f'- layout_anchor：{layout_anchor}。\n'
        f'- must_differ_from：{differ_rule}。必须与这些图在场景类型、景别、主体朝向、人物参与方式、动作关系、构图骨架中至少拉开三项差异。\n'
        '- 上述结构化字段优先级高于自由描述；若自由 prompt 与结构化字段冲突，以结构化字段为准。'
    )



def call_image_generation(client: OpenAI, prompt: str, image_payloads, image_size_ratio: str, text_type: str, country: str, product_json=None, image_type: str = '', plan_item=None, all_plan_types=None, max_images: int = 1):
    model = get_optional_env('ARK_IMAGE_MODEL', 'doubao-seedream-5-0-260128')
    size = resolve_image_size(image_size_ratio)
    quality = get_optional_env('ARK_IMAGE_QUALITY', '')
    watermark = get_optional_bool_env('ARK_IMAGE_WATERMARK', False)
    sequential_mode = get_optional_env('ARK_SEQUENTIAL_IMAGE_GENERATION', 'auto')
    sequential_max_images = get_optional_int_env('ARK_SEQUENTIAL_MAX_IMAGES', 1)
    normalized_product_json = normalize_product_json(product_json) if product_json else None
    product_json_text = build_product_json_prompt_text(normalized_product_json)
    must_keep = '；'.join((normalized_product_json or {}).get('must_keep') or []) or '未单独提取'
    must_not_change = '；'.join((normalized_product_json or {}).get('must_not_change') or []) or '未单独提取'
    forbidden_changes = '；'.join((normalized_product_json or {}).get('forbidden_changes') or []) or '未单独提取'
    selling_points = '；'.join((normalized_product_json or {}).get('selling_points') or []) or '未单独提取'
    image_type = str(image_type or '').strip()
    plan_control_prompt = ''
    if isinstance(plan_item, dict):
        plan_control_prompt = build_plan_control_prompt(plan_item, all_plan_types or [])
    type_specific_rules = ''
    if image_type == '首屏主视觉图':
        type_specific_rules = (
            '- 当前图类型：首屏主视觉图。必须使用有场景的主视觉画面，并采用“大场景 + 单主体强聚焦”构图：场景需要真实存在且能承接商品气质，但商品主体仍必须是绝对视觉中心；禁止做成纯白底棚拍、纯色背景孤立陈列或空场静物图。\n'
            '- 优先保留完整环境信息、空间纵深或前后景层次，让用户一眼感知使用语境，但场景元素不得比商品更抢眼；禁止与核心卖点图、使用场景图复用同一站姿、同一手持关系、同一商品朝向、同一景别或同一构图骨架。\n'
        )
    elif image_type == '核心卖点图':
        type_specific_rules = (
            '- 当前图类型：核心卖点图。必须使用有场景的画面，并围绕一个核心卖点采用“场景内功能动作 / 局部卖点展示”结构重构视角；可采用场景中的局部放大、半身持握、俯拍陈列、剖面感或结构展示，但禁止继续沿用首屏主视觉图的同姿势、同朝向、同主体位置、同镜头距离。\n'
            '- 该图的场景必须直接服务卖点表达，例如收纳、清洁、使用前后、桌面操作、随身携带、厨房备餐等；优先出现操作关系、功能触发点、局部放大区域或利益点对应动作，禁止仅把首图换个背景后继续展示整件商品。即使保留人物，也必须让人物动作、身体朝向、持握关系、商品位置至少两项明显变化。\n'
        )
    elif image_type == '使用场景图':
        type_specific_rules = (
            '- 当前图类型：使用场景图。必须表现商品正在被真实使用，而不是静态拿着展示；优先采用操作中、接触中、桌面使用中、收纳取用中等动态关系。\n'
            '- 这张图禁止复用首屏主视觉图或核心卖点图的站位、朝向、裁切、商品位置与版式骨架，人物姿势、商品相对位置、镜头距离必须明显不同。\n'
        )
    elif image_type == 'fashion-look':
        type_specific_rules = (
            '- 当前图类型：服饰穿搭图。最终画面必须是“清晰可见的真人模特穿着商品”的完整穿搭成图；禁止只出衣服、禁止平铺挂拍、禁止无头模特、禁止裁切到看不出人物身份、禁止把商品单独陈列当成最终结果。\n'
            '- 若同时提供商品图与模特参考图，必须优先使用商品图锁定服饰主体，使用模特参考图锁定最终出镜人物身份、脸部、发型、肤感、体态比例与整体气质；禁止替换为其他人物，禁止混入其他模特特征。\n'
            '- 该图是服饰最终成图，不允许生成任何新增可见文字元素：标题、卖点文案、说明字、logo 文案、水印、字幕、角标、标签字样、吊牌字样、排版字、海报字都禁止出现。\n'
            '- 若商品本体原始设计自带品牌标识、logo、印花文字或标签细节，只能按商品图原样保留，不得新增、改写、放大或替换。\n'
        )
    enriched_prompt = (
        f'{prompt}\n\n'
        f'当前图类型：{image_type or "未指定"}\n\n'
        f'不可变商品特征：\n{product_json_text}\n\n'
        f'{plan_control_prompt}\n\n'
        f'额外执行约束：\n'
        f'- 图片尺寸比例参考：{image_size_ratio or "1:1"}\n'
        f'- 说明文字种类：{text_type or "中文"}\n'
        f'- 国家参考：{country or "中国"}\n'
        f'- 必须保留（must_keep）：{must_keep}\n'
        f'- 绝对不可改变（must_not_change）：{must_not_change}\n'
        f'- 明确禁止出现（forbidden_changes）：{forbidden_changes}\n'
        f'- 可表达卖点（selling_points）：{selling_points}\n'
        f'- 若提供了不可变商品特征，必须将其中的主体品类、核心主体、颜色体系、材质、轮廓、结构、关键部件、品牌标识、logo位置、稳定细节、must_keep、must_not_change、forbidden_changes 与 consistency_rules 视为最高优先级约束。\n'
        f'- 若提供了参考商品图，必须把参考图视为主体锚点，优先复用其主体外观、颜色关系、材质质感、结构比例、边缘轮廓、关键部件、logo/品牌位与稳定细节。\n'
        f'- selling_points 只能用于补充文案重点、信息层级与卖点表达，不得推动商品变成其他颜色、其他材质、其他结构、其他部件方案或其他品牌观感。\n'
        f'- 允许变化的仅限背景、道具、光线、构图、文案排版与非主体装饰；禁止把商品改成另一种外观、另一种材质表现、另一种结构、另一种颜色体系、另一种关键部件组合或另一种品牌识别。\n'
        f'- 不要把场景氛围、背景纯度、人物气质或镜头语言误当作商品主体特征；它们只能作为从属变化，不能覆盖主体锁定要求。\n'
        f'- 本张图必须与同套图中的其他图形成明显展示差异，不能复用相同的商品朝向、相同的人物动作、相同的持握方式、相同的商品摆位、相同的景别或相同的版式骨架。\n'
        f'- 若本张图包含人物、手部或模特，它们只能服务当前图类型表达，且应与其他图的人物姿势、身体朝向、商品相对位置明显不同。\n'
        f'- 若本张图不包含人物，则必须通过商品朝向、远近景切换、局部特写、平铺/立放/悬浮/包装展开等摆放方式变化，主动与其他图区分。\n'
        f'- 主图、卖点图、细节图、参数图、售后图至少应在展示角度、构图重心与商品摆法上明显不同，禁止做成同一参考姿势的连续换背景或加字版本。\n'
        f'- 首屏主视觉图、核心卖点图、使用场景图三张图尤其要避免同姿势复用；宁可牺牲部分背景统一感，也必须优先拉开商品朝向、人物动作、手持关系、远近景和商品在画面中的位置差异。\n'
        f'{type_specific_rules}'
        f'- 若卖点、生活方式、消费场景、节日氛围或合规表达与地区有关，优先按国家参考进行画面设计与文案表达。'
    )
    request_payload = {
        'model': model,
        'prompt': enriched_prompt,
        'size': size,
        'response_format': 'b64_json',
        'stream': True,
    }

    extra_body = {
        'watermark': watermark,
        'sequential_image_generation': sequential_mode,
        'sequential_image_generation_options': {
            'max_images': max(1, min(max_images, sequential_max_images)),
        },
    }
    if image_payloads:
        extra_body['image'] = [payload['data_url'] for payload in image_payloads]
    if quality:
        extra_body['quality'] = quality
    request_payload['extra_body'] = extra_body
    app.logger.warning('ARK image request extra_body: %s', json.dumps(extra_body, ensure_ascii=False))

    response = client.images.generate(**request_payload)
    return collect_streamed_generated_images(response)


def generate_suite_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
    client = get_ark_client()
    images = []
    all_plan_types = [str(item.get('type', '')).strip() for item in plan.get('items', []) if str(item.get('type', '')).strip()]
    plan_items = list(plan.get('items') or [])
    sequential_max_images = max(get_optional_int_env('ARK_SEQUENTIAL_MAX_IMAGES', 1), 1)
    index = 0

    while index < len(plan_items):
        item = plan_items[index]
        remaining_items = plan_items[index:]
        generated_items = call_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
            product_json,
            item['type'],
            item,
            all_plan_types,
            max_images=min(len(remaining_items), sequential_max_images),
        )

        consumed_count = 0
        for generated_item, plan_item in zip(generated_items, remaining_items):
            image_bytes, mime_type = decode_generated_image(generated_item)
            download_name, relative_path, image_url = save_generated_image(task_id, plan_item['sort'], plan_item['type'], image_bytes, mime_type)
            images.append(
                {
                    'sort': plan_item['sort'],
                    'kind': 'generated',
                    'type': plan_item['type'],
                    'type_tag': plan_item['type_tag'],
                    'title': plan_item['title'],
                    'keywords': plan_item['keywords'],
                    'prompt': plan_item['prompt'],
                    'image_url': image_url,
                    'image_path': relative_path,
                    'download_name': download_name,
                }
            )
            consumed_count += 1

        if consumed_count < 1:
            raise ValueError('图像生成接口未返回可用图片内容')

        index += consumed_count

    return images



def generate_aplus_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None):
    client = get_ark_client()
    images = []

    for item in plan['items']:
        generated_items = call_image_generation(
            client,
            item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
            product_json,
            item['type'],
            max_images=1,
        )
        generated_item = generated_items[0]
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


@app.post('/api/generate-fashion-model')
def generate_fashion_model():
    try:
        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            payload = {}

        gender = get_request_value(payload, request.form, 'gender', '女') or '女'
        age = get_request_value(payload, request.form, 'age', '青年') or '青年'
        ethnicity = get_request_value(payload, request.form, 'ethnicity', '欧美白人') or '欧美白人'
        body_type = get_request_value(payload, request.form, 'body_type', '标准') or '标准'
        appearance_details = get_request_value(payload, request.form, 'appearance_details', '')
        image_size_ratio = get_request_value(payload, request.form, 'image_size_ratio', '3:4') or '3:4'

        task_id = uuid.uuid4().hex
        prompt = build_fashion_model_prompt(gender, age, ethnicity, body_type, appearance_details)
        generated_item = call_image_generation(
            get_ark_client(),
            prompt,
            [],
            image_size_ratio,
            '无文字',
            '中国',
            None,
            'fashion-model',
            max_images=1,
        )[0]
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, 1, 'fashion-model', image_bytes, mime_type)
        model_id = f'ai-{task_id}'
        model = build_fashion_model_response(
            task_id,
            model_id,
            gender,
            age,
            ethnicity,
            body_type,
            appearance_details,
            prompt,
            image_url,
            relative_path,
            download_name,
        )

        return jsonify(
            {
                'success': True,
                'task_id': task_id,
                'model': model,
                'image_url': image_url,
                'image_path': relative_path,
                'download_name': download_name,
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
            fashion_platform = FASHION_DEFAULT_PLATFORM
            fashion_selling_text = FASHION_DEFAULT_SELLING_TEXT
            fashion_country = FASHION_DEFAULT_COUNTRY
            fashion_text_type = FASHION_DEFAULT_TEXT_TYPE
            fashion_selected_style = FASHION_DEFAULT_SELECTED_STYLE
            if fashion_action == 'scene_plan':
                selected_model = parse_fashion_selected_model_payload(request.form)
                planning_payloads = image_payloads + [selected_model['payload']]
            else:
                selected_model = None
                planning_payloads = image_payloads
            if not planning_payloads:
                return jsonify({'success': False, 'error': '请至少上传商品图或模特参考图'}), 400

            if fashion_action == 'scene_plan':
                scene_plan = build_fashion_scene_plan(
                    fashion_platform,
                    fashion_selling_text,
                    planning_payloads,
                    fashion_country,
                    fashion_text_type,
                    image_size_ratio,
                    fashion_selected_style,
                )
                fashion_debug = {
                    'selected_model': selected_model.get('debug'),
                    'product_image_count': len(image_payloads),
                    'generation_payload_order': ['images'] * len(image_payloads) + ['fashion_selected_model_image'],
                }
                return jsonify(
                    {
                        'success': True,
                        'mode': 'fashion',
                        'fashion_action': 'scene_plan',
                        'plan': scene_plan,
                        'selected_style': fashion_selected_style,
                        'fashion_debug': fashion_debug,
                        'fashion_selection': {
                            'selected_model': {
                                'source': selected_model['source'],
                                'id': selected_model['id'],
                                'name': selected_model['name'],
                            },
                        },
                    }
                )

            selected_model = parse_fashion_selected_model_payload(request.form)
            selected_model_payload = selected_model['payload']
            scene_plan = parse_fashion_scene_plan_payload(request.form.get('fashion_scene_plan', ''))
            scene_group_ids = parse_json_string_list(request.form.get('fashion_scene_group_ids', ''), '场景')
            pose_ids = parse_json_string_list(request.form.get('fashion_pose_ids', ''), '姿态')

            selections = parse_fashion_scene_selections(scene_plan.get('scene_groups') or [], scene_group_ids, pose_ids)
            pose_camera_settings = parse_fashion_pose_camera_settings(
                request.form.get('fashion_pose_camera_settings', ''),
                selections,
            )
            prompt_entries = build_fashion_generation_prompts(
                fashion_platform,
                fashion_selling_text,
                fashion_country,
                fashion_text_type,
                image_size_ratio,
                fashion_selected_style,
                selected_model,
                scene_plan,
                selections,
                pose_camera_settings,
            )

            task_id = uuid.uuid4().hex
            task_name = build_task_name(fashion_platform, 'fashion', len(prompt_entries))
            generated_at = build_generated_at()
            reference_images = build_reference_images(task_id, image_payloads, source='product')
            reference_images.extend(
                build_reference_images(
                    task_id,
                    [selected_model_payload],
                    source='fashion_reference',
                    start_sort=len(reference_images) + 1,
                )
            )

            fashion_generation_payloads = image_payloads + [selected_model_payload]
            fashion_debug = {
                'selected_model': selected_model.get('debug'),
                'product_image_count': len(image_payloads),
                'generation_payload_order': ['images'] * len(image_payloads) + ['fashion_selected_model_image'],
            }
            max_verify_attempts = max(1, get_optional_int_env('FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS', FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS))
            images = []
            failed_prompt_entries = []
            for index, prompt_entry in enumerate(prompt_entries, start=1):
                app.logger.warning(
                    'Fashion image generation start: index=%s total=%s title=%s shot_size=%s view_angle=%s',
                    index,
                    len(prompt_entries),
                    prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                    prompt_entry.get('shot_size', ''),
                    prompt_entry.get('view_angle', ''),
                )
                verification = None
                generated_items = []
                image_bytes = None
                mime_type = 'image/png'
                for attempt in range(1, max_verify_attempts + 1):
                    generated_items = call_image_generation(
                        get_ark_client(),
                        prompt_entry['prompt'],
                        fashion_generation_payloads,
                        image_size_ratio,
                        '无文字',
                        fashion_country,
                        product_json,
                        'fashion-look',
                        max_images=1,
                    )
                    generated_count = len(generated_items) if isinstance(generated_items, list) else 0
                    app.logger.warning(
                        'Fashion image generation result: index=%s total=%s attempt=%s generated_count=%s title=%s',
                        index,
                        len(prompt_entries),
                        attempt,
                        generated_count,
                        prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                    )
                    if not generated_items:
                        continue
                    image_bytes, mime_type = decode_generated_image(generated_items[0])
                    generated_payload = {
                        'filename': f'fashion-look-{index:02d}.png',
                        'mime_type': mime_type,
                        'bytes': image_bytes,
                        'base64': base64.b64encode(image_bytes).decode('utf-8'),
                        'data_url': f'data:{mime_type};base64,{base64.b64encode(image_bytes).decode("utf-8")}',
                    }
                    verification = verify_fashion_generated_output(
                        generated_payload,
                        selected_model_payload,
                        image_payloads,
                    )
                    app.logger.warning(
                        'Fashion output verification: index=%s attempt=%s passed=%s score=%s failed_checks=%s reason=%s',
                        index,
                        attempt,
                        verification.get('passed'),
                        verification.get('score'),
                        ','.join(verification.get('failed_checks') or []),
                        verification.get('reason', ''),
                    )
                    if verification.get('passed'):
                        break
                if not generated_items or image_bytes is None:
                    failed_prompt_entries.append(
                        {
                            'index': index,
                            'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                            'reason': '生成结果为空',
                        }
                    )
                    continue
                if not verification or not verification.get('passed'):
                    failed_prompt_entries.append(
                        {
                            'index': index,
                            'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                            'reason': (verification or {}).get('reason', '质检未通过'),
                            'failed_checks': (verification or {}).get('failed_checks', []),
                        }
                    )
                    continue
                download_name, relative_path, image_url = save_generated_image(task_id, index, 'fashion-look', image_bytes, mime_type)
                images.append(
                    {
                        'sort': index,
                        'kind': 'generated',
                        'type': '服饰穿搭图',
                        'type_tag': 'Look',
                        'title': prompt_entry['pose'].get('title') or f'服饰穿搭图 {index}',
                        'keywords': [prompt_entry.get('shot_size', ''), prompt_entry.get('view_angle', '')],
                        'prompt': prompt_entry['prompt'],
                        'image_url': image_url,
                        'image_path': relative_path,
                        'download_name': download_name,
                        'verification': verification,
                    }
                )

            if not images:
                failure_titles = '、'.join(item['title'] for item in failed_prompt_entries[:3])
                failure_reason = '；'.join(
                    item['reason'] for item in failed_prompt_entries[:2] if str(item.get('reason') or '').strip()
                )
                failure_hint = f'（失败场景：{failure_titles}）' if failure_titles else ''
                failure_reason_hint = f'：{failure_reason}' if failure_reason else ''
                raise RuntimeError(f'生成结果未通过模特/文字质检，请稍后重试{failure_hint}{failure_reason_hint}')

            return jsonify(
                {
                    'success': True,
                    'mode': 'fashion',
                    'fashion_action': 'generate',
                    'task_id': task_id,
                    'task_name': task_name,
                    'generated_at': generated_at,
                    'selected_style': fashion_selected_style,
                    'fashion_debug': fashion_debug,
                    'reference_images': reference_images,
                    'images': images,
                    'fashion_selection': {
                        'selected_model': {
                            'source': selected_model['source'],
                            'id': selected_model['id'],
                            'name': selected_model['name'],
                            'gender': selected_model.get('gender', ''),
                            'age': selected_model.get('age', ''),
                            'ethnicity': selected_model.get('ethnicity', ''),
                            'body_type': selected_model.get('body_type', ''),
                        },
                        'scene_group_ids': scene_group_ids,
                        'pose_ids': pose_ids,
                        'pose_camera_settings': pose_camera_settings,
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
