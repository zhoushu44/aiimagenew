import os
os.environ['APP_MODE'] = 'mode1'
from dotenv import load_dotenv
load_dotenv()
import app
from app import get_mode1_client, call_mode1_image_edit, create_mode1_blank_canvas_payload

client = get_mode1_client()

print("=== 测试1: mode1 文生图（白图+图生图）===")
from app import call_mode1_text2image
try:
    generated_item, model = call_mode1_text2image(client, "生成一张简洁白底电商产品海报，主体是一个红色陶瓷马克杯，干净光照，无文字。")
    print(f"模型: {model}")
    print(f"URL: {generated_item.get('url', 'N/A')}")
    print("文生图 成功!")
except Exception as exc:
    print(f"文生图 失败: {exc}")

print()
print("=== 测试2: mode1 图生图（换装）===")
try:
    image1_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_1.png"
    image2_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_2.png"
    image_payloads = [
        app.build_remote_image_payload(image1_url),
        app.build_remote_image_payload(image2_url),
    ]
    generated_item, model = call_mode1_image_edit(client, "将图1的服装换为图2的服装", image_payloads, '1:1')
    print(f"模型: {model}")
    print(f"URL: {generated_item.get('url', 'N/A')}")
    print("图生图 成功!")
except Exception as exc:
    print(f"图生图 失败: {exc}")
