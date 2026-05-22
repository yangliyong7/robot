"""网易严选联盟真实 API"""

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


class YanxuanClient:
    """
    网易严选联盟转链
    申请: https://union.you.163.com/
    """
    API_URL = 'https://union.you.163.com/api/open/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['yanxuan']
        self.app_key = cfg['app_key']
        self.app_secret = cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')

    def _configured(self):
        return not is_placeholder(self.app_key)

    def _sign(self, params: dict) -> str:
        keys = sorted(params.keys())
        raw = self.app_secret + ''.join(f'{k}{params[k]}' for k in keys) + self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('yanxuan', ['app_key'])

        ts = str(int(time.time() * 1000))
        params = {
            'appKey': self.app_key,
            'pid': self.pid,
            'sourceUrl': url,
            'timestamp': ts,
        }
        if self.app_secret and not is_placeholder(self.app_secret):
            params['sign'] = self._sign(params)

        resp = await http_request('POST', self.API_URL, json=params)
        result = parse_json_response(resp)

        if result.get('code') not in (0, '0', 200, '200', 'SUCCESS'):
            return api_error('yanxuan', result.get('msg') or result.get('message') or str(result), result)

        data = result.get('data') or result
        rebate_url = data.get('targetUrl') or data.get('link') or data.get('convertUrl', '')
        if not rebate_url:
            return api_error('yanxuan', '严选联盟未返回推广链接', result)

        return success_result(
            'yanxuan',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('itemName', '网易严选'),
            original_price=float(data.get('retailPrice') or data.get('price') or 0),
            commission=float(data.get('commission') or 0),
        )
