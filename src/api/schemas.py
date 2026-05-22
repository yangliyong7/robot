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


class WxIdBody(BaseModel):
    wxid: str


class AdminWithdrawReject(BaseModel):
    wxid: str
    reason: str = '管理员拒绝'
