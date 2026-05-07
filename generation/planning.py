import json
import logging
import os
import re

import requests
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    get_supabase_setting, get_supabase_setting_int,
    get_optional_env, get_optional_int_env,
)
from image_utils import (
    build_multimodal_content, normalize_product_json, build_product_json_prompt_text,
)
from prompts import (
    SUITE_TYPE_META, SUITE_TYPE_RULES, APLUS_MODULE_META,
    APLUS_PLAN_SYSTEM_PROMPT, APLUS_PLAN_USER_PROMPT_TEMPLATE,
    SUITE_PLAN_SYSTEM_PROMPT, SUITE_PLAN_USER_PROMPT_TEMPLATE,
    PRODUCT_JSON_SYSTEM_PROMPT, PRODUCT_JSON_USER_PROMPT_TEMPLATE,
    FASHION_SCENE_PLAN_SYSTEM_PROMPT, FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE,
    FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT, FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE,
    FASHION_OUTPUT_MAX_VERIFY_ATTEMPTS, FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS,
    FASHION_MODEL_APPEARANCE_FALLBACK,
)
from utils import (
    normalize_hex_color, strip_code_fences, parse_json_candidate,
    normalize_plan_short_text, normalize_plan_enum, normalize_plan_type_list,
)

logger = logging.getLogger(__name__)


CHAT_COMPLETION_RETRYABLE_STATUS_CODES = {429, 502, 503, 504, 524}
CHAT_COMPLETION_FALLBACK_ERROR_TOKENS = (
    'Your request was blocked', 'AccountOverdueError', 'overdue balance',
    'usage limit', 'usage_limit_reached', 'HTTPSConnectionPool',
    'SSLError', 'SSLEOFError', 'EOF occurred in violation of protocol',
    'Max retries exceeded', '524',
    '401', '403', '503',
    'authentication_error', 'auth_unavailable',
    'token is expired', 'Invalid API Key', 'Incorrect API key',
    'invalid_api_key',
    'model_not_found', 'No available channel', 'new_api_error',
    'Expecting value', 'JSONDecodeError',
)
CHAT_COMPLETION_FALLBACK_TIMEOUT_TOKENS = (
    'timed out', 'timeout', 'read timeout', 'read timed out',
    'connect timeout', 'connection timed out',
)


def _format_error_brief(error_text: str) -> str:
    error_lower = error_text.lower()
    if 'ssl' in error_lower or 'eof' in error_lower:
        return 'SSL_ERROR'
    if 'timed out' in error_lower or 'timeout' in error_lower:
        return 'TIMEOUT_ERROR'
    if 'connection aborted' in error_lower or 'connection reset' in error_lower:
        return 'CONNECTION_ERROR'
    if 'max retries exceeded' in error_lower:
        return 'MAX_RETRIES_EXCEEDED'
    if len(error_text) > 80:
        return error_text[:80] + '...'
    return error_text


def get_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise ValueError(f'缺少环境变量：{name}')
    return value


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


def _create_chat_client(api_key: str, base_url: str) -> OpenAI:
    normalized_base_url = str(base_url or '').strip().rstrip('/') + '/'
    return OpenAI(api_key=api_key, base_url=normalized_base_url)


def _run_chat_completion(client: OpenAI, model: str, system_prompt: str, user_content, temperature: float, timeout_seconds: int):
    return client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
        temperature=temperature,
        timeout=timeout_seconds,
    )


def _run_chat_completion_http(api_key: str, base_url: str, model: str, system_prompt: str, user_content, temperature: float, timeout_seconds: int):
    normalized_base_url = str(base_url or '').strip().rstrip('/') + '/'
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        status=0,
        backoff_factor=0.5,
        allowed_methods=frozenset({'POST'}),
        status_forcelist=frozenset(),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    try:
        response = session.post(
            f'{normalized_base_url}chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_content},
                ],
                'temperature': temperature,
                'stream': False,
            },
            timeout=timeout_seconds,
        )
    finally:
        session.close()
    if response.status_code >= 400:
        raise RuntimeError(f'Error code: {response.status_code} - {response.text}')
    return response.json()


