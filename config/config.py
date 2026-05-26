"""
运行时配置模块：仅保留数据库路径；其余配置由 init_runtime_settings() 从 SQLite 加载。
"""

from __future__ import annotations

import os

DATABASE_CONFIG = {
    'db_path': os.environ.get('ROBOT_DB_PATH', 'data/rebate_bot.db'),
}

# 业务代码 import 的配置名（值由数据库填充）
CONFIG_ATTRS = [
    'WECHAT_CONFIG',
    'ANTI_BAN_CONFIG',
    'SCHEDULE_CONFIG',
    'DEEPSEEK_CONFIG',
    'REBATE_CONFIG',
    'LOCAL_LIFE_CONFIG',
    'DIGITAL_RIGHTS_CONFIG',
    'TRAVEL_CONFIG',
    'COMMISSION_CONFIG',
    'CHECKIN_CONFIG',
    'COMMANDS',
    'ORDER_SYNC_CONFIG',
    'ADMIN_CONFIG',
    'LOG_CONFIG',
    'OTHER_CONFIG',
    'API_SERVER_CONFIG',
    'ADMIN_PANEL_CONFIG',
    'SENSITIVE_WORDS',
]

_LIST_ATTRS = {'SENSITIVE_WORDS'}
_DICT_ATTRS = {a for a in CONFIG_ATTRS if a not in _LIST_ATTRS}

for _name in _DICT_ATTRS:
    globals()[_name] = {}

SENSITIVE_WORDS: list = []

# CONFIG_ATTRS 含 DATABASE_CONFIG 的同步在 settings_store 中单独处理
CONFIG_ATTRS_WITH_DB = [*CONFIG_ATTRS, 'DATABASE_CONFIG']
