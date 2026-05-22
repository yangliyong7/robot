"""当当联盟真实 API"""

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


class DangdangClient:
    """
    当当网盟转链接口
    申请: http://union.dangdang.com/
    """
    API_URL = 'https://union.dangdang.com/openapi/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['dangdang']
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
            return config_missing('dangdang', ['app_key'])

        ts = str(int(time.time()))
        params = {
            'app_key': self.app_key,
            'pid': self.pid,
            'url': url,
            'timestamp': ts,
        }
        if self.app_secret and not is_placeholder(self.app_secret):
            params['sign'] = self._sign(params)

        resp = await http_request('GET', self.API_URL, params=params)
        result = parse_json_response(resp)

        if result.get('code') not in (0, '0', 200, '200', 'success'):
            return api_error('dangdang', result.get('message') or result.get('msg') or str(result), result)

        data = result.get('data') or result
        rebate_url = data.get('convert_url') or data.get('link') or data.get('url', '')
        if not rebate_url:
            return api_error('dangdang', '当当未返回推广链接', result)

        return success_result(
            'dangdang',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('product_name', '当当商品'),
            original_price=float(data.get('price') or 0),
            commission=float(data.get('commission') or 0),
        )
