"""阿里妈妈 / 淘宝开放平台公共调用（闲鱼、饿了么等复用）"""

from datetime import datetime
from typing import Dict, Optional

from config.config import REBATE_CONFIG
from src.platforms.base import deep_get, http_request, is_placeholder, md5_sign, parse_json_response


class AliMamaBase:
    API_URL = 'https://gw.api.taobao.com/router/rest'

    def __init__(self, cfg_key: str, fallback_taobao: bool = True):
        cfg = REBATE_CONFIG.get(cfg_key, {}) or {}
        tb = REBATE_CONFIG.get('taobao', {}) or {}
        use_tb = cfg.get('use_taobao_credentials', fallback_taobao)
        tb_key = tb.get('top_app_key') or tb.get('app_key')
        tb_secret = tb.get('top_app_secret') or tb.get('app_secret')
        self.app_key = cfg.get('app_key') or (tb_key if use_tb else '')
        self.app_secret = cfg.get('app_secret') or (tb_secret if use_tb else '')
        self.adzone_id = cfg.get('adzone_id') or tb.get('adzone_id', '')
        self.pid = cfg.get('pid') or tb.get('pid', '')
        self.site_id = self._parse_site_id(self.pid)

    @staticmethod
    def _parse_site_id(pid: str) -> str:
        parts = (pid or '').split('_')
        if len(parts) >= 4:
            return parts[2]
        return ''

    def _configured(self, *extra_fields) -> bool:
        fields = [self.app_key, self.app_secret, self.adzone_id] + list(extra_fields)
        return not any(is_placeholder(v) for v in fields)

    async def call(self, method: str, extra: dict) -> dict:
        params = {
            'method': method,
            'app_key': self.app_key,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'json',
            'v': '2.0',
            'sign_method': 'md5',
            **extra,
        }
        params['sign'] = md5_sign(params, self.app_secret)
        resp = await http_request('GET', self.API_URL, params=params)
        return parse_json_response(resp)

    @staticmethod
    def parse_error(result: dict) -> str:
        if not result:
            return ''
        if 'error_response' in result:
            err = result['error_response']
            return err.get('sub_msg') or err.get('msg', '')
        return ''

    @staticmethod
    def first_click_url(data: dict) -> str:
        if not isinstance(data, dict):
            return ''
        for key in (
            'click_url', 'short_click_url', 'coupon_click_url',
            'cps_long_url', 'cps_short_url', 'url', 'h5_url',
            'short_url', 'long_url', 'page_url',
        ):
            val = data.get(key)
            if val:
                return str(val)
        for nested in ('link_info_dto', 'data', 'result'):
            found = AliMamaBase.first_click_url(data.get(nested) or {})
            if found:
                return found
        return ''
