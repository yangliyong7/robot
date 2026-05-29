"""无 wxauto / 无微信客户端时的机器人回复模拟。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.message_handler import ChatContext, MessageHandler


async def simulate_bot_reply(
    text: str,
    *,
    wxid: str = 'test_wxid',
    nickname: str = '测试用户',
    chat_name: str = '',
    is_group: bool = False,
    sender_name: str = '',
) -> dict[str, Any]:
    """走完整 MessageHandler 路由与业务逻辑，返回回复与路由决策。"""
    trimmed = (text or '').strip()
    handler = MessageHandler()
    decision = handler.decide(trimmed)
    ctx = ChatContext(
        wxid=(wxid or 'test_wxid').strip(),
        nickname=(nickname or wxid or '测试用户').strip(),
        chat_name=(chat_name or nickname or wxid or '测试会话').strip(),
        is_group=bool(is_group),
        sender_name=(sender_name or nickname or '').strip(),
    )

    reply: str | None = None
    error: str | None = None
    try:
        reply = await handler.handle(ctx, trimmed, decision)
    except Exception as exc:
        error = str(exc)

    return {
        'replied': bool(reply),
        'reply': reply or '',
        'error': error,
        'decision': {
            'action': decision.action,
            'kind': decision.kind,
            'content': decision.content,
        },
        'context': asdict(ctx),
    }
