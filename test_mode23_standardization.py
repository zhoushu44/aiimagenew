"""
mode2/mode3 标准化重构测试脚本

测试目标：
1. 验证 mode2 和 mode3 的配置获取是否一致
2. 验证错误处理逻辑是否一致
3. 验证重试机制是否一致
4. 验证并发控制是否一致
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generation.modes import (
    # 配置获取函数
    get_mode2_retry_attempts,
    get_mode2_retry_delay_seconds,
    get_mode2_parallel_workers,
    get_mode2_partial_retry_attempts,
    get_mode3_retry_attempts,
    get_mode3_retry_delay_seconds,
    get_mode3_parallel_workers,
    get_mode3_partial_retry_attempts,
    
    # 错误处理函数
    classify_mode2_error,
    classify_mode3_error,
    is_retryable_mode2_error,
    is_retryable_mode3_error,
    should_log_mode2_traceback,
    should_log_mode3_traceback,
    compute_mode2_retry_delay,
    
    # API 获取函数
    get_mode2_api_key,
    get_mode2_base_url,
    get_mode3_api_key,
    get_mode3_base_url,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_config_consistency():
    """测试配置获取的一致性"""
    logger.info("=" * 80)
    logger.info("测试 1: 配置获取一致性")
    logger.info("=" * 80)
    
    # 测试配置获取
    mode2_configs = {
        'retry_attempts': get_mode2_retry_attempts(),
        'retry_delay_seconds': get_mode2_retry_delay_seconds(),
        'parallel_workers': get_mode2_parallel_workers(),
        'partial_retry_attempts': get_mode2_partial_retry_attempts(),
    }
    
    mode3_configs = {
        'retry_attempts': get_mode3_retry_attempts(),
        'retry_delay_seconds': get_mode3_retry_delay_seconds(),
        'parallel_workers': get_mode3_parallel_workers(),
        'partial_retry_attempts': get_mode3_partial_retry_attempts(),
    }
    
    logger.info("mode2 配置:")
    for key, value in mode2_configs.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("\nmode3 配置:")
    for key, value in mode3_configs.items():
        logger.info(f"  {key}: {value}")
    
    # 检查一致性
    logger.info("\n配置一致性检查:")
    all_consistent = True
    for key in mode2_configs.keys():
        mode2_value = mode2_configs[key]
        mode3_value = mode3_configs[key]
        is_consistent = mode2_value == mode3_value
        logger.info(f"  {key}: {'✓ 一致' if is_consistent else '✗ 不一致'} (mode2={mode2_value}, mode3={mode3_value})")
        if not is_consistent:
            all_consistent = False
    
    return all_consistent


def test_error_classification():
    """测试错误分类的一致性"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 2: 错误分类一致性")
    logger.info("=" * 80)
    
    # 创建测试异常
    test_exceptions = [
        Exception("SSL_ERROR: certificate verify failed"),
        Exception("Read timed out"),
        Exception("Connection aborted"),
        Exception("Connection reset"),
        Exception("HTTP 500 Internal Server Error"),
        Exception("HTTP 502 Bad Gateway"),
        Exception("HTTP 503 Service Unavailable"),
        Exception("HTTP 504 Gateway Timeout"),
        Exception("积分不足或没有相关权益"),  # mode2 特有
        Exception("Unexpected end of JSON input"),  # mode2 特有
    ]
    
    logger.info("错误分类对比:")
    all_consistent = True
    for exc in test_exceptions:
        mode2_kind = classify_mode2_error(exc)
        mode3_kind = classify_mode3_error(exc)
        
        # mode2 特有的错误类型
        mode2_specific = {'JIMENG_API_ERROR', 'JSON_DECODE_ERROR'}
        
        # 如果不是 mode2 特有错误，应该一致
        if mode2_kind not in mode2_specific:
            is_consistent = mode2_kind == mode3_kind
            logger.info(f"  '{str(exc)[:50]}...':")
            logger.info(f"    mode2: {mode2_kind}")
            logger.info(f"    mode3: {mode3_kind}")
            logger.info(f"    {'✓ 一致' if is_consistent else '✗ 不一致'}")
            if not is_consistent:
                all_consistent = False
        else:
            logger.info(f"  '{str(exc)[:50]}...':")
            logger.info(f"    mode2: {mode2_kind} (mode2 特有)")
            logger.info(f"    mode3: {mode3_kind}")
            logger.info(f"    ✓ mode2 特有错误，无需一致")
    
    return all_consistent


