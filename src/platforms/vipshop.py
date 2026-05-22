"""唯品会联盟 ADP 开放平台真实 API"""

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


class VipshopClient:
    """
    唯品会联盟 genByVIPUrl 转链
    文档: https://union.vip.com / vipapis ADP
    """
    API_URL = 'https://gw.vipapis.com'

    def __init__(self):
        cfg = REBATE_CONFIG['vipshop']
        self.app_key = cfg['app_key']
        self.app_secret = cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')
        self.access_token = cfg.get('access_token', '')

    def _configured(self):
        if is_placeholder(self.app_key):
            return False
        return not is_placeholder(self.access_token)

    async def convert(self, url: str) -> dict:
        if not self._configured():
            return config_missing('vipshop', ['app_key', 'access_token'])

        # VIP OSP 风格请求体
        service = 'com.vip.adp.api.open.service.UnionUrlV2Service'
        method = 'genByVIPUrl'
        request_body = {
            'request': {
                'openId': self.pid or 'rebate_bot',
                'realUrl': url,
                'adCode': self.pid,
            }
        }
        params = {
            'service': service,
            'method': method,
            'version': '1.0.0',
            'appKey': self.app_key,
            'timestamp': str(int(time.time() * 1000)),
            'format': 'JSON',
            'accessToken': self.access_token,
        }
        sign_raw = self.app_secret + json.dumps(request_body, ensure_ascii=False, separators=(',', ':')) + params['timestamp']
        params['sign'] = hashlib.md5(sign_raw.encode('utf-8')).hexdigest().upper()

        resp = await http_request(
            'POST',
            f'{self.API_URL}/',
            params=params,
            json=request_body,
            headers={'Content-Type': 'application/json'},
        )
        result = parse_json_response(resp)

        rebate_url = (
            deep_get(result, 'result', 'url')
            or deep_get(result, 'data', 'url')
            or result.get('url')
        )
        if not rebate_url:
            return api_error('vipshop', result.get('returnMessage') or '唯品会转链失败', result)

        return success_result(
            'vipshop',
            rebate_url=rebate_url,
            original_url=url,
            title='唯品会商品',
            commission=float(deep_get(result, 'result', 'commission') or 0),
        )
