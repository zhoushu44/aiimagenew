import json
import logging
import threading
import time
import uuid
import gc
from datetime import datetime, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_task_queue = []
_task_threads = {}
_task_status = {}
_task_start_times = {}
_lock = threading.Lock()

MAX_CONCURRENT_TASKS = 3
TASK_TIMEOUT_SECONDS = 300


def add_task_to_queue(
    batch_id: str,
    task_id: str,
    config: Dict,
    input_images: List[Dict],
    _logger: logging.Logger | None = None
) -> bool:
    log = _logger or logger
    
    with _lock:
        task_data = {
            'batch_id': batch_id,
            'task_id': task_id,
            'config': config,
            'input_images': input_images,
            'status': 'pending',
            'created_at': datetime.now(timezone.utc).isoformat(),
        }
        
        _task_queue.append(task_data)
        _task_status[task_id] = 'pending'
        
        log.info(f"任务已加入队列: task_id={task_id}, queue_length={len(_task_queue)}")
    
    return True


def get_active_task_count() -> int:
    with _lock:
        count = 0
        for task_id, thread in _task_threads.items():
            if thread.is_alive() and _task_status.get(task_id) == 'processing':
                count += 1
        return count


def cleanup_completed_threads():
    with _lock:
        completed_tasks = []
        for task_id, thread in _task_threads.items():
            if not thread.is_alive():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            del _task_threads[task_id]
            if task_id in _task_start_times:
                del _task_start_times[task_id]
        
        if completed_tasks:
            logger.info(f"清理已完成线程: {len(completed_tasks)} 个")


def check_task_timeouts():
    with _lock:
        current_time = time.time()
        timed_out = []
        
        for task_id, start_time in _task_start_times.items():
            if current_time - start_time > TASK_TIMEOUT_SECONDS:
                if _task_status.get(task_id) == 'processing':
                    timed_out.append(task_id)
        
        for task_id in timed_out:
            logger.warning(f"任务超时: task_id={task_id}")
            _task_status[task_id] = 'timeout'
            
            try:
                from batch_models import update_task_progress
                update_task_progress(task_id, 0, '任务超时', 'failed', _logger=logger)
            except:
                pass


def start_task_processor(
    _logger: logging.Logger | None = None
):
    log = _logger or logger
    
    cleanup_completed_threads()
    
    check_task_timeouts()
    
    with _lock:
        if len(_task_queue) == 0:
            return
        
        active_count = 0
        for tid, thread in _task_threads.items():
            if thread.is_alive() and _task_status.get(tid) == 'processing':
                active_count += 1
        
        if active_count >= MAX_CONCURRENT_TASKS:
            log.info(f"已达到最大并发数 {MAX_CONCURRENT_TASKS}，等待任务完成")
            return
        
        task_data = _task_queue.pop(0)
        task_id = task_data['task_id']
        
        if task_id in _task_threads and _task_threads[task_id].is_alive():
            log.warning(f"任务已在处理中: task_id={task_id}")
            return
        
        if _task_status.get(task_id) == 'cancelled':
            log.info(f"任务已取消，跳过: task_id={task_id}")
            return
        
        thread = threading.Thread(
            target=_process_task_wrapper,
            args=(task_data, _logger),
            daemon=True
        )
        
        _task_threads[task_id] = thread
        _task_status[task_id] = 'processing'
        _task_start_times[task_id] = time.time()
        
        thread.start()
        
        log.info(f"任务处理线程已启动: task_id={task_id}")


def _process_task_wrapper(
    task_data: Dict,
    _logger: logging.Logger | None = None
):
    log = _logger or logger
    task_id = task_data['task_id']
    
    try:
        _process_task(task_data, _logger)
    except Exception as e:
        log.error(f"任务处理异常: task_id={task_id}, error={e}", exc_info=True)
        
        with _lock:
            _task_status[task_id] = 'failed'
        
        try:
            from batch_models import update_task_progress
            update_task_progress(task_id, 0, f'处理异常: {str(e)[:100]}', 'failed', _logger=log)
        except:
            pass
    finally:
        try:
            if 'input_images' in task_data:
                del task_data['input_images']
            del task_data['config']
            gc.collect()
        except:
            pass