def should_enable_chat_fallback_to_ark() -> bool:
    fallback_mode = str(get_supabase_setting('CHAT_FALLBACK_TO_ARK', get_optional_env('CHAT_FALLBACK_TO_ARK', 'auto')) or 'auto').strip().lower()
    if fallback_mode in {'on', 'true', '1', 'yes'}:
        return True
    if fallback_mode in {'off', 'false', '0', 'no'}:
        return False
    return True


def get_suite_plan_timeout_seconds() -> int:
    return max(get_supabase_setting_int('SUITE_PLAN_TIMEOUT_SECONDS', get_optional_int_env('SUITE_PLAN_TIMEOUT_SECONDS', 180)), 60)


def call_chat_completion(system_prompt: str, user_content, temperature: float = 0.7, timeout_seconds: int = 120):
    primary_api_key = get_supabase_setting('OPENAI_API_KEY', get_env('OPENAI_API_KEY'))
    primary_base_url = get_supabase_setting('OPENAI_BASE_URL', get_env('OPENAI_BASE_URL'))
    primary_model = get_supabase_setting('OPENAI_MODEL', get_env('OPENAI_MODEL'))

    try:
        response = _run_chat_completion_http(
            primary_api_key,
            primary_base_url,
            primary_model,
            system_prompt,
            user_content,
            temperature,
            timeout_seconds,
        )
        model = primary_model
    except Exception as exc:
        error_text = str(exc)
        error_lower = error_text.lower()
        should_fallback_to_ark = should_enable_chat_fallback_to_ark() and (
            any(token in error_text for token in CHAT_COMPLETION_FALLBACK_ERROR_TOKENS)
            or any(token in error_lower for token in CHAT_COMPLETION_FALLBACK_TIMEOUT_TOKENS)
        )
        if not should_fallback_to_ark:
            raise

        fallback_api_key = get_supabase_setting('ARK_CHAT_API_KEY', get_optional_env('ARK_CHAT_API_KEY', '')) or get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
        fallback_base_url = get_supabase_setting('ARK_CHAT_BASE_URL', get_optional_env('ARK_CHAT_BASE_URL', '')) or get_supabase_setting('ARK_BASE_URL', get_optional_env('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3'))
        fallback_model = get_supabase_setting('ARK_CHAT_MODEL', get_optional_env('ARK_CHAT_MODEL', 'doubao-1-5-lite-32k-250115'))
        if not fallback_api_key:
            raise

        logger.warning(
            'Primary chat failed, fallback to Ark: model=%s error=%s',
            fallback_model,
            _format_error_brief(error_text),
        )
        try:
            response = _run_chat_completion(
                _create_chat_client(fallback_api_key, fallback_base_url),
                fallback_model,
                system_prompt,
                user_content,
                temperature,
                timeout_seconds,
            )
        except Exception as fallback_exc:
            raise RuntimeError(f'主AI接口失败且备用AI接口也失败。主接口错误：{error_text}；备用接口错误：{fallback_exc}') from fallback_exc
        model = fallback_model

    if isinstance(response, dict):
        choice = ((response.get('choices') or [None])[0] or {})
        message = choice.get('message') or {}
        text = message.get('content') or ''
        usage = response.get('usage') or {}
        finish_reason = choice.get('finish_reason') or ''
        choice_count = len(response.get('choices') or [])
    else:
        choices = getattr(response, 'choices', None) or [None]
        choice = choices[0] or {}
        message = choice.message if hasattr(choice, 'message') else {}
        text = getattr(message, 'content', '') if message else ''
        usage = getattr(response, 'usage', None) or {}
        finish_reason = getattr(choice, 'finish_reason', '') if choice else ''
        choice_count = len(choices)
    if isinstance(text, list):
        text = ''.join(part.text for part in text if getattr(part, 'text', None))
    elif text is None:
        text = ''
    text = str(text).strip() if text else ''
    reasoning_text = message.get('reasoning_content', '') if isinstance(message, dict) else (getattr(message, 'reasoning_content', '') if message else '')
    if isinstance(reasoning_text, list):
        reasoning_text = ''.join(part.text for part in reasoning_text if getattr(part, 'text', None))
    elif reasoning_text is None:
        reasoning_text = ''
    reasoning_text = str(reasoning_text).strip() if reasoning_text else ''
    if isinstance(usage, dict):
        prompt_tokens = usage.get('prompt_tokens')
        completion_tokens = usage.get('completion_tokens')
        total_tokens = usage.get('total_tokens')
        reasoning_tokens = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens') if isinstance(usage.get('completion_tokens_details'), dict) else None
    else:
        prompt_tokens = getattr(usage, 'prompt_tokens', None)
        completion_tokens = getattr(usage, 'completion_tokens', None)
        total_tokens = getattr(usage, 'total_tokens', None)
        completion_details = getattr(usage, 'completion_tokens_details', None)
        reasoning_tokens = getattr(completion_details, 'reasoning_tokens', None) if completion_details else None
    logger.warning(
        'Chat completion response summary: model=%s choices=%s finish_reason=%s content_len=%s reasoning_len=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s reasoning_tokens=%s',
        model,
        choice_count,
        finish_reason,
        len(text),
        len(reasoning_text),
        prompt_tokens,
        completion_tokens,
        total_tokens,
        reasoning_tokens,
    )

    if not text:
        fallback_fields = ['reasoning_content']
        for field in fallback_fields:
            fallback_text = message.get(field, '') if isinstance(message, dict) else (getattr(message, field, '') if message else '')
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


