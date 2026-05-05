import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests

from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    build_supabase_request_url,
    _build_supabase_service_headers,
)

logger = logging.getLogger(__name__)

BATCH_TABLE = 'batch_tasks'
TASK_TABLE = 'batch_task_items'
IMAGE_TABLE = 'batch_task_images'


def create_batch_record(
    user_id: str,
    gen_type: str,
    platform: Optional[str] = None,
    country: Optional[str] = None,
    text_type: Optional[str] = None,
    ratio: Optional[str] = None,
    selling_points: Optional[str] = None,
    prompt_config: Optional[Dict] = None,
    total_tasks: int = 0,
    points_cost: int = 0,
    _logger: logging.Logger | None = None
) -> Dict:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase配置缺失")
    
    normalized_user_id = str(user_id or '').strip()
    if not normalized_user_id:
        raise ValueError("用户ID无效")
    
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
    
    payload = {
        'batch_id': batch_id,
        'user_id': normalized_user_id,
        'gen_type': gen_type,
        'platform': platform,
        'country': country,
        'text_type': text_type,
        'ratio': ratio,
        'selling_points': selling_points,
        'prompt_config': json.dumps(prompt_config) if prompt_config else None,
        'status': 'pending',
        'total_tasks': total_tasks,
        'completed_tasks': 0,
        'failed_tasks': 0,
        'points_cost': points_cost,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    response = requests.post(
        build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
        headers=_build_supabase_service_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    
    log.info(f"创建批次记录成功: batch_id={batch_id}")
    return {'batch_id': batch_id, 'status': 'pending', 'total_tasks': total_tasks}


def create_task_record(
    batch_id: str,
    task_index: int,
    input_images: List[Dict],
    _logger: logging.Logger | None = None
) -> Dict:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase配置缺失")
    
    task_id = f"{batch_id}_task_{task_index}"
    
    payload = {
        'task_id': task_id,
        'batch_id': batch_id,
        'task_index': task_index,
        'status': 'pending',
        'progress': 0,
        'current_step': '等待处理',
        'input_images': json.dumps(input_images) if input_images else None,
        'result_images': None,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    response = requests.post(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    
    log.info(f"创建任务记录成功: task_id={task_id}")
    return {'task_id': task_id, 'status': 'pending'}


def update_task_progress(
    task_id: str,
    progress: int,
    current_step: str,
    status: Optional[str] = None,
    _logger: logging.Logger | None = None
) -> bool:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    
    patch_payload = {
        'progress': progress,
        'current_step': current_step,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    if status:
        patch_payload['status'] = status
        if status == 'completed':
            patch_payload['completed_at'] = datetime.now(timezone.utc).isoformat()
        elif status == 'processing':
            patch_payload['started_at'] = datetime.now(timezone.utc).isoformat()
    
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'task_id': f'eq.{task_id}'},
        json=patch_payload,
        timeout=20,
    )
    response.raise_for_status()
    
    log.info(f"更新任务进度: task_id={task_id}, progress={progress}%")
    return True


def update_task_result(
    task_id: str,
    result_images: List[Dict],
    status: str = 'completed',
    _logger: logging.Logger | None = None
) -> bool:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    
    get_task_response = requests.get(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'task_id': f'eq.{task_id}', 'select': 'batch_id'},
        timeout=20,
    )
    get_task_response.raise_for_status()
    task_rows = get_task_response.json()
    batch_id = task_rows[0].get('batch_id') if task_rows else None
    
    patch_payload = {
        'status': status,
        'progress': 100,
        'current_step': '完成生成',
        'result_images': json.dumps(result_images) if result_images else None,
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'task_id': f'eq.{task_id}'},
        json=patch_payload,
        timeout=20,
    )
    response.raise_for_status()
    
    if batch_id and status == 'completed':
        _increment_batch_completed_count(batch_id, _logger=log)
    
    log.info(f"更新任务结果: task_id={task_id}, status={status}")
    return True


def _increment_batch_completed_count(
    batch_id: str,
    _logger: logging.Logger | None = None
) -> bool:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    
    get_batch_response = requests.get(
        build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'batch_id': f'eq.{batch_id}', 'select': 'completed_tasks,total_tasks'},
        timeout=20,
    )
    get_batch_response.raise_for_status()
    batch_rows = get_batch_response.json()
    
    if not batch_rows:
        return False
    
    current_completed = batch_rows[0].get('completed_tasks', 0) or 0
    total_tasks = batch_rows[0].get('total_tasks', 0) or 0
    new_completed = current_completed + 1
    
    patch_payload = {
        'completed_tasks': new_completed,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    if new_completed >= total_tasks:
        patch_payload['status'] = 'completed'
        patch_payload['completed_at'] = datetime.now(timezone.utc).isoformat()
    
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'batch_id': f'eq.{batch_id}'},
        json=patch_payload,
        timeout=20,
    )
    response.raise_for_status()
    
    log.info(f"更新批次完成计数: batch_id={batch_id}, completed={new_completed}/{total_tasks}")
    return True


