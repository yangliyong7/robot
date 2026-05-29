from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool = True
    message: str = ''
    data: Optional[Dict[str, Any]] = None


class UserEnsureRequest(BaseModel):
    wxid: str
    nickname: str = ''


class ConvertRequest(BaseModel):
    wxid: str
    nickname: str = ''
    content: str
    notify_chat: Optional[str] = None
    notify_is_group: bool = False


class BotReplyRequest(BaseModel):
    """无 wxauto 时的自动回复模拟请求。"""
    text: str = Field(min_length=1)
    wxid: str = 'test_wxid'
    nickname: str = '测试用户'
    chat_name: str = ''
    is_group: bool = False
    sender_name: str = ''


class WxIdBody(BaseModel):
    wxid: str


class AdminWithdrawReject(BaseModel):
    wxid: str
    reason: str = '管理员拒绝'
