"""
康养服务模块
专注于洗浴中心、SPA、按摩等一二线城市高频放松场景
接入美团联盟 API 实现真实返利转链
"""

import logging
import requests
import hashlib
import time
from config.config import LOCAL_LIFE_CONFIG

logger = logging.getLogger(__name__)


class WellnessService:
    def __init__(self):
        self.app_id = LOCAL_LIFE_CONFIG.get('meituan_app_id')
        self.app_secret = LOCAL_LIFE_CONFIG.get('meituan_app_secret')
        self.pid = LOCAL_LIFE_CONFIG.get('meituan_pid')
        # 美团联盟搜索接口地址（以官方文档为准）
        self.api_url = "https://api-open.meituan.com/api/v1/union/search"

    def _generate_sign(self, params: dict) -> str:
        """
        生成美团 API 签名
        """
        sorted_params = sorted(params.items())
        sign_str = "".join([f"{k}{v}" for k, v in sorted_params]) + self.app_secret
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    async def search_bath_center(self, city: str = "北京", keyword: str = "") -> str:
        """
        搜索高品质洗浴中心（真实 API 调用）
        """
        logger.info(f"正在通过美团联盟搜索 {city} 的洗浴中心: {keyword}")
        
        if not self.app_id:
            return "⚠️ 管理员尚未配置美团联盟 API，暂时无法提供实时比价。请联系管理员配置 app_id。"

        try:
            # 1. 准备请求参数
            params = {
                "app_id": self.app_id,
                "pid": self.pid,
                "keyword": keyword if keyword else "洗浴 SPA",
                "city": city,
                "category_id": "2000",  # 假设 2000 是休闲娱乐/洗浴类目
                "timestamp": int(time.time()),
            }
            
            # 2. 生成签名并发起请求
            params["sign"] = self._generate_sign(params)
            response = requests.get(self.api_url, params=params, timeout=5)
            data = response.json()

            # 3. 处理返回结果
            if data.get('code') == 0 and data.get('data'):
                items = data['data'][:3]  # 取前3个结果
                msg = f"🛁 **{city} 高品质洗浴/水疗推荐**\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                
                for i, item in enumerate(items, 1):
                    msg += f"{i}️⃣ **{item.get('title', '未知门店')}** (⭐ {item.get('score', 'N/A')}分)\n"
                    msg += f"   📍 位置：{item.get('district', '')}\n"
                    msg += f"   💰 团购价：¥{item.get('price', 0)} [点击领券预订]( {item.get('rebate_url', '#')} )\n\n"
                
                msg += f"💡 **省钱提示**：以上价格均为团购优惠价，通过链接购买还有额外返利！"
                return msg
            else:
                return f"😅 抱歉，在 {city} 没找到关于「{keyword}」的特惠信息，换个关键词试试？"

        except Exception as e:
            logger.error(f"美团 API 调用失败: {str(e)}")
            return "⚠️ 服务器繁忙，请稍后再试。"

    async def get_weekend_spa_deals(self, city: str = "上海") -> str:
        """
        获取周末 SPA 特惠（目前先返回引导文案，后续可接入定时任务推送）
        """
        return (
            f"💆‍♀️ **{city} 周末解压指南**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✨ 回复【{city} SPA】获取实时优惠列表\n"
            f"✨ 回复【监控 SPA】开启降价提醒\n\n"
            f"💡 工作辛苦了，周末记得对自己好一点！"
        )
