"""管理后台配置 schema：字段结构来自数据库 app_config，不读代码里的 defaults。"""

from __future__ import annotations

import copy
import re
from typing import Any

SECRET_KEY_PATTERN = re.compile(
    r'(secret|token|password|sign_key|api_key|client_secret|app_secret|top_app_secret|access_token)',
    re.I,
)

MVP_PLATFORMS = ('haodanku', 'taobao', 'jd', 'pdd')

MVP_COMMISSION_KEYS = ('min_withdraw', 'taobao_rate', 'jd_rate', 'pdd_rate')

MVP_CHECKIN_KEYS = ('base_reward', 'continuous_rewards', 'total_rewards', 'start_hour', 'end_hour')

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
    'login_mode',
    'auto_accept_friend',
    'auto_accept_group',
    'passive_mode',
    'listen_private',
    'listen_groups',
    'listen_newmessage_first',
    'listen_recent_sessions',
    'listen_chats',
    'group_reply_mode',
    'poll_interval_seconds',
    'poll_interval_jitter',
    'private_msg_interval',
    'filter_mute',
    'listen_targets',
    'listen_blacklist',
    'bot_display_names',
    'my_nickname',
    'send_delay_min',
    'send_delay_max',
    'notification_poll_seconds',
    'compare_public_base_url',
)

MVP_ANTI_BAN_KEYS = (
    'min_reply_interval_seconds',
    'max_replies_per_minute',
    'random_delay_min',
    'random_delay_max',
    'max_group_msgs_per_hour',
    'max_msgs_per_hour_per_group',
    'enable_response_variety',
    'group_msg_interval',
    'group_defaults',
    'group_settings',
    'ignore_nickname_keywords',
    'ignore_wxids',
    'night_start',
    'night_end',
    'night_delay_multiplier',
    'passive_extra_keywords',
)

# 布尔字段（库中为空时也渲染为复选框）
BOOL_FIELD_KEYS = frozenset({
    'enabled',
    'passive_mode',
    'listen_private',
    'listen_groups',
    'filter_mute',
    'only_bot_convert_orders',
    'settle_on_confirm',
    'enable_response_variety',
    'auto_accept_friend',
    'auto_accept_group',
    'listen_newmessage_first',
})

# 逗号分隔列表字段
STRING_LIST_FIELD_KEYS = frozenset({
    'listen_targets',
    'listen_blacklist',
    'listen_chats',
    'bot_display_names',
    'admin_wxids',
    'admin_nickname_keywords',
    'ignore_nickname_keywords',
    'ignore_wxids',
    'passive_extra_keywords',
})

# JSON 对象字段（后台用多行 JSON 编辑）
JSON_FIELD_KEYS = frozenset({
    'group_defaults',
    'group_settings',
    'continuous_rewards',
    'total_rewards',
})

MVP_ADMIN_PANEL_KEYS = ('enabled', 'password', 'session_secret')

MVP_ADMIN_KEYS = ('admin_wxids', 'admin_nickname_keywords')

