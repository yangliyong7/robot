"""
各平台联盟订单拉取（订单同步 / 回调等效）
将联盟订单状态映射为: paid / confirmed / settled / invalid
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from config.config import REBATE_CONFIG, COMMISSION_CONFIG
from src.platforms.base import deep_get, http_request, is_placeholder, md5_sign, parse_json_response
from src.platforms.alimama_base import AliMamaBase
from src.platforms.ctrip import CtripClient
from src.platforms.tongcheng import TongchengClient
from src.platforms.qunar import QunarClient
from src.platforms.meituan import MeituanClient

logger = logging.getLogger(__name__)


def _parse_pdd_custom_parameters(value) -> str:
    """多多进宝 custom_parameters 常为 JSON，提取 uid/wxid"""
    if not value:
        return ''
    text = str(value).strip()
    if text.startswith('{'):
        try:
            data = json.loads(text)
            return str(data.get('uid') or data.get('wxid') or data.get('external_id') or '').strip()
        except json.JSONDecodeError:
            pass
    return text

# 淘宝 tk_status: 12付款 14确认收货 3已结算 13失效
TAOBAO_CONFIRM = {14, 3}
TAOBAO_INVALID = {13}
TAOBAO_PAID = {12}


class AllianceOrderFetcher:
    """联盟订单增量查询"""

    def __init__(self):
        self.tb = REBATE_CONFIG.get('taobao', {})
        self.jd = REBATE_CONFIG.get('jd', {})
        self.pdd = REBATE_CONFIG.get('pdd', {})

    async def fetch_all(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        orders = []
        orders.extend(await self.fetch_taobao_orders(start_time, end_time))
        orders.extend(await self.fetch_jd_orders(start_time, end_time))
        orders.extend(await self.fetch_pdd_orders(start_time, end_time))
        orders.extend(await self.fetch_xianyu_orders(start_time, end_time))
        orders.extend(await self.fetch_ctrip_orders(start_time, end_time))
        orders.extend(await self.fetch_tongcheng_orders(start_time, end_time))
        orders.extend(await self.fetch_qunar_orders(start_time, end_time))
        orders.extend(await self.fetch_meituan_orders(start_time, end_time))
        return orders

    async def fetch_taobao_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        top_key = self.tb.get('top_app_key') or self.tb.get('app_key')
        if is_placeholder(top_key):
            return []

        client = _TaobaoOrderApi(self.tb)
        raw_list = await client.query_orders(start_time, end_time)
        results = []
        for row in raw_list:
            tk_status = int(row.get('tk_status') or 0)
            if tk_status in TAOBAO_INVALID:
                norm_status = 'invalid'
            elif tk_status in TAOBAO_CONFIRM:
                norm_status = 'confirmed'
            elif tk_status in TAOBAO_PAID:
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(row.get('pub_share_fee') or row.get('total_commission_fee') or 0)
            rate = COMMISSION_CONFIG.get('taobao_rate', 0.7)
            results.append({
                'platform': 'taobao',
                'platform_order_id': str(row.get('trade_id') or row.get('trade_parent_id') or ''),
                'platform_item_id': str(row.get('item_id') or row.get('num_iid') or ''),
                'wxid': str(row.get('external_id') or row.get('special_id') or '').strip(),
                'title': row.get('item_title') or row.get('title') or '',
                'pay_amount': float(row.get('alipay_total_price') or row.get('pay_price') or 0),
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': str(tk_status),
                'norm_status': norm_status,
                'order_time': row.get('tk_create_time') or row.get('tb_paid_time') or '',
            })
        return [o for o in results if o['platform_order_id']]

    async def fetch_jd_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        if is_placeholder(self.jd.get('app_key')):
            return []

        client = _JDOrderApi(self.jd)
        raw_list = await client.query_orders(start_time, end_time)
        results = []
        rate = COMMISSION_CONFIG.get('jd_rate', 0.7)
        for row in raw_list:
            valid_code = int(row.get('validCode') or row.get('valid_code') or 0)
            # 京东: 16完成/17已结算 等，因文档版本差异做宽松映射
            if valid_code in (2, 3, 4):
                norm_status = 'invalid'
            elif valid_code in (16, 17, 18):
                norm_status = 'confirmed'
            elif valid_code in (15,):
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(row.get('estimateFee') or row.get('actualFee') or 0)
            results.append({
                'platform': 'jd',
                'platform_order_id': str(row.get('orderId') or row.get('order_id') or ''),
                'platform_item_id': str(row.get('skuId') or ''),
                'wxid': str(row.get('subUnionId') or row.get('positionId') or '').strip(),
                'title': row.get('skuName') or '',
                'pay_amount': float(row.get('estimateCosPrice') or row.get('payPrice') or 0),
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': str(valid_code),
                'norm_status': norm_status,
                'order_time': row.get('orderTime') or '',
            })
        return [o for o in results if o['platform_order_id']]

    async def fetch_xianyu_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        cfg = REBATE_CONFIG.get('xianyu', {}) or {}
        client = _XianyuOrderApi(cfg)
        if not client.configured():
            return []

        raw_list = await client.query_orders(start_time, end_time)
        results = []
        rate = COMMISSION_CONFIG.get('xianyu_rate', 0.7)
        for row in raw_list:
            status = str(row.get('order_status') or row.get('status') or '')
            if status in ('13', 'invalid', 'INVALID'):
                norm_status = 'invalid'
            elif status in ('3', '14', 'settled', 'SETTLED', 'confirmed'):
                norm_status = 'confirmed'
            elif status in ('12', 'paid', 'PAID'):
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(row.get('commission_fee') or row.get('pub_share_fee') or 0)
            results.append({
                'platform': 'xianyu',
                'platform_order_id': str(row.get('trade_id') or row.get('order_id') or ''),
                'platform_item_id': str(row.get('item_id') or ''),
                'wxid': str(row.get('external_id') or row.get('unid') or '').strip(),
                'title': row.get('item_title') or row.get('title') or '',
                'pay_amount': float(row.get('pay_amount') or row.get('alipay_total_price') or 0),
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': status,
                'norm_status': norm_status,
                'order_time': row.get('order_time') or row.get('create_time') or '',
            })
        return [o for o in results if o['platform_order_id']]

    async def fetch_ctrip_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        client = CtripClient()
        if not client._configured():
            return []
        raw_list = await client.query_orders(start_time, end_time)
        return self._normalize_travel_orders('ctrip', raw_list, COMMISSION_CONFIG.get('ctrip_rate', 0.7))

    async def fetch_tongcheng_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        client = TongchengClient()
        if not client._configured():
            return []
        raw_list = await client.query_orders(start_time, end_time)
        return self._normalize_travel_orders('tongcheng', raw_list, COMMISSION_CONFIG.get('tongcheng_rate', 0.7))

    async def fetch_qunar_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        client = QunarClient()
        if not client._configured():
            return []
        raw_list = await client.query_orders(start_time, end_time)
        return self._normalize_travel_orders('qunar', raw_list, COMMISSION_CONFIG.get('qunar_rate', 0.7))

    @staticmethod
    def _normalize_travel_orders(platform: str, raw_list: List[Dict], rate: float) -> List[Dict]:
        results = []
        for row in raw_list:
            status = str(row.get('orderStatus') or row.get('status') or row.get('OrderStatus') or '')
            status_lower = status.lower()
            if status_lower in ('cancel', 'cancelled', 'invalid', 'refund'):
                norm_status = 'invalid'
            elif status_lower in ('completed', 'finished', 'settled', 'checkout'):
                norm_status = 'confirmed'
            elif status_lower in ('paid', 'booked', 'confirmed'):
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(
                row.get('commission') or row.get('Commission') or row.get('estimateFee') or 0
            )
            results.append({
                'platform': platform,
                'platform_order_id': str(
                    row.get('orderId') or row.get('order_id') or row.get('OrderId') or ''
                ),
                'platform_item_id': str(row.get('productId') or row.get('hotelId') or ''),
                'wxid': str(row.get('ouid') or row.get('OUID') or row.get('subUnionId') or '').strip(),
                'title': row.get('productName') or row.get('hotelName') or row.get('title') or '',
                'pay_amount': float(row.get('orderAmount') or row.get('payAmount') or 0),
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': status,
                'norm_status': norm_status,
                'order_time': row.get('orderTime') or row.get('createTime') or '',
            })
        return [o for o in results if o['platform_order_id']]

    async def fetch_meituan_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        client = MeituanClient()
        if not client._cps_configured():
            return []

        raw_list = await client.query_orders(start_time, end_time)
        results = []
        rate = COMMISSION_CONFIG.get('meituan_rate', 0.7)
        for row in raw_list:
            status = str(row.get('status') or row.get('couponStatus') or '')
            if status in ('4', '5', 'cancel', 'invalid'):
                norm_status = 'invalid'
            elif status in ('3', '6', 'settled'):
                norm_status = 'confirmed'
            elif status in ('2', 'paid'):
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(row.get('profit') or row.get('cpaProfit') or 0)
            results.append({
                'platform': 'meituan',
                'platform_order_id': str(row.get('orderId') or ''),
                'platform_item_id': str(row.get('productViewSign') or row.get('productId') or ''),
                'wxid': str(row.get('sid') or '').strip(),
                'title': row.get('productName') or '',
                'pay_amount': float(row.get('payPrice') or 0),
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': status,
                'norm_status': norm_status,
                'order_time': row.get('payTime') or row.get('updateTime') or '',
            })
        return [o for o in results if o['platform_order_id']]

    async def fetch_pdd_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        if is_placeholder(self.pdd.get('client_id')):
            return []

        client = _PDDOrderApi(self.pdd)
        raw_list = await client.query_orders(start_time, end_time)
        results = []
        rate = COMMISSION_CONFIG.get('pdd_rate', 0.7)
        for row in raw_list:
            status = int(row.get('order_status') or -1)
            # 0已支付 1已成团 2确认收货 3审核成功 5已结算
            if status in (4, 10):
                norm_status = 'invalid'
            elif status in (2, 3, 5):
                norm_status = 'confirmed'
            elif status in (0, 1):
                norm_status = 'paid'
            else:
                norm_status = 'pending'

            commission = float(row.get('promotion_amount') or row.get('estimate_fee') or 0) / 100
            wxid = _parse_pdd_custom_parameters(row.get('custom_parameters'))
            results.append({
                'platform': 'pdd',
                'platform_order_id': str(row.get('order_sn') or ''),
                'platform_item_id': str(row.get('goods_id') or ''),
                'wxid': wxid,
                'title': row.get('goods_name') or '',
                'pay_amount': float(row.get('order_amount') or 0) / 100,
                'commission': commission,
                'user_rebate': round(commission * rate, 2),
                'platform_status': str(status),
                'norm_status': norm_status,
                'order_time': row.get('order_pay_time') or '',
            })
        return [o for o in results if o['platform_order_id']]


class _TaobaoOrderApi:
    API_URL = 'https://gw.api.taobao.com/router/rest'

    def __init__(self, cfg):
        self.app_key = cfg.get('top_app_key') or cfg.get('app_key', '')
        self.app_secret = cfg.get('top_app_secret') or cfg.get('app_secret', '')
        self.pid = cfg.get('pid', '')

    async def query_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """taobao.tbk.order.details.get 推广者订单明细"""
        start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        all_rows = []
        page = 1
        while page <= 50:
            params = {
                'method': 'taobao.tbk.order.details.get',
                'app_key': self.app_key,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'format': 'json',
                'v': '2.0',
                'sign_method': 'md5',
                'start_time': start_str,
                'end_time': end_str,
                'query_type': '2',
                'page_no': str(page),
                'page_size': '100',
                'order_scene': '1',
            }
            params['sign'] = md5_sign(params, self.app_secret)
            resp = await http_request('GET', self.API_URL, params=params)
            data = parse_json_response(resp)
            if 'error_response' in data:
                logger.warning('淘宝订单查询失败: %s', data)
                break

            resp_key = data.get('tbk_order_details_get_response') or data.get('tbk_order_details_get_responce') or {}
            results = resp_key.get('results') or {}
            rows = results.get('publisher_order_dto') or results.get('order_detail') or []
            if isinstance(rows, dict):
                rows = [rows]
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return all_rows


class _JDOrderApi:
    API_URL = 'https://api.jd.com/routerjson'

    def __init__(self, cfg):
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']

    async def query_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        param_json = {
            'orderReq': {
                'pageNo': 1,
                'pageSize': 100,
                'type': 1,
                'startTime': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'endTime': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            }
        }
        all_rows = []
        page = 1
        while page <= 50:
            param_json['orderReq']['pageNo'] = page
            params = {
                'method': 'jd.union.open.order.row.query',
                'app_key': self.app_key,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'format': 'json',
                'v': '1.0',
                'sign_method': 'md5',
                'param_json': json.dumps(param_json, ensure_ascii=False),
            }
            params['sign'] = md5_sign(params, self.app_secret)
            resp = await http_request('GET', self.API_URL, params=params)
            data = parse_json_response(resp)
            key = 'jd_union_open_order_row_query_responce'
            body = data.get(key) or data.get('jd_union_open_order_row_query_response') or {}
            result = body.get('queryResult') or body.get('result') or ''
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}
            rows = result.get('data') or []
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return all_rows


class _PDDOrderApi:
    API_URL = 'https://gw-api.pinduoduo.com/api/router'

    def __init__(self, cfg):
        self.client_id = cfg['client_id']
        self.client_secret = cfg['client_secret']

    async def query_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """pdd.ddk.order.list.range.get 按时间范围查订单"""
        all_rows = []
        page = 1
        while page <= 50:
            biz = {
                'start_time': int(start_time.timestamp()),
                'end_time': int(end_time.timestamp()),
                'page': page,
                'page_size': 100,
            }
            params = {
                'type': 'pdd.ddk.order.list.range.get',
                'client_id': self.client_id,
                'timestamp': str(int(datetime.now().timestamp())),
                'data_type': 'JSON',
            }
            params.update(biz)
            params['sign'] = md5_sign(params, self.client_secret)
            resp = await http_request('POST', self.API_URL, data=params)
            data = parse_json_response(resp)
            resp_body = data.get('order_list_get_response') or {}
            rows = resp_body.get('order_list') or []
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return all_rows


class _XianyuOrderApi(AliMamaBase):
    def __init__(self, cfg):
        super().__init__('xianyu', fallback_taobao=True)

    def configured(self):
        return self._configured()

    async def query_orders(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """alibaba.idle.affiliate.cps.income.details.query"""
        all_rows = []
        page = 1
        while page <= 50:
            result = await self.call('alibaba.idle.affiliate.cps.income.details.query', {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'page_no': str(page),
                'page_size': '100',
            })
            if self.parse_error(result):
                logger.warning('闲鱼订单查询失败: %s', result)
                break

            resp = result.get('alibaba_idle_affiliate_cps_income_details_query_response') or {}
            data = resp.get('data') or resp.get('result') or {}
            rows = data.get('result') or data.get('list') or data.get('details') or []
            if isinstance(rows, dict):
                rows = [rows]
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 100:
                break
            page += 1
        return all_rows
