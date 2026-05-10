"""
Mode1 标准化验证测试

验证 mode1 与 mode2/mode3 的一致性
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generation.modes import (
    # mode1 函数
    classify_mode1_error,
    compute_mode1_retry_delay,
    should_log_mode1_traceback,
    get_mode1_timeout_seconds,
    get_mode1_request_timeout,
    is_retryable_mode1_error,
    
    # mode2 函数
    classify_mode2_error,
    compute_mode2_retry_delay,
    should_log_mode2_traceback,
    get_mode2_timeout_seconds,
    get_mode2_request_timeout,
    is_retryable_mode2_error,
    
    # mode3 函数
    classify_mode3_error,
    compute_retry_delay,
    should_log_mode3_traceback,
    get_mode3_timeout_seconds,
    get_mode3_request_timeout,
    is_retryable_mode3_error,
)


def test_function_existence():
    """测试所有必需函数是否存在"""
    print("=" * 60)
    print("测试 1: 函数存在性验证")
    print("=" * 60)
    
    mode1_functions = [
        ('classify_mode1_error', classify_mode1_error),
        ('compute_mode1_retry_delay', compute_mode1_retry_delay),
        ('should_log_mode1_traceback', should_log_mode1_traceback),
        ('get_mode1_timeout_seconds', get_mode1_timeout_seconds),
        ('get_mode1_request_timeout', get_mode1_request_timeout),
        ('is_retryable_mode1_error', is_retryable_mode1_error),
    ]
    
    mode2_functions = [
        ('classify_mode2_error', classify_mode2_error),
        ('compute_mode2_retry_delay', compute_mode2_retry_delay),
        ('should_log_mode2_traceback', should_log_mode2_traceback),
        ('get_mode2_timeout_seconds', get_mode2_timeout_seconds),
        ('get_mode2_request_timeout', get_mode2_request_timeout),
        ('is_retryable_mode2_error', is_retryable_mode2_error),
    ]
    
    mode3_functions = [
        ('classify_mode3_error', classify_mode3_error),
        ('compute_retry_delay', compute_retry_delay),
        ('should_log_mode3_traceback', should_log_mode3_traceback),
        ('get_mode3_timeout_seconds', get_mode3_timeout_seconds),
        ('get_mode3_request_timeout', get_mode3_request_timeout),
        ('is_retryable_mode3_error', is_retryable_mode3_error),
    ]
    
    all_passed = True
    
    for mode_name, functions in [('mode1', mode1_functions), ('mode2', mode2_functions), ('mode3', mode3_functions)]:
        print(f"\n{mode_name} 函数检查:")
        for func_name, func in functions:
            if func is not None and callable(func):
                print(f"  ✓ {func_name}")
            else:
                print(f"  ✗ {func_name} - 缺失或不可调用")
                all_passed = False
    
    return all_passed


def test_error_classification_consistency():
    """测试错误分类一致性"""
    print("\n" + "=" * 60)
    print("测试 2: 错误分类一致性验证")
    print("=" * 60)
    
    test_errors = [
        (RuntimeError('Read timed out'), 'TIMEOUT_ERROR'),
        (RuntimeError('SSL: UNEXPECTED_EOF'), 'SSL_EOF_ERROR'),
        (RuntimeError('ssl error'), 'SSL_ERROR'),
        (RuntimeError('Connection aborted'), 'CONNECTION_ABORTED'),
        (RuntimeError('Connection reset'), 'CONNECTION_RESET'),
        (RuntimeError('Max retries exceeded'), 'NETWORK_RETRY_EXHAUSTED'),
    ]
    
    all_passed = True
    
    for exc, expected_kind in test_errors:
        mode1_kind = classify_mode1_error(exc)
        mode3_kind = classify_mode3_error(exc)
        
        if mode1_kind == mode3_kind == expected_kind:
            print(f"  ✓ {expected_kind}: mode1={mode1_kind}, mode3={mode3_kind}")
        else:
            print(f"  ✗ {expected_kind}: mode1={mode1_kind}, mode3={mode3_kind}")
            all_passed = False
    
    return all_passed


def test_retry_delay_consistency():
    """测试重试延迟计算一致性"""
    print("\n" + "=" * 60)
    print("测试 3: 重试延迟计算一致性验证")
    print("=" * 60)
    
    test_cases = [
        (RuntimeError('Read timed out'), 0.5, 0),
        (RuntimeError('SSL error'), 0.5, 1),
        (RuntimeError('Connection aborted'), 0.5, 2),
    ]
    
    all_passed = True
    
    for exc, base_delay, attempt in test_cases:
        mode1_delay = compute_mode1_retry_delay(base_delay, attempt, exc)
        mode3_delay = compute_retry_delay(base_delay, attempt, exc)
        
        if abs(mode1_delay - mode3_delay) < 0.01:
            print(f"  ✓ {type(exc).__name__}: mode1={mode1_delay:.2f}s, mode3={mode3_delay:.2f}s")
        else:
            print(f"  ✗ {type(exc).__name__}: mode1={mode1_delay:.2f}s, mode3={mode3_delay:.2f}s")
            all_passed = False
    
    return all_passed


def test_timeout_configuration():
    """测试超时配置一致性"""
    print("\n" + "=" * 60)
    print("测试 4: 超时配置一致性验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试超时秒数
    mode1_timeout = get_mode1_timeout_seconds()
    mode2_timeout = get_mode2_timeout_seconds()
    mode3_timeout = get_mode3_timeout_seconds()
    
    print(f"  mode1 timeout: {mode1_timeout}s")
    print(f"  mode2 timeout: {mode2_timeout}s")
    print(f"  mode3 timeout: {mode3_timeout}s")
    
    if mode1_timeout >= 30 and mode2_timeout >= 30 and mode3_timeout >= 30:
        print("  ✓ 所有超时配置 >= 30秒")
    else:
        print("  ✗ 存在超时配置 < 30秒")
        all_passed = False
    
    # 测试请求超时元组
    mode1_req_timeout = get_mode1_request_timeout()
    mode2_req_timeout = get_mode2_request_timeout()
    mode3_req_timeout = get_mode3_request_timeout()
    
    print(f"\n  mode1 request_timeout: {mode1_req_timeout}")
    print(f"  mode2 request_timeout: {mode2_req_timeout}")
    print(f"  mode3 request_timeout: {mode3_req_timeout}")
    
    for mode_name, req_timeout in [('mode1', mode1_req_timeout), ('mode2', mode2_req_timeout), ('mode3', mode3_req_timeout)]:
        if isinstance(req_timeout, tuple) and len(req_timeout) == 2:
            connect_timeout, total_timeout = req_timeout
            if 3 <= connect_timeout <= total_timeout:
                print(f"  ✓ {mode_name} 请求超时配置有效: connect={connect_timeout}s, total={total_timeout}s")
            else:
                print(f"  ✗ {mode_name} 请求超时配置无效: connect={connect_timeout}s, total={total_timeout}s")
                all_passed = False
        else:
            print(f"  ✗ {mode_name} 请求超时格式错误: {req_timeout}")
            all_passed = False
    
    return all_passed


def test_log_traceback_consistency():
    """测试日志追踪一致性"""
    print("\n" + "=" * 60)
    print("测试 5: 日志追踪一致性验证")
    print("=" * 60)
    
    test_errors = [
        RuntimeError('Read timed out'),
        RuntimeError('SSL error'),
        RuntimeError('Connection aborted'),
        RuntimeError('Unknown error'),
    ]
    
    all_passed = True
    
    for exc in test_errors:
        mode1_should_log = should_log_mode1_traceback(exc)
        mode3_should_log = should_log_mode3_traceback(exc)
        
        if mode1_should_log == mode3_should_log:
            print(f"  ✓ {str(exc)[:30]}: mode1={mode1_should_log}, mode3={mode3_should_log}")
        else:
            print(f"  ✗ {str(exc)[:30]}: mode1={mode1_should_log}, mode3={mode3_should_log}")
            all_passed = False
    
    return all_passed


def test_retryable_error_consistency():
    """测试可重试错误判断一致性"""
    print("\n" + "=" * 60)
    print("测试 6: 可重试错误判断一致性验证")
    print("=" * 60)
    
    test_errors = [
        RuntimeError('Read timed out'),
        RuntimeError('SSL error'),
        RuntimeError('Connection aborted'),
        RuntimeError('Unknown error'),
    ]
    
    all_passed = True
    
    for exc in test_errors:
        mode1_retryable = is_retryable_mode1_error(exc)
        mode3_retryable = is_retryable_mode3_error(exc)
        
        if mode1_retryable == mode3_retryable:
            print(f"  ✓ {str(exc)[:30]}: mode1={mode1_retryable}, mode3={mode3_retryable}")
        else:
            print(f"  ✗ {str(exc)[:30]}: mode1={mode1_retryable}, mode3={mode3_retryable}")
            all_passed = False
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Mode1 标准化验证测试")
    print("=" * 60)
    
    tests = [
        ("函数存在性", test_function_existence),
        ("错误分类一致性", test_error_classification_consistency),
        ("重试延迟一致性", test_retry_delay_consistency),
        ("超时配置一致性", test_timeout_configuration),
        ("日志追踪一致性", test_log_traceback_consistency),
        ("可重试错误一致性", test_retryable_error_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n  ✗ 测试异常: {e}")
            results.append((test_name, False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    for test_name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计: {passed_tests}/{total_tests} 测试通过")
    
    if passed_tests == total_tests:
        print("\n✓ 所有测试通过！mode1 已成功标准化")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查标准化结果")
        return 1


if __name__ == '__main__':
    sys.exit(main())