def update_batch_status(
    batch_id: str,
    status: str,
    completed_tasks: Optional[int] = None,
    failed_tasks: Optional[int] = None,
    _logger: logging.Logger | None = None
) -> bool:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    
    patch_payload = {
        'status': status,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    if completed_tasks is not None:
        patch_payload['completed_tasks'] = completed_tasks
    
    if failed_tasks is not None:
        patch_payload['failed_tasks'] = failed_tasks
    
    if status == 'completed':
        patch_payload['completed_at'] = datetime.now(timezone.utc).isoformat()
    elif status == 'cancelled':
        patch_payload['cancelled_at'] = datetime.now(timezone.utc).isoformat()
    
    response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={'batch_id': f'eq.{batch_id}'},
        json=patch_payload,
        timeout=20,
    )
    response.raise_for_status()
    
    log.info(f"更新批次状态: batch_id={batch_id}, status={status}")
    return True


def fetch_batch_progress(
    batch_id: str,
    user_id: str,
    _logger: logging.Logger | None = None
) -> Optional[Dict]:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    
    response = requests.get(
        build_supabase_request_url(f'/rest/v1/{BATCH_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': '*',
            'batch_id': f'eq.{batch_id}',
            'user_id': f'eq.{user_id}',
            'limit': '1',
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    
    if not isinstance(payload, list) or not payload:
        return None
    
    batch_row = payload[0]
    
    tasks_response = requests.get(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'select': 'task_id,task_index,status,progress,current_step,result_images',
            'batch_id': f'eq.{batch_id}',
            'order': 'task_index.asc',
        },
        timeout=20,
    )
    tasks_response.raise_for_status()
    tasks_payload = tasks_response.json()
    
    tasks = []
    for task_row in tasks_payload:
        task_data = {
            'taskId': task_row.get('task_index'),
            'status': task_row.get('status'),
            'progress': task_row.get('progress', 0),
            'currentStep': task_row.get('current_step', ''),
            'resultImages': json.loads(task_row.get('result_images', '[]')) if task_row.get('result_images') else [],
        }
        tasks.append(task_data)
    
    return {
        'batchId': batch_row.get('batch_id'),
        'status': batch_row.get('status'),
        'totalTasks': batch_row.get('total_tasks', 0),
        'completedTasks': batch_row.get('completed_tasks', 0),
        'failedTasks': batch_row.get('failed_tasks', 0),
        'points_cost': batch_row.get('points_cost', 0),
        'tasks': tasks,
    }


def cancel_batch(
    batch_id: str,
    user_id: str,
    reason: Optional[str] = None,
    refund_points: bool = True,
    _logger: logging.Logger | None = None
) -> Dict:
    log = _logger or logger
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase配置缺失")
    
    progress = fetch_batch_progress(batch_id, user_id, _logger)
    if not progress:
        raise ValueError("批次不存在或无权限访问")
    
    if progress['status'] in ['completed', 'cancelled']:
        raise ValueError(f"批次状态为{progress['status']}，无法取消")
    
    points_cost = progress.get('points_cost', 0) or 0
    
    update_batch_status(batch_id, 'cancelled', _logger=_logger)
    
    tasks_response = requests.patch(
        build_supabase_request_url(f'/rest/v1/{TASK_TABLE}'),
        headers=_build_supabase_service_headers(),
        params={
            'batch_id': f'eq.{batch_id}',
            'status': 'eq.pending',
        },
        json={
            'status': 'cancelled',
            'cancelled_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        },
        timeout=20,
    )
    tasks_response.raise_for_status()
    
    cancelled_count = len([t for t in progress['tasks'] if t['status'] == 'pending'])
    
    refunded_points = 0
    if refund_points and points_cost > 0:
        from app import add_user_points
        try:
            add_user_points(
                user_id,
                points_cost,
                'refund',
                f'批量任务取消返还-{batch_id}',
                {'batch_id': batch_id, 'reason': reason}
            )
            refunded_points = points_cost
            log.info(f"取消批次返还积分: batch_id={batch_id}, points={points_cost}")
        except Exception as e:
            log.error(f"返还积分失败: {e}")
    
    log.info(f"取消批次: batch_id={batch_id}, cancelled_tasks={cancelled_count}")
    
    return {
        'batchId': batch_id,
        'status': 'cancelled',
        'cancelledTasks': cancelled_count,
        'refundedPoints': refunded_points,
        'message': '批次任务已取消'
    }
