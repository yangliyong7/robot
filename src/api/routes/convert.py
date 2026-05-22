from fastapi import APIRouter, Depends

from src.api.auth import verify_api_token
from src.api.schemas import ApiResponse, ConvertRequest, UserEnsureRequest
from src.database import DatabaseManager
from src.modules.ecommerce import EcommerceService

router = APIRouter(prefix='/v1', tags=['convert'])
_db = DatabaseManager()
_ecommerce = EcommerceService()


@router.post('/users/ensure', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def ensure_user(body: UserEnsureRequest):
    _db.add_user(body.wxid, body.nickname or body.wxid)
    return ApiResponse(success=True, message='ok', data={'wxid': body.wxid})


@router.post('/convert', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def convert_link(body: ConvertRequest):
    _db.add_user(body.wxid, body.nickname or body.wxid)
    message = await _ecommerce.handle_link(
        body.content,
        wxid=body.wxid,
        notify_chat=body.notify_chat or body.nickname or body.wxid,
        notify_is_group=body.notify_is_group,
        user_nickname=body.nickname,
    )
    return ApiResponse(success=True, message=message)
