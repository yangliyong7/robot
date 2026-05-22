"""美团联盟真实 API - 旧版 generateLink + CPS Open API（团购/闪购）"""

import hashlib
import json
import logging
import time
from datetime import datetime
from typing import List, Optional

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
from src.platforms.meituan_cps import cps_post

logger = logging.getLogger(__name__)

MEITUAN_CPS_HINT = '请在 union.meituan.com 申请 CPS Open API（media.meituan.com/cps_open）密钥'


class MeituanClient:
    """美团联盟 - 推广链接 / 商品搜索 / 订单查询"""
    LEGACY_API_URL = 'https://openapi.meituan.com/api/generateLink'

    def __init__(self):
        cfg = REBATE_CONFIG.get('meituan', {}) or {}
        self.app_key = cfg.get('app_key', '')
        self.app_secret = cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')
        self.utm_source = cfg.get('utm_source', cfg.get('media_id', self.pid))
        self.sid = cfg.get('sid', '')
        self.default_act_id = cfg.get('default_act_id', '')
        self.cps_app_key = cfg.get('cps_app_key') or self.app_key
        self.cps_app_secret = cfg.get('cps_app_secret') or self.app_secret
        self.use_cps_open = cfg.get('use_cps_open', True)

    def _legacy_configured(self) -> bool:
        return not any(is_placeholder(v) for v in (self.app_key, self.app_secret, self.utm_source))

    def _cps_configured(self) -> bool:
        return not any(is_placeholder(v) for v in (self.cps_app_key, self.cps_app_secret))

    def _configured(self) -> bool:
        return self._cps_configured() or self._legacy_configured()

    def _sign_legacy(self, params: dict) -> str:
        keys = sorted(params.keys())
        raw = ''.join(f'{k}{params[k]}' for k in keys) + self.app_secret
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    async def _cps_request(self, path: str, payload: dict) -> dict:
        return await cps_post(path, payload, self.cps_app_key, self.cps_app_secret)

    async def convert(self, url: str, wxid: str = None) -> dict:
        cps_result = None
        if self.use_cps_open and self._cps_configured():
            cps_result = await self.get_referral_link(text=url, wxid=wxid)
            if cps_result.get('success'):
                return cps_result
            logger.info('美团 CPS 转链失败，尝试旧版 API: %s', cps_result.get('message'))

        if not self._legacy_configured():
            if cps_result:
                return cps_result
            return config_missing('meituan', ['app_key', 'app_secret', 'utm_source/pid'])

        timestamp = str(int(time.time()))
        params = {
            'utmSource': str(self.utm_source),
            'appKey': self.app_key,
            'timestamp': timestamp,
            'linkType': '1',
            'materialId': url,
        }
        params['sign'] = self._sign_legacy(params)

        resp = await http_request('GET', self.LEGACY_API_URL, params=params)
        result = parse_json_response(resp)

        if result.get('code') not in (0, '0', 200, '200') and not result.get('data'):
            msg = result.get('message') or result.get('msg') or str(result)
            return api_error('meituan', f'美团联盟 API 错误: {msg}', result)

        data = result.get('data') or result
        rebate_url = (
            data.get('link') or data.get('url') or data.get('shortLink')
            or deep_get(data, 'referralLink')
        )
        if not rebate_url:
            return api_error('meituan', '未获取到美团推广链接', result)

        return success_result(
            'meituan',
            rebate_url=rebate_url,
            original_url=url,
            title=data.get('title', '美团优惠'),
            commission=float(data.get('commission') or data.get('profit') or 0),
            convert_method='legacy_generate_link',
        )

    async def get_referral_link(
        self,
        text: str = '',
        act_id: str = None,
        product_view_sign: str = None,
        wxid: str = None,
        platform: int = None,
        biz_line: int = None,
        link_type: int = 2,
    ) -> dict:
        """CPS Open - get_referral_link"""
        if not self._cps_configured():
            return config_missing('meituan', ['cps_app_key', 'cps_app_secret'])

        payload = {'linkType': link_type}
        if text:
            payload['text'] = text[:200]
        elif act_id or self.default_act_id:
            payload['actId'] = str(act_id or self.default_act_id)
        elif product_view_sign:
            payload['productViewSign'] = product_view_sign
        else:
            return api_error('meituan', '请提供链接、活动ID或商品ID', {})

        if platform is not None:
            payload['platform'] = platform
        if biz_line is not None:
            payload['bizLine'] = biz_line
        sid = wxid or self.sid
        if sid:
            payload['sid'] = str(sid)[:64]

        result = await self._cps_request('get_referral_link', payload)
        if result.get('code') not in (0, '0'):
            msg = result.get('message') or result.get('msg') or str(result)
            return api_error('meituan', f'{msg}。{MEITUAN_CPS_HINT}', result)

        data = result.get('data')
        link_map = result.get('referralLinkMap') or {}
        rebate_url = (
            (link_map.get(str(link_type)) if link_map else None)
            or (link_map.get(link_type) if link_map else None)
            or data
            or deep_get(result, 'convertedLinkInfoList', 0, 'link')
        )
        if isinstance(rebate_url, dict):
            rebate_url = rebate_url.get('link') or rebate_url.get('data')
        if not rebate_url:
            return api_error('meituan', '未获取到美团 CPS 推广链接', result)

        detail = result.get('skuDetailInfo') or result.get('couponPackDetail') or {}
        commission = float(
            deep_get(result, 'commissionInfo', 'commission')
            or deep_get(detail, 'commissionInfo', 'commission')
            or 0
        )
        title = (
            deep_get(detail, 'couponPackDetail', 'name')
            or detail.get('name')
            or result.get('shareText')
            or '美团优惠'
        )
        sell = deep_get(detail, 'couponPackDetail', 'sellPrice') or detail.get('sellPrice')
        orig = deep_get(detail, 'couponPackDetail', 'originalPrice') or detail.get('originalPrice')

        return success_result(
            'meituan',
            rebate_url=str(rebate_url),
            original_url=text or f'meituan:act:{act_id or self.default_act_id}',
            title=str(title),
            original_price=float(orig or 0) / 100 if orig and float(orig) > 500 else float(orig or 0),
            final_price=float(sell or 0) / 100 if sell and float(sell) > 500 else float(sell or 0),
            commission=commission,
            product_view_sign=result.get('productViewSign') or result.get('skuViewId') or '',
            convert_method='cps_get_referral_link',
        )

    async def search_coupons(
        self,
        keyword: str = '',
        platform: int = 2,
        biz_line: int = 1,
        page_size: int = 10,
        city_id: str = None,
    ) -> dict:
        """CPS Open - query_coupon 团购/闪购商品搜索"""
        if not self._cps_configured():
            return {'success': False, 'message': config_missing('meituan', ['cps_app_key']).get('message')}

        payload = {
            'platform': platform,
            'bizLine': biz_line,
            'pageNo': 1,
            'pageSize': min(page_size, 20),
        }
        if keyword:
            payload['searchText'] = keyword[:100]
        if city_id:
            payload['cityId'] = str(city_id)

        result = await self._cps_request('query_coupon', payload)
        if result.get('code') not in (0, '0'):
            return {
                'success': False,
                'message': result.get('message') or MEITUAN_CPS_HINT,
                'raw': result,
            }

        rows = result.get('data') or []
        if isinstance(rows, dict):
            rows = [rows]
        deals = []
        for row in rows:
            pack = row.get('couponPackDetail') or {}
            comm = row.get('commissionInfo') or {}
            pvs = pack.get('productViewSign') or pack.get('skuViewId') or row.get('productViewSign')
            sell = pack.get('sellPrice') or 0
            orig = pack.get('originalPrice') or sell
            try:
                sell_f = float(sell)
                orig_f = float(orig)
                if sell_f > 500:
                    sell_f /= 100
                if orig_f > 500:
                    orig_f /= 100
            except (TypeError, ValueError):
                sell_f, orig_f = 0.0, 0.0

            deals.append({
                'title': pack.get('name') or row.get('brandInfo', {}).get('brandName') or '美团团购',
                'price': sell_f,
                'original_price': orig_f or sell_f,
                'commission': float(comm.get('commission') or 0),
                'commission_percent': comm.get('commissionPercent'),
                'product_view_sign': pvs,
                'head_url': pack.get('headUrl', ''),
                'sale_volume': pack.get('saleVolume', ''),
            })

        return {'success': True, 'deals': deals, 'has_next': result.get('hasNext', False)}

    async def query_orders(
        self,
        start_time: datetime,
        end_time: datetime,
        platform: int = None,
    ) -> List[dict]:
        """CPS Open - query_order"""
        if not self._cps_configured():
            return []

        all_rows = []
        scroll_id = ''
        for _ in range(50):
            payload = {
                'startTime': int(start_time.timestamp()),
                'endTime': int(end_time.timestamp()),
                'queryTimeType': 2,
                'searchType': 2,
                'limit': 100,
                'page': 1,
            }
            if platform is not None:
                payload['platform'] = platform
            if scroll_id:
                payload['scrollId'] = scroll_id

            result = await self._cps_request('query_order', payload)
            if result.get('code') not in (0, '0'):
                logger.warning('美团订单查询失败: %s', result)
                break

            data = result.get('data') or {}
            rows = data.get('dataList') or []
            if not rows:
                break
            all_rows.extend(rows)
            scroll_id = data.get('scrollId') or ''
            if not scroll_id or len(rows) < 100:
                break
        return all_rows