def test_retryable_error_detection():
    """测试可重试错误检测的一致性"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 3: 可重试错误检测一致性")
    logger.info("=" * 80)
    
    # 创建测试异常
    test_exceptions = [
        Exception("SSL_ERROR: certificate verify failed"),
        Exception("Read timed out"),
        Exception("Connection aborted"),
        Exception("Connection reset"),
        Exception("HTTP 500 Internal Server Error"),
        Exception("HTTP 502 Bad Gateway"),
        Exception("HTTP 503 Service Unavailable"),
        Exception("HTTP 504 Gateway Timeout"),
        Exception("积分不足或没有相关权益"),  # mode2 特有
        Exception("Unexpected end of JSON input"),  # mode2 特有
        Exception("ValueError: Invalid parameter"),  # 不可重试
    ]
    
    logger.info("可重试错误检测对比:")
    all_consistent = True
    for exc in test_exceptions:
        mode2_retryable = is_retryable_mode2_error(exc)
        mode3_retryable = is_retryable_mode3_error(exc)
        
        # mode2 特有的可重试错误
        mode2_specific_messages = ['积分不足', 'JSON', 'json']
        is_mode2_specific = any(msg in str(exc) for msg in mode2_specific_messages)
        
        logger.info(f"  '{str(exc)[:50]}...':")
        logger.info(f"    mode2: {'可重试' if mode2_retryable else '不可重试'}")
        logger.info(f"    mode3: {'可重试' if mode3_retryable else '不可重试'}")
        
        # 如果不是 mode2 特有错误，应该一致
        if not is_mode2_specific:
            is_consistent = mode2_retryable == mode3_retryable
            logger.info(f"    {'✓ 一致' if is_consistent else '✗ 不一致'}")
            if not is_consistent:
                all_consistent = False
        else:
            logger.info(f"    ✓ mode2 特有错误，允许差异")
    
    return all_consistent


def test_api_configuration():
    """测试 API 配置"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 4: API 配置")
    logger.info("=" * 80)
    
    try:
        mode2_api_key = get_mode2_api_key()
        mode2_base_url = get_mode2_base_url()
        mode3_api_key = get_mode3_api_key()
        mode3_base_url = get_mode3_base_url()
        
        logger.info("mode2 API 配置:")
        logger.info(f"  API Key: {'已配置' if mode2_api_key else '未配置'}")
        logger.info(f"  Base URL: {mode2_base_url}")
        
        logger.info("\nmode3 API 配置:")
        logger.info(f"  API Key: {'已配置' if mode3_api_key else '未配置'}")
        logger.info(f"  Base URL: {mode3_base_url}")
        
        # 检查 base URL 是否不同（这是唯一应该不同的地方）
        is_different = mode2_base_url != mode3_base_url
        logger.info(f"\nBase URL 差异检查: {'✓ 不同（正确）' if is_different else '✗ 相同（错误）'}")
        
        return True
    except Exception as e:
        logger.error(f"API 配置测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    logger.info("开始 mode2/mode3 标准化测试")
    logger.info("=" * 80)
    
    results = {
        '配置获取一致性': test_config_consistency(),
        '错误分类一致性': test_error_classification(),
        '可重试错误检测一致性': test_retryable_error_detection(),
        'API 配置': test_api_configuration(),
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
        logger.info("所有测试通过！mode2 和 mode3 已标准化。")
    else:
        logger.warning("部分测试失败，需要进一步重构。")
    logger.info("=" * 80)
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
