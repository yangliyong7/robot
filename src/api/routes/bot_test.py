from fastapi import APIRouter, Depends

from src.api.auth import verify_api_token
from src.api.schemas import ApiResponse, BotReplyRequest
from src.bot_simulator import simulate_bot_reply

router = APIRouter(prefix='/v1', tags=['bot-test'])


@router.post('/bot/reply', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def bot_reply(body: BotReplyRequest):
    """模拟微信入站消息，返回机器人自动回复（无需 wxauto）。"""
    result = await simulate_bot_reply(
        body.text,
        wxid=body.wxid,
        nickname=body.nickname,
        chat_name=body.chat_name,
        is_group=body.is_group,
        sender_name=body.sender_name,
    )
    if result.get('error'):
        return ApiResponse(
            success=False,
            message=result['error'],
            data=result,
        )
    return ApiResponse(
        success=True,
        message=result.get('reply') or '',
        data=result,
    )
