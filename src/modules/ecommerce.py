"""
电商返利核心模块
整合多平台查券、比价及 AI 购物建议
"""

import logging
from datetime import datetime
from src.rebate_api import RebateAPI, extract_url_from_text
from src.ai.deepseek_client import DeepSeekClient
from src.database import DatabaseManager
from src.compliance_copy import estimated_reward_label, link_success_notes
from src.modules.price_comparison import PriceComparisonService

logger = logging.getLogger(__name__)


class EcommerceService:
    def __init__(self):
        self.rebate_api = RebateAPI()
        self.ai_client = DeepSeekClient()
        self.db = DatabaseManager()
        self.price_comparison = PriceComparisonService()

    async def handle_link(self, url: str, wxid: str = None, notify_chat: str = None,
                          notify_is_group: bool = False, user_nickname: str = None) -> str:
        """
        处理商品链接：转链 + AI 评估
        :param url: 商品链接或含链接的文本
        :param wxid: 用户微信ID（用于记录订单）
        :param notify_chat: 结算通知发送目标（群名或私聊昵称）
        :param notify_is_group: 是否在群聊下单
        :param user_nickname: 群内下单用户昵称（用于 @ 提醒）
        :return: 格式化后的回复消息
        """
        urls = extract_url_from_text(url)
        text = url.strip()
        platform = self.rebate_api.detect_platform(text)
        # 好单库 analyze.taoword 需要完整文案（含淘口令/短链）
        convert_input = text if platform == 'taobao' else (urls[0] if urls else text)
        link = urls[0] if urls else text
        result = await self.rebate_api.convert_link(convert_input, platform, wxid=wxid)

        if not result['success']:
            # 转链失败（可能商品未加入推广计划），触发比价
            logger.warning(f"转链失败，尝试比价: {result.get('message', '未知错误')}")
            
            # 提取商品名称（如果有）
            product_name = result.get('title', '')
            if not product_name:
                # 尝试从链接提取或使用默认关键词
                product_name = "该商品"
            
            # 触发比价
            try:
                comparison_result = await self.price_comparison.compare_price(
                    keyword=product_name,
                    exclude_platform=platform,
                    wxid=wxid
                )
                if comparison_result.get('success'):
                    msg = f"❌ 该商品暂无推广优惠\n\n"
                    msg += self.price_comparison.format_comparison_message(comparison_result)
                    return msg
            except Exception as e:
                logger.warning(f'比价失败: {e}')
            
            return f"❌ 解析失败：{result.get('message', '未知错误')}\n\n💡 该商品可能未加入推广计划，建议直接购买或搜索其他平台"

        order_no = None
        if wxid:
            order_no = f"ORDER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{wxid[-4:]}"
            self.db.add_order(
                order_no=order_no,
                wxid=wxid,
                platform=result.get('platform', 'unknown'),
                product_title=result.get('title', ''),
                product_url=link,
                original_price=result.get('original_price', 0),
                commission=result.get('commission', 0),
                user_rebate=result.get('user_rebate', 0),
                platform_item_id=str(result.get('item_id', '') or ''),
                notify_chat=notify_chat,
                notify_is_group=notify_is_group,
                user_nickname=user_nickname,
            )
            result['order_no'] = order_no
            logger.info(f"订单已记录: {order_no}")

        # 3. 构造商品信息用于 AI 分析
        product_info = {
            'title': result.get('title', '未知商品'),
            'platform': platform,
            'original_price': result.get('original_price', 0),
            'final_price': result.get('final_price', 0),
            'commission': result.get('commission', 0),
            'user_rebate': result.get('user_rebate', 0)
        }

        # 4. 检查用户是否省到钱（核心判断标准）
        # 省钱 = 有优惠券 OR 有返利（佣金）
        has_coupon = result.get('coupon_amount', 0) > 0
        has_rebate = result.get('user_rebate', 0) > 0
        has_commission = result.get('commission', 0) > 0
        
        # 只要有任何一项优惠，就算省钱了
        user_saved_money = has_coupon or has_rebate or has_commission
        
        logger.info(
            f'优惠检查: coupon={has_coupon}(¥{result.get("coupon_amount", 0):.2f}), '
            f'rebate={has_rebate}(¥{result.get("user_rebate", 0):.2f}), '
            f'commission={has_commission}(¥{result.get("commission", 0):.2f}), '
            f'省钱={user_saved_money}'
        )
        
        # 5. 如果用户没省到钱，触发全网比价
        comparison_msg = ''
        if not user_saved_money:
            product_name = result.get('title', '该商品')
            logger.info(f'用户未省到钱，触发比价: {product_name}')
            
            try:
                comparison_result = await self.price_comparison.compare_price(
                    keyword=product_name,
                    exclude_platform=platform,
                    wxid=wxid
                )
                if comparison_result.get('success'):
                    comparison_msg = '\n\n' + self.price_comparison.format_comparison_message(comparison_result)
                else:
                    logger.info(f'比价无结果: {comparison_result.get("message", "")}')
            except Exception as e:
                logger.warning(f'比价失败: {e}', exc_info=True)
        
        # 6. 获取 AI 购物建议
        advice = await self.ai_client.generate_advice(
            context="用户发送了一个商品链接，请给出简短的购买建议或评价。",
            product_info=product_info
        )

        # 7. 组合最终回复
        message = self._format_ecommerce_message(result, advice)
        message += comparison_msg
        return message

    async def handle_keyword_search(self, keyword: str) -> str:
        """
        处理关键词搜索：全网比价（目前以模拟逻辑为主，待接入真实搜索 API）
        :param keyword: 搜索关键词
        :return: 比价结果消息
        """
        # TODO: 后续接入淘宝/京东/拼多多的搜索 API
        # 目前先返回一个引导性回复
        return f"🔍 正在为你搜索「{keyword}」的全网最低价...\n\n💡 提示：目前支持直接发送商品链接进行精准查券哦！"

    def _format_ecommerce_message(self, result: dict, ai_advice: str) -> str:
        """格式化电商回复消息"""
        platform_names = {
            'taobao': '淘宝/天猫',
            'jd': '京东',
            'pdd': '拼多多',
            'meituan': '美团',
            'douyin': '抖音电商',
            'vipshop': '唯品会',
            'dangdang': '当当',
            'kuaishou': '快手',
            'bilibili': 'B站会员购',
            'xiaomi': '小米有品',
            'yanxuan': '网易严选',
            'xianyu': '闲鱼',
            'eleme': '饿了么',
            'weixin_store': '微信小店/推客',
            'ctrip': '携程',
            'tongcheng': '同程旅行',
            'qunar': '去哪儿',
            'fliggy': '飞猪旅行',
            'taopiaopiao': '淘票票',
        }
        platform = result.get('platform', 'unknown')
        name = platform_names.get(platform, platform)

        msg = f"🛒 {name}优惠详情\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        
        if result.get('title'):
            msg += f"📦 商品：{result['title']}\n"
        
        if result.get('original_price'):
            msg += f"💰 原价：¥{result['original_price']:.2f}\n"
        
        if result.get('coupon_amount') and result['coupon_amount'] > 0:
            msg += f"🎫 优惠券：-¥{result['coupon_amount']:.2f}\n"
        
        if result.get('final_price'):
            msg += f"✨ 到手价：¥{result['final_price']:.2f}\n"
        
        if result.get('user_rebate') and result['user_rebate'] > 0:
            msg += f"🎁 {estimated_reward_label()}：¥{result['user_rebate']:.2f}\n"

        msg += f"\n💬 导购参考：\n{ai_advice}\n"
        msg += f"\n🔗 推广购买链接：\n{result.get('rebate_url', '')}\n"
        msg += link_success_notes()

        return msg
