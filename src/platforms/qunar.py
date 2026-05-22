"""去哪儿联盟 - 推广链接 + 订单查询"""

import hashlib
import json
import logging
import time
from datetime import datetime
from urllib.parse import quote

from config.config import REBATE_CONFIG, TRAVEL_CONFIG
from src.platforms.base import (
    config_missing,
    deep_get,
    http_request,
    is_placeholder,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)


class QunarClient:
    def __init__(self):
        cfg = REBATE_CONFIG.get('qunar', {}) or {}
        legacy = TRAVEL_CONFIG or {}
        self.site_id = cfg.get('site_id') or legacy.get('qunar_pid', '')
        self.sign_key = cfg.get('sign_key', '')
        self.app_key = cfg.get('app_key', '')
        self.api_url = cfg.get('api_url', 'https://openapi.qunar.com/api/router').rstrip('/')
        self.link_base = cfg.get('link_base', 'https://touch.qunar.com/hotel/')

    def _configured(self):
        return not is_placeholder(self.site_id)

    def _api_configured(self):
        return not any(is_placeholder(v) for v in (self.app_key, self.sign_key))

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('qunar', ['site_id'])

        jump = url if url.startswith('http') else self._keyword_to_jump(url)
        link = self.build_promotion_link(jump, wxid=wxid)

        if self._api_configured():
            api_link = await self._try_api_convert(jump, wxid)
            if api_link:
                link = api_link

        title = '去哪儿酒店预订' if 'hotel' in jump else '去哪儿旅行预订'
        return success_result(
            'qunar',
            rebate_url=link,
            original_url=url,
            title=title,
            convert_method='alliance_link',
        )

    async def get_hotel_link(self, city: str, wxid: str = None) -> dict:
        jump = f'{self.link_base}?city={quote(city)}'
        return await self.convert(jump, wxid=wxid)

    def build_promotion_link(self, jump_url: str, wxid: str = None) -> str:
        ouid = str(wxid or '')[:64]
        sep = '&' if '?' in jump_url else '?'
        link = f'{jump_url}{sep}bd_source={self.site_id}'
        if ouid:
            link += f'&ouid={ouid}'
        return link

    async def _try_api_convert(self, jump_url: str, wxid: str = None) -> str:
        biz = {'url': jump_url, 'siteId': self.site_id}
        if wxid:
            biz['ouid'] = str(wxid)[:64]
        result = await self._call('union.link.convert', biz)
        data = deep_get(result, 'data') or result
        for key in ('promotionUrl', 'clickUrl', 'url'):
            if isinstance(data, dict) and data.get(key):
                return str(data[key])
        return ''

    async def query_orders(self, start_time: datetime, end_time: datetime) -> list:
        if not self._api_configured():
            return []
        biz = {
            'siteId': self.site_id,
            'startTime': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'endTime': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'page': 1,
            'pageSize': 100,
        }
        result = await self._call('union.order.list', biz)
        rows = deep_get(result, 'data', 'orders') or deep_get(result, 'orders') or []
        return rows if isinstance(rows, list) else []

    async def _call(self, method: str, biz: dict) -> dict:
        timestamp = str(int(time.time()))
        body = {
            'method': method,
            'appKey': self.app_key,
            'timestamp': timestamp,
            'data': json.dumps(biz, ensure_ascii=False),
        }
        sign_raw = f'{body["appKey"]}{body["timestamp"]}{body["data"]}{self.sign_key}'
        body['sign'] = hashlib.md5(sign_raw.encode('utf-8')).hexdigest()
        resp = await http_request('POST', self.api_url, json=body)
        return parse_json_response(resp)

    @staticmethod
    def _keyword_to_jump(keyword: str) -> str:
        text = (keyword or '').strip()
        if '机票' in text:
            return 'https://touch.qunar.com/flight/'
        return f'https://touch.qunar.com/hotel/?keyword={quote(text)}'
