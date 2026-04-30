import time
import os
os.environ['APP_MODE'] = 'mode3'
import app

colors = ['红色', '蓝色', '绿色', '黄色', '紫色', '橙色', '黑色', '白色', '粉色']
plan = {
    'items': [
        {
            'sort': idx + 1,
            'type': f'并发测试图{idx+1}',
            'type_tag': f'T{idx+1}',
            'title': f'并发测试图{idx+1}',
            'keywords': [],
            'prompt': f'生成一张简洁白底电商产品海报，主体是一个{color}陶瓷马克杯，干净光照，无文字。',
        }
        for idx, color in enumerate(colors)
    ]
}

start = time.time()
print('start', time.strftime('%H:%M:%S'))
try:
    result = app.generate_mode3_suite_images_parallel(
        plan, [], 'realtest9-' + str(int(start)), '1:1', '无文字', '中国',
        None, [i['type'] for i in plan['items']]
    )
    elapsed = time.time() - start
    print('elapsed_seconds', round(elapsed, 2))
    print('count', len(result))
    print('sorts', [i['sort'] for i in result])
    print('urls', [i['image_url'] for i in result])
except Exception as exc:
    elapsed = time.time() - start
    print('elapsed_seconds', round(elapsed, 2))
    print('FAILED:', exc)