def extract_json_candidate(text: str) -> str:
    cleaned = strip_code_fences(str(text or ''))
    if not cleaned:
        return cleaned
    start_indexes = [index for index in [cleaned.find('{'), cleaned.find('[')] if index >= 0]
    if not start_indexes:
        return cleaned
    start = min(start_indexes)
    opener = cleaned[start]
    closer = '}' if opener == '{' else ']'
    end = cleaned.rfind(closer)
    if end <= start:
        return cleaned
    return cleaned[start:end + 1].strip()


def build_json_repair_prompt(raw_text: str, error_message: str) -> str:
    return (
        '下面内容本应是 JSON，但格式不合法。请只返回修复后的合法 JSON，不要解释，不要 Markdown 代码块。\n'
        f'解析错误：{error_message}\n'
        '原始内容：\n'
        f'{str(raw_text or "")}'
    )


def call_chat_json_with_repair(
    system_prompt: str,
    user_content,
    parser,
    error_prefix: str,
    temperature: float = 0.3,
    timeout_seconds: int = 60,
    repair_attempts: int = 1,
):
    response_text = call_chat_completion(system_prompt, user_content, temperature=temperature, timeout_seconds=timeout_seconds)
    try:
        return parser(response_text), response_text
    except ValueError as first_exc:
        last_exc = first_exc
        repaired_text = response_text
        for attempt in range(max(int(repair_attempts or 0), 0)):
            try:
                repaired_text = call_chat_completion(
                    '你是严格的 JSON 修复器，只能输出合法 JSON。',
                    build_json_repair_prompt(repaired_text, str(last_exc)),
                    temperature=0,
                    timeout_seconds=min(max(timeout_seconds, 60), 120),
                )
                return parser(repaired_text), repaired_text
            except ValueError as exc:
                last_exc = exc
                logger.warning('%s JSON repair attempt %s failed: %s', error_prefix, attempt + 1, exc)
        raise last_exc


def parse_style_analysis(text: str):
    payload = parse_json_candidate(text, '风格分析结果格式异常')

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


