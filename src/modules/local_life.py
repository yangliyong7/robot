"""
本地生活模块
整合美团 CPS Open API、饿了么等平台的优惠查询与返利
"""

import logging
from config.config import LOCAL_LIFE_CONFIG, COMMISSION_CONFIG
from src.ai.deepseek_client import DeepSeekClient
from src.platforms.eleme import ElemeClient
from src.platforms.meituan import MeituanClient
from src.rebate_api import RebateAPI
from src.compliance_copy import estimated_reward_label, link_success_notes

logger = logging.getLogger(__name__)


class LocalLifeService:
    def __init__(self):
        self.meituan_app_id = LOCAL_LIFE_CONFIG.get('meituan_app_id')
        self.meituan_secret = LOCAL_LIFE_CONFIG.get('meituan_app_secret')
        self.eleme = ElemeClient()
        self.meituan = MeituanClient()
        self.rebate_api = RebateAPI()
        self.ai_client = DeepSeekClient()

    async def search_food(self, city: str = '北京', keyword: str = '美食', wxid: str = None) -> str:
        """搜索附近美食/团购（美团 CPS Open API query_coupon）"""
        logger.info('正在搜索 %s 的 %s...', city, keyword)
        deals = await self._search_meituan_deals(city, keyword, wxid=wxid)
        if not deals:
            return f'😅 抱歉，在 {city} 没找到关于「{keyword}」的优惠信息，换个词试试？'

        advice = await self.ai_client.generate_advice(
            context=f'用户在{city}想找{keyword}，以下是找到的优惠列表：{deals}',
            product_info={'type': 'local_deal'},
        )
        return self._format_local_message(deals, advice)

    async def _search_meituan_deals(self, city: str, keyword: str, wxid: str = None) -> list:
        """美团团购/闪购搜索，失败时返回示例数据"""
        if not self.meituan._cps_configured():
            return await self._mock_search_deals(city, keyword)

        city_id = LOCAL_LIFE_CONFIG.get('meituan_city_id', '')
        search = await self.meituan.search_coupons(
            keyword=keyword,
            platform=2,
            biz_line=1,
            page_size=5,
            city_id=city_id or None,
        )
        if not search.get('success') or not search.get('deals'):
            logger.warning('美团团购搜索无结果: %s', search.get('message'))
            return await self._mock_search_deals(city, keyword)

        deals = []
        for item in search['deals'][:3]:
            link = ''
            pvs = item.get('product_view_sign')
            if pvs:
                link_result = await self.meituan.get_referral_link(
                    product_view_sign=pvs,
                    wxid=wxid,
                    platform=2,
                    biz_line=1,
                )
                if link_result.get('success'):
                    link = link_result.get('rebate_url', '')
            if not link:
                link = 'https://i.meituan.com'

            deals.append({
                'title': item.get('title', keyword),
                'price': item.get('price', 0),
                'original_price': item.get('original_price', item.get('price', 0)),
                'distance': item.get('sale_volume', '美团热销'),
                'link': link,
            })
        return deals

    async def get_takeaway_redpacket(self, wxid: str = None) -> str:
        """获取外卖红包链接（饿了么 + 可选美团）"""
        lines = ['🧧 今日外卖红包已备好！', '━━━━━━━━━━━━━━━']

        eleme_result = await self.eleme.get_activity_link(wxid=wxid)
        if eleme_result.get('success'):
            rate = COMMISSION_CONFIG.get('eleme_rate', 0.7)
            rebate = round(float(eleme_result.get('commission', 0)) * rate, 2)
            lines.append(f"🍜 饿了么：{eleme_result.get('title', '天天领红包')}")
            lines.append(f"🔗 {eleme_result.get('rebate_url', '')}")
            if eleme_result.get('tpwd'):
                lines.append(f"📱 口令：{eleme_result['tpwd']}")
            if rebate > 0:
                lines.append(f"🎁 预估{estimated_reward_label()}：¥{rebate:.2f}")
            lines.append('')
        else:
            lines.append(f"🍜 饿了么：{eleme_result.get('message', '暂未配置')}")
            lines.append('')

        meituan_url = LOCAL_LIFE_CONFIG.get('meituan_waimai_url', '')
        if meituan_url:
            lines.append(f'🛵 美团外卖：{meituan_url}')
        elif self.meituan._configured():
            mt = await self.meituan.convert('https://i.meituan.com/waimai', wxid=wxid)
            if mt.get('success'):
                lines.append(f"🛵 美团外卖：{mt.get('rebate_url', '')}")
            else:
                lines.append(f"🛵 美团：{mt.get('message', '转链失败')}")
        else:
            lines.append('🛵 美团：请在 LOCAL_LIFE_CONFIG 配置 meituan_waimai_url 或美团联盟密钥')

        lines.append('')
        lines.append('💡 每天都能领，下单前记得先领券哦~')
        lines.append(link_success_notes())
        return '\n'.join(lines)

    async def _mock_search_deals(self, city, keyword):
        """未配置美团 CPS 密钥时的示例数据"""
        return [
            {
                'title': f'{city}必吃榜·老张{keyword}店',
                'price': 128.0,
                'original_price': 200.0,
                'distance': '1.2km',
                'link': 'https://i.meituan.com',
            },
            {
                'title': f'人气爆棚·{keyword}双人超值套餐',
                'price': 88.0,
                'original_price': 156.0,
                'distance': '800m',
                'link': 'https://i.meituan.com',
            },
        ]

    def _format_local_message(self, deals: list, ai_advice: str) -> str:
        msg = '🍲 为您精选的优惠\n'
        msg += '━━━━━━━━━━━━━━━\n'

        for i, deal in enumerate(deals[:3], 1):
            save_amount = deal['original_price'] - deal['price']
            msg += f"{i}. 【{deal['title']}】\n"
            msg += f"   💰 团购价：¥{deal['price']} (立省¥{save_amount})\n"
            msg += f"   📍 {deal['distance']}\n"
            msg += f"   🔗 {deal['link']}\n\n"

        msg += f'💬 AI 推荐语：\n{ai_advice}\n'
        return msg
