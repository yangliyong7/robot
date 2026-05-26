"""管理后台配置 schema：字段结构来自数据库 app_config，不读代码里的 defaults。"""

from __future__ import annotations

import copy
import re
from typing import Any

SECRET_KEY_PATTERN = re.compile(
    r'(secret|token|password|sign_key|api_key|client_secret|app_secret|top_app_secret|access_token)',
    re.I,
)

MVP_PLATFORMS = ('taobao', 'jd', 'pdd')

MVP_COMMISSION_KEYS = ('taobao_rate', 'jd_rate', 'pdd_rate', 'min_withdraw')

MVP_ORDER_SYNC_KEYS = (
    'enabled',
    'only_bot_convert_orders',
    'interval_minutes',
    'lookback_minutes',
    'settle_on_confirm',
    'match_within_days',
)

MVP_WECHAT_KEYS = (
    'enabled',
    'passive_mode',
    'listen_private',
    'listen_groups',
    'group_reply_mode',
    'listen_targets',
    'listen_blacklist',
    'bot_display_names',
    'my_nickname',
    'poll_interval_seconds',
    'filter_mute',
)

MVP_ANTI_BAN_KEYS = (
    'min_reply_interval_seconds',
    'max_replies_per_minute',
    'random_delay_min',
    'random_delay_max',
    'max_group_msgs_per_hour',
)

MVP_ADMIN_PANEL_KEYS = ('enabled', 'password', 'session_secret')

MVP_ADMIN_KEYS = ('admin_wxids', 'admin_nickname_keywords')

MVP_REBATE_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    'taobao': ('app_id', 'app_secret', 'pid', 'adzone_id', 'top_app_key', 'top_app_secret'),
    'jd': (
        'app_key', 'app_secret', 'union_id', 'position_id',
        'promotion_method', 'chain_type', 'site_id',
    ),
    'pdd': ('client_id', 'client_secret', 'pid'),
}

FIELD_LABELS: dict[str, str] = {
    'min_withdraw': '最低提现金额（元）',
    'enabled': '启用',
    'only_bot_convert_orders': '仅结算机器人转链订单',
    'interval_minutes': '同步间隔（分钟）',
    'lookback_minutes': '回溯窗口（分钟）',
    'settle_on_confirm': '确认收货后自动结算',
    'match_within_days': '订单匹配天数',
    'host': '监听地址',
    'port': '监听端口',
    'api_token': 'API Token',
    'passive_mode': '被动模式（无关闲聊不回复）',
    'listen_private': '监听私聊',
    'listen_groups': '监听群聊',
    'group_reply_mode': '群聊回复模式（link_only/at_me_only/all）',
    'listen_targets': '仅监听名单（逗号分隔，留空=全部）',
    'listen_blacklist': '黑名单（逗号分隔）',
    'bot_display_names': '机器人昵称（用于群@识别，逗号分隔）',
    'my_nickname': '本机微信昵称',
    'poll_interval_seconds': '轮询间隔（秒）',
    'filter_mute': '忽略免打扰会话',
    'min_reply_interval_seconds': '同一聊天最小回复间隔（秒）',
    'max_replies_per_minute': '每分钟最大回复数',
    'random_delay_min': '回复随机延迟下限（秒）',
    'random_delay_max': '回复随机延迟上限（秒）',
    'max_group_msgs_per_hour': '单群每小时最大回复数',
    'admin_wxids': '管理员微信号（逗号分隔）',
    'admin_nickname_keywords': '管理员昵称关键词（逗号分隔）',
    'password': '登录密码',
    'session_secret': 'Session 签名密钥',
    'promotion_method': '转链方式',
    'chain_type': '链接类型',
}

PLATFORM_LABELS: dict[str, str] = {
    'taobao': '淘宝 / 好单库',
    'jd': '京东联盟',
    'pdd': '拼多多',
}


def _is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_PATTERN.search(key))


def _infer_type(key: str, value: Any) -> str:
    if _is_secret_key(key):
        return 'secret'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'int'
    if isinstance(value, float):
        return 'float'
    return 'text'


