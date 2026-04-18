import os
from dotenv import load_dotenv
from supabase import create_client, Client

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

# 初始化Supabase客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# 执行SQL脚本
try:
    print("正在执行SQL脚本...")
    # 使用Supabase的RPC功能执行SQL
    # 注意：Supabase的Python客户端库不直接支持执行任意SQL
    # 我们需要创建一个RPC函数来执行SQL
    
    # 首先创建一个RPC函数来执行SQL
    create_rpc_sql = """
    create or replace function public.execute_sql(sql text)
    returns jsonb
    language plpgsql
    security definer
    as $$
    declare
        result jsonb;
    begin
        execute sql;
        return jsonb_build_object('success', true);
    exception
        when others then
            return jsonb_build_object('success', false, 'error', SQLERRM);
    end;
    $$;
    """
    
    # 执行创建RPC函数的SQL
    # 注意：这里我们使用requests库直接调用Supabase的REST API来执行SQL
    import requests
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/postgrest_execute_sql"
    headers = {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {'sql': create_rpc_sql}
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(f"创建RPC函数响应: {response.status_code} - {response.text}")
    
    # 执行创建积分表的SQL
    payload = {'sql': sql_script}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    print(f"执行SQL脚本响应: {response.status_code} - {response.text}")
    
    if response.status_code == 200:
        print("SQL脚本执行成功！")
    else:
        print(f"执行失败: {response.text}")
        
except Exception as e:
    print(f"执行失败: {e}")
