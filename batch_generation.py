import json
import logging
import time
import uuid
import base64
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def generate_batch_images(
    gen_type: str,
    config: Dict,
    input_images: List[Dict],
    task_id: str,
    _logger: logging.Logger | None = None
) -> List[Dict]:
    log = _logger or logger
    
    log.info(f"开始生成图片: gen_type={gen_type}, task_id={task_id}")
    
    if gen_type == 'suite':
        return _generate_suite_images(config, input_images, task_id, _logger=log)
    elif gen_type == 'aplus':
        return _generate_aplus_images(config, input_images, task_id, _logger=log)
    elif gen_type == 'fashion':
        return _generate_fashion_images(config, input_images, task_id, _logger=log)
    else:
        log.error(f"未知的生成类型: gen_type={gen_type}")
        return []


def _prepare_image_payloads(input_images: List[Dict], _logger: logging.Logger | None = None) -> List[Dict]:
    log = _logger or logger
    
    if not input_images:
        return []
    
    image_payloads = []
    
    for img in input_images:
        if isinstance(img, dict):
            payload = {}
            
            if 'bytes' in img:
                image_bytes = img['bytes']
                mime_type = img.get('mime_type', 'image/jpeg')
                data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                payload['bytes'] = image_bytes
                payload['data_url'] = data_url
                payload['mime_type'] = mime_type
                payload['filename'] = img.get('name', img.get('filename', 'image.png'))
            elif 'data' in img:
                mime_type = img.get('mime_type', img.get('type', 'image/jpeg'))
                data_url = f"data:{mime_type};base64,{img['data']}"
                try:
                    image_bytes = base64.b64decode(img['data'])
                except Exception:
                    image_bytes = None
                payload['data_url'] = data_url
                payload['bytes'] = image_bytes
                payload['mime_type'] = mime_type
                payload['filename'] = img.get('name', 'image.png')
            elif 'data_url' in img:
                payload['data_url'] = img['data_url']
                payload['mime_type'] = img.get('mime_type', 'image/jpeg')
                payload['filename'] = img.get('name', 'image.png')
            elif 'url' in img:
                payload['url'] = img['url']
                payload['mime_type'] = img.get('mime_type', img.get('type', 'image/jpeg'))
                payload['filename'] = img.get('name', 'image.png')
            
            if payload:
                log.info(f"Created payload with keys: {list(payload.keys())}")
                image_payloads.append(payload)
    
    log.info(f"准备了 {len(image_payloads)} 个图片payload")
    return image_payloads


def _generate_suite_images(
    config: Dict,
    input_images: List[Dict],
    task_id: str,
    _logger: logging.Logger | None = None
) -> List[Dict]:
    log = _logger or logger
    
    log.info(f"生成商品套图: task_id={task_id}")
    
    try:
        from generation import (
            generate_suite_images,
            build_suite_plan,
            get_suite_plan_timeout_seconds,
        )
        from image_utils import build_reference_images
        
        platform = config.get('platform', '亚马逊')
        country = config.get('country', '中国')
        text_type = config.get('textType', '中文')
        ratio = config.get('ratio', '1:1')
        selling_points = config.get('sellingPoints', '')
        
        prompt_config = config.get('promptConfig', {})
        prompt_mode = prompt_config.get('mode', 'auto')
        
        image_payloads = _prepare_image_payloads(input_images, _logger=log)
        
        if not image_payloads:
            log.warning("没有输入图片，使用模拟结果")
            return _generate_mock_suite_results(config, _logger=log)
        
        output_count = 3
        scene_types = prompt_config.get('sceneTypes', ['hero', 'usage', 'detail'])
        if scene_types:
            output_count = len(scene_types)
        
        selected_style = None
        if prompt_mode == 'auto':
            scene_style = prompt_config.get('sceneStyle', 'modern')
            selected_style = {
                'id': scene_style,
                'name': _get_style_name(scene_style),
                'prompt': _get_style_description(scene_style),
            }
        
        log.info(f"调用build_suite_plan: platform={platform}, output_count={output_count}")
        
        plan = build_suite_plan(
            platform=platform,
            selling_text=selling_points,
            output_count=output_count,
            image_payloads=image_payloads,
            country=country,
            text_type=text_type,
            image_size_ratio=ratio,
            selected_style=selected_style,
            mode='suite',
            product_json=None,
        )
        
        log.info(f"生成计划完成: {len(plan.get('items', []))} 个场景")
        
        reference_images = build_reference_images(task_id, image_payloads, source='product')
        
        images = generate_suite_images(
            plan=plan,
            image_payloads=image_payloads,
            task_id=task_id,
            image_size_ratio=ratio,
            text_type=text_type,
            country=country,
            product_json=None,
            _logger=log,
        )
        
        log.info(f"图片生成完成: {len(images)} 张")
        
        result_images = []
        for img in images:
            result_images.append({
                'url': img.get('image_url', ''),
                'type': img.get('type', ''),
                'sceneType': img.get('title', ''),
                'width': 1024,
                'height': 1024,
                'prompt': img.get('prompt', ''),
                'downloadName': img.get('download_name', ''),
                'imagePath': img.get('image_path', ''),
            })
        
        return result_images
        
    except Exception as e:
        log.error(f"生成商品套图失败: {e}", exc_info=True)
        return _generate_mock_suite_results(config, _logger=log)


