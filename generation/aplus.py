import concurrent.futures
import logging
import time

from image_utils import decode_generated_image, save_generated_image

logger = logging.getLogger(__name__)


def generate_aplus_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None, _logger: logging.Logger | None = None):
    from generation.modes import (
        call_app_mode_image_generation,
        _get_parallel_config,
    )
    from config import get_app_mode

    log = _logger or logger
    plan_items = list(plan.get('items') or [])
    if not plan_items:
        return []

    app_mode = get_app_mode()
    workers, partial_retry_attempts, retry_delay_seconds = _get_parallel_config(app_mode, len(plan_items))

    results = []
    failures = []

    def run_one(plan_item: dict):
        generated_items = call_app_mode_image_generation(
            None,
            plan_item['prompt'],
            image_payloads,
            image_size_ratio,
            text_type,
            country,
            product_json,
            plan_item['type'],
            max_images=1,
            _logger=log,
        )
        generated_item = generated_items[0]
        image_bytes, mime_type = decode_generated_image(generated_item)
        download_name, relative_path, image_url = save_generated_image(task_id, plan_item['sort'], plan_item['type'], image_bytes, mime_type)
        return {
            'sort': plan_item['sort'],
            'kind': 'generated',
            'type': plan_item['type'],
            'type_tag': plan_item['type_tag'],
            'title': plan_item['title'],
            'keywords': plan_item['keywords'],
            'prompt': plan_item['prompt'],
            'module': plan_item.get('module', ''),
            'story_role': plan_item.get('story_role', ''),
            'decision_task': plan_item.get('decision_task', ''),
            'info_density': plan_item.get('info_density', ''),
            'layout_style': plan_item.get('layout_style', ''),
            'font_style': plan_item.get('font_style', ''),
            'color_scheme': plan_item.get('color_scheme', ''),
            'decor_elements': plan_item.get('decor_elements', []),
            'image_url': image_url,
            'image_path': relative_path,
            'download_name': download_name,
        }

    pending_items = list(plan_items)
    for attempt_index in range(partial_retry_attempts + 1):
        if not pending_items:
            break
        batch_workers = min(len(pending_items), workers)
        batch_results = []
        batch_failures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_workers) as executor:
            future_map = {executor.submit(run_one, item): item for item in pending_items}
            for future in concurrent.futures.as_completed(future_map):
                plan_item = future_map[future]
                try:
                    batch_results.append(future.result())
                except Exception as exc:
                    batch_failures.append((plan_item, f'{plan_item.get("type") or plan_item.get("title") or plan_item.get("sort")}：{exc}'))
        results.extend(batch_results)
        pending_items = [item for item, _msg in batch_failures]
        failures = [_msg for _item, _msg in batch_failures]
        if pending_items and attempt_index < partial_retry_attempts:
            log.warning(
                'A+ parallel partial generation missing %s/%s, retrying in %.2fs (%s/%s): %s',
                len(pending_items), len(plan_items), retry_delay_seconds * (attempt_index + 1),
                attempt_index + 1, partial_retry_attempts,
                '; '.join(failures[:3]),
            )
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if failures:
        raise ValueError(f'A+ 部分图片生成失败：{"；".join(failures[:3])}')
    return sorted(results, key=lambda item: item.get('sort') or 0)
