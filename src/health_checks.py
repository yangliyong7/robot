from __future__ import annotations

from typing import Dict, List, Tuple

from config.config import ORDER_SYNC_CONFIG, REBATE_CONFIG, WECHAT_CONFIG
from src.platforms.base import is_placeholder


def _missing(keys: List[str], cfg: dict) -> List[str]:
    miss = []
    for k in keys:
        v = cfg.get(k)
        if v is None or v == '' or is_placeholder(str(v)):
            miss.append(k)
    return miss


def validate_runtime_config() -> List[Tuple[str, str, str, Dict]]:
    """
    返回 (key, severity, message, detail) 列表，用于写入后台健康页。
    不做网络请求，只做本地配置可用性检查。
    """
    out: List[Tuple[str, str, str, Dict]] = []

    # 订单同步
    if not ORDER_SYNC_CONFIG.get('enabled', True):
        out.append(('order_sync', 'warn', '订单同步未启用', {'enabled': False}))
    else:
        out.append(('order_sync', 'ok', '订单同步已启用', {'enabled': True}))

    # wxauto
    if not WECHAT_CONFIG.get('enabled', True):
        out.append(('wxauto', 'warn', '微信机器人未启用（WECHAT_CONFIG.enabled=false）', {}))

    # 好单库（淘宝订单）
    hdk = REBATE_CONFIG.get('haodanku', {}) if isinstance(REBATE_CONFIG.get('haodanku'), dict) else {}
    miss = _missing(['app_id', 'app_secret', 'tb_name'], hdk)
    if miss:
        out.append(('taobao_orders', 'warn', f'淘宝订单查询（好单库）缺少配置: {", ".join(miss)}', {'missing': miss}))
    else:
        out.append(('taobao_orders', 'ok', '淘宝订单查询（好单库）配置完整', {}))

    # 京东转链（是否可用只看字段完整性；权限需运行时报错再告警）
    jd = REBATE_CONFIG.get('jd', {}) if isinstance(REBATE_CONFIG.get('jd'), dict) else {}
    miss_base = _missing(['app_key', 'app_secret'], jd)
    if miss_base:
        out.append(('jd_convert', 'warn', f'京东联盟缺少配置: {", ".join(miss_base)}', {'missing': miss_base}))
    else:
        method = (jd.get('promotion_method') or 'byunionid').lower()
        if method == 'common':
            miss = _missing(['site_id'], jd)
            if miss:
                out.append(('jd_convert', 'warn', '京东转链(common)未配置 site_id', {'promotion_method': method}))
            else:
                out.append(('jd_convert', 'ok', '京东转链(common)已配置（权限仍需实测）', {'promotion_method': method}))
        elif method == 'byunionid':
            miss = _missing(['union_id', 'position_id'], jd)
            if miss:
                out.append(('jd_convert', 'warn', f'京东转链(byunionid)缺少: {", ".join(miss)}', {'promotion_method': method}))
            else:
                out.append(('jd_convert', 'ok', '京东转链(byunionid)已配置（权限仍需实测）', {'promotion_method': method}))
        else:
            out.append(('jd_convert', 'ok', '京东转链(auto)已配置（权限仍需实测）', {'promotion_method': method}))

    # 拼多多
    pdd = REBATE_CONFIG.get('pdd', {}) if isinstance(REBATE_CONFIG.get('pdd'), dict) else {}
    miss = _missing(['client_id', 'client_secret', 'pid'], pdd)
    if miss:
        out.append(('pdd_orders', 'warn', f'拼多多联盟缺少配置: {", ".join(miss)}', {'missing': miss}))
    else:
        out.append(('pdd_orders', 'ok', '拼多多联盟配置完整', {}))

    return out

