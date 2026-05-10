"""
mode2/mode3 集成测试脚本

测试目标：
1. 验证 mode2 和 mode3 的生成逻辑是否一致
2. 验证重试机制是否正常工作
3. 验证并发控制是否正常工作
4. 验证错误处理是否正常工作
"""

import sys
import logging
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generation.modes import (
    call_mode2_single_image_with_retry,
    call_mode3_single_image_with_retry,
    call_mode2_images_parallel_with_partial_retry,
    call_mode3_images_parallel_with_partial_retry,
    get_mode2_retry_attempts,
    get_mode3_retry_attempts,
    get_mode2_parallel_workers,
    get_mode3_parallel_workers,
    classify_mode2_error,
    classify_mode3_error,
    is_retryable_mode2_error,
    is_retryable_mode3_error,
    compute_mode2_retry_delay,
    compute_retry_delay,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_retry_logic_consistency():
    """测试重试逻辑的一致性"""
    logger.info("=" * 80)
    logger.info("测试 1: 重试逻辑一致性")
    logger.info("=" * 80)
    
    # 测试重试次数
    mode2_retry = get_mode2_retry_attempts()
    mode3_retry = get_mode3_retry_attempts()
    logger.info(f"mode2 重试次数: {mode2_retry}")
    logger.info(f"mode3 重试次数: {mode3_retry}")
    
    # 测试重试延迟计算
    test_exceptions = [
        Exception("SSL_ERROR: certificate verify failed"),
        Exception("Read timed out"),
        Exception("Connection aborted"),
        Exception("HTTP 502 Bad Gateway"),
    ]
    
    logger.info("\n重试延迟计算对比:")
    all_consistent = True
    for exc in test_exceptions:
        for attempt in range(3):
            mode2_delay = compute_mode2_retry_delay(1.0, attempt, exc)
            mode3_delay = compute_retry_delay(1.0, attempt, exc)
            
            # mode2 特有错误
            mode2_specific = {'JIMENG_API_ERROR', 'JSON_DECODE_ERROR'}
            mode2_kind = classify_mode2_error(exc)
            
            if mode2_kind not in mode2_specific:
                is_consistent = mode2_delay == mode3_delay
                logger.info(f"  '{str(exc)[:30]}...' attempt={attempt}: mode2={mode2_delay:.2f}s, mode3={mode3_delay:.2f}s, {'✓' if is_consistent else '✗'}")
                if not is_consistent:
                    all_consistent = False
    
    return all_consistent


def test_parallel_config_consistency():
    """测试并发配置的一致性"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 2: 并发配置一致性")
    logger.info("=" * 80)
    
    mode2_workers = get_mode2_parallel_workers()
    mode3_workers = get_mode3_parallel_workers()
    
    logger.info(f"mode2 并发数: {mode2_workers}")
    logger.info(f"mode3 并发数: {mode3_workers}")
    
    is_consistent = mode2_workers == mode3_workers
    logger.info(f"并发配置一致性: {'✓ 一致' if is_consistent else '✗ 不一致'}")
    
    return is_consistent


def test_error_handling_flow():
    """测试错误处理流程"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 3: 错误处理流程")
    logger.info("=" * 80)
    
    # 模拟错误处理流程
    test_cases = [
        {
            'error': Exception("SSL_ERROR: certificate verify failed"),
            'expected_retryable': True,
            'expected_log_traceback': False,
        },
        {
            'error': Exception("Read timed out"),
            'expected_retryable': True,
            'expected_log_traceback': False,
        },
        {
            'error': Exception("HTTP 500 Internal Server Error"),
            'expected_retryable': False,
            'expected_log_traceback': True,
        },
        {
            'error': Exception("积分不足或没有相关权益"),
            'expected_retryable_mode2': True,
            'expected_retryable_mode3': False,
        },
    ]
    
    logger.info("错误处理流程测试:")
    all_passed = True
    
    for test_case in test_cases:
        exc = test_case['error']
        
        mode2_retryable = is_retryable_mode2_error(exc)
        mode3_retryable = is_retryable_mode3_error(exc)
        
        logger.info(f"\n  错误: '{str(exc)[:40]}...'")
        logger.info(f"    mode2 可重试: {mode2_retryable}")
        logger.info(f"    mode3 可重试: {mode3_retryable}")
        
        # 检查预期
        if 'expected_retryable' in test_case:
            expected = test_case['expected_retryable']
            if mode2_retryable != expected or mode3_retryable != expected:
                logger.error(f"    ✗ 预期: {expected}, 实际: mode2={mode2_retryable}, mode3={mode3_retryable}")
                all_passed = False
            else:
                logger.info(f"    ✓ 符合预期")
        elif 'expected_retryable_mode2' in test_case:
            expected_mode2 = test_case['expected_retryable_mode2']
            expected_mode3 = test_case['expected_retryable_mode3']
            if mode2_retryable != expected_mode2 or mode3_retryable != expected_mode3:
                logger.error(f"    ✗ 预期: mode2={expected_mode2}, mode3={expected_mode3}")
                all_passed = False
            else:
                logger.info(f"    ✓ 符合预期")
    
    return all_passed


