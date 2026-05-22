from fastapi import APIRouter, Depends, Query

from src.api.auth import verify_api_token
from src.api.bot_messages import (
    get_balance_message,
    get_help_message,
    get_orders_message,
    get_stats_message,
    handle_checkin,
)
from src.api.schemas import ApiResponse, WxIdBody
from src.database import DatabaseManager
from src.services.wallet_service import WalletService

router = APIRouter(prefix='/v1', tags=['wallet'])
_db = DatabaseManager()
_wallet = WalletService(_db)


@router.get('/help', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def help_text():
    return ApiResponse(success=True, message=get_help_message())


@router.get('/wallet/balance', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def balance(wxid: str = Query(...)):
    _db.add_user(wxid, wxid)
    return ApiResponse(success=True, message=get_balance_message(_db, wxid))


@router.get('/wallet/orders', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def orders(wxid: str = Query(...)):
    _db.add_user(wxid, wxid)
    return ApiResponse(success=True, message=get_orders_message(_db, wxid))


@router.get('/wallet/stats', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def stats(wxid: str = Query(...)):
    _db.add_user(wxid, wxid)
    return ApiResponse(success=True, message=get_stats_message(_db, wxid))


@router.post('/wallet/withdraw', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def withdraw(body: WxIdBody):
    _db.add_user(body.wxid, body.wxid)
    result = _wallet.apply_withdraw(body.wxid)
    if not result['success']:
        return ApiResponse(success=False, message=f"❌ 结算申请失败\n\n{result['message']}")
    message = (
        f"✅ 结算申请已提交\n"
        f"━━━━━━━━━━━━━━━\n"
        f"申请编号：#{result['withdraw_id']}\n"
        f"申请金额：¥{result['amount']:.2f}\n"
        f"状态：待管理员审核\n\n"
        f"💡 审核通过后将线下转账，请留意通知\n"
        f"⚠️ 请勿刷单或虚假交易，违规将取消奖励资格"
    )
    return ApiResponse(success=True, message=message, data=result)


@router.post('/wallet/checkin', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def checkin(body: WxIdBody):
    _db.add_user(body.wxid, body.wxid)
    return ApiResponse(success=True, message=handle_checkin(_db, body.wxid))
