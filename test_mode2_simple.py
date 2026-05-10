import time
import json
import requests
from datetime import datetime

BASE_URL = 'http://127.0.0.1:5078'
AUTH_TOKEN = 'eyJhY2Nlc3NfdG9rZW4iOiJleUpoYkdjaU9pSklVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKemRXSWlPaUl5TWpobE5HTmxOUzA0TXpFMUxUUmxZemN0T0dVME5pMWxOalF4TmpJelltSXlNbVlpTENKaGRXUWlPaUpoZFhSb1pXNTBhV05oZEdWa0lpd2laWGh3SWpveE56YzRNVE0yT1RJeUxDSnBZWFFpT2pFM056Z3hNek16TWpJc0ltVnRZV2xzSWpvaUlpd2ljR2h2Ym1VaU9pSTROakV6TlRnNE9UZzROVEEzSWl3aVlYQndYMjFsZEdGa1lYUmhJanA3SW5CeWIzWnBaR1Z5SWpvaWNHaHZibVVpTENKd2NtOTJhV1JsY25NaU9sc2ljR2h2Ym1VaVhYMHNJblZ6WlhKZmJXVjBZV1JoZEdFaU9uc2laVzFoYVd4ZmRtVnlhV1pwWldRaU9tWmhiSE5sTENKd2FHOXVaVjkyWlhKcFptbGxaQ0k2Wm1Gc2MyVXNJbk4xWWlJNklqSXlPR1UwWTJVMUxUZ3pNVFV0TkdWak55MDRaVFEyTFdVMk5ERTJNak5pWWpJeVppSjlMQ0p5YjJ4bElqb2lZWFYwYUdWdWRHbGpZWFJsWkNJc0ltRmhiQ0k2SW1GaGJERWlMQ0poYlhJaU9sdDdJbTFsZEdodlpDSTZJbTkwY0NJc0luUnBiV1Z6ZEdGdGNDSTZNVGMzT0RFek16TXlNbjFkTENKelpYTnphVzl1WDJsa0lqb2lNalZqWVdZeE1URXRNRFExTmkwME56QmtMV0ZrTXprdE5EVXlNekpqTVdSbE5ERXhJaXdpYVhOZllXNXZibmx0YjNWeklqcG1ZV3h6WlgwLmhJeU5VbUF5alBBMldJaXQyaU5fYVBNbFFraVcwTXd5d1F4QkhNaXVib2MiLCJyZWZyZXNoX3Rva2VuIjoiNGVvN3Y1a2l1YzV5IiwidXNlciI6eyJpZCI6IjIyOGU0Y2U1LTgzMTUtNGVjNy04ZTQ2LWU2NDE2MjNiYjIyZiIsInBob25lIjoiODYxMzU4ODk4ODUwNyIsImVtYWlsIjoiIiwidXNlcl9tZXRhZGF0YSI6eyJwaG9uZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJlbWFpbCI6bnVsbH19fQ'

COOKIES = {'aiimagenew_supabase_session': AUTH_TOKEN}

print('=' * 70)
print(f'Mode2 快速测试 - {datetime.now().strftime("%H:%M:%S")}')
print('=' * 70)

# 测试文生图
print('\n[测试] Mode2 文生图 (jimeng-5.0)')
start = time.time()
resp = requests.post(
    f'{BASE_URL}/api/generate-mode2-text2image',
    cookies=COOKIES,
    json={'prompt': '一只可爱的橘色猫咪', 'ratio': '1:1', 'resolution': '2k'},
    timeout=120
)
print(f'  状态码: {resp.status_code}')
print(f'  耗时: {time.time()-start:.1f}s')
result = resp.json()
if result.get('success'):
    print(f'  ✅ 成功')
else:
    print(f'  ❌ 失败: {result.get("error", "未知")}')
