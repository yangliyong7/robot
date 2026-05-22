"""同程旅行联盟 - 推广链接 + 订单查询"""

import hashlib
import json
import logging
import time
from datetime import datetime
from urllib.parse import quote

from config.config import REBATE_CONFIG, TRAVEL_CONFIG
from src.platforms.base import (
    api_error,
    config_missing,
    deep_get,
    http_request,
    is_placeholder,
    md5_sign,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)

TONGCHENG_HINT = '请在同程分销联盟申请 app_key/app_secret/refid/channel_id'


class TongchengClient:
    def __init__(self):
        cfg = REBATE_CONFIG.get('tongcheng', {}) or {}
        legacy = TRAVEL_CONFIG or {}
        self.app_key = cfg.get('app_key', '')
        self.app_secret = cfg.get('app_secret', '')
        self.refid = cfg.get('refid') or legacy.get('tongcheng_pid', '')
        self.channel_id = cfg.get('channel_id', '')
        self.api_url = cfg.get('api_url', 'https://openapi.elong.com/rest').rstrip('/')
        self.link_base = cfg.get(
            'link_base',
            'https://m.ly.com/hotel/',
        )

    def _configured(self):
        return not is_placeholder(self.refid)

    def _api_configured(self):
        return not any(is_placeholder(v) for v in (self.app_key, self.app_secret))

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('tongcheng', ['refid'])

        jump = url if url.startswith('http') else self._keyword_to_jump(url)
        link = self.build_promotion_link(jump, wxid=wxid)

        if self._api_configured():
            api_link = await self._try_api_convert(jump, wxid)
            if api_link:
                link = api_link

        title = '同程酒店预订' if 'hotel' in jump else '同程旅行预订'
        return success_result(
            'tongcheng',
            rebate_url=link,
            original_url=url,
            title=title,
            convert_method='alliance_link',
        )

    async def get_hotel_link(self, city: str, wxid: str = None) -> dict:
        jump = f'{self.link_base}?cityName={quote(city)}'
        return await self.convert(jump, wxid=wxid)

    def build_promotion_link(self, jump_url: str, wxid: str = None) -> str:
        ouid = str(wxid or '')[:64]
        sep = '&' if '?' in jump_url else '?'
        tracked = f'{jump_url}{sep}refid={self.refid}'
        if self.channel_id:
            tracked += f'&tcwvcnew={self.channel_id}'
        if ouid:
            tracked += f'&ouid={ouid}'
        return tracked

    async def _try_api_convert(self, jump_url: str, wxid: str = None) -> str:
        method = (REBATE_CONFIG.get('tongcheng', {}) or {}).get(
            'convert_method', 'alliance.link.convert'
        )
        biz = {
            'refid': self.refid,
            'url': jump_url,
        }
        if wxid:
            biz['ouid'] = str(wxid)[:64]
        if self.channel_id:
            biz['channelId'] = self.channel_id

        result = await self._call(method, biz)
        data = deep_get(result, 'data') or result
        for key in ('clickUrl', 'click_url', 'promotionUrl', 'url'):
            val = deep_get(data, key) if isinstance(data, dict) else None
            if not val and isinstance(data, dict):
                val = data.get(key)
            if val:
                return str(val)
        return ''

    async def query_orders(self, start_time: datetime, end_time: datetime) -> list:
        if not self._api_configured():
            return []
        method = (REBATE_CONFIG.get('tongcheng', {}) or {}).get(
            'order_method', 'alliance.order.list'
        )
        biz = {
            'startTime': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'endTime': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'pageIndex': 1,
            'pageSize': 100,
        }
        result = await self._call(method, biz)
        rows = deep_get(result, 'data', 'list') or deep_get(result, 'orders') or []
        return rows if isinstance(rows, list) else []

    async def _call(self, method: str, biz: dict) -> dict:
        timestamp = str(int(time.time()))
        params = {
            'method': method,
            'appKey': self.app_key,
            'timestamp': timestamp,
            'version': '1.0',
            'format': 'json',
            'bizContent': json.dumps(biz, ensure_ascii=False),
        }
        params['sign'] = md5_sign(params, self.app_secret)
        resp = await http_request('POST', self.api_url, data=params)
        return parse_json_response(resp)

    @staticmethod
    def _keyword_to_jump(keyword: str) -> str:
        text = (keyword or '').strip()
        if '机票' in text:
            return 'https://m.ly.com/flight/'
        return f'https://m.ly.com/hotel/?keyword={quote(text)}'
