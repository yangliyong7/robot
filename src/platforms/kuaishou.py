"""快手分销 / 快手电商联盟真实 API"""

import hashlib
import json
import logging
import time

from config.config import REBATE_CONFIG
from src.platforms.base import (
    api_error,
    config_missing,
    deep_get,
    http_request,
    is_placeholder,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)


class KuaishouClient:
    """
    快手开放平台 CPS 转链
    文档: https://open.kuaishou.com/
    """
    API_URL = 'https://open.kuaishou.com/openapi/cps/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['kuaishou']
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']
        self.pid = cfg.get('pid', '')
        self.access_token = cfg.get('access_token', '')

    def _configured(self):
        if is_placeholder(self.app_key) or is_placeholder(self.app_secret):
            return False
        return not is_placeholder(self.access_token)

    def _sign(self, params: dict) -> str:
        keys = sorted(params.keys())
        raw = self.app_secret + ''.join(f'{k}{params[k]}' for k in keys) + self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('kuaishou', ['app_key', 'app_secret', 'access_token'])

        ts = str(int(time.time()))
        body = {
            'url': url,
            'pid': self.pid,
            'access_token': self.access_token,
            'app_id': self.app_key,
            'timestamp': ts,
        }
        body['sign'] = self._sign({k: v for k, v in body.items() if k != 'sign'})

        resp = await http_request('POST', self.API_URL, json=body)
        result = parse_json_response(resp)

        if result.get('result') != 1 and result.get('code') not in (0, '0'):
            return api_error('kuaishou', result.get('error_msg') or result.get('message') or str(result), result)

        data = result.get('data') or result
        rebate_url = data.get('cps_link') or data.get('link') or deep_get(data, 'convert_result', 'link')
        if not rebate_url:
            return api_error('kuaishou', '快手未返回推广链接', result)

        return success_result(
            'kuaishou',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('item_title', '快手商品'),
            original_price=float(data.get('price') or 0) / 100 if data.get('price') else 0,
            commission=float(data.get('commission_amount') or 0),
        )