def parse_product_json(text: str):
    try:
        payload = parse_json_candidate(text, '商品结构化信息格式异常')
    except ValueError:
        payload = extract_json_object_from_text(strip_code_fences(text))
        if payload is None:
            raise ValueError('商品结构化信息格式异常：无法解析为 JSON 对象')
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息格式异常：顶层必须为对象')
    return normalize_product_json(payload)


def parse_product_json_payload(raw_value: str):
    normalized_raw = (raw_value or '').strip()
    if not normalized_raw:
        return None
    try:
        payload = json.loads(normalized_raw)
    except json.JSONDecodeError:
        payload = extract_json_object_from_text(normalized_raw)
        if payload is None:
            raise ValueError('商品结构化信息参数格式异常')
    if not isinstance(payload, dict):
        raise ValueError('商品结构化信息参数格式异常：顶层必须为对象')
    return normalize_product_json(payload)


def extract_json_object_from_text(text: str):
    if not text:
        return None
    candidate_patterns = [
        r'\{[\s\S]*\}',
    ]
    for pattern in candidate_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


PRODUCT_JSON_FALLBACK = {
    'product_name': '', 'category': '', 'core_subject': '',
    'subject_composition': {'subject_count': '', 'subject_units': [], 'assembly_form': ''},
    'appearance': {
        'primary_colors': [], 'secondary_colors': [], 'materials': [],
        'textures_patterns': [], 'silhouette': '', 'structure': '',
        'surface_finish': '', 'craft_details': [],
    },
    'key_components': [],
    'brand_identity': {'brand_name': '', 'logo_details': '', 'text_markings': [], 'logo_positions': []},
    'immutable_traits': [], 'consistency_rules': [],
    'must_keep': [], 'must_not_change': [], 'forbidden_changes': [], 'selling_points': [],
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


def extract_product_json_from_image_payloads(selling_text: str, image_payloads):
    if not image_payloads:
        return None
    product_json, _response_text = call_chat_json_with_repair(
        PRODUCT_JSON_SYSTEM_PROMPT,
        build_multimodal_content(
            PRODUCT_JSON_USER_PROMPT_TEMPLATE.format(selling_text=selling_text or '（未填写）'),
            image_payloads,
        ),
        parse_product_json,
        '商品结构化信息格式异常',
        temperature=0.2,
        timeout_seconds=get_suite_plan_timeout_seconds(),
        repair_attempts=1,
    )
    try:
        return normalize_product_json(product_json)
    except ValueError as exc:
        logger.warning('商品结构化信息解析失败，已降级为空结构：%s', exc)
        return normalize_product_json(PRODUCT_JSON_FALLBACK)


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
    payload = parse_json_candidate(text, '套图规划结果格式异常')

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

        module = normalize_plan_enum(
            item.get('module'),
            {'opening_narrative', 'scene_narrative', 'value_visualization', 'trust_narrative'},
            'scene_narrative',
        )
        story_role = normalize_plan_short_text(item.get('story_role'), '未指定故事节点')
        decision_task = normalize_plan_short_text(item.get('decision_task'), '未指定决策任务')
        info_density = normalize_plan_enum(item.get('info_density'), {'low', 'medium', 'high'}, 'medium')

        scene_required_raw = item.get('scene_required')
        if not isinstance(scene_required_raw, bool):
            raise ValueError(f'套图规划结果格式异常：第 {index} 项 scene_required 必须为布尔值')

        human_presence = normalize_plan_enum(item.get('human_presence'), {'none', 'hand-only', 'model'}, 'none')
        scene_type = normalize_plan_short_text(item.get('scene_type'), '未指定场景')
        camera_shot = normalize_plan_short_text(item.get('camera_shot'), '未指定景别')
        subject_angle = normalize_plan_short_text(item.get('subject_angle'), '未指定角度')
        action_type = normalize_plan_short_text(item.get('action_type'), '静态陈列')
        layout_anchor = normalize_plan_short_text(item.get('layout_anchor'), '主体居中放大')
        layout_style = normalize_plan_short_text(item.get('layout_style'), '单图分层')
        font_style = normalize_plan_short_text(item.get('font_style'), '清晰无衬线')
        color_scheme = normalize_plan_short_text(item.get('color_scheme'), '低饱和同色系')
        decor_elements = item.get('decor_elements') if isinstance(item.get('decor_elements'), list) else []
        decor_elements = [normalize_plan_short_text(value) for value in decor_elements]
        decor_elements = [value for value in decor_elements if value][:4]
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
                'module': module,
                'story_role': story_role,
                'decision_task': decision_task,
                'info_density': info_density,
                'scene_required': scene_required_raw,
                'scene_type': scene_type,
                'camera_shot': camera_shot,
                'subject_angle': subject_angle,
                'human_presence': human_presence,
                'action_type': action_type,
                'layout_anchor': layout_anchor,
                'layout_style': layout_style,
                'font_style': font_style,
                'color_scheme': color_scheme,
                'decor_elements': decor_elements,
                'must_differ_from': must_differ_from,
            }
        )

    return {
        'summary': summary,
        'output_count': expected_output_count,
        'items': normalized_items,
    }