def _generate_aplus_images(
    config: Dict,
    input_images: List[Dict],
    task_id: str,
    _logger: logging.Logger | None = None
) -> List[Dict]:
    log = _logger or logger
    
    log.info(f"生成A+详情页: task_id={task_id}")
    
    try:
        from generation import (
            generate_aplus_images,
            build_aplus_plan,
        )
        from image_utils import build_reference_images
        
        platform = config.get('platform', '亚马逊')
        country = config.get('country', '美国')
        text_type = config.get('textType', '英文')
        ratio = config.get('ratio', '3:4')
        selling_points = config.get('sellingPoints', '')
        
        prompt_config = config.get('promptConfig', {})
        prompt_mode = prompt_config.get('mode', 'auto')
        
        image_payloads = _prepare_image_payloads(input_images, _logger=log)
        
        if not image_payloads:
            log.warning("没有输入图片，使用模拟结果")
            return _generate_mock_aplus_results(config, _logger=log)
        
        scene_types = prompt_config.get('sceneTypes', ['hero', 'usage', 'detail'])
        output_count = len(scene_types) if scene_types else 4
        
        selected_style = None
        if prompt_mode == 'auto':
            scene_style = prompt_config.get('sceneStyle', 'modern')
            selected_style = {
                'id': scene_style,
                'name': _get_style_name(scene_style),
                'prompt': _get_style_description(scene_style),
            }
        
        log.info(f"调用build_aplus_plan: platform={platform}, output_count={output_count}")
        
        plan = build_aplus_plan(
            platform=platform,
            selling_text=selling_points,
            output_count=output_count,
            image_payloads=image_payloads,
            country=country,
            text_type=text_type,
            image_size_ratio=ratio,
            selected_style=selected_style,
            product_json=None,
        )
        
        log.info(f"A+计划完成: {len(plan.get('items', []))} 个模块")
        
        reference_images = build_reference_images(task_id, image_payloads, source='product')
        
        images = generate_aplus_images(
            plan=plan,
            image_payloads=image_payloads,
            task_id=task_id,
            image_size_ratio=ratio,
            text_type=text_type,
            country=country,
            product_json=None,
            _logger=log,
        )
        
        log.info(f"A+图片生成完成: {len(images)} 张")
        
        result_images = []
        for img in images:
            result_images.append({
                'url': img.get('image_url', ''),
                'type': img.get('type', ''),
                'sceneType': img.get('title', ''),
                'width': 1024,
                'height': 1024,
                'prompt': img.get('prompt', ''),
                'downloadName': img.get('download_name', ''),
                'imagePath': img.get('image_path', ''),
            })
        
        return result_images
        
    except Exception as e:
        log.error(f"生成A+详情页失败: {e}", exc_info=True)
        return _generate_mock_aplus_results(config, _logger=log)