def _process_task(
    task_data: Dict,
    _logger: logging.Logger | None = None
):
    log = _logger or logger
    
    batch_id = task_data['batch_id']
    task_id = task_data['task_id']
    config = task_data['config']
    input_images = task_data['input_images']
    
    log.info(f"开始处理任务: task_id={task_id}, batch_id={batch_id}")
    
    try:
        from batch_models import (
            update_task_progress,
            update_task_result,
            update_batch_status,
        )
        
        if _task_status.get(task_id) == 'cancelled':
            log.info(f"任务已取消: task_id={task_id}")
            update_task_progress(task_id, 0, '已取消', 'cancelled', _logger=log)
            return
        
        update_task_progress(task_id, 10, '准备图片数据', 'processing', _logger=log)
        
        image_payloads = _prepare_image_payloads_from_task(input_images, _logger=log)
        
        if _task_status.get(task_id) == 'cancelled':
            log.info(f"任务已取消: task_id={task_id}")
            update_task_progress(task_id, 0, '已取消', 'cancelled', _logger=log)
            return
        
        update_task_progress(task_id, 20, '分析图片中', _logger=log)
        
        update_task_progress(task_id, 40, '生成提示词', _logger=log)
        
        if _task_status.get(task_id) == 'cancelled':
            log.info(f"任务已取消: task_id={task_id}")
            update_task_progress(task_id, 0, '已取消', 'cancelled', _logger=log)
            return
        
        update_task_progress(task_id, 50, 'AI处理中', _logger=log)
        
        from batch_generation import generate_batch_images
        result_images = generate_batch_images(
            gen_type=config.get('genType', 'suite'),
            config=config,
            input_images=image_payloads,
            task_id=task_id,
            _logger=log,
        )
        
        if _task_status.get(task_id) == 'cancelled':
            log.info(f"任务已取消: task_id={task_id}")
            update_task_progress(task_id, 0, '已取消', 'cancelled', _logger=log)
            return
        
        update_task_progress(task_id, 90, '保存结果', _logger=log)
        
        update_task_result(task_id, result_images, 'completed', _logger=log)
        
        with _lock:
            _task_status[task_id] = 'completed'
        
        log.info(f"任务处理完成: task_id={task_id}, 生成图片数: {len(result_images)}")
        
    except Exception as e:
        log.error(f"任务处理失败: task_id={task_id}, error={e}", exc_info=True)
        
        with _lock:
            _task_status[task_id] = 'failed'
        
        try:
            from batch_models import update_task_progress
            update_task_progress(task_id, 0, f'处理失败: {str(e)[:100]}', 'failed', _logger=log)
        except:
            pass


def _prepare_image_payloads_from_task(input_images: List[Dict], _logger: logging.Logger | None = None) -> List[Dict]:
    log = _logger or logger
    
    if not input_images:
        return []
    
    import base64
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
            elif 'path' in img:
                try:
                    with open(img['path'], 'rb') as f:
                        image_bytes = f.read()
                    mime_type = img.get('mime_type', 'image/jpeg')
                    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"
                    payload['bytes'] = image_bytes
                    payload['data_url'] = data_url
                    payload['mime_type'] = mime_type
                    payload['filename'] = img.get('name', 'image.png')
                except Exception as e:
                    log.error(f"读取图片文件失败: {img['path']}, error={e}")
                    continue
            
            if payload:
                image_payloads.append(payload)
    
    log.info(f"准备了 {len(image_payloads)} 个图片payload")
    return image_payloads


def get_task_status(task_id: str) -> Optional[str]:
    with _lock:
        return _task_status.get(task_id)


def get_queue_status() -> Dict:
    with _lock:
        return {
            'queue_length': len(_task_queue),
            'active_tasks': get_active_task_count(),
            'max_concurrent': MAX_CONCURRENT_TASKS,
            'total_processed': len(_task_status),
        }


def cancel_task(task_id: str, _logger: logging.Logger | None = None) -> bool:
    log = _logger or logger
    
    with _lock:
        if task_id not in _task_status:
            log.warning(f"任务不存在: task_id={task_id}")
            return False
        
        current_status = _task_status[task_id]
        
        if current_status in ['completed', 'failed', 'cancelled']:
            log.warning(f"任务状态为{current_status}，无法取消: task_id={task_id}")
            return False
        
        _task_status[task_id] = 'cancelled'
        
        for i, task in enumerate(_task_queue):
            if task['task_id'] == task_id:
                _task_queue.pop(i)
                log.info(f"任务已从队列中移除: task_id={task_id}")
                break
        
        log.info(f"任务已取消: task_id={task_id}")
        return True


def cancel_batch(batch_id: str, _logger: logging.Logger | None = None) -> int:
    log = _logger or logger
    
    cancelled_count = 0
    
    with _lock:
        tasks_to_remove = []
        for i, task in enumerate(_task_queue):
            if task['batch_id'] == batch_id:
                tasks_to_remove.append(i)
                _task_status[task['task_id']] = 'cancelled'
                cancelled_count += 1
        
        for i in reversed(tasks_to_remove):
            _task_queue.pop(i)
    
    log.info(f"批次已取消: batch_id={batch_id}, 取消任务数: {cancelled_count}")
    return cancelled_count


def start_background_processor(
    interval: int = 5,
    _logger: logging.Logger | None = None
):
    log = _logger or logger
    
    def _background_loop():
        while True:
            try:
                if len(_task_queue) > 0:
                    start_task_processor(_logger=log)
            except Exception as e:
                log.error(f"后台处理器错误: {e}", exc_info=True)
            
            time.sleep(interval)
    
    thread = threading.Thread(target=_background_loop, daemon=True)
    thread.start()
    
    log.info(f"后台任务处理器已启动，检查间隔: {interval}秒，最大并发: {MAX_CONCURRENT_TASKS}")
    return thread


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    start_background_processor()
    
    while True:
        time.sleep(1)
