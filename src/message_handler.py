"""微信消息业务处理"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from config.config import WECHAT_CONFIG
from src.api.admin_guard import is_admin
from src.api.bot_messages import (
    get_balance_message,
    get_help_message,
    get_orders_message,
    get_stats_message,
    handle_checkin,
)
from src.database import DatabaseManager
from src.message_router import RouteDecision, route_message
from src.modules.ecommerce import EcommerceService
from src.services.wallet_service import WalletService

logger = logging.getLogger(__name__)

ADMIN_APPROVE_RE = re.compile(r'^通过提现\s*#?(\d+)\s*$', re.I)
ADMIN_REJECT_RE = re.compile(r'^拒绝提现\s*#?(\d+)\s+(.+)$', re.I)
ADMIN_SYNC_RE = re.compile(r'^(同步订单|联盟同步)$', re.I)


@dataclass
class ChatContext:
    """wxid 为微信号（wxauto sender_info.id）。"""
    wxid: str
    nickname: str
    chat_name: str
    is_group: bool = False
    sender_name: str = ''


class MessageHandler:
    def __init__(self):
        self.db = DatabaseManager()
        self.wallet = WalletService(self.db)
        self.ecommerce = EcommerceService()

    @property
    def passive_mode(self) -> bool:
        return bool(WECHAT_CONFIG.get('passive_mode', True))

    def decide(self, text: str) -> RouteDecision:
        return route_message(text, self.passive_mode)

    async def handle(self, ctx: ChatContext, text: str, decision: RouteDecision | None = None) -> str | None:
        trimmed = (text or '').strip()
        if not trimmed:
            return None

        admin_reply = await self._handle_admin_text(ctx, trimmed)
        if admin_reply:
            self.db.add_user(ctx.wxid, ctx.nickname or ctx.wxid)
            pending = self._pull_pending_notifications(ctx.wxid)
            return '\n\n'.join(p for p in (pending, admin_reply) if p)

        decision = decision or self.decide(trimmed)
        if decision.action == 'ignore':
            return None
        if decision.action == 'pass':
            return None

        self.db.add_user(ctx.wxid, ctx.nickname or ctx.wxid)

        pending = self._pull_pending_notifications(ctx.wxid)
        body = await self._dispatch(ctx, decision)
        if body is None:
            return pending or None
        parts = [p for p in (pending, body) if p]
        return '\n\n'.join(parts) if parts else None

    def _pull_pending_notifications(self, wxid: str) -> str:
        rows = self.db.get_pending_notifications(wxid, limit=3)
        if not rows:
            return ''
        ids = [row['id'] for row in rows]
        parts = [row['message'] for row in rows]
        self.db.mark_notifications_delivered(ids)
        return '\n\n'.join(parts)

    async def _dispatch(self, ctx: ChatContext, decision: RouteDecision) -> str | None:
        kind = decision.kind or ''
        if kind == 'help':
            return get_help_message()
        if kind == 'balance':
            return get_balance_message(self.db, ctx.wxid)
        if kind == 'orders':
            return get_orders_message(self.db, ctx.wxid)
        if kind == 'stats':
            return get_stats_message(self.db, ctx.wxid)
        if kind == 'checkin':
            return handle_checkin(self.db, ctx.wxid)
        if kind == 'withdraw':
            return self._handle_withdraw(ctx)
        if kind == 'convert':
            return await self._handle_convert(ctx, decision.content or '')
        return None

    def _handle_withdraw(self, ctx: ChatContext) -> str:
        result = self.wallet.apply_withdraw(ctx.wxid)
        if not result['success']:
            return f"❌ 结算申请失败\n\n{result['message']}"
        return (
            f"✅ 结算申请已提交\n"
            f"━━━━━━━━━━━━━━━\n"
            f"申请编号：#{result['withdraw_id']}\n"
            f"申请金额：¥{result['amount']:.2f}\n"
            f"状态：待管理员审核\n\n"
            f"💡 审核通过后将线下转账，请留意通知\n"
            f"⚠️ 请勿刷单或虚假交易，违规将取消奖励资格"
        )

    async def _handle_convert(self, ctx: ChatContext, content: str) -> str:
        return await self.ecommerce.handle_link(
            content,
            wxid=ctx.wxid,
            notify_chat=ctx.chat_name,
            notify_is_group=ctx.is_group,
            user_nickname=ctx.sender_name or ctx.nickname,
        )

    async def _handle_admin_text(self, ctx: ChatContext, text: str) -> str | None:
        if not text or not is_admin(ctx.wxid, ctx.nickname):
            return None

        m = ADMIN_APPROVE_RE.match(text)
        if m:
            result = self.wallet.approve_withdraw(int(m.group(1)))
            if result['success']:
                return (
                    f"✅ 提现 #{m.group(1)} 已标记完成\n"
                    f"用户: {result['wxid']}\n"
                    f"金额: ¥{result['amount']:.2f}\n"
                    f"请确认已完成线下转账"
                )
            return f"❌ 操作失败: {result['message']}"

        m = ADMIN_REJECT_RE.match(text)
        if m:
            result = self.wallet.reject_withdraw(int(m.group(1)), m.group(2).strip())
            if result['success']:
                return (
                    f"✅ 已拒绝提现 #{m.group(1)}，¥{result['amount']:.2f} 已退回用户余额\n"
                    f"用户: {result['wxid']}"
                )
            return f"❌ 操作失败: {result['message']}"

        if ADMIN_SYNC_RE.match(text):
            from src.services.order_sync_service import OrderSyncService

            sync = OrderSyncService(self.db, wallet_service=self.wallet)
            result = await sync.sync_once()
            if result.get('success'):
                st = result.get('stats', {})
                return (
                    f"✅ 联盟订单同步完成\n"
                    f"拉取: {st.get('fetched', 0)} | 关联: {st.get('linked', 0)} | "
                    f"结算: {st.get('settled', 0)} | 失效: {st.get('invalid', 0)}"
                )
            return f"❌ 同步失败: {result.get('message', '')}"

        if text in ('待审提现', '提现列表'):
            return self.wallet.format_pending_withdrawals_message()

        return None


def run_handle(handler: MessageHandler, ctx: ChatContext, text: str) -> str | None:
    """同步入口：供 wxauto 回调使用。"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(handler.handle(ctx, text))
    except Exception as exc:
        logger.exception('处理消息失败 wxid=%s text=%s: %s', ctx.wxid, text[:80], exc)
        return '❌ 处理失败，请稍后再试或联系管理员'
    finally:
        loop.close()
