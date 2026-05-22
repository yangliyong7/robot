"""
联盟 API 公共基础：配置校验、HTTP 请求、结果规范化
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

PLACEHOLDER_MARKERS = ('your_', 'YOUR_', 'xxx', 'placeholder')


def is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    if not s:
        return True
    return any(s.startswith(m) for m in PLACEHOLDER_MARKERS)


def config_missing(platform: str, fields: list) -> Dict:
    return {
        'success': False,
        'platform': platform,
        'message': f'请先在 config/config.py 配置 {platform} 联盟密钥: {", ".join(fields)}',
    }


def api_error(platform: str, message: str, raw: Any = None) -> Dict:
    result = {'success': False, 'platform': platform, 'message': message}
    if raw is not None:
        result['raw'] = raw
    return result


def success_result(
    platform: str,
    rebate_url: str,
    original_url: str,
    title: str = '',
    original_price: float = 0,
    final_price: float = 0,
    coupon_amount: float = 0,
    commission: float = 0,
    **extra,
) -> Dict:
    data = {
        'success': True,
        'platform': platform,
        'title': title or '商品',
        'original_price': float(original_price or 0),
        'final_price': float(final_price if final_price else max(0, (original_price or 0) - (coupon_amount or 0))),
        'coupon_amount': float(coupon_amount or 0),
        'commission': float(commission or 0),
        'rebate_url': rebate_url,
        'original_url': original_url,
    }
    data.update(extra)
    if not data['final_price'] and data['original_price']:
        data['final_price'] = max(0, data['original_price'] - data['coupon_amount'])
    return data


def md5_sign(params: Dict, secret: str, secret_wrap: bool = True) -> str:
    """通用 MD5 签名：secret + key1val1key2val2 + secret"""
    items = sorted((k, v) for k, v in params.items() if k != 'sign' and v is not None)
    sign_str = secret if secret_wrap else ''
    for k, v in items:
        sign_str += f'{k}{v}'
    if secret_wrap:
        sign_str += secret
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()


def extract_first_url(text: str) -> Optional[str]:
    pattern = r'https?://[^\s<>"\'\[\]]+'
    urls = re.findall(pattern, text or '')
    return urls[0] if urls else None


async def http_request(method: str, url: str, **kwargs) -> requests.Response:
    """在线程池中执行同步 HTTP，避免阻塞事件循环"""
    loop = asyncio.get_event_loop()

    def _do():
        return requests.request(method, url, timeout=kwargs.pop('timeout', 15), **kwargs)

    return await loop.run_in_executor(None, _do)


def parse_json_response(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {'_raw_text': resp.text[:500]}


def deep_get(data: Any, *keys, default=None):
    cur = data
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int) and len(cur) > key:
            cur = cur[key]
        else:
            return default
        if cur is None:
            return default
    return cur
