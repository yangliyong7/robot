"""REBATE_CONFIG 读取辅助：好单库与淘宝 TOP 分表存储，兼容旧版合并配置。"""

from __future__ import annotations

from typing import Any

from config.config import REBATE_CONFIG

def _rebate_root() -> dict[str, Any]:
    return REBATE_CONFIG if isinstance(REBATE_CONFIG, dict) else {}


def get_haodanku_config() -> dict[str, Any]:
    root = _rebate_root()
    hdk = root.get('haodanku') if isinstance(root.get('haodanku'), dict) else {}
    legacy = root.get('taobao') if isinstance(root.get('taobao'), dict) else {}
    return {
        'app_id': hdk.get('app_id') or legacy.get('app_id') or '',
        'app_secret': hdk.get('app_secret') or legacy.get('app_secret') or '',
        'tb_name': hdk.get('tb_name') or legacy.get('tb_name') or '',
    }


def get_taobao_top_config() -> dict[str, Any]:
    root = _rebate_root()
    tb = root.get('taobao') if isinstance(root.get('taobao'), dict) else {}
    return {
        'top_app_key': tb.get('top_app_key') or tb.get('app_key') or '',
        'top_app_secret': tb.get('top_app_secret') or '',
        'adzone_id': tb.get('adzone_id', ''),
        'pid': tb.get('pid', ''),
        'convert_mode': (tb.get('convert_mode') or 'item'),
    }
