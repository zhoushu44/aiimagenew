# 🚀 快速开始指南

## 📋 前置要求

- Python 3.10+
- pip (Python包管理器)
- Git

## 🔧 安装步骤

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/aiimagenew.git
cd aiimagenew
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

#### 生产环境
```bash
pip install -r requirements.txt
```

#### 开发环境
```bash
pip install -r requirements-dev.txt
```

### 4. 安装Pre-commit Hooks

```bash
pre-commit install
```

## 🎯 常用命令

### 查看所有可用命令
```bash
make help
```

### 运行测试
```bash
# 运行所有测试
make test

# 运行测试并生成覆盖率报告
make test-cov
```

### 代码质量检查
```bash
# 运行所有检查
make check-all

# 仅运行代码检查
make lint

# 格式化代码
make format
```

### 安全检查
```bash
make security
```

### 清理临时文件
```bash
make clean
```

## 📝 开发流程

### 1. 创建功能分支
```bash
git checkout -b feature/your-feature-name
```

### 2. 开发并测试
```bash
# 编写代码
# 添加测试
# 运行测试
make test

# 格式化代码
make format

# 运行检查
make lint
```

### 3. 提交代码
```bash
git add .
git commit -m "feat: add your feature"

# Pre-commit hooks会自动运行检查
```

### 4. 推送并创建PR
```bash
git push origin feature/your-feature-name
# 在GitHub上创建Pull Request
```

## 🔍 代码质量工具

### Black - 代码格式化
```bash
# 格式化所有Python文件
black .

# 检查但不修改
black --check .
```

### isort - 导入排序
```bash
# 排序导入
isort .

# 检查但不修改
isort --check-only .
```

### Flake8 - 代码检查
```bash
flake8 .
```

### mypy - 类型检查
```bash
mypy generation/
```

### Pylint - 代码质量检查
```bash
pylint generation/
```

## 🧪 测试

### 运行特定测试
```bash
# 运行特定文件
python -m pytest tests/test_text_logic.py

# 运行特定测试函数
python -m pytest tests/test_text_logic.py::test_should_main_image_have_text

# 运行并显示打印输出
python -m pytest tests/ -s

# 运行标记为slow的测试
python -m pytest tests/ -m slow
```

### 测试覆盖率
```bash
# 生成覆盖率报告
python -m pytest tests/ --cov=generation --cov-report=html

# 查看报告
# 打开 htmlcov/index.html
```

## 🐛 故障排除

### 问题1: 找不到模块
```bash
# 确保在虚拟环境中
which python  # Linux/Mac
where python  # Windows

# 重新安装依赖
pip install -r requirements-dev.txt
```

### 问题2: Pre-commit失败
```bash
# 手动运行pre-commit
pre-commit run --all-files

# 更新pre-commit
pre-commit autoupdate
```

### 问题3: 测试失败
```bash
# 清理缓存
make clean

# 重新运行测试
make test
```

## 📚 更多资源

- [贡献指南](CONTRIBUTING.md)
- [API文档](docs/API_DOCUMENTATION.md)
- [开发指南](docs/DEVELOPMENT_GUIDE.md)
- [部署指南](docs/DEPLOYMENT_GUIDE.md)

## 💬 获取帮助

如果遇到问题，可以：

1. 查看 [文档](docs/)
2. 创建 [Issue](https://github.com/yourusername/aiimagenew/issues)
3. 发送邮件至 team@aiimage.com

---

**祝你开发愉快！** 🎉
