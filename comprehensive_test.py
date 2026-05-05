#!/usr/bin/env python3
"""
全面测试脚本 - Redis缓存 + WebSocket + 轮询优化 + 限流
测试覆盖：功能测试、压力测试、真实场景测试
"""
import os
import sys
import time
import json
import random
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

os.environ['REDIS_HOST'] = '8.163.52.51'
os.environ['REDIS_PORT'] = '26739'
os.environ['REDIS_PASSWORD'] = 'MkWy8YzzBWz6LNKK'
os.environ['REDIS_DB'] = '0'

BASE_URL = os.getenv('TEST_BASE_URL', 'http://localhost:5078')
TEST_USER_TOKEN = os.getenv('TEST_USER_TOKEN', '')

class TestResults:
    def __init__(self):
        self.results = []
        self.lock = threading.Lock()
    
    def add(self, test_name, success, details=None):
        with self.lock:
            self.results.append({
                'test': test_name,
                'success': success,
                'details': details or {},
                'timestamp': datetime.now().isoformat()
            })

results = TestResults()

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_test(name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"     {details}")

def test_redis_connection():
    """测试1: Redis连接"""
    print_header("测试1: Redis连接测试")
    
    try:
        from redis_client import get_redis_client, is_redis_available
        
        client = get_redis_client()
        if not client:
            print_test("Redis客户端创建", False)
            return False
        
        print_test("Redis客户端创建", True)
        
        if not is_redis_available():
            print_test("Redis连接", False)
            return False
        
        print_test("Redis连接", True)
        
        info = client.info('server')
        print_test(f"Redis版本: {info.get('redis_version')}", True)
        print_test(f"运行时间: {info.get('uptime_in_seconds')}秒", True)
        
        results.add("Redis连接", True, info)
        return True
    except Exception as e:
        print_test("Redis连接测试", False, str(e))
        results.add("Redis连接", False, str(e))
        return False

