import json
import os

from config import get_supabase_setting_json


DEFAULT_POINTS_RULES = {
    'suite': {
        'key': 'suite',
        'label': '套图',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'output_count',
    },
    'mode2': {
        'key': 'mode2',
        'label': 'AI 生图',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'output_count',
    },
    'aplus': {
        'key': 'aplus',
        'label': 'A+ 模块',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'selected_modules_count',
    },
    'fashion': {
        'key': 'fashion',
        'label': '服饰场景',
        'unit_cost': 1,
        'minimum_cost': 1,
        'metric': 'selected_scene_count',
    },
}


ALLOWED_POINTS_RULE_METRICS = {
    'output_count',
    'selected_modules_count',
    'selected_scene_count',
}


POINTS_RULE_SETTING_KEYS = {
    'suite': 'POINTS_RULE_SUITE',
    'mode2': 'POINTS_RULE_MODE2',
    'aplus': 'POINTS_RULE_APLUS',
    'fashion': 'POINTS_RULE_FASHION',
}


def normalize_points_rule(mode: str, rule_payload) -> dict:
    default_rule = dict(DEFAULT_POINTS_RULES.get(mode, DEFAULT_POINTS_RULES['suite']))
    if not isinstance(rule_payload, dict):
        return default_rule

    normalized_rule = dict(default_rule)
    normalized_rule['key'] = str(rule_payload.get('key') or default_rule['key']).strip() or default_rule['key']
    normalized_rule['label'] = str(rule_payload.get('label') or default_rule['label']).strip() or default_rule['label']

    try:
        normalized_rule['unit_cost'] = max(int(rule_payload.get('unit_cost', default_rule['unit_cost'])), 0)
    except (TypeError, ValueError):
        normalized_rule['unit_cost'] = default_rule['unit_cost']

    try:
        normalized_rule['minimum_cost'] = max(int(rule_payload.get('minimum_cost', default_rule['minimum_cost'])), 0)
    except (TypeError, ValueError):
        normalized_rule['minimum_cost'] = default_rule['minimum_cost']

    metric = str(rule_payload.get('metric') or default_rule['metric']).strip()
    normalized_rule['metric'] = metric if metric in ALLOWED_POINTS_RULE_METRICS else default_rule['metric']
    return normalized_rule


def _get_env_points_rule_json(mode: str) -> dict | None:
    setting_key = POINTS_RULE_SETTING_KEYS.get(mode)
    if not setting_key:
        return None
    raw_value = os.getenv(setting_key, '').strip()
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


def get_points_rules() -> dict[str, dict]:
    rules: dict[str, dict] = {}
    for mode in POINTS_RULE_SETTING_KEYS:
        env_rule = _get_env_points_rule_json(mode)
        if env_rule is not None:
            rules[mode] = normalize_points_rule(mode, env_rule)
        else:
            rules[mode] = normalize_points_rule(mode, DEFAULT_POINTS_RULES[mode])
    return rules


def get_points_rule(mode: str) -> dict:
    normalized_mode = str(mode or '').strip().lower()
    rules = get_points_rules()
    return rules.get(normalized_mode, rules['suite'])


def calculate_points_cost(mode: str, *, output_count: int = 0, selected_modules_count: int = 0, selected_scene_count: int = 0) -> tuple[int, dict]:
    rule = get_points_rule(mode)
    metrics = {
        'output_count': max(int(output_count or 0), 0),
        'selected_modules_count': max(int(selected_modules_count or 0), 0),
        'selected_scene_count': max(int(selected_scene_count or 0), 0),
    }
    base_count = max(metrics.get(rule['metric'], 0), 1)
    unit_cost = max(int(rule.get('unit_cost') or 0), 0)
    minimum_cost = max(int(rule.get('minimum_cost') or 0), 0)
    total_cost = max(base_count * unit_cost, minimum_cost)
    return total_cost, {
        **rule,
        'base_count': base_count,
        'cost': total_cost,
        'metrics': metrics,
    }


def build_points_consume_payload(mode: str, *, output_count: int = 0, selected_modules_count: int = 0, selected_scene_count: int = 0, transaction_type: str = 'consume', reason: str = '', metadata: dict | None = None) -> dict:
    total_cost, rule_payload = calculate_points_cost(
        mode,
        output_count=output_count,
        selected_modules_count=selected_modules_count,
        selected_scene_count=selected_scene_count,
    )
    return {
        'amount': total_cost,
        'mode': str(mode or '').strip().lower() or 'suite',
        'type': str(transaction_type or 'consume').strip() or 'consume',
        'reason': str(reason or '').strip(),
        'metadata': metadata if isinstance(metadata, dict) else {},
        'rule': rule_payload,
    }
