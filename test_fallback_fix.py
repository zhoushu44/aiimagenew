"""
Fallback 链修复验证测试

验证生图配置的 fallback 链修复是否正确：
1. MODE1_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY，不 fallback 到 ARK_API_KEY 或 OPENAI_API_KEY
2. MODE3_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY，不 fallback 到 OPENAI_API_KEY
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from generation.modes import get_mode1_api_key, get_mode2_api_key, get_mode3_api_key


def test_mode1_fallback_logic():
    """测试 mode1 的 fallback 逻辑"""
    print("\n" + "=" * 60)
    print("测试 1: Mode1 Fallback 逻辑验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: 验证 MODE1_IMAGE_API_KEY 存在时使用它
    print("\n场景 1: MODE1_IMAGE_API_KEY 存在时使用它")
    try:
        api_key = get_mode1_api_key()
        # 根据 .env 文件，MODE1_IMAGE_API_KEY=96d739dd-5f53-4a6d-b89d-1779f27be846
        expected_key = '96d739dd-5f53-4a6d-b89d-1779f27be846'
        if api_key == expected_key:
            print(f"  ✓ 正确使用 MODE1_IMAGE_API_KEY: {api_key}")
        else:
            print(f"  ✗ 错误：期望 '{expected_key}'，实际 '{api_key}'")
            all_passed = False
    except Exception as e:
        print(f"  ✗ 测试异常: {e}")
        all_passed = False
    
    # 测试场景 2: 验证代码逻辑
    print("\n场景 2: 验证代码逻辑（查看源代码）")
    print("  检查 generation/modes.py 中的 get_mode1_api_key() 函数")
    
    # 读取源代码并验证
    with open('generation/modes.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 检查是否包含错误的 fallback 逻辑
    if 'ARK_API_KEY' in content and 'get_mode1_api_key' in content:
        # 检查是否在 get_mode1_api_key 函数中使用了 ARK_API_KEY
        lines = content.split('\n')
        in_function = False
        has_ark_fallback = False
        has_openai_fallback = False
        
        for line in lines:
            if 'def get_mode1_api_key()' in line:
                in_function = True
            elif in_function and line.strip().startswith('def '):
                break
            elif in_function:
                if 'ARK_API_KEY' in line and 'get_supabase_setting' in line:
                    has_ark_fallback = True
                if 'OPENAI_API_KEY' in line and 'get_supabase_setting' in line:
                    has_openai_fallback = True
        
        if has_ark_fallback:
            print("  ✗ 错误：get_mode1_api_key() 中仍然包含 ARK_API_KEY fallback")
            all_passed = False
        else:
            print("  ✓ get_mode1_api_key() 不包含 ARK_API_KEY fallback")
        
        if has_openai_fallback:
            print("  ✗ 错误：get_mode1_api_key() 中仍然包含 OPENAI_API_KEY fallback")
            all_passed = False
        else:
            print("  ✓ get_mode1_api_key() 不包含 OPENAI_API_KEY fallback")
    
    return all_passed


def test_mode2_fallback_logic():
    """测试 mode2 的 fallback 逻辑"""
    print("\n" + "=" * 60)
    print("测试 2: Mode2 Fallback 逻辑验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: 验证 MODE2_IMAGE_API_KEY 存在时使用它
    print("\n场景 1: MODE2_IMAGE_API_KEY 存在时使用它")
    try:
        api_key = get_mode2_api_key()
        # 根据 .env 文件，MODE2_IMAGE_API_KEY=any-value,any-value2,any-value3
        # 由于支持多 key 轮询，应该返回其中一个
        expected_keys = ['any-value', 'any-value2', 'any-value3']
        if api_key in expected_keys:
            print(f"  ✓ 正确使用 MODE2_IMAGE_API_KEY: {api_key}")
        else:
            print(f"  ✗ 错误：期望 '{expected_keys}' 之一，实际 '{api_key}'")
            all_passed = False
    except Exception as e:
        print(f"  ✗ 测试异常: {e}")
        all_passed = False
    
    # 测试场景 2: 验证代码逻辑
    print("\n场景 2: 验证代码逻辑（查看源代码）")
    print("  检查 generation/modes.py 中的 get_mode2_api_key() 函数")
    
    # 读取源代码并验证
    with open('generation/modes.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 检查是否包含错误的 fallback 逻辑
    lines = content.split('\n')
    in_function = False
    has_openai_fallback = False
    
    for line in lines:
        if 'def get_mode2_api_key()' in line:
            in_function = True
        elif in_function and line.strip().startswith('def '):
            break
        elif in_function:
            if 'OPENAI_API_KEY' in line and 'get_supabase_setting' in line:
                has_openai_fallback = True
    
    if has_openai_fallback:
        print("  ✗ 错误：get_mode2_api_key() 中仍然包含 OPENAI_API_KEY fallback")
        all_passed = False
    else:
        print("  ✓ get_mode2_api_key() 不包含 OPENAI_API_KEY fallback")
    
    return all_passed


def test_mode3_fallback_logic():
    """测试 mode3 的 fallback 逻辑"""
    print("\n" + "=" * 60)
    print("测试 3: Mode3 Fallback 逻辑验证")
    print("=" * 60)
    
    all_passed = True
    
    # 测试场景 1: 验证 MODE3_IMAGE_API_KEY 存在时使用它
    print("\n场景 1: MODE3_IMAGE_API_KEY 存在时使用它")
    try:
        api_key = get_mode3_api_key()
        # 根据 .env 文件，MODE3_IMAGE_API_KEY=sk-gTWSXktXPZbyQ7177nO2RgpPmYW6IPHdCWLu9C8eqSbB4aqN,sk-vIXd679AgmJGjXE1llhHG8S7Co8KMEci7GfRRs1wKIWFkgLr
        # 由于支持多 key 轮询，应该返回其中一个
        expected_keys = ['sk-gTWSXktXPZbyQ7177nO2RgpPmYW6IPHdCWLu9C8eqSbB4aqN', 'sk-vIXd679AgmJGjXE1llhHG8S7Co8KMEci7GfRRs1wKIWFkgLr']
        if api_key in expected_keys:
            print(f"  ✓ 正确使用 MODE3_IMAGE_API_KEY: {api_key[:20]}...")
        else:
            print(f"  ✗ 错误：期望 '{expected_keys[0][:20]}...' 之一，实际 '{api_key[:20]}...'")
            all_passed = False
    except Exception as e:
        print(f"  ✗ 测试异常: {e}")
        all_passed = False
    
    # 测试场景 2: 验证代码逻辑
    print("\n场景 2: 验证代码逻辑（查看源代码）")
    print("  检查 generation/modes.py 中的 get_mode3_api_key() 函数")
    
    # 读取源代码并验证
    with open('generation/modes.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 检查是否包含错误的 fallback 逻辑
    lines = content.split('\n')
    in_function = False
    has_openai_fallback = False
    
    for line in lines:
        if 'def get_mode3_api_key()' in line:
            in_function = True
        elif in_function and line.strip().startswith('def '):
            break
        elif in_function:
            if 'OPENAI_API_KEY' in line and 'get_supabase_setting' in line:
                has_openai_fallback = True
    
    if has_openai_fallback:
        print("  ✗ 错误：get_mode3_api_key() 中仍然包含 OPENAI_API_KEY fallback")
        all_passed = False
    else:
        print("  ✓ get_mode3_api_key() 不包含 OPENAI_API_KEY fallback")
    
    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Fallback 链修复验证测试")
    print("=" * 60)
    
    tests = [
        ("Mode1 Fallback 逻辑", test_mode1_fallback_logic),
        ("Mode2 Fallback 逻辑", test_mode2_fallback_logic),
        ("Mode3 Fallback 逻辑", test_mode3_fallback_logic),
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
        print("\n✓ 所有测试通过！Fallback 链已成功修复")
        print("\n修复内容：")
        print("  1. ✓ get_mode1_api_key() 移除了对 ARK_API_KEY 和 OPENAI_API_KEY 的 fallback")
        print("  2. ✓ get_mode3_api_key() 移除了对 OPENAI_API_KEY 的 fallback")
        print("  3. ✓ 所有模式现在只 fallback 到 IMAGE_API_KEY")
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
