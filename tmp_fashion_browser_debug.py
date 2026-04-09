from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
import time

url = 'http://127.0.0.1:5078/fashion'
image_path = r'E:\360MoveData\Users\Administrator\Desktop\新建文件夹\aiimagenew\1.png'
output_dir = r'E:\360MoveData\Users\Administrator\Desktop\新建文件夹\aiimagenew'
state_path = os.path.join(output_dir, 'fashion_browser_debug.json')
screenshot_path = os.path.join(output_dir, 'fashion_browser_debug.png')
selectors = {
    'upload': '#fileInput',
    'thumbs': '#thumbs .thumb',
    'generate_model': '#generateModelBtn',
    'model_card': '[data-role="select-fashion-model"]',
    'generate': '#generateBtn',
    'pose_card': '[data-role="select-fashion-pose"]',
    'selected_pose': '[data-role="select-fashion-pose"].is-selected',
    'status': '#resultStatusMessage',
    'result_card': '#resultGrid .result-card',
    'summary': '#taskSummaryLine',
}

opts = Options()
opts.add_argument('--headless=new')
opts.add_argument('--disable-gpu')
opts.add_argument('--window-size=1600,1400')
opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

driver = webdriver.Edge(options=opts)
wait = WebDriverWait(driver, 120)
summary = {'steps': []}


def log_step(name, extra=None):
    item = {'name': name, 'time': time.time()}
    if extra:
        item.update(extra)
    summary['steps'].append(item)


def text(css):
    try:
        return driver.find_element(By.CSS_SELECTOR, css).text.strip()
    except Exception:
        return ''


