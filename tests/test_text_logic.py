import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from generation.planning import (
    should_main_image_have_text,
    get_product_text_rule,
    build_main_image_text_prompt,
    extract_selling_points,
    distribute_text_content,
    get_text_position_by_index,
    get_unified_text_style,
    build_differentiated_text_prompt,
)

def test_should_main_image_have_text():
    print("="*60)
    print("测试: should_main_image_have_text")
    print("="*60)
    
    test_cases = [
        {
            'name': '测试场景1: 洗发水 + 淘宝天猫 + 中文',
            'product_category': '洗发水',
            'platform': '淘宝天猫1688',
            'text_type': '中文',
            'expected_need_text': True,
            'expected_priority': 'high'
        },
        {
            'name': '测试场景2: 洗发水 + 亚马逊 + 中文',
            'product_category': '洗发水',
            'platform': '亚马逊',
            'text_type': '中文',
            'expected_need_text': False,
            'expected_priority': None
        },
        {
            'name': '测试场景3: 洗发水 + 淘宝天猫 + 无文字',
            'product_category': '洗发水',
            'platform': '淘宝天猫1688',
            'text_type': '无文字',
            'expected_need_text': False,
            'expected_priority': None
        },
        {
            'name': '测试场景4: 连衣裙 + 淘宝天猫 + 中文',
            'product_category': '连衣裙',
            'platform': '淘宝天猫1688',
            'text_type': '中文',
            'expected_need_text': False,
            'expected_priority': 'none'
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        
        need_text, text_rules = should_main_image_have_text(
            product_category=test_case['product_category'],
            platform=test_case['platform'],
            text_type=test_case['text_type']
        )
        
        if need_text == test_case['expected_need_text']:
            print(f"  ✅ need_text: {need_text} (预期: {test_case['expected_need_text']})")
            
            if need_text and text_rules:
                priority = text_rules.get('priority')
                if priority == test_case['expected_priority']:
                    print(f"  ✅ priority: {priority} (预期: {test_case['expected_priority']})")
                    passed += 1
                else:
                    print(f"  ❌ priority: {priority} (预期: {test_case['expected_priority']})")
                    failed += 1
            else:
                passed += 1
        else:
            print(f"  ❌ need_text: {need_text} (预期: {test_case['expected_need_text']})")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*60}")
    
    return failed == 0


def test_extract_selling_points():
    print("\n" + "="*60)
    print("测试: extract_selling_points")
    print("="*60)
    
    selling_text = "深层滋养、72h保湿、烟酰胺精华、敏感肌适用"
    points = extract_selling_points(selling_text)
    
    print(f"输入: {selling_text}")
    print(f"输出: {points}")
    
    expected_points = ['深层滋养', '72h保湿', '烟酰胺精华', '敏感肌适用']
    
    if points == expected_points:
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败,预期: {expected_points}")
        return False


def test_distribute_text_content():
    print("\n" + "="*60)
    print("测试: distribute_text_content")
    print("="*60)
    
    selling_points = ['深层滋养', '72h保湿', '烟酰胺精华', '敏感肌适用', '温和不刺激']
    output_count = 6
    product_category = '美妆护肤'
    
    text_distribution = distribute_text_content(selling_points, output_count, product_category)
    
    print(f"卖点: {selling_points}")
    print(f"主图数量: {output_count}")
    print(f"产品类别: {product_category}")
    print(f"\n文案分配结果:")
    
    for i, text_config in enumerate(text_distribution):
        print(f"\n主图 {i+1}:")
        print(f"  位置: {text_config['position']}")
        print(f"  策略: {text_config['text_strategy']}")
        print(f"  内容: {text_config['text_content']}")
        print(f"  文案位置: {text_config['text_position']}")
        print(f"  需要文案: {text_config['need_text']}")
    
    if len(text_distribution) == output_count:
        print(f"\n✅ 生成了正确数量的文案配置")
        return True
    else:
        print(f"\n❌ 文案配置数量错误: {len(text_distribution)} (预期: {output_count})")
        return False


def test_get_text_position_by_index():
    print("\n" + "="*60)
    print("测试: get_text_position_by_index")
    print("="*60)
    
    positions = []
    for i in range(6):
        pos = get_text_position_by_index(i)
        positions.append(pos)
        print(f"主图 {i+1}: {pos}")
    
    unique_positions = len(set(positions))
    print(f"\n不同位置数量: {unique_positions}")
    
    if unique_positions > 1:
        print("✅ 文案位置多样化测试通过")
        return True
    else:
        print("❌ 文案位置缺乏多样化")
        return False


def test_multi_image_text_differentiation():
    print("\n" + "="*60)
    print("测试: 多张主图文案差异化")
    print("="*60)
    
    selling_points = ['深层滋养', '72h保湿', '烟酰胺精华', '敏感肌适用', '温和不刺激']
    text_distribution = distribute_text_content(selling_points, 6, '美妆护肤')
    
    assert len(text_distribution) == 6, "文案配置数量错误"
    assert text_distribution[0]['text_strategy'] == '核心卖点', "第一张主图策略错误"
    assert text_distribution[0]['need_text'] == True, "第一张主图应该需要文案"
    assert text_distribution[5]['need_text'] == False, "最后一张主图不应该需要文案"
    
    text_contents = [t['text_content'] for t in text_distribution if t['need_text']]
    assert len(text_contents) == len(set(text_contents)), "文案内容不应重复"
    
    text_positions = [t['text_position'] for t in text_distribution if t['need_text']]
    assert len(set(text_positions)) > 1, "文案位置应该多样化"
    
    print("✅ 多张主图文案差异化测试通过")
    return True


def main():
    print("="*60)
    print("主图文案添加逻辑测试")
    print("="*60)
    
    all_passed = True
    
    all_passed = test_should_main_image_have_text() and all_passed
    all_passed = test_extract_selling_points() and all_passed
    all_passed = test_distribute_text_content() and all_passed
    all_passed = test_get_text_position_by_index() and all_passed
    all_passed = test_multi_image_text_differentiation() and all_passed
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有测试通过!")
    else:
        print("❌ 部分测试失败")
    print("="*60)
    
    return all_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
