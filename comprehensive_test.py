"""
全面测试脚本
测试项目的各个方面
"""
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def test_imports():
    """测试所有模块导入"""
    print("="*60)
    print("测试 1: 模块导入测试")
    print("="*60)
    
    modules = [
        ('app', 'Flask主应用'),
        ('config', '配置模块'),
        ('utils', '工具函数'),
        ('image_utils', '图片工具'),
        ('prompts', '提示词模板'),
        ('points_rules', '积分规则'),
        ('cos_utils', 'COS工具'),
        ('redis_client', 'Redis客户端'),
        ('supabase_client', 'Supabase客户端'),
        ('celery_app', 'Celery应用'),
        ('celery_tasks', 'Celery任务'),
        ('generation.modes', '生成模式'),
        ('generation.planning', '规划模块'),
        ('generation.suite', '套图生成'),
        ('generation.aplus', 'A+生成'),
    ]
    
    success_count = 0
    failed_modules = []
    
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✅ {description:20s} ({module_name})")
            success_count += 1
        except Exception as e:
            print(f"❌ {description:20s} ({module_name})")
            print(f"   错误: {str(e)[:100]}")
            failed_modules.append((module_name, str(e)))
    
    print(f"\n导入测试结果: {success_count}/{len(modules)} 成功")
    
    if failed_modules:
        print("\n失败的模块:")
        for module, error in failed_modules:
            print(f"  - {module}: {error[:100]}")
        return False
    
    return True


