import os
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接信息
# 注意：这些信息需要从Supabase项目设置中获取
DB_HOST = os.getenv('DB_HOST', 'aws-0-ap-northeast-1.pooler.supabase.com')
DB_PORT = os.getenv('DB_PORT', '6543')
DB_NAME = os.getenv('DB_NAME', 'postgres')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

if not DB_USER or not DB_PASSWORD:
    print("错误：缺少数据库连接信息，请在.env文件中配置DB_USER和DB_PASSWORD")
    print("这些信息可以从Supabase项目设置中的数据库连接信息获取")
    exit(1)

# 读取SQL脚本
with open('supabase/migrations/20260414_create_user_points_balances.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

# 连接到数据库
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    print("成功连接到数据库")
    
    # 创建游标
    cur = conn.cursor()
    
    # 执行SQL脚本
    print("开始执行SQL脚本...")
    cur.execute(sql_script)
    
    # 提交事务
    conn.commit()
    print("SQL脚本执行成功！")
    
    # 关闭游标和连接
    cur.close()
    conn.close()
    print("数据库连接已关闭")
    
except psycopg2.OperationalError as e:
    print(f"连接数据库失败: {e}")
    exit(1)
except psycopg2.Error as e:
    print(f"执行SQL脚本失败: {e}")
    # 回滚事务
    if 'conn' in locals():
        conn.rollback()
        conn.close()
    exit(1)