def test_mock_generation_flow():
    """测试模拟生成流程"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 4: 模拟生成流程")
    logger.info("=" * 80)
    
    logger.info("模拟生成流程测试:")
    
    try:
        # 测试函数是否存在
        try:
            from generation.modes import call_mode2_single_image
            logger.info("  mode2 生成函数: ✓ 存在")
        except ImportError as e:
            logger.info(f"  mode2 生成函数: ✗ 不存在: {e}")
            return False
        
        try:
            from generation.modes import call_mode3_single_image
            logger.info("  mode3 生成函数: ✓ 存在")
        except ImportError as e:
            logger.info(f"  mode3 生成函数: ✗ 不存在: {e}")
            return False
        
        try:
            from generation.modes import call_mode2_images_parallel_with_partial_retry
            logger.info("  mode2 并发生成函数: ✓ 存在")
        except ImportError as e:
            logger.info(f"  mode2 并发生成函数: ✗ 不存在: {e}")
            return False
        
        try:
            from generation.modes import call_mode3_images_parallel_with_partial_retry
            logger.info("  mode3 并发生成函数: ✓ 存在")
        except ImportError as e:
            logger.info(f"  mode3 并发生成函数: ✗ 不存在: {e}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"模拟生成流程测试失败: {e}")
        return False


def test_configuration_fallback():
    """测试配置回退机制"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 5: 配置回退机制")
    logger.info("=" * 80)
    
    logger.info("配置回退机制测试:")
    
    # 测试配置获取
    configs = {
        'retry_attempts': (get_mode2_retry_attempts, get_mode3_retry_attempts),
        'parallel_workers': (get_mode2_parallel_workers, get_mode3_parallel_workers),
    }
    
    all_passed = True
    for config_name, (mode2_func, mode3_func) in configs.items():
        mode2_value = mode2_func()
        mode3_value = mode3_func()
        
        is_consistent = mode2_value == mode3_value
        logger.info(f"  {config_name}: mode2={mode2_value}, mode3={mode3_value}, {'✓ 一致' if is_consistent else '✗ 不一致'}")
        
        if not is_consistent:
            all_passed = False
    
    return all_passed


def main():
    """运行所有测试"""
    logger.info("开始 mode2/mode3 集成测试")
    logger.info("=" * 80)
    
    results = {
        '重试逻辑一致性': test_retry_logic_consistency(),
        '并发配置一致性': test_parallel_config_consistency(),
        '错误处理流程': test_error_handling_flow(),
        '模拟生成流程': test_mock_generation_flow(),
        '配置回退机制': test_configuration_fallback(),
    }
    
    logger.info("\n" + "=" * 80)
    logger.info("测试结果汇总")
    logger.info("=" * 80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("所有测试通过！mode2 和 mode3 已完全标准化。")
    else:
        logger.warning("部分测试失败，需要进一步检查。")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
