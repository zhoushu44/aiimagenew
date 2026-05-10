# Fallback 链标准化修复报告

## 修复概述

本次修复成功标准化了生图配置的 fallback 链，确保所有模式都遵循统一的核心原则。

## 核心原则

1. **OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 只用于文本规划，不用于生图**
2. **IMAGE_API_KEY / IMAGE_BASE_URL / IMAGE_MODEL 作为通用生图配置的兜底**
3. **MODE1/2/3_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY，不应该 fallback 到 OPENAI_API_KEY 或 ARK_API_KEY**

## 修复前的问题

### Mode1 的 fallback 链（错误）
```
MODE1_IMAGE_API_KEY → IMAGE_API_KEY → ARK_API_KEY → OPENAI_API_KEY ❌
```

### Mode2 的 fallback 链（正确）
```
MODE2_IMAGE_API_KEY → IMAGE_API_KEY ✅
```

### Mode3 的 fallback 链（错误）
```
MODE3_IMAGE_API_KEY → IMAGE_API_KEY → OPENAI_API_KEY ❌
```

## 修复后的结果

### Mode1 的 fallback 链（正确）
```
MODE1_IMAGE_API_KEY → IMAGE_API_KEY ✅
```

### Mode2 的 fallback 链（正确）
```
MODE2_IMAGE_API_KEY → IMAGE_API_KEY ✅
```

### Mode3 的 fallback 链（正确）
```
MODE3_IMAGE_API_KEY → IMAGE_API_KEY ✅
```

## 修复内容

### 1. 修复 get_mode1_api_key() 函数

**文件**: `generation/modes.py`

**修复前**:
```python
def get_mode1_api_key() -> str:
    keys = _parse_api_keys(get_supabase_setting('MODE1_IMAGE_API_KEY', get_optional_env('MODE1_IMAGE_API_KEY', '')))
    if keys:
        return get_round_robin_api_key('mode1')
    api_key = _common_image_api_key('')
    if not api_key:
        api_key = get_supabase_setting('ARK_API_KEY', get_optional_env('ARK_API_KEY', ''))
    if not api_key:
        api_key = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
    return api_key
```

**修复后**:
```python
def get_mode1_api_key() -> str:
    keys = _parse_api_keys(get_supabase_setting('MODE1_IMAGE_API_KEY', get_optional_env('MODE1_IMAGE_API_KEY', '')))
    if keys:
        return get_round_robin_api_key('mode1')
    return _common_image_api_key('')
```

**变更说明**: 移除了对 `ARK_API_KEY` 和 `OPENAI_API_KEY` 的 fallback，只保留对 `IMAGE_API_KEY` 的 fallback。

### 2. 修复 get_mode3_api_key() 函数

**文件**: `generation/modes.py`

**修复前**:
```python
def get_mode3_api_key() -> str:
    keys = _parse_api_keys(get_supabase_setting('MODE3_IMAGE_API_KEY', get_optional_env('MODE3_IMAGE_API_KEY', '')))
    if keys:
        return get_round_robin_api_key('mode3')
    api_key = _common_image_api_key('')
    if not api_key:
        api_key = get_supabase_setting('OPENAI_API_KEY', get_optional_env('OPENAI_API_KEY', ''))
    return api_key
```

**修复后**:
```python
def get_mode3_api_key() -> str:
    keys = _parse_api_keys(get_supabase_setting('MODE3_IMAGE_API_KEY', get_optional_env('MODE3_IMAGE_API_KEY', '')))
    if keys:
        return get_round_robin_api_key('mode3')
    return _common_image_api_key('')
```

**变更说明**: 移除了对 `OPENAI_API_KEY` 的 fallback，只保留对 `IMAGE_API_KEY` 的 fallback。

## 测试验证

创建了测试文件 `test_fallback_fix.py`，验证修复结果：

### 测试结果
```
✓ 通过: Mode1 Fallback 逻辑
✓ 通过: Mode2 Fallback 逻辑
✓ 通过: Mode3 Fallback 逻辑

总计: 3/3 测试通过
```

### 验证内容
1. ✓ get_mode1_api_key() 移除了对 ARK_API_KEY 和 OPENAI_API_KEY 的 fallback
2. ✓ get_mode3_api_key() 移除了对 OPENAI_API_KEY 的 fallback
3. ✓ 所有模式现在只 fallback 到 IMAGE_API_KEY

## 影响范围

### 修改的文件
- `generation/modes.py`: 修复了 `get_mode1_api_key()` 和 `get_mode3_api_key()` 函数

### 新增的文件
- `test_fallback_fix.py`: 验证修复结果的测试文件

### 不受影响的功能
- 文本规划功能：仍然使用 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`
- Mode2 的生图功能：原本就是正确的 fallback 链
- 其他配置项：如 `BASE_URL`、`MODEL` 等配置不受影响

## 配置建议

### 推荐的配置方式

1. **设置通用生图配置**（可选）:
   ```bash
   IMAGE_API_KEY=your-common-image-api-key
   IMAGE_BASE_URL=https://your-image-api-endpoint
   IMAGE_MODEL=your-image-model
   ```

2. **为每个模式设置专用配置**（推荐）:
   ```bash
   # Mode1 配置
   MODE1_IMAGE_API_KEY=your-mode1-api-key
   MODE1_IMAGE_BASE_URL=https://your-mode1-endpoint
   MODE1_IMAGE_MODEL=your-mode1-model
   
   # Mode2 配置
   MODE2_IMAGE_API_KEY=your-mode2-api-key
   MODE2_IMAGE_BASE_URL=https://your-mode2-endpoint
   MODE2_IMAGE_MODEL=your-mode2-model
   
   # Mode3 配置
   MODE3_IMAGE_API_KEY=your-mode3-api-key
   MODE3_IMAGE_BASE_URL=https://your-mode3-endpoint
   MODE3_IMAGE_MODEL=your-mode3-model
   ```

3. **文本规划配置**（必需）:
   ```bash
   OPENAI_API_KEY=your-openai-api-key
   OPENAI_BASE_URL=https://api.openai.com/v1
   OPENAI_MODEL=gpt-4
   ```

## 总结

本次修复成功实现了生图配置 fallback 链的标准化，确保：

1. ✓ OPENAI_API_KEY 不用于生图
2. ✓ IMAGE_API_KEY 作为通用生图配置的兜底
3. ✓ MODE1/2/3_IMAGE_API_KEY 只 fallback 到 IMAGE_API_KEY

所有测试通过，修复完成。
