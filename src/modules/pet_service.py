"""
宠物上门服务模块
支持上门喂养、遛狗、洗澡美容预约
"""

import logging

logger = logging.getLogger(__name__)


class PetService:
    def __init__(self):
        # 模拟美团/本地宠物店推广链接
        self.service_links = {
            "feeding": "https://mock-meituan-pet-feeding",
            "walking": "https://mock-meituan-pet-walking"
        }

    async def get_home_service(self, service_type: str = "feeding") -> str:
        """
        获取宠物上门服务信息
        :param service_type: feeding(喂养), walking(遛狗)
        """
        if service_type == "walking":
            return (
                f"🐕 **专业遛狗服务**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 价格：¥39.9/次 (30分钟)\n"
                f"✅ 包含：牵绳遛弯、清理排泄物、反馈视频\n"
                f"🔗 [点击预约靠谱铲屎官]( {self.service_links['walking']} )\n\n"
                f"⚠️ 建议提前半天预约，周末火爆！"
            )
        else:
            return (
                f"🐱 **春节/出差上门喂养**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💰 价格：¥49.9/次 (30分钟内)\n"
                f"✅ 包含：加粮换水、清理猫砂、陪玩逗猫、全程录像\n"
                f"🔗 [点击预约金牌喂养师]( {self.service_links['feeding']} )\n\n"
                f"✨ 一二线城市覆盖，让毛孩子在家也安心！"
            )
