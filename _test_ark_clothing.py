import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

imagesResponse = client.images.generate(
    model="doubao-seedream-5-0-260128",
    prompt="将图1的服装换为图2的服装",
    size="2K",
    response_format="url",
    extra_body={
        "image": [
            "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_1.png",
            "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imagesToimage_2.png"
        ],
        "watermark": True,
        "sequential_image_generation": "disabled",
    }
)

print("生成成功!")
print("图片URL:", imagesResponse.data[0].url)
