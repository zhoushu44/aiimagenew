import os
import json
from dotenv import load_dotenv
import requests

# 加载环境变量
load_dotenv()

# 获取Supabase连接信息
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("错误：缺少Supabase连接信息，请在.env文件中配置")
    exit(1)

# 构建请求头部
headers = {
    'apikey': SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
    'Content-Type': 'application/json'
}

# 步骤1：创建user_points_balances表
print("步骤1：创建user_points_balances表...")
create_table_sql = """
create table if not exists public.user_points_balances (
  user_id uuid primary key references auth.users (id) on delete cascade,
  balance integer not null default 0,
  total_earned integer not null default 0,
  total_spent integer not null default 0,
  signup_bonus_awarded_at timestamptz,
  last_daily_claim_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint user_points_balances_balance_nonnegative check (balance >= 0),
  constraint user_points_balances_total_earned_nonnegative check (total_earned >= 0),
  constraint user_points_balances_total_spent_nonnegative check (total_spent >= 0)
);
"""

# 注意：由于Supabase的REST API不支持直接执行SQL，我们需要使用另一种方法
# 我们可以使用Supabase的管理API来执行SQL
# 但是这需要额外的权限，可能无法直接使用

# 让我们尝试使用PostgREST的直接连接
# 首先，我们需要获取数据库的连接信息
print("尝试获取数据库连接信息...")

# 由于我们无法直接执行SQL，我们需要使用其他方法
# 让我们尝试使用Supabase的Python客户端库的其他功能
# 但是，Supabase的Python客户端库主要用于CRUD操作，不支持直接创建表

print("由于Supabase的REST API限制，我们无法直接通过API执行SQL脚本")
print("建议的解决方案：")
print("1. 登录Supabase控制台 (https://app.supabase.com/)")
print("2. 选择项目 owpkdaajcfpyqsatarte")
print("3. 点击左侧导航栏中的 SQL Editor")
print("4. 复制粘贴 supabase/migrations/20260414_create_user_points_balances.sql 文件的内容")
print("5. 点击 Run 按钮执行脚本")
print("\n这样可以直接在Supabase控制台中创建积分表，无需依赖本地环境")
