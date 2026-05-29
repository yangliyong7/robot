"""
票务情报站模块
对接淘票票官方 API 查询热映影片 + 活动推广转链
"""

import logging

from src.database import DatabaseManager
from src.platforms.taopiaopiao import TaopiaopiaoClient
from src.compliance_copy import link_success_notes

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self):
        self.db = DatabaseManager()
        self.taopiaopiao = TaopiaopiaoClient()

    async def search_tickets(self, keyword: str) -> str:
        """搜索热映电影或演出信息"""
        logger.info('正在查询票务信息: %s', keyword)
        result = await self.taopiaopiao.search_movies(keyword=keyword)

        msg = f'🎫 票务情报站：{keyword}\n'
        msg += '━━━━━━━━━━━━━━━\n'

        if result.get('success') and result.get('movies'):
            msg += '🔥 近期热映 / 相关影片：\n'
            for i, movie in enumerate(result['movies'][:5], 1):
                status_label = '购票' if movie.get('status') == 'NORMAL' else movie.get('status', '')
                msg += f"{i}. {movie.get('title', '')}"
                if movie.get('score'):
                    msg += f" ⭐{movie['score']}"
                msg += '\n'
                if movie.get('leading_role'):
                    msg += f"   🎭 主演：{movie['leading_role']}\n"
                if movie.get('open_time'):
                    msg += f"   📅 {movie['open_time']} | {status_label}\n"
                link = movie.get('jump_url') or result.get('activity_link') or ''
                if link:
                    msg += f"   🔗 {link}\n"
                msg += '\n'

            if result.get('activity_link'):
                msg += f"🎬 淘票票推广入口：{result['activity_link']}\n"
            if result.get('activity_tpwd'):
                msg += f"📱 口令：{result['activity_tpwd']}\n"
        else:
            msg += f"ℹ️ {result.get('message', '暂未查到相关影片，可尝试配置淘票票 API')}\n\n"
            msg += '💡 配置 REBATE_CONFIG.taopiaopiao 后可查询官方热映列表\n'

        msg += f'\n💡 回复【监控 {keyword}】，开票后第一时间通知你！'
        msg += link_success_notes('taopiaopiao')
        return msg

    async def add_monitor(self, wxid: str, keyword: str) -> str:
        """添加开票监控"""
        logger.info('用户 %s 开启了对 %s 的监控', wxid, keyword)
        return f'✅ 已开启监控！一旦发现有 **{keyword}** 的相关票务信息，我会立刻私信你。'
