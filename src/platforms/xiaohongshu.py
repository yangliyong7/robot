"""小红书开放平台 / 买手带货转链（Ark common_controller）"""

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

DEFAULT_API_URL = 'https://ark.xiaohongshu.com/ark/open_api/v3/common_controller'
DEFAULT_VERSION = '2.0'
# 买手/CPS 转链 method 以开放平台文档为准，可在 config 中覆盖
DEFAULT_CONVERT_METHOD = 'cps.link.convert'


class XiaohongshuClient:
    """
    小红书带货推广转链
    - 申请: https://open.xiaohongshu.com/  OAuth 获取 access_token
    - 买手/好物推荐联盟开通后，在后台确认 convert_method 并填入 config
    - api_url 可改为合作伙伴专属网关（与 bilibili 相同模式）
    """

    def __init__(self):
        cfg = REBATE_CONFIG['xiaohongshu']
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']
        self.access_token = cfg.get('access_token', '')
        self.pid = cfg.get('pid', '')
        raw_url = (cfg.get('api_url') or '').strip()
        self.api_url = raw_url or DEFAULT_API_URL
        self.version = cfg.get('version', DEFAULT_VERSION)
        self.convert_method = (cfg.get('convert_method') or DEFAULT_CONVERT_METHOD).strip()

    def _configured(self):
        if is_placeholder(self.app_key) or is_placeholder(self.app_secret):
            return False
        return not is_placeholder(self.access_token)

    @staticmethod
    def _make_sign(method: str, app_id: str, app_secret: str, version: str, timestamp: int) -> str:
        raw = f'{method}?appId={app_id}&timestamp={timestamp}&version={version}{app_secret}'
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('xiaohongshu', ['app_key', 'app_secret', 'access_token'])

        timestamp = int(time.time())
        biz = {'itemUrl': url, 'url': url}
        if self.pid:
            biz['pid'] = self.pid
            biz['cpsPid'] = self.pid
        if wxid:
            biz['subUserId'] = str(wxid)[-32:]
            biz['externalId'] = str(wxid)[-32:]

        payload = {
            'method': self.convert_method,
            'appId': self.app_key,
            'sign': self._make_sign(
                self.convert_method, self.app_key, self.app_secret, self.version, timestamp
            ),
            'timestamp': timestamp,
            'version': self.version,
            'accessToken': self.access_token,
            **biz,
        }

        resp = await http_request(
            'POST',
            self.api_url,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json;charset=utf-8'},
        )
        result = parse_json_response(resp)

        if result.get('sn_error'):
            err = result['sn_error']
            return api_error(
                'xiaohongshu',
                err.get('error_msg') or err.get('error_code') or str(err),
                result,
            )

        ok = result.get('success')
        err_code = result.get('error_code', result.get('code'))
        if ok is False or (err_code not in (None, 0, '0', 10000, '10000') and not deep_get(result, 'data')):
            return api_error(
                'xiaohongshu',
                result.get('error_msg') or result.get('msg') or result.get('message')
                or '小红书转链失败，请确认已开通买手/好物推荐并核对 convert_method',
                result,
            )

        data = result.get('data') or result
        rebate_url = (
            data.get('link')
            or data.get('url')
            or data.get('deeplink')
            or data.get('cpsLink')
            or data.get('promotion_url')
            or data.get('promotionUrl')
            or data.get('item_url')
            or deep_get(data, 'linkInfo', 'url')
        )
        if not rebate_url:
            return api_error('xiaohongshu', '未返回小红书推广链接', result)

        return success_result(
            'xiaohongshu',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('title') or data.get('itemName') or data.get('product_name') or '小红书商品',
            original_price=float(data.get('price') or data.get('salePrice') or 0),
            commission=float(data.get('commission') or data.get('cosFee') or 0),
        )