def click(element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    driver.execute_script('arguments[0].click();', element)


try:
    driver.get(url)
    driver.execute_script(
        """
        window.__fashionDebug = { calls: [] };
        const originalFetch = window.fetch.bind(window);
        window.fetch = async function(input, init) {
          const url = typeof input === 'string' ? input : (input && input.url) || '';
          const method = (init && init.method) || 'GET';
          const call = { url, method, startedAt: Date.now() };
          if (init && init.body instanceof FormData) {
            const bodyEntries = {};
            for (const [key, value] of init.body.entries()) {
              if (value instanceof File) {
                bodyEntries[key] = (bodyEntries[key] || []).concat([{ name: value.name, size: value.size, type: value.type }]);
              } else {
                bodyEntries[key] = value;
              }
            }
            call.body = bodyEntries;
          }
          try {
            const response = await originalFetch(input, init);
            call.status = response.status;
            call.ok = response.ok;
            try {
              const cloned = response.clone();
              call.responseText = await cloned.text();
            } catch (err) {
              call.responseText = '<<unreadable>>';
            }
            window.__fashionDebug.calls.push(call);
            return response;
          } catch (error) {
            call.fetchError = String(error);
            window.__fashionDebug.calls.push(call);
            throw error;
          }
        };
        """
    )
    log_step('page_loaded', {'title': driver.title})

    upload = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selectors['upload'])))
    upload.send_keys(image_path)
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, selectors['thumbs'])) >= 1)
    log_step('product_uploaded', {'thumb_count': len(driver.find_elements(By.CSS_SELECTOR, selectors['thumbs']))})

    click(wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selectors['generate_model']))))
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, selectors['model_card'])) >= 1)
    models = driver.find_elements(By.CSS_SELECTOR, selectors['model_card'])
    log_step('models_ready', {'model_count': len(models), 'generate_btn': text(selectors['generate'])})

    click(models[0])
    wait.until(lambda d: '生成推荐场景' in text(selectors['generate']))
    log_step('model_selected', {'generate_btn': text(selectors['generate'])})

    click(driver.find_element(By.CSS_SELECTOR, selectors['generate']))
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, selectors['pose_card'])) >= 2)
    log_step('scene_plan_ready', {
        'pose_count': len(driver.find_elements(By.CSS_SELECTOR, selectors['pose_card'])),
        'generate_btn': text(selectors['generate']),
        'status': text(selectors['status']),
    })

    for idx in [0, 1]:
        poses = driver.find_elements(By.CSS_SELECTOR, selectors['pose_card'])
        click(poses[idx])
        time.sleep(0.4)

    wait.until(lambda d: '生成服饰穿戴图' in text(selectors['generate']))
    local_before = driver.execute_script("return JSON.parse(localStorage.getItem('aiDesignState:fashion') || '{}');")
    ws_state_before = driver.execute_script("return window.fashionWorkspace && window.fashionWorkspace.getState ? window.fashionWorkspace.getState() : null;")
    log_step('poses_selected', {
        'selected_pose_count': len(driver.find_elements(By.CSS_SELECTOR, selectors['selected_pose'])),
        'generate_btn': text(selectors['generate']),
        'selected_pose_ids': local_before.get('fashionSelectedPoseIds'),
        'selected_group_ids': local_before.get('fashionSelectedSceneGroupIds'),
        'flow_step_before_generate': local_before.get('fashionFlowStep'),
        'scene_generation_state_before_generate': local_before.get('fashionSceneGenerationState'),
        'workspace_selected_pose_ids': (ws_state_before or {}).get('fashionSelectedPoseIds') if isinstance(ws_state_before, dict) else None,
        'workspace_cta': (ws_state_before or {}).get('cta') if isinstance(ws_state_before, dict) else None,
    })

    click(driver.find_element(By.CSS_SELECTOR, selectors['generate']))
    time.sleep(3)
    log_step('generate_clicked', {
        'generate_btn_after_click': text(selectors['generate']),
        'status_after_click': text(selectors['status']),
    })

    deadline = time.time() + 180
    result = None
    while time.time() < deadline:
        cards = driver.find_elements(By.CSS_SELECTOR, selectors['result_card'])
        status = text(selectors['status'])
        button_text = text(selectors['generate'])
        if cards:
            result = {
                'mode': 'success',
                'card_count': len(cards),
                'status': status,
                'generate_btn': button_text,
            }
            break
        if status and ('生成结果数量不足' in status or '失败' in status or '请稍后重试' in status or '错误' in status):
            result = {
                'mode': 'error_status',
                'status': status,
                'generate_btn': button_text,
            }
            break
        time.sleep(1)

    if result is None:
        result = {
            'mode': 'timeout',
            'status': text(selectors['status']),
            'generate_btn': text(selectors['generate']),
        }

    local_after = driver.execute_script("return JSON.parse(localStorage.getItem('aiDesignState:fashion') || '{}');")
    ws_state_after = driver.execute_script("return window.fashionWorkspace && window.fashionWorkspace.getState ? window.fashionWorkspace.getState() : null;")
    fetch_debug = driver.execute_script("return window.__fashionDebug;")
    browser_logs = driver.get_log('browser')

    summary.update({
        'result': result,
        'final_generate_btn': text(selectors['generate']),
        'final_status': text(selectors['status']),
        'task_summary_line': text(selectors['summary']),
        'local_storage_after': {
            'fashionFlowStep': local_after.get('fashionFlowStep'),
            'fashionSceneGenerationState': local_after.get('fashionSceneGenerationState'),
            'fashionSelectedPoseIds': local_after.get('fashionSelectedPoseIds'),
            'fashionSelectedSceneGroupIds': local_after.get('fashionSelectedSceneGroupIds'),
            'fashionSceneError': local_after.get('fashionSceneError'),
        },
        'workspace_state_after': ws_state_after,
        'fetch_debug': fetch_debug,
        'browser_logs': browser_logs[-20:],
    })
    driver.save_screenshot(screenshot_path)
except Exception as exc:
    summary['exception'] = repr(exc)
    summary['final_generate_btn'] = text(selectors['generate'])
    summary['final_status'] = text(selectors['status'])
    try:
        summary['fetch_debug'] = driver.execute_script("return window.__fashionDebug || null;")
    except Exception:
        pass
    try:
        driver.save_screenshot(screenshot_path)
    except Exception:
        pass
finally:
    with open(state_path, 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    driver.quit()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('STATE_PATH', state_path)
    print('SCREENSHOT_PATH', screenshot_path)