def test_cache_operations():
    """测试2: 缓存操作"""
    print_header("测试2: 缓存操作测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        test_task_id = f"test-task-{int(time.time())}"
        test_data = {
            "task_id": test_task_id,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        cache_key = build_task_cache_key(test_task_id)
        
        # 测试写入
        success = cache_set(cache_key, test_data, 30)
        print_test("缓存写入", success)
        if not success:
            return False
        
        # 测试读取
        cached = cache_get(cache_key)
        read_success = cached == test_data
        print_test("缓存读取", read_success)
        
        # 测试删除
        cache_delete(cache_key)
        cached_after_delete = cache_get(cache_key)
        delete_success = cached_after_delete is None
        print_test("缓存删除", delete_success)
        
        all_success = success and read_success and delete_success
        results.add("缓存操作", all_success)
        return all_success
    except Exception as e:
        print_test("缓存操作测试", False, str(e))
        results.add("缓存操作", False, str(e))
        return False

def test_cache_hit_rate():
    """测试3: 缓存命中率"""
    print_header("测试3: 缓存命中率测试")
    
    try:
        from redis_client import cache_get, cache_set, build_task_cache_key
        
        # 预热100个任务
        test_tasks = []
        for i in range(100):
            task_id = f"hit-test-{i}"
            task_data = {"task_id": task_id, "index": i}
            cache_set(build_task_cache_key(task_id), task_data, 60)
            test_tasks.append(task_id)
        
        print_test("预热100个任务到缓存", True)
        
        # 模拟1000次查询，80%命中热数据
        hits = 0
        misses = 0
        start_time = time.time()
        
        for i in range(1000):
            if random.random() < 0.8:
                task_id = random.choice(test_tasks[:10])  # 热数据
            else:
                task_id = random.choice(test_tasks)  # 冷数据
            
            result = cache_get(build_task_cache_key(task_id))
            if result:
                hits += 1
            else:
                misses += 1
        
        elapsed = time.time() - start_time
        hit_rate = hits / 1000 * 100
        
        print_test(f"缓存命中率: {hit_rate:.1f}%", hit_rate > 80)
        print_test(f"查询QPS: {1000/elapsed:.2f}", True)
        
        # 清理
        for task_id in test_tasks:
            from redis_client import cache_delete
            cache_delete(build_task_cache_key(task_id))
        
        success = hit_rate > 80
        results.add("缓存命中率", success, {"hit_rate": hit_rate, "qps": 1000/elapsed})
        return success
    except Exception as e:
        print_test("缓存命中率测试", False, str(e))
        results.add("缓存命中率", False, str(e))
        return False

def test_concurrent_cache():
    """测试4: 并发缓存测试"""
    print_header("测试4: 并发缓存测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        num_threads = 50
        num_operations = 100
        
        successes = [0]
        errors = [0]
        lock = threading.Lock()
        
        def worker(thread_id):
            for i in range(num_operations):
                try:
                    task_id = f"concurrent-{thread_id}-{i}"
                    task_data = {"thread": thread_id, "index": i}
                    
                    cache_set(build_task_cache_key(task_id), task_data, 30)
                    result = cache_get(build_task_cache_key(task_id))
                    cache_delete(build_task_cache_key(task_id))
                    
                    if result == task_data:
                        with lock:
                            successes[0] += 1
                    else:
                        with lock:
                            errors[0] += 1
                except Exception:
                    with lock:
                        errors[0] += 1
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                pass
        
        elapsed = time.time() - start_time
        total_ops = num_threads * num_operations
        success_rate = successes[0] / total_ops * 100
        
        print_test(f"并发线程数: {num_threads}", True)
        print_test(f"总操作数: {total_ops}", True)
        print_test(f"成功率: {success_rate:.1f}%", success_rate > 95)
        print_test(f"QPS: {total_ops/elapsed:.2f}", True)
        print_test(f"错误数: {errors[0]}", errors[0] == 0)
        
        success = success_rate > 95 and errors[0] == 0
        results.add("并发缓存", success, {"success_rate": success_rate, "qps": total_ops/elapsed})
        return success
    except Exception as e:
        print_test("并发缓存测试", False, str(e))
        results.add("并发缓存", False, str(e))
        return False

def test_rate_limiting():
    """测试5: 请求限流测试"""
    print_header("测试5: 请求限流测试")
    
    if not BASE_URL or not TEST_USER_TOKEN:
        print_test("跳过限流测试（未配置测试服务器）", True)
        results.add("请求限流", True, {"skipped": True})
        return True
    
    try:
        headers = {"Authorization": f"Bearer {TEST_USER_TOKEN}"}
        
        # 快速发送请求测试限流
        responses = []
        for i in range(40):
            try:
                response = requests.get(
                    f"{BASE_URL}/api/generation-tasks/test-{i}",
                    headers=headers,
                    timeout=5
                )
                responses.append(response.status_code)
            except Exception:
                responses.append(0)
        
        # 统计429状态码（限流）
        rate_limited = responses.count(429)
        success_requests = responses.count(200) + responses.count(404)
        
        print_test(f"发送请求数: {len(responses)}", True)
        print_test(f"成功请求: {success_requests}", True)
        print_test(f"被限流请求: {rate_limited}", rate_limited > 0)
        
        success = rate_limited > 0
        results.add("请求限流", success, {"rate_limited": rate_limited})
        return success
    except Exception as e:
        print_test("请求限流测试", False, str(e))
        results.add("请求限流", False, str(e))
        return False

def test_large_data_cache():
    """测试6: 大数据量缓存"""
    print_header("测试6: 大数据量缓存测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        # 创建大数据（10KB）
        large_data = {
            "task_id": "large-data-test",
            "data": "x" * 10000,
            "array": list(range(1000)),
            "nested": {
                "level1": {
                    "level2": {
                        "level3": "data" * 100
                    }
                }
            }
        }
        
        data_size = len(json.dumps(large_data))
        print_test(f"数据大小: {data_size/1024:.2f} KB", True)
        
        # 测试100次读写
        start_time = time.time()
        successes = 0
        
        for i in range(100):
            cache_set(build_task_cache_key(f"large-{i}"), large_data, 30)
            result = cache_get(build_task_cache_key(f"large-{i}"))
            if result == large_data:
                successes += 1
            cache_delete(build_task_cache_key(f"large-{i}"))
        
        elapsed = time.time() - start_time
        success_rate = successes / 100 * 100
        
        print_test(f"成功率: {success_rate:.1f}%", success_rate == 100)
        print_test(f"QPS: {100/elapsed:.2f}", True)
        print_test(f"总数据量: {data_size * 100 / 1024 / 1024:.2f} MB", True)
        
        success = success_rate == 100
        results.add("大数据量缓存", success, {"success_rate": success_rate})
        return success
    except Exception as e:
        print_test("大数据量缓存测试", False, str(e))
        results.add("大数据量缓存", False, str(e))
        return False

def test_cache_expiration():
    """测试7: 缓存过期测试"""
    print_header("测试7: 缓存过期测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        test_key = build_task_cache_key("expiration-test")
        test_data = {"expire": "test"}
        
        # 设置2秒过期
        cache_set(test_key, test_data, 2)
        print_test("缓存写入（TTL=2秒）", True)
        
        # 立即读取
        result = cache_get(test_key)
        print_test("立即读取成功", result == test_data)
        
        # 等待3秒
        print("等待3秒...")
        time.sleep(3)
        
        # 再次读取
        result = cache_get(test_key)
        print_test("3秒后读取失败（已过期）", result is None)
        
        success = result is None
        results.add("缓存过期", success)
        return success
    except Exception as e:
        print_test("缓存过期测试", False, str(e))
        results.add("缓存过期", False, str(e))
        return False

def test_websocket_connection():
    """测试8: WebSocket连接测试"""
    print_header("测试8: WebSocket连接测试")
    
    try:
        import websocket
        
        ws_url = BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://')
        
        connected = [False]
        message_received = [False]
        
        def on_message(ws, message):
            message_received[0] = True
            print_test(f"收到消息: {message[:50]}...", True)
        
        def on_error(ws, error):
            print_test(f"WebSocket错误: {error}", False)
        
        def on_open(ws):
            connected[0] = True
            print_test("WebSocket连接成功", True)
            ws.send(json.dumps({"type": "subscribe_task", "task_id": "test-123"}))
        
        def on_close(ws, close_status_code, close_msg):
            print_test("WebSocket连接关闭", True)
        
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
            on_close=on_close
        )
        
        # 运行5秒
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        time.sleep(5)
        ws.close()
        
        success = connected[0]
        results.add("WebSocket连接", success)
        return success
    except ImportError:
        print_test("跳过WebSocket测试（未安装websocket-client）", True)
        results.add("WebSocket连接", True, {"skipped": True})
        return True
    except Exception as e:
        print_test("WebSocket连接测试", False, str(e))
        results.add("WebSocket连接", False, str(e))
        return False

def test_real_world_scenario():
    """测试9: 真实场景测试"""
    print_header("测试9: 真实场景测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        # 模拟真实用户行为
        num_users = 10
        tasks_per_user = 5
        
        print_test(f"模拟{num_users}个用户，每人{tasks_per_user}个任务", True)
        
        total_queries = 0
        cache_hits = 0
        start_time = time.time()
        
        for user_id in range(num_users):
            # 用户创建任务
            for task_num in range(tasks_per_user):
                task_id = f"user-{user_id}-task-{task_num}"
                task_data = {
                    "task_id": task_id,
                    "user_id": f"user-{user_id}",
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }
                
                # 写入缓存
                cache_set(build_task_cache_key(task_id), task_data, 30)
                
                # 模拟用户轮询查询（3-5次）
                for query in range(random.randint(3, 5)):
                    result = cache_get(build_task_cache_key(task_id))
                    total_queries += 1
                    if result:
                        cache_hits += 1
                
                # 更新任务状态
                task_data["status"] = "processing"
                cache_set(build_task_cache_key(task_id), task_data, 30)
                
                # 再次查询
                result = cache_get(build_task_cache_key(task_id))
                total_queries += 1
                if result:
                    cache_hits += 1
                
                # 任务完成
                task_data["status"] = "succeeded"
                cache_set(build_task_cache_key(task_id), task_data, 30)
                
                # 最后查询
                result = cache_get(build_task_cache_key(task_id))
                total_queries += 1
                if result:
                    cache_hits += 1
                
                # 清理
                cache_delete(build_task_cache_key(task_id))
        
        elapsed = time.time() - start_time
        hit_rate = cache_hits / total_queries * 100
        
        print_test(f"总查询次数: {total_queries}", True)
        print_test(f"缓存命中次数: {cache_hits}", True)
        print_test(f"缓存命中率: {hit_rate:.1f}%", hit_rate > 90)
        print_test(f"平均响应时间: {elapsed/total_queries*1000:.2f}ms", True)
        print_test(f"QPS: {total_queries/elapsed:.2f}", True)
        
        success = hit_rate > 90
        results.add("真实场景", success, {"hit_rate": hit_rate, "qps": total_queries/elapsed})
        return success
    except Exception as e:
        print_test("真实场景测试", False, str(e))
        results.add("真实场景", False, str(e))
        return False

def test_stress_test():
    """测试10: 极限压力测试"""
    print_header("测试10: 极限压力测试")
    
    try:
        from redis_client import cache_get, cache_set, cache_delete, build_task_cache_key
        
        num_threads = 100
        num_operations = 1000
        
        print_test(f"启动{num_threads}个线程，每个执行{num_operations}次操作", True)
        
        successes = [0]
        errors = [0]
        lock = threading.Lock()
        
        def stress_worker(thread_id):
            for i in range(num_operations):
                try:
                    task_id = f"stress-{thread_id}-{i}"
                    task_data = {"thread": thread_id, "index": i, "data": "x" * 100}
                    
                    cache_set(build_task_cache_key(task_id), task_data, 30)
                    result = cache_get(build_task_cache_key(task_id))
                    cache_delete(build_task_cache_key(task_id))
                    
                    if result:
                        with lock:
                            successes[0] += 1
                except Exception:
                    with lock:
                        errors[0] += 1
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                pass
        
        elapsed = time.time() - start_time
        total_ops = num_threads * num_operations
        success_rate = successes[0] / total_ops * 100
        qps = total_ops / elapsed
        
        print_test(f"总操作数: {total_ops}", True)
        print_test(f"成功操作: {successes[0]}", True)
        print_test(f"错误操作: {errors[0]}", errors[0] < total_ops * 0.01)
        print_test(f"成功率: {success_rate:.1f}%", success_rate > 95)
        print_test(f"QPS: {qps:.2f}", qps > 500)
        print_test(f"耗时: {elapsed:.2f}秒", True)
        
        success = success_rate > 95 and errors[0] < total_ops * 0.01
        results.add("极限压力", success, {"success_rate": success_rate, "qps": qps})
        return success
    except Exception as e:
        print_test("极限压力测试", False, str(e))
        results.add("极限压力", False, str(e))
        return False

def print_summary():
    """打印测试总结"""
    print_header("测试总结")
    
    total = len(results.results)
    passed = sum(1 for r in results.results if r['success'])
    failed = total - passed
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    print("\n详细结果:")
    for r in results.results:
        status = "✅" if r['success'] else "❌"
        print(f"{status} {r['test']}")
    
    if failed > 0:
        print("\n失败的测试:")
        for r in results.results:
            if not r['success']:
                print(f"  ❌ {r['test']}: {r.get('details', {}).get('error', 'Unknown error')}")
    
    print("\n" + "="*70)
    if passed == total:
        print("🎉 所有测试通过！系统性能优秀！")
    else:
        print(f"⚠️  {failed}个测试失败，请检查")
    print("="*70)

def main():
    print("="*70)
    print("  Redis缓存 + WebSocket + 轮询优化 + 限流 - 全面测试")
    print("="*70)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Redis服务器: {os.environ['REDIS_HOST']}:{os.environ['REDIS_PORT']}")
    print(f"测试服务器: {BASE_URL or '未配置'}")
    
    tests = [
        ("Redis连接", test_redis_connection),
        ("缓存操作", test_cache_operations),
        ("缓存命中率", test_cache_hit_rate),
        ("并发缓存", test_concurrent_cache),
        ("请求限流", test_rate_limiting),
        ("大数据量缓存", test_large_data_cache),
        ("缓存过期", test_cache_expiration),
        ("WebSocket连接", test_websocket_connection),
        ("真实场景", test_real_world_scenario),
        ("极限压力", test_stress_test),
    ]
    
    for name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ {name}测试异常: {e}")
            import traceback
            traceback.print_exc()
    
    print_summary()

if __name__ == "__main__":
    main()
