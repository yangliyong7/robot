"""
差旅出行模块
整合携程、同程、去哪儿酒店/机票推广
"""

import logging
import re

from config.config import COMMISSION_CONFIG
from src.ai.deepseek_client import DeepSeekClient
from src.platforms.ctrip import CtripClient
from src.platforms.tongcheng import TongchengClient
from src.platforms.qunar import QunarClient
from src.platforms.fliggy import FliggyClient
from src.compliance_copy import estimated_reward_label, link_success_notes

logger = logging.getLogger(__name__)

TRAVEL_PLATFORM_NAMES = {
    'ctrip': '携程',
    'tongcheng': '同程旅行',
    'qunar': '去哪儿',
    'fliggy': '飞猪旅行',
}


class TravelService:
    def __init__(self):
        self.ctrip = CtripClient()
        self.tongcheng = TongchengClient()
        self.qunar = QunarClient()
        self.fliggy = FliggyClient()
        self.ai_client = DeepSeekClient()

    async def search_hotel(self, city: str, date: str = '今晚', wxid: str = None) -> str:
        """生成携程/同程/去哪儿酒店推广链接"""
        city = self._extract_city(city) or city or '北京'
        sections = [f'🏨 {city} 酒店预订推荐', '━━━━━━━━━━━━━━━', f'📅 入住时间：{date}', '']

        for platform, client in (
            ('ctrip', self.ctrip),
            ('tongcheng', self.tongcheng),
            ('qunar', self.qunar),
        ):
            result = await client.get_hotel_link(city, wxid=wxid)
            name = TRAVEL_PLATFORM_NAMES[platform]
            if result.get('success'):
                rate = COMMISSION_CONFIG.get(f'{platform}_rate', 0.7)
                rebate = round(float(result.get('commission', 0)) * rate, 2)
                sections.append(f'✅ {name}')
                sections.append(f"🔗 {result.get('rebate_url', '')}")
                if rebate > 0:
                    sections.append(f'🎁 预估{estimated_reward_label()}：¥{rebate:.2f}')
                sections.append('')
            else:
                sections.append(f'⏭ {name}：{result.get("message", "未配置")}')
                sections.append('')

        fliggy_result = await self.fliggy.get_activity_link(wxid=wxid)
        if fliggy_result.get('success'):
            rate = COMMISSION_CONFIG.get('fliggy_rate', 0.7)
            rebate = round(float(fliggy_result.get('commission', 0)) * rate, 2)
            sections.append('✅ 飞猪旅行')
            sections.append(f"🔗 {fliggy_result.get('rebate_url', '')}")
            if rebate > 0:
                sections.append(f'🎁 预估{estimated_reward_label()}：¥{rebate:.2f}')
            sections.append('')
        else:
            sections.append(f'⏭ 飞猪：{fliggy_result.get("message", "未配置 activity_id")}')
            sections.append('')

        sections.append('💡 出行订单完成后才确认佣金，请耐心等待到账。')
        sections.append(link_success_notes())
        return '\n'.join(sections)

    async def search_flight(self, content: str, wxid: str = None) -> str:
        """机票推广（目前优先携程）"""
        from_city, to_city = self._parse_flight_cities(content)
        result = await self.ctrip.get_flight_link(from_city, to_city, wxid=wxid)
        if result.get('success'):
            return (
                f'✈️ {from_city} → {to_city} 机票预订\n'
                f"🔗 {result.get('rebate_url', '')}\n"
                f'{link_success_notes()}'
            )
        return f"❌ 机票推广暂不可用：{result.get('message', '请配置携程联盟')}"

    async def convert_travel_link(self, url: str, wxid: str = None) -> str:
        """识别出行链接并转推广链"""
        from src.rebate_api import RebateAPI
        api = RebateAPI()
        platform = api.detect_platform(url)
        if platform not in ('ctrip', 'tongcheng', 'qunar', 'fliggy'):
            return '❌ 未识别的出行平台链接'
        result = await api.convert_link(url, platform, wxid=wxid)
        if not result.get('success'):
            return f"❌ {result.get('message', '转链失败')}"
        return api.format_rebate_message(result)

    @staticmethod
    def _extract_city(text: str) -> str:
        m = re.search(r'([\u4e00-\u9fff]{2,8}?)(?:酒店|订房|住宿|宾馆)', text)
        if m:
            return m.group(1)
        m = re.search(r'([\u4e00-\u9fff]{2,8})', text)
        return m.group(1) if m else ''

    @staticmethod
    def _parse_flight_cities(content: str):
        m = re.search(r'([\u4e00-\u9fff]{2,6}).*?(?:到|去|→|->)\s*([\u4e00-\u9fff]{2,6})', content)
        if m:
            return m.group(1), m.group(2)
        return '北京', '上海'

    async def get_taxi_coupon(self) -> str:
        return (
            '🚗 出行打车福利\n'
            '━━━━━━━━━━━━━━━\n'
            '✅ 高德/滴滴 CPS 需单独申请联盟\n'
            '💡 可先使用「携程/同程」预订机酒出行套餐'
        )
