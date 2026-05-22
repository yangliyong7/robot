"""抖音精选联盟 / 抖店开放平台真实 API"""

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


class DouyinClient:
    """
    抖店精选联盟转链
    文档: https://op.jinritemai.com/ (buyin / alliance 相关接口)
    需在 config 配置 access_token（OAuth 授权后获取）
    """
    API_URL = 'https://openapi-fxg.jinritemai.com/alliance/product/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['douyin']
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']
        self.pid = cfg.get('pid', '')
        self.access_token = cfg.get('access_token', '')

    def _configured(self):
        if is_placeholder(self.app_key) or is_placeholder(self.app_secret):
            return False
        return not is_placeholder(self.access_token)

    def _sign(self, method: str, param_json: str, timestamp: str) -> str:
        raw = f'{self.app_secret}app_key{self.app_key}method{method}param_json{param_json}timestamp{timestamp}v2{self.app_secret}'
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('douyin', ['app_key', 'app_secret', 'access_token'])

        method = 'alliance.product.link.convert'
        timestamp = str(int(time.time()))
        param = {'product_url': url, 'pid': self.pid}
        param_json = json.dumps(param, ensure_ascii=False, separators=(',', ':'))
        sign = self._sign(method, param_json, timestamp)

        body = {
            'app_key': self.app_key,
            'method': method,
            'param_json': param_json,
            'timestamp': timestamp,
            'v': '2',
            'sign': sign,
            'access_token': self.access_token,
        }
        resp = await http_request('POST', self.API_URL, json=body)
        result = parse_json_response(resp)

        data = result.get('data') or result
        if result.get('code') not in (0, 10000, '0', '10000') and not data.get('product_url'):
            return api_error('douyin', result.get('msg') or result.get('message') or str(result), result)

        rebate_url = data.get('product_url') or data.get('deeplink') or data.get('share_url', '')
        if not rebate_url:
            return api_error('douyin', '未返回抖音推广链接', result)

        return success_result(
            'douyin',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('product_name', '抖音商品'),
            original_price=float(data.get('price') or 0) / 100 if data.get('price') else 0,
            commission=float(data.get('commission') or data.get('cos_fee') or 0),
        )