MVP_REBATE_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    'haodanku': ('app_id', 'app_secret', 'tb_name'),
    'taobao': ('top_app_key', 'top_app_secret', 'adzone_id', 'pid', 'convert_mode'),
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
    'listen_groups': '启用群聊监听',
    'group_reply_mode': '群聊回复模式',
    'listen_targets': '群聊白名单（逗号分隔群名，与微信会话列表一致）',
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
    'site_id': '网站 ID（siteId，common 转链用）',
    'union_id': '联盟 unionId',
    'position_id': '推广位 positionId',
    'app_key': 'App Key',
    'top_app_key': '淘宝开放平台 App Key',
    'top_app_secret': '淘宝开放平台 App Secret',
    'adzone_id': '推广位 adzone_id',
    'pid': '联盟 PID',
    'convert_mode': '转链模式',
    'poll_interval_jitter': '轮询间隔抖动系数',
    'private_msg_interval': '私聊最小回复间隔（秒）',
    'send_delay_min': '发送延迟下限（秒）',
    'send_delay_max': '发送延迟上限（秒）',
    'notification_poll_seconds': '通知轮询间隔（秒）',
    'compare_public_base_url': '全网比价页地址（对外）',
    'enable_response_variety': '启用回复话术多样化',
    'group_defaults': '群聊默认限流（JSON）',
    'group_msg_interval': '群消息最小间隔（秒）',
    'group_settings': '群聊单独限流（JSON）',
    'ignore_nickname_keywords': '忽略昵称关键词（逗号分隔）',
    'ignore_wxids': '忽略微信号（逗号分隔）',
    'max_msgs_per_hour_per_group': '单群每小时最大回复数',
    'night_delay_multiplier': '夜间延迟倍数',
    'night_start': '夜间开始时刻（0–23 时）',
    'night_end': '夜间结束时刻（0–23 时）',
    'passive_extra_keywords': '被动模式额外关键词（逗号分隔）',
    'login_mode': '微信登录方式',
    'auto_accept_friend': '自动通过好友申请',
    'auto_accept_group': '自动通过群邀请',
    'listen_chats': '指定监听会话（逗号分隔，留空=按策略自动）',
    'listen_recent_sessions': '自动监听最近会话数量',
    'listen_newmessage_first': '优先处理有新消息的会话',
    'base_reward': '每日基础奖励（元）',
    'continuous_rewards': '连续签到里程碑奖励（JSON）',
    'total_rewards': '累计签到里程碑奖励（JSON）',
    'start_hour': '签到开始时刻（0–23 时）',
    'end_hour': '签到结束时刻（0–23 时）',
}

FIELD_HINTS: dict[str, str] = {
    'listen_groups': '开启后仅处理「群聊白名单」中的群；白名单留空则不回复任何群消息。',
    'listen_targets': '仅控制群聊：填写与微信会话列表一致的群名（逗号分隔）。私聊不受此字段限制，默认全部监听。',
    'listen_private': '关闭后不自动回复私聊；群聊仍须开启「启用群聊监听」并在群聊白名单中填写群名。',
    'listen_blacklist': '命中黑名单的会话一律不处理（优先于白名单）。',
    'continuous_rewards': '键为连续天数、值为额外奖励（元）。例：{"3": 0.2, "7": 0.5, "15": 1.0, "30": 2.0}。仅在刚好达到该连续天数时额外发放，可与基础奖励叠加。',
    'total_rewards': '键为累计签到总天数、值为额外奖励（元）。例：{"10": 1.0, "30": 3.0, "100": 10.0}。仅在累计天数刚好达到该档位时额外发放一次，断签不影响累计天数。',
    'base_reward': '用户每天签到固定获得的基础金额，与里程碑奖励叠加。',
    'start_hour': '允许签到的开始小时（含）。与结束时刻配合使用，例如 0 与 23 表示全天可签。',
    'end_hour': '允许签到的结束小时（含）。',
}

# 固定枚举：后台渲染为下拉框（value, 显示文案）
SELECT_FIELD_OPTIONS: dict[str, list[tuple[str, str]]] = {
    'login_mode': (
        ('qrcode', '二维码扫码登录'),
        ('manual', '手动登录（已在本机登录微信）'),
    ),
    'promotion_method': (
        ('byunionid', '微信导购转链（推荐，需申请接口权限）'),
        ('common', '联盟网站转链（需已验证 site_id）'),
        ('auto', '自动切换（先导购，失败再用网站）'),
    ),
    'convert_mode': (
        ('item', '单品转链（商品详情页链接）'),
        ('general', '万能转链（淘口令 / 长链等）'),
        ('auto', '自动选择转链方式'),
    ),
    'group_reply_mode': (
        ('link_only', '仅链接 / 口令 / 关键词'),
        ('at_me_only', '仅 @ 机器人'),
        ('all', '全部群消息'),
    ),
    'chain_type': (
        ('1', '长链（完整推广链接）'),
        ('2', '短链（推荐，适合微信发送）'),
        ('3', '长链 + 短链（同时返回两种链接）'),
    ),
}