def test_text_logic():
    """测试文案逻辑"""
    print("\n" + "="*60)
    print("测试 2: 文案逻辑测试")
    print("="*60)
    
    try:
        from generation.planning import (
            should_main_image_have_text,
            get_product_text_rule,
            build_main_image_text_prompt,
            extract_selling_points,
            distribute_text_content,
        )
        
        print("✅ 文案逻辑函数导入成功")
        
        # 测试1: 淘宝洗发水应该有文案
        need_text, rules = should_main_image_have_text(
            product_category="洗发水",
            platform="淘宝天猫1688",
            text_type="中文"
        )
        
        if need_text and rules.get('priority') == 'high':
            print("✅ 测试1通过: 淘宝洗发水需要文案(高优先级)")
        else:
            print("❌ 测试1失败: 淘宝洗发水应该需要文案")
            return False
        
        # 测试2: 亚马逊洗发水不应该有文案
        need_text, rules = should_main_image_have_text(
            product_category="洗发水",
            platform="亚马逊",
            text_type="中文"
        )
        
        if not need_text:
            print("✅ 测试2通过: 亚马逊洗发水不需要文案")
        else:
            print("❌ 测试2失败: 亚马逊洗发水不应该需要文案")
            return False
        
        # 测试3: 连衣裙不应该有文案
        need_text, rules = should_main_image_have_text(
            product_category="连衣裙",
            platform="淘宝天猫1688",
            text_type="中文"
        )
        
        if not need_text:
            print("✅ 测试3通过: 连衣裙不需要文案")
        else:
            print("❌ 测试3失败: 连衣裙不应该需要文案")
            return False
        
        # 测试4: 卖点提取
        selling_points = extract_selling_points("深层滋养、72h保湿、烟酰胺精华")
        if len(selling_points) == 3:
            print(f"✅ 测试4通过: 卖点提取正确 {selling_points}")
        else:
            print(f"❌ 测试4失败: 卖点提取错误 {selling_points}")
            return False
        
        # 测试5: 文案分配
        text_distribution = distribute_text_content(
            selling_points=selling_points,
            output_count=6,
            product_category="美妆护肤"
        )
        
        if len(text_distribution) == 6:
            print(f"✅ 测试5通过: 文案分配正确 (6张主图)")
        else:
            print(f"❌ 测试5失败: 文案分配错误 {len(text_distribution)}")
            return False
        
        print("\n文案逻辑测试: 全部通过 ✅")
        return True
        
    except Exception as e:
        print(f"❌ 文案逻辑测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_config_files():
    """测试配置文件"""
    print("\n" + "="*60)
    print("测试 3: 配置文件测试")
    print("="*60)
    
    config_files = [
        'pyproject.toml',
        '.flake8',
        '.pylintrc',
        '.yamllint.yml',
        '.editorconfig',
        '.pre-commit-config.yaml',
        'Makefile',
        'requirements-dev.txt',
        'CONTRIBUTING.md',
        'QUICKSTART.md',
    ]
    
    success_count = 0
    
    for config_file in config_files:
        file_path = BASE_DIR / config_file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {config_file:30s} ({size} bytes)")
            success_count += 1
        else:
            print(f"❌ {config_file:30s} (不存在)")
    
    print(f"\n配置文件测试: {success_count}/{len(config_files)} 存在")
    
    return success_count == len(config_files)


def test_project_structure():
    """测试项目结构"""
    print("\n" + "="*60)
    print("测试 4: 项目结构测试")
    print("="*60)
    
    directories = [
        'generation',
        'pages',
        'scripts',
        'static',
        'tests',
        'docs',
        'database',
        'supabase',
    ]
    
    success_count = 0
    
    for directory in directories:
        dir_path = BASE_DIR / directory
        if dir_path.exists() and dir_path.is_dir():
            file_count = len(list(dir_path.rglob('*')))
            print(f"✅ {directory:20s} ({file_count} 文件)")
            success_count += 1
        else:
            print(f"❌ {directory:20s} (不存在)")
    
    print(f"\n项目结构测试: {success_count}/{len(directories)} 目录存在")
    
    return success_count == len(directories)


def test_flask_app():
    """测试Flask应用"""
    print("\n" + "="*60)
    print("测试 5: Flask应用测试")
    print("="*60)
    
    try:
        import app
        
        # 检查Flask应用
        if hasattr(app, 'app'):
            flask_app = app.app
            print(f"✅ Flask应用创建成功")
            
            # 检查路由
            routes = list(flask_app.url_map.iter_rules())
            print(f"✅ 注册路由数量: {len(routes)}")
            
            # 检查配置
            if hasattr(flask_app, 'config'):
                print(f"✅ Flask配置加载成功")
            
            return True
        else:
            print("❌ Flask应用未找到")
            return False
            
    except Exception as e:
        print(f"❌ Flask应用测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_celery_config():
    """测试Celery配置"""
    print("\n" + "="*60)
    print("测试 6: Celery配置测试")
    print("="*60)
    
    try:
        from celery_app import celery_app
        
        print(f"✅ Celery应用创建成功")
        print(f"✅ Broker: {celery_app.conf.broker_url[:50]}...")
        print(f"✅ Backend: {celery_app.conf.result_backend[:50] if celery_app.conf.result_backend else 'None'}...")
        
        # 检查任务
        tasks = list(celery_app.tasks.keys())
        custom_tasks = [t for t in tasks if not t.startswith('celery.')]
        print(f"✅ 注册任务数量: {len(custom_tasks)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Celery配置测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_documentation():
    """测试文档完整性"""
    print("\n" + "="*60)
    print("测试 7: 文档完整性测试")
    print("="*60)
    
    docs = {
        'README.md': '项目说明',
        'CHANGELOG.md': '更新日志',
        'CONTRIBUTING.md': '贡献指南',
        'QUICKSTART.md': '快速开始',
        'docs/项目整理完成报告.md': '整理报告',
        'docs/项目质量提升完成报告.md': '提升报告',
    }
    
    success_count = 0
    
    for doc_path, description in docs.items():
        file_path = BASE_DIR / doc_path
        if file_path.exists():
            size = file_path.stat().st_size
            lines = len(file_path.read_text(encoding='utf-8').splitlines())
            print(f"✅ {description:15s} ({lines} 行, {size} bytes)")
            success_count += 1
        else:
            print(f"❌ {description:15s} (不存在)")
    
    print(f"\n文档完整性测试: {success_count}/{len(docs)} 存在")
    
    return success_count == len(docs)


def main():
    """运行所有测试"""
    print("="*60)
    print("AI Image Generation Platform - 全面测试")
    print("="*60)
    print(f"测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {BASE_DIR}")
    
    results = []
    
    # 运行所有测试
    results.append(("模块导入", test_imports()))
    results.append(("文案逻辑", test_text_logic()))
    results.append(("配置文件", test_config_files()))
    results.append(("项目结构", test_project_structure()))
    results.append(("Flask应用", test_flask_app()))
    results.append(("Celery配置", test_celery_config()))
    results.append(("文档完整性", test_documentation()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:15s}: {status}")
    
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    print(f"\n总计: {success_count}/{total_count} 测试通过")
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！项目状态良好！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
