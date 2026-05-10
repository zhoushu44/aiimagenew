"""
Fallback 链标准化测试

验证生图配置的 fallback 链是否符合核心原则：
1. OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 只用于文本规划，不用于生图
2. IMAGE_API_KEY / IMAGE_BASE_URL / IMAGE_MODEL 作为通用生图配置的兜底
3. MODE1/2/3_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY，不应该 fallback 到 OPENAI_API_KEY 或 ARK_API_KEY
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generation.modes import get_mode1_api_key, get_mode2_api_key, get_mode3_api_key


def clear_env_and_set(vars_dict):
    """清除并设置环境变量"""
    env_vars_to_clear = list(vars_dict.keys())
    old_values = {}
    for var in env_vars_to_clear:
        old_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    # 设置新的环境变量
    for var, value in vars_dict.items():
        os.environ[var] = value
    
    # 清除本地配置缓存
    import config
    config.LOCAL_CONFIG.clear()
    
    return old_values


def restore_env(old_values):
    """恢复环境变量"""
    for var in old_values.keys():
        if var in os.environ:
            del os.environ[var]
        if old_values[var] is not None:
            os.environ[var] = old_values[var]


def test_mode1_fallback_chain():
    """测试 mode1 的 fallback 链：MODE1_IMAGE_API_KEY → IMAGE_API_KEY"""
    print("\n" + "=" * 60)
    print("测试 1: Mode1 Fallback 链验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: MODE1_IMAGE_API_KEY 存在时，应该直接使用
    print("\n场景 1: MODE1_IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'MODE1_IMAGE_API_KEY': 'mode1-key-123',
        'IMAGE_API_KEY': 'image-key-456',
        'ARK_API_KEY': 'ark-key-789',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode1_api_key()
    if api_key == 'mode1-key-123':
        print("  ✓ 正确使用 MODE1_IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'mode1-key-123'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 2: MODE1_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在时，应该 fallback 到 IMAGE_API_KEY
    print("\n场景 2: MODE1_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'IMAGE_API_KEY': 'image-key-456',
        'ARK_API_KEY': 'ark-key-789',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode1_api_key()
    if api_key == 'image-key-456':
        print("  ✓ 正确 fallback 到 IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'image-key-456'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 3: MODE1_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，不应该 fallback 到 ARK_API_KEY
    print("\n场景 3: MODE1_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，ARK_API_KEY 存在")
    old_values = clear_env_and_set({
        'ARK_API_KEY': 'ark-key-789',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode1_api_key()
    if api_key == '':
        print("  ✓ 正确返回空字符串，未 fallback 到 ARK_API_KEY")
    else:
        print(f"  ✗ 错误：期望空字符串，实际 '{api_key}'（不应 fallback 到 ARK_API_KEY）")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 4: MODE1_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，不应该 fallback 到 OPENAI_API_KEY
    print("\n场景 4: MODE1_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，OPENAI_API_KEY 存在")
    old_values = clear_env_and_set({
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode1_api_key()
    if api_key == '':
        print("  ✓ 正确返回空字符串，未 fallback 到 OPENAI_API_KEY")
    else:
        print(f"  ✗ 错误：期望空字符串，实际 '{api_key}'（不应 fallback 到 OPENAI_API_KEY）")
        all_passed = False
    
    restore_env(old_values)
    
    return all_passed


def test_mode2_fallback_chain():
    """测试 mode2 的 fallback 链：MODE2_IMAGE_API_KEY → IMAGE_API_KEY"""
    print("\n" + "=" * 60)
    print("测试 2: Mode2 Fallback 链验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: MODE2_IMAGE_API_KEY 存在时，应该直接使用
    print("\n场景 1: MODE2_IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'MODE2_IMAGE_API_KEY': 'mode2-key-123',
        'IMAGE_API_KEY': 'image-key-456',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode2_api_key()
    if api_key == 'mode2-key-123':
        print("  ✓ 正确使用 MODE2_IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'mode2-key-123'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 2: MODE2_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在时，应该 fallback 到 IMAGE_API_KEY
    print("\n场景 2: MODE2_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'IMAGE_API_KEY': 'image-key-456',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode2_api_key()
    if api_key == 'image-key-456':
        print("  ✓ 正确 fallback 到 IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'image-key-456'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 3: MODE2_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，不应该 fallback 到 OPENAI_API_KEY
    print("\n场景 3: MODE2_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，OPENAI_API_KEY 存在")
    old_values = clear_env_and_set({
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode2_api_key()
    if api_key == 'any-value':
        print("  ✓ 正确返回默认值 'any-value'，未 fallback 到 OPENAI_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'any-value'，实际 '{api_key}'（不应 fallback 到 OPENAI_API_KEY）")
        all_passed = False
    
    restore_env(old_values)
    
    return all_passed


def test_mode3_fallback_chain():
    """测试 mode3 的 fallback 链：MODE3_IMAGE_API_KEY → IMAGE_API_KEY"""
    print("\n" + "=" * 60)
    print("测试 3: Mode3 Fallback 链验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: MODE3_IMAGE_API_KEY 存在时，应该直接使用
    print("\n场景 1: MODE3_IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'MODE3_IMAGE_API_KEY': 'mode3-key-123',
        'IMAGE_API_KEY': 'image-key-456',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode3_api_key()
    if api_key == 'mode3-key-123':
        print("  ✓ 正确使用 MODE3_IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'mode3-key-123'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 2: MODE3_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在时，应该 fallback 到 IMAGE_API_KEY
    print("\n场景 2: MODE3_IMAGE_API_KEY 不存在，IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'IMAGE_API_KEY': 'image-key-456',
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode3_api_key()
    if api_key == 'image-key-456':
        print("  ✓ 正确 fallback 到 IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：期望 'image-key-456'，实际 '{api_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景 3: MODE3_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，不应该 fallback 到 OPENAI_API_KEY
    print("\n场景 3: MODE3_IMAGE_API_KEY 和 IMAGE_API_KEY 都不存在，OPENAI_API_KEY 存在")
    old_values = clear_env_and_set({
        'OPENAI_API_KEY': 'openai-key-abc'
    })
    
    api_key = get_mode3_api_key()
    if api_key == '':
        print("  ✓ 正确返回空字符串，未 fallback 到 OPENAI_API_KEY")
    else:
        print(f"  ✗ 错误：期望空字符串，实际 '{api_key}'（不应 fallback 到 OPENAI_API_KEY）")
        all_passed = False
    
    restore_env(old_values)
    
    return all_passed


def test_all_modes_consistency():
    """测试所有模式的一致性"""
    print("\n" + "=" * 60)
    print("测试 4: 所有模式一致性验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景：只有 IMAGE_API_KEY 存在时，所有模式都应该使用它
    print("\n场景：只有 IMAGE_API_KEY 存在")
    old_values = clear_env_and_set({
        'IMAGE_API_KEY': 'common-image-key-xyz'
    })
    
    mode1_key = get_mode1_api_key()
    mode2_key = get_mode2_api_key()
    mode3_key = get_mode3_api_key()
    
    if mode1_key == 'common-image-key-xyz' and mode2_key == 'common-image-key-xyz' and mode3_key == 'common-image-key-xyz':
        print("  ✓ 所有模式都正确 fallback 到 IMAGE_API_KEY")
    else:
        print(f"  ✗ 错误：mode1='{mode1_key}', mode2='{mode2_key}', mode3='{mode3_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    # 测试场景：每个模式都有自己的 API key
    print("\n场景：每个模式都有自己的 API key")
    old_values = clear_env_and_set({
        'MODE1_IMAGE_API_KEY': 'mode1-specific-key',
        'MODE2_IMAGE_API_KEY': 'mode2-specific-key',
        'MODE3_IMAGE_API_KEY': 'mode3-specific-key',
        'IMAGE_API_KEY': 'common-image-key-xyz'
    })
    
    mode1_key = get_mode1_api_key()
    mode2_key = get_mode2_api_key()
    mode3_key = get_mode3_api_key()
    
    if mode1_key == 'mode1-specific-key' and mode2_key == 'mode2-specific-key' and mode3_key == 'mode3-specific-key':
        print("  ✓ 所有模式都正确使用各自的 API key")
    else:
        print(f"  ✗ 错误：mode1='{mode1_key}', mode2='{mode2_key}', mode3='{mode3_key}'")
        all_passed = False
    
    restore_env(old_values)
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Fallback 链标准化验证测试")
    print("=" * 60)
    
    tests = [
        ("Mode1 Fallback 链", test_mode1_fallback_chain),
        ("Mode2 Fallback 链", test_mode2_fallback_chain),
        ("Mode3 Fallback 链", test_mode3_fallback_chain),
        ("所有模式一致性", test_all_modes_consistency),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n  ✗ 测试异常: {e}")
            import traceback
            traceback.print_exc()
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
        print("\n✓ 所有测试通过！Fallback 链已成功标准化")
        print("\n核心原则验证：")
        print("  1. ✓ OPENAI_API_KEY 不用于生图")
        print("  2. ✓ IMAGE_API_KEY 作为通用生图配置的兜底")
        print("  3. ✓ MODE1/2/3_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查 fallback 链配置")
        return 1


if __name__ == '__main__':
    sys.exit(main())