def build_suite_plan(platform: str, selling_text: str, output_count: int, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None, mode: str = 'suite', product_json=None):
    _, type_rules = get_suite_type_rules(output_count)
    prompt = build_suite_plan_prompt(platform, selling_text, output_count, type_rules, country, text_type, image_size_ratio, selected_style, mode, product_json)
    plan, _response_text = call_chat_json_with_repair(
        SUITE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        lambda text: parse_suite_plan(text, output_count, type_rules),
        '套图规划结果格式异常',
        temperature=0.3,
        timeout_seconds=get_suite_plan_timeout_seconds(),
        repair_attempts=1,
    )
    return plan


def parse_fashion_scene_plan(text: str):
    payload = parse_json_candidate(text, '场景规划结果格式异常')

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


def build_fashion_scene_plan_prompt(platform: str, selling_text: str, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    return FASHION_SCENE_PLAN_USER_PROMPT_TEMPLATE.format(
        image_size_ratio=image_size_ratio or '1:1',
    )


def build_fashion_scene_plan(platform: str, selling_text: str, image_payloads, country: str, text_type: str, image_size_ratio: str, selected_style=None):
    prompt = build_fashion_scene_plan_prompt(platform, selling_text, country, text_type, image_size_ratio, selected_style)
    plan, _response_text = call_chat_json_with_repair(
        FASHION_SCENE_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        parse_fashion_scene_plan,
        '服饰场景规划结果格式异常',
        temperature=0.3,
        timeout_seconds=FASHION_SCENE_PLAN_MODEL_TIMEOUT_SECONDS,
        repair_attempts=1,
    )
    return plan


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


def parse_fashion_selected_model_payload_from_data(form, selected_payloads):
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
    payload = parse_json_candidate(text, '服饰成图质检结果格式异常')

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
    verification, _response_text = call_chat_json_with_repair(
        FASHION_OUTPUT_VERIFIER_SYSTEM_PROMPT,
        build_multimodal_content(FASHION_OUTPUT_VERIFIER_USER_PROMPT_TEMPLATE, verification_payloads),
        parse_fashion_output_verification,
        '服饰成图质检结果格式异常',
        temperature=0,
        timeout_seconds=90,
        repair_attempts=1,
    )
    return verification


def get_request_value(payload: dict, form, key: str, default: str = '') -> str:
    if key in payload:
        return str(payload.get(key, default) or '').strip()
    return str(form.get(key, default) or '').strip()


def build_fashion_model_prompt(gender: str, age: str, ethnicity: str, body_type: str, appearance_details: str) -> str:
    normalized_gender = gender or '女'
    normalized_age = age or '青年（18-35岁）'
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
    payload = parse_json_candidate(text, 'A+ 规划结果格式异常')

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
    prompt = build_aplus_plan_prompt(platform, selling_text, selected_module_keys, country, text_type, image_size_ratio, selected_style, product_json)
    plan, _response_text = call_chat_json_with_repair(
        APLUS_PLAN_SYSTEM_PROMPT,
        build_multimodal_content(prompt, image_payloads),
        lambda text: parse_aplus_plan(text, selected_module_keys),
        'A+ 规划结果格式异常',
        temperature=0.3,
        timeout_seconds=90,
        repair_attempts=1,
    )
    return plan


def get_mode3_suite_batch_size() -> int:
    return max(get_supabase_setting_int('MODE3_SUITE_BATCH_SIZE', get_optional_int_env('MODE3_SUITE_BATCH_SIZE', 1)), 1)


def _common_timeout_seconds() -> int:
    return max(get_supabase_setting_int('TIMEOUT_SECONDS', get_optional_int_env('TIMEOUT_SECONDS', 180)), 30)


def get_mode1_timeout_seconds() -> int:
    return max(get_supabase_setting_int('MODE1_TIMEOUT_SECONDS', get_optional_int_env('MODE1_TIMEOUT_SECONDS', _common_timeout_seconds())), 30)


def get_mode2_timeout_seconds() -> int:
    return max(get_supabase_setting_int('MODE2_TIMEOUT_SECONDS', get_optional_int_env('MODE2_TIMEOUT_SECONDS', _common_timeout_seconds())), 30)


def extract_generated_image_from_content(content):
    if isinstance(content, str):
        data_url_match = re.search(r'data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+', content)
        if data_url_match:
            data_url = re.sub(r'\s+', '', data_url_match.group(0))
            return {'b64_json': data_url.split(',', 1)[1]}
        base64_match = re.search(r'(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{800,}={0,2})(?![A-Za-z0-9+/=])', content)
        if base64_match:
            return {'b64_json': base64_match.group(1)}
        image_url_match = re.search(r'https?://[^\s\]})"\']+\.(?:png|jpe?g|webp|gif)(?:\?[^\s\]})"\']*)?', content, re.IGNORECASE)
        if image_url_match:
            return {'url': image_url_match.group(0)}
        return None

    if isinstance(content, list):
        for part in content:
            if hasattr(part, 'model_dump'):
                part = part.model_dump()
            elif hasattr(part, 'dict'):
                part = part.dict()
            if not isinstance(part, dict):
                continue
            if part.get('type') in {'image_url', 'input_image'}:
                image_url = part.get('image_url') or part.get('url')
                if isinstance(image_url, dict):
                    image_url = image_url.get('url')
                if isinstance(image_url, str) and image_url.startswith('data:image/') and ',' in image_url:
                    return {'b64_json': image_url.split(',', 1)[1]}
                if isinstance(image_url, str) and image_url:
                    return {'url': image_url}
            if part.get('type') in {'image', 'output_image'}:
                image_data = part.get('image') or part.get('data') or part.get('b64_json')
                if isinstance(image_data, dict):
                    image_data = image_data.get('b64_json') or image_data.get('data') or image_data.get('url')
                if isinstance(image_data, str) and image_data.startswith('data:image/') and ',' in image_data:
                    return {'b64_json': image_data.split(',', 1)[1]}
                if isinstance(image_data, str) and image_data.startswith(('http://', 'https://')):
                    return {'url': image_data}
                if isinstance(image_data, str) and image_data:
                    return {'b64_json': image_data}
            nested = extract_generated_image_from_content(part.get('text') or part.get('content'))
            if nested:
                return nested
    return None


def normalize_chat_completion_image_response(response):
    if hasattr(response, 'model_dump'):
        response_dict = response.model_dump()
    elif hasattr(response, 'dict'):
        response_dict = response.dict()
    elif isinstance(response, dict):
        response_dict = response
    else:
        return response

    choices = response_dict.get('choices') if isinstance(response_dict, dict) else None
    if not isinstance(choices, list) or not choices:
        return response
    message = (choices[0] or {}).get('message') or {}
    generated_item = extract_generated_image_from_content(message.get('content'))
    if generated_item:
        return {'data': [generated_item]}
    return response


