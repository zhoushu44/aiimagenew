import os
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取Supabase连接信息
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("错误：缺少Supabase连接信息，请在.env文件中配置")
    exit(1)

# 读取SQL脚本
with open('supabase/migrations/20260414_create_user_points_balances.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

# 构建请求URL和头部
url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/postgrest_execute_sql"
headers = {
    'apikey': SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
    'Content-Type': 'application/json'
}

# 构建请求体
payload = {
    'sql': sql_script
}

# 发送请求
try:
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    print("SQL脚本执行成功！")
    print("响应:", response.json())
except requests.RequestException as e:
    print(f"执行失败: {e}")
    if response:
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