def _generate_fashion_images(
    config: Dict,
    input_images: List[Dict],
    task_id: str,
    _logger: logging.Logger | None = None
) -> List[Dict]:
    log = _logger or logger
    
    log.info(f"生成服饰穿戴: task_id={task_id}")
    
    try:
        from generation import (
            build_fashion_scene_plan,
            build_fashion_generation_prompts,
            build_fashion_model_prompt,
        )
        from generation.modes import call_app_mode_image_generation, get_ark_client
        from image_utils import build_reference_images
        from app import save_generated_image
        
        model_type = config.get('modelType', 'ai')
        ratio = config.get('ratio', '3:4')
        
        model_config = config.get('modelConfig', {})
        gender = model_config.get('gender', '女')
        age = model_config.get('age', '青年（18-35岁）')
        ethnicity = model_config.get('ethnicity', '欧美白人')
        body_type = model_config.get('bodyType', '标准')
        
        image_payloads = _prepare_image_payloads(input_images, _logger=log)
        
        if not image_payloads:
            log.warning("没有输入图片，使用模拟结果")
            return _generate_mock_fashion_results(config, _logger=log)
        
        log.info(f"AI模特配置: gender={gender}, age={age}, ethnicity={ethnicity}")
        
        model_prompt = build_fashion_model_prompt(
            gender=gender,
            age=age,
            ethnicity=ethnicity,
            body_type=body_type,
        )
        
        log.info("调用build_fashion_scene_plan")
        
        scene_plan = build_fashion_scene_plan(
            image_payloads=image_payloads,
            model_prompt=model_prompt,
            _logger=log,
        )
        
        log.info(f"场景规划完成: {len(scene_plan.get('scene_groups', []))} 组场景")
        
        prompt_entries = build_fashion_generation_prompts(
            scene_plan=scene_plan,
            model_prompt=model_prompt,
            image_payloads=image_payloads,
            _logger=log,
        )
        
        log.info(f"生成提示词完成: {len(prompt_entries)} 个场景")
        
        result_images = []
        client = get_ark_client()
        
        for idx, entry in enumerate(prompt_entries[:3], start=1):
            try:
                prompt = entry.get('prompt', '')
                
                generated_items = call_app_mode_image_generation(
                    client=client,
                    prompt=prompt,
                    image_payloads=image_payloads,
                    image_size_ratio=ratio,
                    text_type='中文',
                    country='中国',
                    product_json=None,
                    image_type='fashion',
                    plan_item=entry,
                    all_plan_types=[],
                    max_images=1,
                    _logger=log,
                )
                
                if generated_items:
                    item = generated_items[0]
                    image_url = item.get('url', '') or item.get('image_url', '')
                    
                    result_images.append({
                        'url': image_url,
                        'type': entry.get('pose', {}).get('title', f'场景{idx}'),
                        'sceneType': entry.get('pose', {}).get('title', f'服饰穿搭图 {idx}'),
                        'width': 1024,
                        'height': 1024,
                        'prompt': prompt,
                    })
                    
            except Exception as e:
                log.error(f"生成第{idx}张图片失败: {e}")
        
        log.info(f"服饰穿戴生成完成: {len(result_images)} 张")
        return result_images
        
    except Exception as e:
        log.error(f"生成服饰穿戴失败: {e}", exc_info=True)
        return _generate_mock_fashion_results(config, _logger=log)


def _generate_mock_suite_results(config: Dict, _logger: logging.Logger | None = None) -> List[Dict]:
    log = _logger or logger
    log.warning("使用模拟结果")
    
    prompt_config = config.get('promptConfig', {})
    scene_types = prompt_config.get('sceneTypes', ['hero', 'usage', 'detail'])
    
    result_images = []
    for scene_type in scene_types:
        prompt = _build_suite_prompt(
            scene_type=scene_type,
            style_desc=_get_style_description(prompt_config.get('sceneStyle', 'modern')),
            scene_notes=prompt_config.get('sceneNotes', ''),
            config=config,
        )
        
        result_images.append({
            'url': f'https://example.com/suite_{scene_type}_{int(time.time())}.jpg',
            'type': scene_type,
            'sceneType': _get_scene_type_name(scene_type),
            'width': 1024,
            'height': 1024,
            'prompt': prompt,
        })
    
    return result_images


def _generate_mock_aplus_results(config: Dict, _logger: logging.Logger | None = None) -> List[Dict]:
    log = _logger or logger
    log.warning("使用模拟A+结果")
    
    prompt_config = config.get('promptConfig', {})
    scene_types = prompt_config.get('sceneTypes', ['hero', 'usage', 'detail'])
    
    result_images = []
    for scene_type in scene_types:
        result_images.append({
            'url': f'https://example.com/aplus_{scene_type}_{int(time.time())}.jpg',
            'type': scene_type,
            'sceneType': _get_scene_type_name(scene_type),
            'width': 1024,
            'height': 1024,
            'prompt': f"A+ content for {scene_type}",
        })
    
    return result_images


def _generate_mock_fashion_results(config: Dict, _logger: logging.Logger | None = None) -> List[Dict]:
    log = _logger or logger
    log.warning("使用模拟服饰结果")
    
    model_config = config.get('modelConfig', {})
    gender = model_config.get('gender', '女')
    
    prompt = f"Professional fashion photography, {gender} model, wearing the product, high-end fashion style, studio lighting"
    
    return [
        {
            'url': f'https://example.com/fashion_front_{int(time.time())}.jpg',
            'type': 'front',
            'sceneType': '正面展示',
            'width': 1024,
            'height': 1024,
            'prompt': prompt,
        },
        {
            'url': f'https://example.com/fashion_side_{int(time.time())}.jpg',
            'type': 'side',
            'sceneType': '侧面展示',
            'width': 1024,
            'height': 1024,
            'prompt': prompt,
        },
    ]


