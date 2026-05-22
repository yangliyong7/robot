"""苏宁联盟真实 API - 商品推广链接（二合一）"""

import base64
import hashlib
import json
import logging
from datetime import datetime

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

API_URI = '/api/http/sopRequest'
API_VERSION = 'v1.2'


class SuningClient:
    """
    苏宁网盟转链
    文档: https://open.suning.com/  接口 suning.netalliance.extensionlink.get
    申请: https://union.suning.com/
    """

    def __init__(self):
        cfg = REBATE_CONFIG['suning']
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']
        self.promotion_id = cfg.get('promotion_id', cfg.get('pid', ''))
        self.api_domain = (cfg.get('api_domain') or 'open.suning.com').strip()
        self.api_port = int(cfg.get('api_port') or 443)
        self.use_https = cfg.get('use_https', True) if cfg.get('use_https') is not None else True

    def _configured(self):
        return not any(
            is_placeholder(v) for v in (self.app_key, self.app_secret, self.promotion_id)
        )

    def _api_base_url(self) -> str:
        scheme = 'https' if self.use_https or self.api_port == 443 else 'http'
        port_part = '' if (scheme == 'https' and self.api_port == 443) or (
            scheme == 'http' and self.api_port == 80
        ) else f':{self.api_port}'
        return f'{scheme}://{self.api_domain}{port_part}{API_URI}'

    @staticmethod
    def _sign(app_secret: str, app_method: str, date: str, app_key: str, body: bytes) -> str:
        base_str = base64.b64encode(body).decode('utf-8')
        raw = f'{app_secret}{app_method}{date}{app_key}{API_VERSION}{base_str}'
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    async def _call(self, biz_name: str, app_method: str, biz_params: dict) -> dict:
        body_obj = {
            'sn_request': {
                'sn_body': {
                    biz_name: biz_params,
                }
            }
        }
        body_bytes = json.dumps(body_obj, ensure_ascii=False).encode('utf-8')
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        headers = {
            'AppMethod': app_method,
            'AppRequestTime': date,
            'Format': 'json',
            'AppKey': self.app_key,
            'signInfo': self._sign(self.app_secret, app_method, date, self.app_key, body_bytes),
            'VersionNo': API_VERSION,
            'Content-Type': 'application/json;charset=UTF-8',
        }
        resp = await http_request('POST', self._api_base_url(), data=body_bytes, headers=headers)
        return parse_json_response(resp)

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('suning', ['app_key', 'app_secret', 'promotion_id'])

        biz_params = {
            'productUrl': url,
            'promotionId': str(self.promotion_id),
        }
        if wxid:
            biz_params['subUser'] = str(wxid)[-32:]

        result = await self._call(
            'getExtensionlink',
            'suning.netalliance.extensionlink.get',
            biz_params,
        )

        err = deep_get(result, 'sn_responseContent', 'sn_error')
        if err:
            return api_error(
                'suning',
                err.get('error_msg') or err.get('error_code') or '苏宁联盟 API 错误',
                result,
            )

        data = (
            deep_get(result, 'sn_responseContent', 'sn_body', 'getExtensionlink')
            or deep_get(result, 'sn_responseContent', 'sn_body', 'getExtensionlinkResponse')
            or deep_get(result, 'sn_responseContent', 'sn_body')
            or {}
        )
        rebate_url = (
            data.get('extensionUrl')
            or data.get('shortExtensionUrl')
            or data.get('productUrl')
            or data.get('linkUrl')
            or data.get('url')
        )
        if not rebate_url:
            return api_error('suning', '未获取到苏宁推广链接', result)

        return success_result(
            'suning',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('productName') or data.get('commodityName') or '苏宁商品',
            original_price=float(data.get('productPrice') or data.get('price') or 0),
            commission=float(data.get('commission') or data.get('predictCommission') or 0),
        )
