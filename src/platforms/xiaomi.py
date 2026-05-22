"""小米网盟 / 小米有品联盟真实 API"""

import hashlib
import logging
import time

from config.config import REBATE_CONFIG
from src.platforms.base import (
    api_error,
    config_missing,
    http_request,
    is_placeholder,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)


class XiaomiClient:
    """
    小米联盟转链
    申请: https://union.mi.com/
    """
    API_URL = 'https://api.union.mi.com/v1/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['xiaomi']
        self.app_key = cfg['app_key']
        self.app_secret = cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')

    def _configured(self):
        return not is_placeholder(self.app_key)

    def _sign(self, params: dict) -> str:
        keys = sorted(params.keys())
        raw = ''.join(f'{k}={params[k]}&' for k in keys).rstrip('&') + self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('xiaomi', ['app_key'])

        ts = str(int(time.time()))
        params = {
            'appKey': self.app_key,
            'pid': self.pid,
            'url': url,
            'timestamp': ts,
        }
        if self.app_secret and not is_placeholder(self.app_secret):
            params['sign'] = self._sign(params)

        resp = await http_request('GET', self.API_URL, params=params)
        result = parse_json_response(resp)

        if result.get('code') not in (0, '0', 200, '200'):
            return api_error('xiaomi', result.get('message') or str(result), result)

        data = result.get('data') or result
        rebate_url = data.get('convertUrl') or data.get('link') or data.get('shortUrl', '')
        if not rebate_url:
            return api_error('xiaomi', '小米联盟未返回推广链接', result)

        return success_result(
            'xiaomi',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('goodsName', '小米有品'),
            original_price=float(data.get('price') or 0),
            commission=float(data.get('commission') or 0),
        )
