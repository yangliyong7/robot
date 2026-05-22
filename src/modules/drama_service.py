"""
短剧分销模块
支持热门短剧检索与推广链接生成
通过第三方聚合平台 API 实现（如飞猪快跑、好省等）
"""

import logging
import requests
from config.config import DIGITAL_RIGHTS_CONFIG

logger = logging.getLogger(__name__)


class DramaService:
    def __init__(self):
        self.api_base_url = DIGITAL_RIGHTS_CONFIG.get('drama_api_url', '')
        self.app_key = DIGITAL_RIGHTS_CONFIG.get('drama_app_key', '')
        self.pid = DIGITAL_RIGHTS_CONFIG.get('drama_pid', '')

    async def search_drama(self, keyword: str) -> str:
        """
        搜索短剧并生成分销链接
        :param keyword: 短剧名，如"龙王归来"
        """
        logger.info(f"正在搜索短剧: {keyword}")
        
        if not self.app_key or not self.pid:
            return "⚠️ 管理员尚未配置短剧分销 API，暂时无法提供短剧推荐。"

        try:
            # 调用聚合平台 API
            params = {
                "app_key": self.app_key,
                "keyword": keyword,
                "pid": self.pid,
                "limit": 3  # 返回前 3 个结果
            }
            
            response = requests.get(self.api_base_url, params=params, timeout=5)
            data = response.json()

            # 处理返回结果
            if data.get('code') == 0 and data.get('data'):
                dramas = data['data'][:3]
                msg = f"🎬 **热播短剧推荐**\n"
                msg += f"━━━━━━━━━━━━━━━\n"
                
                for i, drama in enumerate(dramas, 1):
                    title = drama.get('title', '未知剧集')
                    cover = drama.get('cover', '')
                    intro = drama.get('intro', '暂无简介')
                    play_link = drama.get('play_url', '#')
                    
                    msg += f"{i}️⃣ **{title}**\n"
                    if cover:
                        msg += f"   🖼️ [点击封面预览]( {cover} )\n"
                    msg += f"   💡 剧情：{intro}\n"
                    msg += f"   🔗 [立即观看（免费看前 5 集）]( {play_link} )\n\n"
                
                msg += f"💡 **提示**：看完免费集数后，充值即可解锁全集大结局！"
                return msg
            else:
                return f"😅 抱歉，没找到关于「{keyword}」的短剧，换个关键词试试？"

        except Exception as e:
            logger.error(f"短剧 API 调用失败: {str(e)}")
            return "⚠️ 服务器繁忙，请稍后再试。"

    async def recommend_daily(self) -> str:
        """
        每日精选热剧（可作为定时任务推送）
        """
        return (
            "📺 **今日必看短剧推荐**\n"
            "━━━━━━━━━━━━━━━\n"
            "1. 《无双》（战神归来题材）\n"
            "2. 《闪婚后，傅先生马甲藏不住了》（甜宠题材）\n\n"
            "💬 回复剧名即可获取观看链接"
        )