def _build_suite_prompt(
    scene_type: str,
    style_desc: str,
    scene_notes: str,
    config: Dict,
) -> str:
    platform = config.get('platform', '亚马逊')
    country = config.get('country', '中国')
    ratio = config.get('ratio', '1:1')
    selling_points = config.get('sellingPoints', '')
    
    scene_prompts = {
        'hero': f"Professional product photography, {style_desc}, hero shot, main product display, clean background, soft lighting, {platform} platform, {country} market, {ratio} ratio",
        'usage': f"Lifestyle product photography, {style_desc}, product in use, natural environment, realistic scene, {platform} platform, {country} market, {ratio} ratio",
        'detail': f"Product detail photography, {style_desc}, close-up shot, macro details, sharp focus, texture highlight, {platform} platform, {country} market, {ratio} ratio",
        'mood': f"Mood photography, {style_desc}, atmospheric scene, emotional appeal, artistic composition, {platform} platform, {country} market, {ratio} ratio",
        'brand': f"Brand story photography, {style_desc}, brand narrative, emotional connection, lifestyle context, {platform} platform, {country} market, {ratio} ratio",
        'effect': f"Before/after comparison, {style_desc}, product effectiveness, clear comparison, professional presentation, {platform} platform, {country} market, {ratio} ratio",
        'craft': f"Craftsmanship photography, {style_desc}, manufacturing process, quality details, professional lighting, {platform} platform, {country} market, {ratio} ratio",
        'series': f"Product series photography, {style_desc}, multiple products, cohesive presentation, professional layout, {platform} platform, {country} market, {ratio} ratio",
    }
    
    prompt = scene_prompts.get(scene_type, f"Professional product photography, {style_desc}, {platform} platform, {country} market, {ratio} ratio")
    
    if selling_points:
        prompt += f", {selling_points}"
    
    if scene_notes:
        prompt += f", {scene_notes}"
    
    return prompt


def _get_style_description(style: str) -> str:
    styles = {
        'modern': 'modern minimalist style, clean lines, soft lighting',
        'luxury': 'high-end luxury style, elegant composition, premium feel',
        'natural': 'natural fresh style, organic elements, soft colors',
        'tech': 'technology style, futuristic elements, modern lighting',
        'vintage': 'vintage classic style, retro elements, warm tones',
        'minimalist': 'minimalist style, simple composition, clean background',
        'lifestyle': 'lifestyle style, natural environment, casual feel',
        'business': 'professional business style, corporate feel, clean design',
        'cozy': 'cozy home style, warm atmosphere, comfortable setting',
        'fashion': 'fashion style, trendy composition, stylish lighting',
        'artistic': 'artistic creative style, unique composition, creative lighting',
        'pastoral': 'pastoral style, natural scenery, peaceful atmosphere',
        'industrial': 'industrial style, raw materials, urban feel',
        'nordic': 'Nordic style, simple elegant, natural light',
        'japanese': 'Japanese style, zen elements, minimalist design',
        'chinese': 'Chinese classical style, traditional elements, elegant composition',
        'bohemian': 'bohemian style, free-spirited, colorful elements',
        'romantic': 'romantic style, soft lighting, dreamy atmosphere',
        'youthful': 'youthful style, energetic composition, vibrant colors',
        'elegant': 'elegant style, refined composition, sophisticated feel',
    }
    
    return styles.get(style, 'professional style, high quality')


def _get_style_name(style: str) -> str:
    names = {
        'modern': '现代简约',
        'luxury': '高端奢华',
        'natural': '自然清新',
        'tech': '科技感',
        'vintage': '复古经典',
        'minimalist': '极简主义',
        'lifestyle': '生活化',
        'business': '商务专业',
        'cozy': '温馨居家',
        'fashion': '时尚潮流',
        'artistic': '艺术创意',
        'pastoral': '田园风格',
        'industrial': '工业风格',
        'nordic': '北欧风格',
        'japanese': '日式风格',
        'chinese': '中式古典',
        'bohemian': '波西米亚',
        'romantic': '浪漫唯美',
        'youthful': '青春活力',
        'elegant': '优雅精致',
    }
    
    return names.get(style, style)


def _get_scene_type_name(scene_type: str) -> str:
    scene_names = {
        'hero': '首屏主视觉',
        'usage': '使用场景图',
        'detail': '商品细节图',
        'mood': '场景氛围图',
        'brand': '品牌故事图',
        'effect': '效果对比图',
        'craft': '工艺制作图',
        'series': '系列展示图',
        'aftersales': '售后保障图',
        'selling': '核心卖点图',
        'multiangle': '多角度图',
        'size': '尺寸/容量/尺码图',
        'spec': '详细规格/参数表',
        'accessories': '配件/赠品图',
        'ingredients': '商品成分图',
        'tips': '使用建议图',
    }
    
    return scene_names.get(scene_type, scene_type)
