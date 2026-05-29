"""
电商返利核心模块
整合多平台查券、比价
"""

import logging
from datetime import datetime
from src.rebate_api import RebateAPI, extract_url_from_text
from src.database import DatabaseManager
from src.compare_context import set_pending_compare
from src.compare_tokens import issue_compare_token
from src.compliance_copy import (
    build_compare_page_url,
    extract_share_product_hint,
    format_no_promo_reply,
    format_promo_reply,
)
from src.modules.price_comparison import PriceComparisonService

logger = logging.getLogger(__name__)


class EcommerceService:
    def __init__(self):
        self.rebate_api = RebateAPI()
        self.db = DatabaseManager()
        self.price_comparison = PriceComparisonService()

    async def handle_link(self, url: str, wxid: str = None, notify_chat: str = None,
                          notify_is_group: bool = False, user_nickname: str = None) -> str:
        """
        处理商品链接：转链 + 比价
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
            return await self._reply_no_promo(result, text, platform, wxid)

        has_coupon = float(result.get('coupon_amount') or 0) > 0
        has_rebate = float(result.get('user_rebate') or 0) > 0
        has_commission = float(result.get('commission') or 0) > 0
        if not (has_coupon or has_rebate or has_commission):
            logger.info('转链成功但无券无返利，按无推广处理: %s', result.get('title', ''))
            return await self._reply_no_promo(result, text, platform, wxid)

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

        return format_promo_reply(result)

    async def _reply_no_promo(
        self, result: dict, raw_text: str, platform: str, wxid: str | None
    ) -> str:
        logger.warning('无推广优惠: %s', result.get('message', ''))
        product_name = result.get('title') or extract_share_product_hint(raw_text) or '该商品'
        if wxid:
            set_pending_compare(wxid, keyword=product_name, platform=platform)
        token = issue_compare_token(wxid=wxid or '', keyword=product_name, platform=platform)
        compare_url = build_compare_page_url(token) if token else ''
        return format_no_promo_reply(result, raw_text=raw_text, compare_url=compare_url)

    async def run_compare_for_keyword(
        self, keyword: str, platform: str | None = None, wxid: str | None = None
    ) -> str:
        """回复【全网比价】或打开比价页时使用。"""
        keyword = (keyword or '').strip()
        if not keyword:
            return '💡 请先发送商品链接，再查看全网比价。'
        try:
            comparison_result = await self.price_comparison.compare_price(
                keyword=keyword,
                exclude_platform=platform,
                wxid=wxid,
            )
            return self.price_comparison.format_comparison_message(comparison_result)
        except Exception as e:
            logger.warning('比价失败: %s', e)
            return '❌ 全网比价暂时不可用，请稍后再试。'

    async def handle_keyword_search(self, keyword: str) -> str:
        """
        处理关键词搜索：全网比价（目前以模拟逻辑为主，待接入真实搜索 API）
        :param keyword: 搜索关键词
        :return: 比价结果消息
        """
        # TODO: 后续接入淘宝/京东/拼多多的搜索 API
        # 目前先返回一个引导性回复
        return f"🔍 正在为你搜索「{keyword}」的全网最低价...\n\n💡 提示：目前支持直接发送商品链接进行精准查券哦！"