def _field_label(key: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    if key.endswith('_rate'):
        name = {'taobao': '淘宝', 'jd': '京东', 'pdd': '拼多多'}.get(
            key.replace('_rate', ''), key.replace('_rate', '')
        )
        return f'{name} 返利比例'
    return key


def _ordered_keys(data: dict[str, Any], first: tuple[str, ...] = ()) -> list[str]:
    keys: list[str] = [k for k in first if k in data]
    keys.extend(sorted(k for k in data if k not in keys))
    return keys


def _fields_from_dict(data: dict[str, Any], *, first: tuple[str, ...] = ()) -> list[dict]:
    fields = []
    for key in _ordered_keys(data, first):
        value = data[key]
        ftype = _infer_type(key, value)
        field: dict[str, Any] = {
            'key': key,
            'label': _field_label(key),
            'type': ftype,
        }
        if ftype == 'float' and key.endswith('_rate'):
            field.update({'min': 0, 'max': 1, 'step': 0.01})
        elif ftype == 'float':
            field['step'] = 'any'
        if key == 'min_withdraw':
            field['min'] = 0.01
        if key == 'interval_minutes':
            field.update({'min': 1, 'max': 1440})
        if key == 'lookback_minutes':
            field.update({'min': 5, 'max': 10080})
        if key == 'match_within_days':
            field.update({'min': 1, 'max': 90})
        if key == 'promotion_method':
            field['hint'] = 'byunionid | common | auto'
        fields.append(field)
    return fields


def _subset_from_db(raw: dict | None, keys: tuple[str, ...]) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    merged_keys = sorted(set(keys) | set(src.keys()))
    return {k: src.get(k, '') for k in merged_keys}


def build_settings_schema(config_data: dict[str, Any] | None = None) -> list[dict]:
    """根据数据库中的 JSON 生成表单字段；库中无该项时仅展示 MVP 字段名（空值）。"""
    data = config_data or {}

    sections: list[dict] = [
        {
            'id': 'commission',
            'title': '返利与提现',
            'description': '三平台返利比例、最低提现金额',
            'config_attr': 'COMMISSION_CONFIG',
            'fields': _fields_from_dict(
                _subset_from_db(data.get('COMMISSION_CONFIG'), MVP_COMMISSION_KEYS),
                first=('min_withdraw',),
            ),
        },
        {
            'id': 'order_sync',
            'title': '订单同步',
            'description': '联盟订单拉取与自动结算返利',
            'config_attr': 'ORDER_SYNC_CONFIG',
            'fields': _fields_from_dict(_subset_from_db(data.get('ORDER_SYNC_CONFIG'), MVP_ORDER_SYNC_KEYS)),
        },
        {
            'id': 'wechat',
            'title': '微信机器人',
            'description': 'wxauto 监听与回复策略（Windows PC 微信）',
            'config_attr': 'WECHAT_CONFIG',
            'fields': _fields_from_dict(_subset_from_db(data.get('WECHAT_CONFIG'), MVP_WECHAT_KEYS)),
        },
        {
            'id': 'anti_ban',
            'title': '防封限流',
            'description': '回复频率与随机延迟',
            'config_attr': 'ANTI_BAN_CONFIG',
            'fields': _fields_from_dict(_subset_from_db(data.get('ANTI_BAN_CONFIG'), MVP_ANTI_BAN_KEYS)),
        },
        {
            'id': 'admin',
            'title': '管理员',
            'description': '可在微信内执行提现审核等指令的账号',
            'config_attr': 'ADMIN_CONFIG',
            'fields': _fields_from_dict(_subset_from_db(data.get('ADMIN_CONFIG'), MVP_ADMIN_KEYS)),
        },
        {
            'id': 'admin_panel',
            'title': '管理后台',
            'description': '本页面登录密码',
            'config_attr': 'ADMIN_PANEL_CONFIG',
            'fields': _fields_from_dict(_subset_from_db(data.get('ADMIN_PANEL_CONFIG'), MVP_ADMIN_PANEL_KEYS)),
        },
    ]

    rebate = data.get('REBATE_CONFIG') if isinstance(data.get('REBATE_CONFIG'), dict) else {}
    for platform in MVP_PLATFORMS:
        platform_raw = rebate.get(platform) if isinstance(rebate.get(platform), dict) else {}
        template_keys = MVP_REBATE_FIELD_KEYS.get(platform, ())
        sections.append({
            'id': f'rebate_{platform}',
            'title': PLATFORM_LABELS.get(platform, platform),
            'description': f'{PLATFORM_LABELS.get(platform, platform)} 联盟密钥',
            'config_attr': 'REBATE_CONFIG',
            'nested_key': platform,
            'fields': _fields_from_dict(_subset_from_db(platform_raw, template_keys)),
        })

    return sections


def build_settings_tree(config_data: dict[str, Any] | None = None) -> list[dict]:
    sections = build_settings_schema(config_data)
    by_id = {s['id']: s for s in sections}

    def leaf(section_id: str) -> dict:
        return {
            'type': 'section',
            'section_id': section_id,
            'title': by_id[section_id]['title'],
        }

    def folder(folder_id: str, title: str, section_ids: list[str]) -> dict:
        return {
            'type': 'folder',
            'id': folder_id,
            'title': title,
            'children': [leaf(sid) for sid in section_ids if sid in by_id],
        }

    return [
        folder('rebate', '返利与提现', ['commission', 'order_sync']),
        folder('platform', '联盟密钥', ['rebate_taobao', 'rebate_jd', 'rebate_pdd']),
        folder('system', '系统', ['wechat', 'anti_ban', 'admin', 'admin_panel']),
    ]
