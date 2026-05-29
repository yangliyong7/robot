"""
商品搜索比价服务
在商品无优惠时，自动对比淘宝、京东、拼多多价格
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from config.config import REBATE_CONFIG, COMMISSION_CONFIG
from src.platforms.taobao import TaobaoClient
from src.platforms.jd import JDClient
from src.platforms.pdd import PDDClient
from src.platforms.base import http_request, parse_json_response, md5_sign, deep_get

logger = logging.getLogger(__name__)


class PriceComparisonService:
    """全网比价服务"""
    
    def __init__(self):
        self.taobao = TaobaoClient()
        self.jd = JDClient()
        self.pdd = PDDClient()
    
    async def compare_price(
        self,
        keyword: str,
        exclude_platform: str = None,
        wxid: str = None
    ) -> Dict:
        """
        全网比价
        :param keyword: 搜索关键词（商品名称）
        :param exclude_platform: 排除的平台（当前商品所在平台）
        :param wxid: 用户微信ID
        :return: 比价结果
        """
        logger.info(f'开始比价: keyword={keyword}, exclude={exclude_platform}')
        
        # 并发搜索各平台
        tasks = []
        
        if exclude_platform != 'taobao':
            tasks.append(self._search_taobao(keyword, wxid))
        
        if exclude_platform != 'jd':
            tasks.append(self._search_jd(keyword, wxid))
        
        if exclude_platform != 'pdd':
            tasks.append(self._search_pdd(keyword, wxid))
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 收集有效结果
        price_list = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f'搜索失败: {result}')
                continue
            if result and result.get('success'):
                price_list.append(result)
        
        if not price_list:
            return {
                'success': False,
                'message': '未找到相关商品',
            }
        
        # 按到手价排序
        price_list.sort(key=lambda x: x.get('final_price', 999999))
        
        # 找出最低价
        best_price = price_list[0]
        
        return {
            'success': True,
            'keyword': keyword,
            'total_results': len(price_list),
            'best_price': best_price,
            'price_list': price_list,
        }
    
    async def _search_taobao(self, keyword: str, wxid: str = None) -> Optional[Dict]:
        """搜索淘宝商品"""
        # TODO: 好单库没有直接的搜索接口，需要接入其他淘宝搜索 API
        # 如：淘宝客官方搜索 taobao.tbk.dg.material.optional
        logger.warning('淘宝搜索暂未实现，跳过')
        return None
    
    async def _search_jd(self, keyword: str, wxid: str = None) -> Optional[Dict]:
        """搜索京东商品（京东联盟 goods.promotiongoodsinfo.query）"""
        try:
            import json
            
            client = JDClient()
            if not client._keys_ok():
                logger.warning('京东联盟未配置，跳过搜索')
                return None
            
            # 调用京东联盟搜索接口
            param_json = {
                'goodsReqDTO': {
                    'keyWord': keyword,
                    'pageSize': 5,
                    'pageIndex': 1,
                }
            }
            
            result = await client._call('jd.union.open.goods.promotiongoodsinfo.query', param_json)
            
            # 打印原始响应调试
            logger.info(f'京东搜索原始响应: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}')
            
            # 解析响应
            resp_key = 'jd_union_open_goods_promotiongoodsinfo_query_responce'
            resp_data = result.get(resp_key) or result.get('jd_union_open_goods_promotiongoodsinfo_query_response', {})
            
            if not resp_data:
                logger.warning(f'京东搜索响应格式异常: {list(result.keys())}')
                return None
            
            logger.info(f'京东搜索响应数据: code={resp_data.get("code")}')
            
            if str(resp_data.get('code')) not in ('0', '200'):
                logger.warning(f'京东搜索失败: {resp_data.get("message")}')
                return None
            
            # 解析返回结果
            result_data = resp_data.get('getResult')
            if isinstance(result_data, str):
                result_data = json.loads(result_data)
            
            goods_list = result_data.get('data', []) if isinstance(result_data, dict) else []
            if not goods_list or len(goods_list) == 0:
                logger.info('京东搜索无结果')
                return None
            
            # 取第一个商品
            item = goods_list[0] if isinstance(goods_list, list) else goods_list
            
            price = float(item.get('wlPrice') or item.get('price') or 0)
            commission_rate = float(item.get('commissionShare') or 0) / 100
            commission = round(price * commission_rate, 2)
            
            rebate_rate = COMMISSION_CONFIG.get('jd_rate', 0.7)
            user_rebate = round(commission * rebate_rate, 2)
            
            material_url = f"https://item.jd.com/{item.get('skuId', '')}.html"
            
            return {
                'success': True,
                'platform': 'jd',
                'title': item.get('skuName') or item.get('goodsName') or keyword,
                'original_price': price,
                'final_price': price,
                'coupon_amount': 0,
                'commission': commission,
                'user_rebate': user_rebate,
                'rebate_url': material_url,
            }
            
        except Exception as e:
            logger.error(f'京东搜索失败: {e}')
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _search_pdd(self, keyword: str, wxid: str = None) -> Optional[Dict]:
        """搜索拼多多商品（多多进宝 goods.search）"""
        try:
            client = PDDClient()
            if not client._configured():
                logger.warning('拼多多联盟未配置，跳过搜索')
                return None
            
            # 搜索接口也需要传 pid 和 custom_parameters（备案参数）
            cp = client._custom_parameters(wxid)
            
            # 调用多多进宝搜索接口
            result = await client._call('pdd.ddk.goods.search', {
                'keyword': keyword,
                'limit': 5,
                'offset': 0,
                'p_id': client.pid,  # 添加备案参数
                'custom_parameters': cp,  # 添加备案参数
            })
            
            logger.info(f'拼多多搜索响应')
            
            if result.get('error_response'):
                err = result['error_response']
                logger.warning(f'拼多多搜索失败: {err.get("sub_msg") or err.get("error_msg")}')
                return None
            
            goods_list = deep_get(result, 'goods_search_response', 'goods_list', default=[])
            if not goods_list or len(goods_list) == 0:
                logger.info('拼多多搜索无结果')
                return None
            
            # 取第一个商品
            item = goods_list[0] if isinstance(goods_list, list) else goods_list
            
            # 拼多多价格是分，需要除以100；佣金按券后价或 market_fee
            price = float(item.get('min_group_price') or item.get('goods_price') or 0) / 100
            coupon_discount = float(item.get('coupon_discount') or item.get('coupon_price') or 0) / 100
            final_price = max(0.0, round(price - coupon_discount, 2))
            promotion_rate = float(item.get('promotion_rate') or 0)  # 千分比
            market_fee = float(item.get('market_fee') or 0) / 100
            if market_fee > 0:
                commission = round(market_fee, 2)
            else:
                commission = round(final_price * promotion_rate / 1000, 2)
            
            rebate_rate = COMMISSION_CONFIG.get('pdd_rate', 0.7)
            user_rebate = round(commission * rebate_rate, 2)
            
            goods_id = item.get('goods_id', '')
            material_url = f"https://mobile.yangkeduo.com/goods.html?goods_id={goods_id}"
            
            return {
                'success': True,
                'platform': 'pdd',
                'title': item.get('goods_name') or item.get('goods_desc') or keyword,
                'original_price': price,
                'final_price': final_price,
                'coupon_amount': coupon_discount,
                'commission': commission,
                'user_rebate': user_rebate,
                'rebate_url': material_url,
            }
            
        except Exception as e:
            logger.error(f'拼多多搜索失败: {e}')
            return None
    
    def format_comparison_message(self, comparison_result: Dict) -> str:
        """格式化比价结果"""
        if not comparison_result.get('success'):
            return f"❌ {comparison_result.get('message', '比价失败')}"
        
        keyword = comparison_result['keyword']
        best = comparison_result['best_price']
        price_list = comparison_result['price_list']
        
        platform_names = {
            'taobao': '淘宝/天猫',
            'jd': '京东',
            'pdd': '拼多多',
        }
        
        msg = f"🔍 「{keyword}」全网比价\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"共找到 {comparison_result['total_results']} 个平台有售\n\n"
        
        # 显示各平台价格
        for i, item in enumerate(price_list, 1):
            platform = item.get('platform', 'unknown')
            name = platform_names.get(platform, platform)
            
            medal = '🥇' if i == 1 else ('🥈' if i == 2 else '🥉')
            
            msg += f"{medal} {name}\n"
            msg += f"   💰 原价：¥{item.get('original_price', 0):.2f}\n"
            
            if item.get('coupon_amount', 0) > 0:
                msg += f"   🎫 优惠券：-¥{item['coupon_amount']:.2f}\n"
            
            msg += f"   ✨ 到手价：¥{item.get('final_price', 0):.2f}\n"
            
            if item.get('user_rebate', 0) > 0:
                msg += f"   🎁 预估返利：¥{item['user_rebate']:.2f}\n"
                msg += f"   💵 实际成本：¥{item['final_price'] - item['user_rebate']:.2f}\n"
            
            # 显示推广链接
            rebate_url = item.get('rebate_url', '')
            if rebate_url:
                # 短链接优先
                short_url = item.get('short_url', rebate_url)
                msg += f"   🔗 购买链接：{short_url}\n"
            
            # 最低价标记
            if i == 1:
                msg += f"   ⭐ 推荐！最低价\n"
            
            msg += f"\n"
        
        # 底部提示
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"💡 价格实时变动，以实际下单为准\n"
        msg += f"⚠️ 返利金额以最终结算为准\n"
        
        return msg
