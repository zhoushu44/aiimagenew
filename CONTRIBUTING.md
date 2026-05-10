# 贡献指南

感谢您考虑为 AI Image Generation Platform 做出贡献！

## 📋 目录

- [行为准则](#行为准则)
- [如何贡献](#如何贡献)
- [开发流程](#开发流程)
- [代码规范](#代码规范)
- [提交信息规范](#提交信息规范)
- [测试规范](#测试规范)
- [文档规范](#文档规范)

## 行为准则

本项目采用贡献者公约作为行为准则。参与此项目即表示您同意遵守其条款。请阅读 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 了解详情。

## 如何贡献

### 报告Bug

如果您发现了bug，请创建一个issue并包含以下信息：

- **Bug描述**: 清楚简洁地描述bug
- **复现步骤**: 如何复现该问题
- **预期行为**: 您期望发生什么
- **实际行为**: 实际发生了什么
- **截图**: 如果适用，添加截图
- **环境信息**:
  - OS: [例如 Windows 10]
  - Python版本: [例如 3.10.11]
  - 项目版本: [例如 1.0.0]

### 建议新功能

如果您有新功能的建议，请创建一个issue并包含以下信息：

- **功能描述**: 清楚简洁地描述功能
- **使用场景**: 描述为什么需要这个功能
- **实现建议**: 如果您有实现建议，请描述

### 提交代码

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建一个 Pull Request

## 开发流程

### 1. 设置开发环境

```bash
# 克隆仓库
git clone https://github.com/yourusername/aiimagenew.git
cd aiimagenew

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
make install-dev

# 安装pre-commit hooks
pre-commit install
```

### 2. 创建分支

```bash
# 从main分支创建新分支
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### 3. 进行开发

- 编写代码
- 添加测试
- 更新文档
- 运行测试

### 4. 提交代码

```bash
# 运行所有检查
make check-all

# 提交代码
git add .
git commit -m "feat: add amazing feature"

# 推送到远程
git push origin feature/your-feature-name
```

### 5. 创建Pull Request

- 在GitHub上创建Pull Request
- 填写PR模板
- 等待代码审查
- 根据反馈进行修改

## 代码规范

### Python代码规范

本项目遵循以下代码规范：

- **PEP 8**: Python代码风格指南
- **Black**: 代码格式化工具
- **isort**: 导入排序工具
- **Pylint**: 代码质量检查工具
- **mypy**: 类型检查工具

### 代码格式化

```bash
# 格式化代码
make format

# 或手动运行
black .
isort .
```

### 代码检查

```bash
# 运行代码检查
make lint

# 或手动运行
black --check .
isort --check-only .
flake8 .
mypy generation/
```

### 类型注解

我们鼓励使用类型注解：

```python
from typing import Dict, List, Optional

def process_image(
    image_path: str,
    options: Optional[Dict[str, any]] = None
) -> Dict[str, str]:
    """
    处理图片
    
    Args:
        image_path: 图片路径
        options: 处理选项
        
    Returns:
        处理结果字典
    """
    pass
```

## 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

### 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type类型

- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式（不影响代码运行的变动）
- `refactor`: 重构（既不是新增功能，也不是修改bug的代码变动）
- `perf`: 性能优化
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动
- `revert`: 回滚

### 示例

```bash
# 新功能
git commit -m "feat: add image watermark feature"

# Bug修复
git commit -m "fix: resolve image upload issue"

# 文档更新
git commit -m "docs: update API documentation"

# 重构
git commit -m "refactor: optimize image processing logic"
```

## 测试规范

### 运行测试

```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-cov

# 运行特定测试
python -m pytest tests/test_text_logic.py -v
```

### 测试覆盖率

我们要求测试覆盖率达到 **80%** 以上。

### 测试命名

- 测试文件: `test_*.py`
- 测试类: `Test*`
- 测试函数: `test_*`

### 测试示例

```python
import pytest
from generation.planning import should_main_image_have_text

class TestMainImageText:
    """主图文案测试"""
    
    def test_should_have_text_for_taobao(self):
        """测试淘宝平台应该有文案"""
        need_text, rules = should_main_image_have_text(
            product_category="洗发水",
            platform="淘宝天猫1688",
            text_type="中文"
        )
        assert need_text is True
        assert rules['priority'] == 'high'
    
    def test_should_not_have_text_for_amazon(self):
        """测试亚马逊平台不应该有文案"""
        need_text, rules = should_main_image_have_text(
            product_category="洗发水",
            platform="亚马逊",
            text_type="中文"
        )
        assert need_text is False
```

## 文档规范

### 文档结构

- `README.md`: 项目介绍和快速开始
- `CHANGELOG.md`: 版本更新日志
- `CONTRIBUTING.md`: 贡献指南
- `docs/`: 详细文档目录
  - `API_DOCUMENTATION.md`: API文档
  - `DEVELOPMENT_GUIDE.md`: 开发指南
  - `DEPLOYMENT_GUIDE.md`: 部署指南
  - `ARCHITECTURE.md`: 架构说明

### 文档风格

- 使用Markdown格式
- 保持简洁明了
- 提供代码示例
- 及时更新

### 文档字符串

使用Google风格的文档字符串：

```python
def calculate_total(items: List[Dict]) -> float:
    """
    计算商品总价
    
    Args:
        items: 商品列表，每个商品包含price和quantity字段
        
    Returns:
        总价
        
    Raises:
        ValueError: 如果items为空
        
    Examples:
        >>> items = [{'price': 10.0, 'quantity': 2}]
        >>> calculate_total(items)
        20.0
    """
    if not items:
        raise ValueError("Items cannot be empty")
    
    return sum(item['price'] * item['quantity'] for item in items)
```

## 版本发布

### 版本号规范

我们使用 [语义化版本](https://semver.org/lang/zh-CN/)：

- **主版本号**: 不兼容的API修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 发布流程

1. 更新 `CHANGELOG.md`
2. 更新版本号
3. 创建Git标签
4. 构建和发布

## 获取帮助

如果您有任何问题，可以：

- 查看 [文档](docs/)
- 创建 [Issue](https://github.com/yourusername/aiimagenew/issues)
- 发送邮件至 team@aiimage.com

## 许可证

通过贡献您的代码，您同意您的贡献将根据MIT许可证进行许可。

---

再次感谢您的贡献！🎉
