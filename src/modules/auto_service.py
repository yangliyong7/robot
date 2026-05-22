"""
汽车养护服务模块
策略：重度保养（机油/轮胎）走京东/天猫，轻度洗护（洗车/美容）走美团
"""

import logging
from src.rebate_api import RebateAPI
from src.modules.local_life import LocalLifeService

logger = logging.getLogger(__name__)


class AutoService:
    def __init__(self):
        self.rebate_api = RebateAPI()
        self.local_life = LocalLifeService()

    async def search_maintenance(self, car_model: str) -> str:
        """
        搜索重度保养套餐（依托京东/天猫联盟）
        :param car_model: 车型，如“宝马3系”
        """
        logger.info(f"正在搜索 {car_model} 的重度保养套餐...")
        
        # 1. 构造关键词并生成转链（此处以模拟链接为例，实际应调用 convert_link）
        keyword = f"{car_model} 全合成机油保养套餐"
        
        # 模拟京东和天猫的返利链接
        jd_url = f"https://item.jd.com/search?keyword={keyword}&pid=YOUR_JD_PID"
        tb_url = f"https://s.taobao.com/search?q={keyword}"

        msg = f"🚗 **{car_model} 深度保养推荐**\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"💡 建议项目：更换机油、机滤、空滤、火花塞\n\n"
        
        msg += f"1️⃣ **京东自营养车** (正品保障⭐)\n"
        msg += f"   ✅ 优势：含工时费、线下门店安装、售后无忧\n"
        msg += f"   🔗 [点击领取 {car_model} 专属套餐]( {jd_url} )\n\n"
        
        msg += f"2️⃣ **天猫养车旗舰店**\n"
        msg += f"   ✅ 优势：品牌直营、经常有满减大额券\n"
        msg += f"   🔗 [点击查看天猫优惠]( {tb_url} )\n\n"
        
        msg += f"💰 **提示**：通过机器人链接下单，您将获得额外返利！"
        return msg

    async def find_car_wash(self, city: str = "北京") -> str:
        """
        查找附近洗车/美容店（依托美团联盟）
        :param city: 用户所在城市
        """
        logger.info(f"正在搜索 {city} 附近的洗车店...")
        
        # 调用本地生活服务搜索“洗车”
        # 实际项目中应调用 self.local_life.search_meituan(category="洗车", city=city)
        
        msg = f"🧼 **{city} 附近精致洗车推荐**\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        msg += f"✨ 已为您筛选评分 4.8 星以上的门店\n\n"
        
        msg += f"1️⃣ **途虎养车工场店(XX路店)**\n"
        msg += f"   💰 团购价：¥29.9 (精洗+吸尘)\n"
        msg += f"   🔗 [点击抢购美团券](https://mock-meituan-wash-link)\n\n"
        
        msg += f"2️⃣ **天猫养车(XX中心店)**\n"
        msg += f"   💰 团购价：¥35.0 (标准洗+打蜡)\n"
        msg += f"   🔗 [点击抢购美团券](https://mock-meituan-wash-link)\n\n"
        
        msg += f"💡 **省钱提示**：美团领券通常比现场支付便宜 50% 以上！"
        return msg
