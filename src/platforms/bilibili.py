"""B站会员购 / 商业推广 API"""

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


class BilibiliClient:
    """
    B站会员购 CPS 需申请商业合作接口。
    支持在 config 中配置 api_url（合作伙伴专属网关），否则使用开放平台通用转链。
    """
    DEFAULT_API_URL = 'https://api.bilibili.com/x/open/cps/link/convert'

    def __init__(self):
        cfg = REBATE_CONFIG['bilibili']
        self.app_key = cfg['app_key']
        self.app_secret = cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')
        self.api_url = cfg.get('api_url', self.DEFAULT_API_URL)
        self.access_token = cfg.get('access_token', '')

    def _configured(self):
        return not is_placeholder(self.app_key)

    def _sign(self, params: dict) -> str:
        keys = sorted(params.keys())
        raw = self.app_secret + ''.join(f'{k}{params[k]}' for k in keys) + self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('bilibili', ['app_key'])

        ts = str(int(time.time()))
        params = {
            'appkey': self.app_key,
            'url': url,
            'pid': self.pid,
            'ts': ts,
        }
        if self.access_token and not is_placeholder(self.access_token):
            params['access_token'] = self.access_token
        if self.app_secret and not is_placeholder(self.app_secret):
            params['sign'] = self._sign(params)

        resp = await http_request('POST', self.api_url, json=params)
        result = parse_json_response(resp)

        if result.get('code') not in (0, '0', 200):
            return api_error(
                'bilibili',
                result.get('message') or 'B站转链失败，请确认已申请会员购 CPS 并配置 api_url/access_token',
                result,
            )

        data = result.get('data') or result
        rebate_url = data.get('convert_url') or data.get('link') or data.get('url', '')
        if not rebate_url:
            return api_error('bilibili', 'B站未返回推广链接', result)

        return success_result(
            'bilibili',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('title', 'B站会员购'),
            original_price=float(data.get('price') or 0),
            commission=float(data.get('commission') or 0),
        )
