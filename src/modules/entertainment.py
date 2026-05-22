"""
沉浸式娱乐服务模块
专注于密室逃脱、剧本杀、Livehouse 等一二线城市高频娱乐项目
依托美团/大众点评 API
"""

import logging
from src.modules.local_life import LocalLifeService

logger = logging.getLogger(__name__)


class EntertainmentService:
    def __init__(self):
        self.local_life = LocalLifeService()

    async def search_script_murder(self, city: str = "北京", keyword: str = "") -> str:
        """
        搜索剧本杀/密室信息
        :param city: 城市名称
        :param keyword: 关键词（如：恐怖、硬核、情感）
        """
        logger.info(f"正在搜索 {city} 的剧本杀/密室: {keyword}")
        
        # 1. 调用底层美团搜索接口（模拟调用，实际需完善 local_life 中的搜索方法）
        # result = await self.local_life.search_meituan(category="休闲娱乐", keyword=keyword, city=city)
        
        msg = f"🎭 **{city} 剧本杀/密室精选**\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"🔍 搜索关键词：{keyword if keyword else '热门好评'}\n\n"
        
        # 2. 模拟返回几条高质量推荐（实际应解析 API 结果）
        msg += f"1️⃣ **《古木吟》** (情感/沉浸)\n"
        msg += f"   ⭐ 9.8分 | 👥 6人 | ⏱ 4h\n"
        msg += f"   💰 团购价：¥128/人 [点击预订](https://mock-meituan-link)\n\n"
        
        msg += f"2️⃣ **《风间雅》** (日式/恐怖)\n"
        msg += f"   ⭐ 9.5分 | 👥 7人 | ⏱ 3.5h\n"
        msg += f"   💰 团购价：¥158/人 [点击预订](https://mock-meituan-link)\n\n"
        
        msg += f"💡 **省钱提示**：通过本链接预订可享额外返利，并支持在线选本！"
        
        return msg

    async def get_weekend_deals(self, city: str = "北京") -> str:
        """
        获取周末娱乐特惠（Livehouse/脱口秀）
        """
        return (
            f"🎸 **{city} 周末娱乐指南**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎤 [脱口秀开放麦特惠票](https://mock-link)\n"
            f"🎸 [本地乐队 Livehouse 预售](https://mock-link)\n"
            f"🎬 [私人影院双人套餐](https://mock-link)\n\n"
            f"✨ 一二线城市限定福利，手慢无！"
        )
