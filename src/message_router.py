"""微信消息硬路由"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

CommandKind = Literal[
    'help', 'balance', 'withdraw', 'orders', 'stats', 'checkin', 'convert', 'compare'
]

COMMANDS: dict[str, re.Pattern[str]] = {
    'help': re.compile(r'^(帮助|help|\?|？|使用说明)$', re.I),
    'balance': re.compile(r'^(余额|查询余额|我的余额)$', re.I),
    'withdraw': re.compile(r'^(提现|申请提现)$', re.I),
    'orders': re.compile(r'^(订单|我的订单|查询订单)$', re.I),
    'stats': re.compile(r'^(统计|收益统计|我的收益)$', re.I),
    'checkin': re.compile(r'^(签到|打卡|每日签到)$', re.I),
    'compare': re.compile(r'^(全网比价|比价)$', re.I),
}

PASSIVE_KEYWORDS = (
    '饿了么', 'eleme', '饿了嘛', '外卖红包',
    '携程', '同程', '去哪儿', '酒店', '机票', '订票', '订房', '航班',
    '飞猪', '淘票票', '美团', '团购',
    '闲鱼', '拼多多', '京东', '淘宝', '天猫',
)


@dataclass
class RouteDecision:
    action: Literal['handle', 'ignore', 'pass']
    kind: Optional[str] = None
    content: Optional[str] = None


def has_product_intent(text: str) -> bool:
    if re.search(r'https?://', text, re.I):
        return True
    if re.search(r'【淘宝】.*?[￥¥Y]\w+[￥¥Y]', text, re.I):
        return True
    if re.search(r'【京东】.*?[￥¥Y]\w+[￥¥Y]', text, re.I):
        return True
    if re.search(r'^(找|买|搜|查)\s*[\u4e00-\u9fff\w]{1,20}', text):
        return True
    return any(kw in text for kw in PASSIVE_KEYWORDS)


def route_message(text: str, passive_mode: bool = True) -> RouteDecision:
    trimmed = (text or '').strip()
    if not trimmed:
        return RouteDecision(action='ignore')

    for kind, pattern in COMMANDS.items():
        if pattern.match(trimmed):
            return RouteDecision(action='handle', kind=kind)

    if has_product_intent(trimmed):
        return RouteDecision(action='handle', kind='convert', content=trimmed)

    if passive_mode:
        return RouteDecision(action='ignore')

    return RouteDecision(action='pass')
