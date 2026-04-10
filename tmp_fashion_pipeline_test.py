import io
import json
import importlib.util
from pathlib import Path
from unittest.mock import patch

APP_PATH = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/app.py')
spec = importlib.util.spec_from_file_location('fashion_app_under_test', APP_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

product_path = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/1.png')
model_path = Path(r'E:/360MoveData/Users/Administrator/Desktop/新/generated-suites/307c91a48f604ed6abdefc5a83e07110/01-fashion-model.png')
product_bytes = product_path.read_bytes()
model_bytes = model_path.read_bytes()

captured = {
    'plan_generation_payloads': None,
    'generate_generation_payloads': None,
    'generate_prompt': None,
    'generate_image_type': None,
    'generate_text_type': None,
}


def fake_build_fashion_scene_plan(platform, selling_text, planning_payloads, country, text_type, image_size_ratio, selected_style):
    captured['plan_generation_payloads'] = [
        {
            'filename': item.get('filename'),
            'mime_type': item.get('mime_type'),
            'byte_size': len(item.get('bytes') or b''),
        }
        for item in planning_payloads
    ]
    return {
        'summary': '自动测试场景规划',
        'scene_prompt': '保留服装主体并让模特穿上商品',
        'scene_groups': [
            {
                'id': 'scene-group-1',
                'title': '测试场景组1',
                'description': '测试用1',
                'scene_prompt': '简洁测试场景1',
                'poses': [
                    {'id': 'pose-1-1', 'title': '测试姿态1-1', 'description': '测试姿态说明1-1', 'scene_prompt': '模特正面站立展示服饰1-1'},
                    {'id': 'pose-1-2', 'title': '测试姿态1-2', 'description': '测试姿态说明1-2', 'scene_prompt': '模特侧身展示服饰1-2'},
                    {'id': 'pose-1-3', 'title': '测试姿态1-3', 'description': '测试姿态说明1-3', 'scene_prompt': '模特近景展示服饰1-3'},
                    {'id': 'pose-1-4', 'title': '测试姿态1-4', 'description': '测试姿态说明1-4', 'scene_prompt': '模特全身展示服饰1-4'},
                ],
            },
            {
                'id': 'scene-group-2',
                'title': '测试场景组2',
                'description': '测试用2',
                'scene_prompt': '简洁测试场景2',
                'poses': [
                    {'id': 'pose-2-1', 'title': '测试姿态2-1', 'description': '测试姿态说明2-1', 'scene_prompt': '模特正面站立展示服饰2-1'},
                    {'id': 'pose-2-2', 'title': '测试姿态2-2', 'description': '测试姿态说明2-2', 'scene_prompt': '模特侧身展示服饰2-2'},
                    {'id': 'pose-2-3', 'title': '测试姿态2-3', 'description': '测试姿态说明2-3', 'scene_prompt': '模特近景展示服饰2-3'},
                    {'id': 'pose-2-4', 'title': '测试姿态2-4', 'description': '测试姿态说明2-4', 'scene_prompt': '模特全身展示服饰2-4'},
                ],
            },
            {
                'id': 'scene-group-3',
                'title': '测试场景组3',
                'description': '测试用3',
                'scene_prompt': '简洁测试场景3',
                'poses': [
                    {'id': 'pose-3-1', 'title': '测试姿态3-1', 'description': '测试姿态说明3-1', 'scene_prompt': '模特正面站立展示服饰3-1'},
                    {'id': 'pose-3-2', 'title': '测试姿态3-2', 'description': '测试姿态说明3-2', 'scene_prompt': '模特侧身展示服饰3-2'},
                    {'id': 'pose-3-3', 'title': '测试姿态3-3', 'description': '测试姿态说明3-3', 'scene_prompt': '模特近景展示服饰3-3'},
                    {'id': 'pose-3-4', 'title': '测试姿态3-4', 'description': '测试姿态说明3-4', 'scene_prompt': '模特全身展示服饰3-4'},
                ],
            },
            {
                'id': 'scene-group-4',
                'title': '测试场景组4',
                'description': '测试用4',
                'scene_prompt': '简洁测试场景4',
                'poses': [
                    {'id': 'pose-4-1', 'title': '测试姿态4-1', 'description': '测试姿态说明4-1', 'scene_prompt': '模特正面站立展示服饰4-1'},
                    {'id': 'pose-4-2', 'title': '测试姿态4-2', 'description': '测试姿态说明4-2', 'scene_prompt': '模特侧身展示服饰4-2'},
                    {'id': 'pose-4-3', 'title': '测试姿态4-3', 'description': '测试姿态说明4-3', 'scene_prompt': '模特近景展示服饰4-3'},
                    {'id': 'pose-4-4', 'title': '测试姿态4-4', 'description': '测试姿态说明4-4', 'scene_prompt': '模特全身展示服饰4-4'},
                ],
            }
        ],
    }



def fake_call_image_generation(client, prompt, image_payloads, image_size_ratio, text_type, country, product_json, image_type, max_images=1):
    captured['generate_generation_payloads'] = [
        {
            'filename': item.get('filename'),
            'mime_type': item.get('mime_type'),
            'byte_size': len(item.get('bytes') or b''),
        }
        for item in image_payloads
    ]
    captured['generate_prompt'] = prompt
    captured['generate_image_type'] = image_type
    captured['generate_text_type'] = text_type
    return [{'b64_json': module.base64.b64encode(product_bytes).decode('ascii')}]



def fake_get_ark_client():
    return object()


with app.test_client() as client:
    with patch.object(module, 'build_fashion_scene_plan', side_effect=fake_build_fashion_scene_plan), patch.object(module, 'call_image_generation', side_effect=fake_call_image_generation), patch.object(module, 'get_ark_client', side_effect=fake_get_ark_client):
        scene_response = client.post(
            '/api/generate-suite',
            data={
                'mode': 'fashion',
                'fashion_action': 'scene_plan',
                'image_size_ratio': '1:1',
                'fashion_selected_model_source': 'ai',
                'fashion_selected_model_id': 'auto-test-model',
                'fashion_selected_model_name': '自动测试模特',
                'fashion_selected_model_gender': '女',
                'fashion_selected_model_age': '青年',
                'fashion_selected_model_ethnicity': '亚洲',
                'fashion_selected_model_body_type': '标准',
                'fashion_selected_model_appearance_details': '黑色中长发，五官柔和',
                'fashion_selected_model_summary': '自动测试摘要',
                'fashion_selected_model_detail_text': '自动测试细节',
                'images': (io.BytesIO(product_bytes), '1.png', 'image/png'),
                'fashion_selected_model_image': (io.BytesIO(model_bytes), '01-fashion-model.jpg', 'image/jpeg'),
            },
            content_type='multipart/form-data',
        )
        scene_payload = scene_response.get_json()
        plan = scene_payload['plan']

        generate_response = client.post(
            '/api/generate-suite',
            data={
                'mode': 'fashion',
                'fashion_action': 'generate',
                'image_size_ratio': '1:1',
                'fashion_selected_model_source': 'ai',
                'fashion_selected_model_id': 'auto-test-model',
                'fashion_selected_model_name': '自动测试模特',
                'fashion_selected_model_gender': '女',
                'fashion_selected_model_age': '青年',
                'fashion_selected_model_ethnicity': '亚洲',
                'fashion_selected_model_body_type': '标准',
                'fashion_selected_model_appearance_details': '黑色中长发，五官柔和',
                'fashion_selected_model_summary': '自动测试摘要',
                'fashion_selected_model_detail_text': '自动测试细节',
                'fashion_scene_plan': json.dumps(plan, ensure_ascii=False),
                'fashion_scene_group_ids': json.dumps(['scene-group-1'], ensure_ascii=False),
                'fashion_pose_ids': json.dumps(['scene-group-1-pose-1'], ensure_ascii=False),
                'fashion_pose_camera_settings': json.dumps([
                    {'pose_id': 'scene-group-1-pose-1', 'shot_size': '半身', 'view_angle': '正面'}
                ], ensure_ascii=False),
                'images': (io.BytesIO(product_bytes), '1.png', 'image/png'),
                'fashion_selected_model_image': (io.BytesIO(model_bytes), '01-fashion-model.jpg', 'image/jpeg'),
            },
            content_type='multipart/form-data',
        )
        generate_payload = generate_response.get_json()

result = {
    'scene_status': scene_response.status_code,
    'scene_success': scene_payload.get('success'),
    'scene_error': scene_payload.get('error'),
    'scene_payload_order': (scene_payload.get('fashion_debug') or {}).get('generation_payload_order'),
    'scene_selected_model_debug': (scene_payload.get('fashion_debug') or {}).get('selected_model'),
    'captured_plan_generation_payloads': captured['plan_generation_payloads'],
    'generate_status': generate_response.status_code,
    'generate_success': generate_payload.get('success'),
    'generate_error': generate_payload.get('error'),
    'generate_payload_order': (generate_payload.get('fashion_debug') or {}).get('generation_payload_order'),
    'generate_selected_model_debug': (generate_payload.get('fashion_debug') or {}).get('selected_model'),
    'captured_generate_generation_payloads': captured['generate_generation_payloads'],
    'reference_images': generate_payload.get('reference_images'),
    'fashion_selection': generate_payload.get('fashion_selection'),
    'generate_text_type': captured['generate_text_type'],
    'generate_image_type': captured['generate_image_type'],
    'prompt_contains_model_anchor': '当前已选模特身份锚点' in (captured['generate_prompt'] or ''),
    'prompt_contains_no_text_rule': '严禁生成任何新增可见文字元素' in (captured['generate_prompt'] or ''),
    'prompt_contains_model_image_rule': '模特图只负责锁定穿着者' in (captured['generate_prompt'] or ''),
    'prompt_excerpt': (captured['generate_prompt'] or '')[:1200],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