# select 字段保存到库时的值类型
SELECT_VALUE_TYPE: dict[str, str] = {
    'chain_type': 'int',
}

PLATFORM_LABELS: dict[str, str] = {
    'haodanku': '好单库（转链）',
    'taobao': '淘宝联盟',
    'jd': '京东联盟',
    'pdd': '多多进宝',
}

PLATFORM_DESCRIPTIONS: dict[str, str] = {
    'haodanku': '好单库 v3 analyze.taoword，用于日常商品转链',
    'taobao': '淘宝开放平台 TOP，用于订单同步及备用转链',
    'jd': '京东联盟密钥',
    'pdd': '拼多多多多进宝开放平台密钥，用于商品转链与佣金查询',
}

# 各平台同名字段（如 app_secret）显示不同中文名
PLATFORM_FIELD_LABELS: dict[str, dict[str, str]] = {
    'haodanku': {
        'app_id': '好单库 App ID',
        'app_secret': '好单库 App Secret',
        'tb_name': '淘宝昵称 tb_name（订单查询必填）',
    },
    'jd': {
        'app_key': '京东联盟 App Key',
        'app_secret': '京东联盟 App Secret',
    },
    'pdd': {
        'client_id': '多多进宝 client_id',
        'client_secret': '多多进宝 client_secret',
        'pid': '推广位 pid',
    },
}


def _is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_PATTERN.search(key))


def _infer_type(key: str, value: Any) -> str:
    if _is_secret_key(key):
        return 'secret'
    if key in SELECT_FIELD_OPTIONS:
        return 'select'
    if key in JSON_FIELD_KEYS or isinstance(value, dict):
        return 'json'
    if key in STRING_LIST_FIELD_KEYS or isinstance(value, list):
        return 'string_list'
    if key in BOOL_FIELD_KEYS and (value in ('', None) or isinstance(value, bool)):
        return 'bool'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'int'
    if isinstance(value, float):
        return 'float'
    return 'text'


def _field_label(key: str, platform: str | None = None) -> str:
    if platform:
        plat_labels = PLATFORM_FIELD_LABELS.get(platform, {})
        if key in plat_labels:
            return plat_labels[key]
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    if key.endswith('_rate'):
        name = {'taobao': '淘宝', 'jd': '京东', 'pdd': '多多进宝'}.get(
            key.replace('_rate', ''), key.replace('_rate', '')
        )
        return f'{name} 返利比例'
    return key


def _ordered_keys(data: dict[str, Any], first: tuple[str, ...] = ()) -> list[str]:
    keys: list[str] = [k for k in first if k in data]
    keys.extend(sorted(k for k in data if k not in keys))
    return keys


def _fields_from_dict(
    data: dict[str, Any], *, first: tuple[str, ...] = (), platform: str | None = None
) -> list[dict]:
    fields = []
    for key in _ordered_keys(data, first):
        value = data[key]
        ftype = _infer_type(key, value)
        field: dict[str, Any] = {
            'key': key,
            'label': _field_label(key, platform),
            'type': ftype,
        }
        if ftype == 'float' and key.endswith('_rate'):
            field.update({'min': 0, 'max': 1, 'step': 0.01})
        elif ftype == 'float':
            field['step'] = 'any'
        if key == 'min_withdraw':
            field['min'] = 0.01
        if key == 'base_reward':
            field['min'] = 0.01
        if key in ('start_hour', 'end_hour'):
            field.update({'min': 0, 'max': 23})
        if key == 'interval_minutes':
            field.update({'min': 1, 'max': 1440})
        if key == 'lookback_minutes':
            field.update({'min': 5, 'max': 10080})
        if key == 'match_within_days':
            field.update({'min': 1, 'max': 90})
        if key in SELECT_FIELD_OPTIONS:
            field['type'] = 'select'
            field['options'] = [
                {'value': opt_val, 'label': opt_label}
                for opt_val, opt_label in SELECT_FIELD_OPTIONS[key]
            ]
            vt = SELECT_VALUE_TYPE.get(key)
            if vt:
                field['value_type'] = vt
        if key in FIELD_HINTS:
            field['hint'] = FIELD_HINTS[key]
        fields.append(field)
    return fields


