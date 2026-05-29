"""拼多多多多进宝真实 API"""

import json
import logging
import re
from datetime import datetime
from typing import Optional
from config.config import REBATE_CONFIG
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

# 已在多多进宝备案通过的 uid，全站转链/搜索固定使用，勿按微信 wxid 动态生成
PDD_FILING_UID = 'test_user_001'

FILING_HINT = (
    'pid/custom_parameters 尚未备案：请用浏览器打开返回的授权链接，'
    '登录拼多多授权一次后即可正常转链。说明：https://jinbao.pinduoduo.com/qa-system?questionId=204'
)


class PDDClient:
    API_URL = 'https://gw-api.pinduoduo.com/api/router'

    def __init__(self):
        cfg = REBATE_CONFIG['pdd']
        self.client_id = cfg['client_id']
        self.client_secret = cfg['client_secret']
        self.pid = cfg['pid']

    def _configured(self):
        return not any(is_placeholder(v) for v in (self.client_id, self.client_secret, self.pid))

    @staticmethod
    def _custom_parameters(_wxid: Optional[str] = None) -> str:
        """返回已备案的 custom_parameters；_wxid 仅保留调用方兼容，不参与生成。"""
        return json.dumps({'uid': PDD_FILING_UID}, ensure_ascii=False)

    @staticmethod
    def _extract_goods_id(url: str) -> Optional[str]:
        """从拼多多链接中提取 goods_id"""
        match = re.search(r'goods_id=(\d+)', url)
        return match.group(1) if match else None

    @staticmethod
    def _is_filing_error(raw) -> bool:
        if not isinstance(raw, dict):
            return False
        err = raw.get('error_response') or raw
        return str(err.get('sub_code')) == '60001' or '备案' in str(err.get('sub_msg', ''))

    async def convert(self, url: str, wxid: Optional[str] = None) -> dict:
        if not self._configured():
            return config_missing('pdd', ['client_id', 'client_secret', 'pid'])

        cp = self._custom_parameters(wxid)

        # 1. 从链接中提取 goods_id
        goods_id = self._extract_goods_id(url)
        
        # 2. 链接直转（备案完成后可用）
        zs = await self._call('pdd.ddk.goods.zs.unit.url.gen', {
            'source_url': url,
            'pid': self.pid,
            'custom_parameters': cp,
        })
        ok = await self._parse_zs(zs, url, wxid, goods_id)
        if ok.get('success'):
            return ok
        if not self._is_filing_error(zs):
            return ok

        # 3. 未备案：用推广链接接口生成「授权备案」页
        goods_sign = await self._sample_goods_sign()
        if not goods_sign:
            return api_error('pdd', '无法获取示例商品 goods_sign，请稍后重试', zs)

        promo = await self._call('pdd.ddk.goods.promotion.url.generate', {
            'p_id': self.pid,
            'goods_sign': goods_sign,
            'custom_parameters': cp,
            'generate_authority_url': True,
        })
        err = promo.get('error_response')
        if err:
            return api_error('pdd', err.get('sub_msg') or err.get('error_msg') or '转链失败', promo)

        lst = deep_get(promo, 'goods_promotion_url_generate_response', 'goods_promotion_url_list', default=[])
        if not lst:
            return api_error('pdd', '未返回推广链接', promo)

        item = lst[0]
        auth_url = item.get('mobile_url') or item.get('url') or ''
        short_url = item.get('mobile_short_url') or item.get('short_url') or auth_url
        return {
            'success': False,
            'platform': 'pdd',
            'message': FILING_HINT,
            'rebate_url': short_url,
            'auth_url': auth_url,
            'need_filing': True,
            'raw': promo,
        }

    async def _sample_goods_sign(self) -> str:
        rec = await self._call('pdd.ddk.goods.recommend.get', {'channel_type': 5, 'limit': 1})
        if rec.get('error_response'):
            return ''
        lst = deep_get(rec, 'goods_basic_detail_response', 'list', default=[])
        if not lst:
            return ''
        return str(lst[0].get('goods_sign') or '')

    async def _get_goods_by_goods_id(self, goods_id: str) -> dict:
        """
        按 goods_id 查询进宝商品佣金/价格（pdd.ddk.goods.recommend.get + goods_id）。
        转链接口不返回佣金，需单独拉取；必须命中同一 goods_id 才采用。
        """
        if not goods_id:
            return {}
        try:
            rec = await self._call('pdd.ddk.goods.recommend.get', {
                'channel_type': 5,
                'limit': 10,
                'offset': 0,
                'pid': self.pid,
                'custom_parameters': self._custom_parameters(),
                'goods_id': str(goods_id),
            })
            if rec.get('error_response'):
                logger.warning('拼多多商品佣金查询失败: %s', rec['error_response'])
                return {}

            lst = deep_get(rec, 'goods_basic_detail_response', 'list', default=[])
            goods = next((x for x in lst if str(x.get('goods_id')) == str(goods_id)), None)
            if not goods:
                logger.info('拼多多 recommend 未命中 goods_id=%s', goods_id)
                return {}

            price_yuan = float(goods.get('min_group_price') or 0) / 100
            rate = float(goods.get('promotion_rate') or 0)  # 千分比，如 60 表示 6%
            coupon = float(goods.get('coupon_discount') or goods.get('coupon_price') or 0) / 100
            final_price = max(0.0, round(price_yuan - coupon, 2))
            market_fee = float(goods.get('market_fee') or 0) / 100
            if market_fee > 0:
                commission_yuan = round(market_fee, 2)
            elif final_price and rate:
                commission_yuan = round(final_price * rate / 1000, 2)
            else:
                commission_yuan = 0.0
            logger.info(
                '拼多多佣金: goods_id=%s 拼团价=%.2f 券=%.2f 券后=%.2f rate=%s 佣金=%.2f',
                goods_id, price_yuan, coupon, final_price, rate, commission_yuan,
            )
            return {
                'goods_name': goods.get('goods_name', ''),
                'goods_desc': goods.get('goods_desc', ''),
                'goods_price': price_yuan,
                'final_price': final_price,
                'promotion_rate': rate,
                'commission_yuan': commission_yuan,
                'coupon_discount': coupon,
                'goods_sign': goods.get('goods_sign', ''),
            }
        except Exception as e:
            logger.warning('拼多多商品佣金查询异常: %s', e)
            return {}

    async def _parse_zs(self, result: dict, url: str, wxid: Optional[str], goods_id: Optional[str] = None) -> dict:
        if result.get('error_response'):
            err = result['error_response']
            return api_error('pdd', err.get('sub_msg') or err.get('error_msg') or '转链失败', result)

        resp = result.get('goods_zs_unit_generate_response') or result.get(
            'goods_zs_unit_url_generate_response', {}
        )
        
        # 兼容两种返回格式：url_list 数组 或 直接返回字段
        url_list = resp.get('url_list') or resp.get('multi_url_list') or []
        if url_list:
            item = url_list[0]
        else:
            # 直接在 response 根节点
            item = resp
        
        rebate_url = (
            item.get('mobile_short_url')
            or item.get('short_url')
            or item.get('url')
            or item.get('mobile_url', '')
        )
        if not rebate_url:
            return api_error('pdd', '多多进宝未返回推广链接', result)

        goods_info = {}
        if goods_id:
            goods_info = await self._get_goods_by_goods_id(goods_id)

        title = (
            goods_info.get('goods_name')
            or item.get('goods_name')
            or item.get('goods_desc')
            or (f'拼多多商品({goods_id})' if goods_id else '拼多多商品')
        )
        original_price = goods_info.get('goods_price', 0) or (
            float(item.get('goods_price') or 0) / 100 if item.get('goods_price') else 0
        )
        coupon_amount = goods_info.get('coupon_discount', 0)
        final_price = goods_info.get('final_price')
        if final_price is None and original_price:
            final_price = max(0.0, float(original_price) - float(coupon_amount or 0))
        commission = goods_info.get('commission_yuan', 0)

        out = success_result(
            'pdd',
            rebate_url=rebate_url,
            original_url=url,
            title=title,
            original_price=original_price,
            final_price=final_price or 0,
            commission=commission,
            coupon_amount=coupon_amount,
            item_id=goods_id or '',
            convert_api='pdd.ddk.goods.zs.unit.url.gen',
            raw=result,  # 保存原始响应用于调试
        )
        if wxid:
            out['sub_union_id'] = wxid
        return out

    async def _sync_promotion_fallback(self, url: str, wxid: Optional[str]):
        """goods_sign 已知时用推广链接接口（同步包装供 _parse_zs 内备用）"""
        return None

    async def _call(self, method: str, biz: dict) -> dict:
        params = {
            'type': method,
            'client_id': self.client_id,
            'timestamp': str(int(datetime.now().timestamp())),
            'data_type': 'JSON',
        }
        params.update(biz)
        params['sign'] = md5_sign(params, self.client_secret)
        resp = await http_request('POST', self.API_URL, data=params)
        return parse_json_response(resp)
