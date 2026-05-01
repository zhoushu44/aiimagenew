import concurrent.futures
import logging
import time

from config import get_app_mode, get_supabase_setting_int, get_optional_int_env
from image_utils import build_enriched_image_prompt, build_generated_suite_image_item

logger = logging.getLogger(__name__)


def generate_mode1_suite_images_parallel(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None, all_plan_types=None, _logger: logging.Logger | None = None):
    from generation.modes import (
        call_mode1_single_image_with_retry,
        get_mode1_parallel_workers,
        get_mode1_partial_retry_attempts,
        get_mode1_retry_delay_seconds,
    )
    log = _logger or logger
    plan_items = list(plan.get('items') or [])
    if not plan_items:
        return []
    workers = min(len(plan_items), get_mode1_parallel_workers())
    partial_retry_attempts = get_mode1_partial_retry_attempts()
    retry_delay_seconds = get_mode1_retry_delay_seconds()
    results = []
    failures = []

    def run_one(plan_item: dict):
        generated_item = call_mode1_single_image_with_retry(
            build_enriched_image_prompt(
                plan_item['prompt'], image_size_ratio, text_type, country,
                product_json, plan_item['type'], plan_item, all_plan_types or [],
            ),
            image_payloads, image_size_ratio, text_type, country,
            product_json, plan_item['type'], plan_item, all_plan_types,
            _logger=log,
        )
        return build_generated_suite_image_item(task_id, plan_item, generated_item)

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
                'Mode1 suite partial generation missing %s/%s images, retrying in %.2fs (%s/%s): %s',
                len(pending_items), len(plan_items), retry_delay_seconds * (attempt_index + 1),
                attempt_index + 1, partial_retry_attempts,
                '; '.join(failures[:3]),
            )
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if failures:
        raise ValueError(f'mode1 套图部分生成失败：{"；".join(failures[:3])}')
    return sorted(results, key=lambda item: item.get('sort') or 0)


def generate_mode2_suite_images_parallel(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None, all_plan_types=None, _logger: logging.Logger | None = None):
    from generation.modes import (
        call_mode2_single_image_with_retry,
        get_mode2_parallel_workers,
        get_mode2_partial_retry_attempts,
        get_mode2_retry_delay_seconds,
    )
    log = _logger or logger
    plan_items = list(plan.get('items') or [])
    if not plan_items:
        return []
    workers = min(len(plan_items), get_mode2_parallel_workers())
    partial_retry_attempts = get_mode2_partial_retry_attempts()
    retry_delay_seconds = get_mode2_retry_delay_seconds()
    results = []
    failures = []

    def run_one(plan_item: dict):
        generated_item = call_mode2_single_image_with_retry(
            build_enriched_image_prompt(
                plan_item['prompt'], image_size_ratio, text_type, country,
                product_json, plan_item['type'], plan_item, all_plan_types or [],
            ),
            image_payloads, image_size_ratio, text_type, country,
            product_json, plan_item['type'], plan_item, all_plan_types,
            _logger=log,
        )
        return build_generated_suite_image_item(task_id, plan_item, generated_item)

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
                'Mode2 suite partial generation missing %s/%s images, retrying in %.2fs (%s/%s): %s',
                len(pending_items), len(plan_items), retry_delay_seconds * (attempt_index + 1),
                attempt_index + 1, partial_retry_attempts,
                '; '.join(failures[:3]),
            )
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if failures:
        raise ValueError(f'mode2 套图部分生成失败：{"；".join(failures[:3])}')
    return sorted(results, key=lambda item: item.get('sort') or 0)


def generate_mode3_suite_images_parallel(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None, all_plan_types=None, _logger: logging.Logger | None = None):
    from generation.modes import (
        call_mode3_single_image_with_retry,
        get_mode3_parallel_workers,
        get_mode3_partial_retry_attempts,
        get_mode3_retry_delay_seconds,
    )
    log = _logger or logger
    plan_items = list(plan.get('items') or [])
    if not plan_items:
        return []
    workers = min(len(plan_items), get_mode3_parallel_workers())
    partial_retry_attempts = get_mode3_partial_retry_attempts()
    retry_delay_seconds = get_mode3_retry_delay_seconds()
    results = []
    failures = []

    def run_one(plan_item: dict):
        generated_item = call_mode3_single_image_with_retry(
            build_enriched_image_prompt(
                plan_item['prompt'], image_size_ratio, text_type, country,
                product_json, plan_item['type'], plan_item, all_plan_types or [],
            ),
            image_payloads, image_size_ratio, text_type, country,
            product_json, plan_item['type'], plan_item, all_plan_types,
            _logger=log,
        )
        return build_generated_suite_image_item(task_id, plan_item, generated_item)

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
                'Mode3 suite partial generation missing %s/%s images, retrying in %.2fs (%s/%s): %s',
                len(pending_items), len(plan_items), retry_delay_seconds * (attempt_index + 1),
                attempt_index + 1, partial_retry_attempts,
                '; '.join(failures[:3]),
            )
            time.sleep(retry_delay_seconds * (attempt_index + 1))

    if failures:
        raise ValueError(f'mode3 套图部分生成失败：{"；".join(failures[:3])}')
    return sorted(results, key=lambda item: item.get('sort') or 0)


def generate_suite_images(plan: dict, image_payloads, task_id: str, image_size_ratio: str, text_type: str, country: str, product_json=None, _logger: logging.Logger | None = None):
    from generation.modes import (
        get_ark_client,
        call_app_mode_image_generation,
    )
    log = _logger or logger
    images = []
    all_plan_types = [str(item.get('type', '')).strip() for item in plan.get('items', []) if str(item.get('type', '')).strip()]
    plan_items = list(plan.get('items') or [])
    app_mode = get_app_mode()
    if app_mode == 'mode1':
        return generate_mode1_suite_images_parallel(plan, image_payloads, task_id, image_size_ratio, text_type, country, product_json, all_plan_types, _logger=log)
    if app_mode == 'mode2':
        return generate_mode2_suite_images_parallel(plan, image_payloads, task_id, image_size_ratio, text_type, country, product_json, all_plan_types, _logger=log)
    if app_mode == 'mode3':
        return generate_mode3_suite_images_parallel(plan, image_payloads, task_id, image_size_ratio, text_type, country, product_json, all_plan_types, _logger=log)
    batch_limit = max(get_supabase_setting_int('ARK_SEQUENTIAL_MAX_IMAGES', get_optional_int_env('ARK_SEQUENTIAL_MAX_IMAGES', 1)), 1)
    client = get_ark_client()
    index = 0

    while index < len(plan_items):
        item = plan_items[index]
        remaining_items = plan_items[index:]
        generated_items = call_app_mode_image_generation(
            client, item['prompt'], image_payloads, image_size_ratio, text_type, country,
            product_json, item['type'], item, all_plan_types,
            max_images=min(len(remaining_items), batch_limit), _logger=log,
        )

        consumed_count = 0
        for generated_item, plan_item in zip(generated_items, remaining_items):
            images.append(build_generated_suite_image_item(task_id, plan_item, generated_item))
            consumed_count += 1

        if consumed_count < 1:
            raise ValueError('图像生成接口未返回可用图片内容')

        index += consumed_count

    return images