def _subset_from_db(
    raw: dict | None, keys: tuple[str, ...], *, include_extra_db_keys: bool = True
) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    if include_extra_db_keys:
        merged_keys = sorted(set(keys) | set(src.keys()))
    else:
        merged_keys = list(keys)
    return {k: src.get(k, '') for k in merged_keys}


def build_settings_schema(config_data: dict[str, Any] | None = None) -> list[dict]:
    """根据数据库中的 JSON 生成表单字段；库中无该项时仅展示 MVP 字段名（空值）。"""
    data = config_data or {}

    sections: list[dict] = [
        {
            'id': 'commission',
            'title': '返利与提现',
            'description': '淘宝、京东、多多进宝返利比例与最低提现金额',
            'config_attr': 'COMMISSION_CONFIG',
            'fields': _fields_from_dict(
                _subset_from_db(
                    data.get('COMMISSION_CONFIG'),
                    MVP_COMMISSION_KEYS,
                    include_extra_db_keys=False,
                ),
                first=MVP_COMMISSION_KEYS,
            ),
        },
        {
            'id': 'checkin',
            'title': '签到奖励配置',
            'description': '每日基础奖励、连续签到与累计签到里程碑额外奖励',
            'config_attr': 'CHECKIN_CONFIG',
            'fields': _fields_from_dict(
                _subset_from_db(data.get('CHECKIN_CONFIG'), MVP_CHECKIN_KEYS),
                first=MVP_CHECKIN_KEYS,
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
            'description': 'wxauto 监听与回复。私聊默认全部监听；群聊须在「群聊白名单」填写群名才会处理。',
            'config_attr': 'WECHAT_CONFIG',
            'fields': _fields_from_dict(
                _subset_from_db(data.get('WECHAT_CONFIG'), MVP_WECHAT_KEYS),
                first=MVP_WECHAT_KEYS,
            ),
        },
        {
            'id': 'anti_ban',
            'title': '防封限流',
            'description': '回复频率与随机延迟',
            'config_attr': 'ANTI_BAN_CONFIG',
            'fields': _fields_from_dict(
                _subset_from_db(data.get('ANTI_BAN_CONFIG'), MVP_ANTI_BAN_KEYS),
                first=MVP_ANTI_BAN_KEYS,
            ),
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
    legacy_taobao = rebate.get('taobao') if isinstance(rebate.get('taobao'), dict) else {}
    for platform in MVP_PLATFORMS:
        platform_raw = rebate.get(platform) if isinstance(rebate.get(platform), dict) else {}
        template_keys = MVP_REBATE_FIELD_KEYS.get(platform, ())
        if platform == 'haodanku':
            platform_raw = {
                k: platform_raw.get(k) or legacy_taobao.get(k, '')
                for k in template_keys
            }
        elif platform == 'taobao':
            platform_raw = {k: platform_raw.get(k, '') for k in template_keys}
        else:
            platform_raw = _subset_from_db(platform_raw, template_keys)
        plat_title = PLATFORM_LABELS.get(platform, platform)
        plat_desc = PLATFORM_DESCRIPTIONS.get(platform)
        if plat_desc is None:
            plat_desc = f'{plat_title} 联盟密钥'
        sections.append({
            'id': f'rebate_{platform}',
            'title': plat_title,
            'description': plat_desc,
            'config_attr': 'REBATE_CONFIG',
            'nested_key': platform,
            'fields': _fields_from_dict(platform_raw, first=template_keys, platform=platform),
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
        folder('rebate', '返利与提现', ['commission', 'checkin', 'order_sync']),
        folder('platform', '联盟密钥', ['rebate_haodanku', 'rebate_taobao', 'rebate_jd', 'rebate_pdd']),
        folder('system', '系统', ['wechat', 'anti_ban', 'admin', 'admin_panel']),
    ]
