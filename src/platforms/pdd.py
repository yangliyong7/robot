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
    def _custom_parameters(wxid: Optional[str] = None) -> str:
        uid = re.sub(r'[^\w\-]', '_', (wxid or 'rebate_bot').strip())[:32] or 'rebate_bot'
        return json.dumps({'uid': uid}, ensure_ascii=False)

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

    async def _get_goods_detail(self, goods_id: str) -> dict:
        """获取商品详细信息（名称、价格、佣金）"""
        try:
            logger.info(f'正在获取商品详情: goods_id={goods_id}')
            detail = await self._call('pdd.ddk.goods.detail.get', {
                'goods_id_list': [goods_id],
            })
            
            logger.info(f'商品详情 API 响应: {detail}')
            
            if detail.get('error_response'):
                logger.warning(f'商品详情 API 错误: {detail["error_response"]}')
                return {}
            
            goods_list = deep_get(detail, 'goods_detail_response', 'goods_details', default=[])
            if not goods_list:
                logger.warning(f'未找到商品详情: goods_id={goods_id}')
                return {}
            
            goods = goods_list[0]
            logger.info(f'获取到商品详情: {goods.get("goods_name", "未知")}')
            return {
                'goods_name': goods.get('goods_name', ''),
                'goods_desc': goods.get('goods_desc', ''),
                'goods_price': float(goods.get('goods_price') or 0) / 100 if goods.get('goods_price') else 0,
                'promotion_rate': float(goods.get('promotion_rate') or 0),
                'coupon_discount': float(goods.get('coupon_discount') or 0) / 100 if goods.get('coupon_discount') else 0,
            }
        except Exception as e:
            logger.warning(f'获取商品详情失败: {e}')
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
        
        rebate_url = item.get('url') or item.get('short_url') or item.get('mobile_url', '')
        if not rebate_url:
            return api_error('pdd', '多多进宝未返回推广链接', result)
        
        # 尝试获取商品详情（名称、价格、佣金）
        goods_info = {}
        if goods_id:
            goods_info = await self._get_goods_detail(goods_id)
        
        # 优先使用商品详情接口返回的数据，其次使用转链接口返回的数据
        title = goods_info.get('goods_name') or item.get('goods_name') or item.get('goods_desc') or '拼多多商品'
        original_price = goods_info.get('goods_price', 0) or (float(item.get('goods_price') or 0) / 100 if item.get('goods_price') else 0)
        commission = goods_info.get('promotion_rate', 0) or float(item.get('promotion_rate') or 0)
        
        out = success_result(
            'pdd',
            rebate_url=rebate_url,
            original_url=url,
            title=title,
            original_price=original_price,
            commission=commission,
            convert_api='pdd.ddk.goods.zs.unit.url.gen',
            raw=result,  # 保存原始响应用于调试
        )
        if wxid:
            out['sub_union_id'] = self._custom_parameters(wxid)
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
