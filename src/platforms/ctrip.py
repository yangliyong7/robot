"""携程联盟 - 推广深链 + ServiceProxy 订单查询"""

import hashlib
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from config.config import REBATE_CONFIG, TRAVEL_CONFIG
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

CTRIP_HINT = '请在 u.ctrip.com/alliance 注册，配置 alliance_id、sid、sign_key(api_key)'


class CtripClient:
    SERVICE_URL = 'https://sopenservice.ctrip.com/OpenService/ServiceProxy.ashx'
    ALLIANCE_LINK = 'https://u.ctrip.com/alliance/alliance.html'

    def __init__(self):
        cfg = REBATE_CONFIG.get('ctrip', {}) or {}
        legacy = TRAVEL_CONFIG or {}
        self.alliance_id = cfg.get('alliance_id') or legacy.get('ctrip_affiliate_id', '')
        self.sid = cfg.get('sid') or legacy.get('ctrip_sid', '1')
        self.sign_key = cfg.get('sign_key') or legacy.get('ctrip_sign_key', '')
        self.default_jump = cfg.get(
            'default_jump_url',
            'https://m.ctrip.com/webapp/hotel/',
        )

    def _configured(self):
        return not any(is_placeholder(v) for v in (self.alliance_id, self.sign_key))

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('ctrip', ['alliance_id', 'sign_key'])

        jump_url = url if url.startswith('http') else self._keyword_to_jump(url)
        link = self.build_alliance_link(jump_url, wxid=wxid)
        title = self._guess_title(url)

        return success_result(
            'ctrip',
            rebate_url=link,
            original_url=url,
            title=title,
            commission=0,
            convert_method='alliance_deeplink',
        )

    async def get_hotel_link(self, city: str, wxid: str = None, check_in: str = '') -> dict:
        jump = f'https://m.ctrip.com/webapp/hotel/?city={quote(city)}'
        if check_in:
            jump += f'&checkin={quote(check_in)}'
        return await self.convert(jump, wxid=wxid)

    async def get_flight_link(self, from_city: str, to_city: str, wxid: str = None) -> dict:
        jump = (
            f'https://m.ctrip.com/webapp/flight/list/?'
            f'dcity={quote(from_city)}&acity={quote(to_city)}'
        )
        return await self.convert(jump, wxid=wxid)

    def build_alliance_link(self, jump_url: str, wxid: str = None) -> str:
        ouid = str(wxid or '')[:64]
        encoded = quote(jump_url, safe='')
        return (
            f'{self.ALLIANCE_LINK}?AllianceID={self.alliance_id}'
            f'&SID={self.sid}&OUID={ouid}&jumpUrl={encoded}'
        )

    async def query_orders(self, start_time: datetime, end_time: datetime) -> list:
        """携程联盟 ServiceProxy 订单拉取（RequestType 以联盟后台文档为准）"""
        if not self._configured():
            return []

        request_type = (REBATE_CONFIG.get('ctrip', {}) or {}).get(
            'order_request_type', 'OrderSearch'
        )
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        signature = self._sign(request_type, timestamp)

        payload = {
            'AllianceID': self.alliance_id,
            'SID': self.sid,
            'RequestType': request_type,
            'TimeStamp': timestamp,
            'Signature': signature,
            'StartTime': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'EndTime': end_time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        resp = await http_request('POST', self.SERVICE_URL, json=payload)
        data = parse_json_response(resp)
        rows = (
            deep_get(data, 'OrderList')
            or deep_get(data, 'Orders')
            or deep_get(data, 'Data')
            or []
        )
        if isinstance(rows, dict):
            rows = rows.get('Order') or rows.get('orders') or [rows]
        return rows if isinstance(rows, list) else []

    def _sign(self, request_type: str, timestamp: str) -> str:
        raw = f'{self.alliance_id}{request_type}{self.sid}{timestamp}{self.sign_key}'
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def _keyword_to_jump(keyword: str) -> str:
        text = (keyword or '').strip()
        if not text:
            return 'https://m.ctrip.com/'
        if '机票' in text or '航班' in text:
            return 'https://m.ctrip.com/webapp/flight/'
        if '门票' in text or '景点' in text:
            return 'https://m.ctrip.com/webapp/ticket/'
        return f'https://m.ctrip.com/webapp/hotel/?keyword={quote(text)}'

    @staticmethod
    def _guess_title(url: str) -> str:
        if 'flight' in url:
            return '携程机票预订'
        if 'ticket' in url:
            return '携程门票预订'
        if 'hotel' in url:
            return '携程酒店预订'
        return '携程旅行预订'
