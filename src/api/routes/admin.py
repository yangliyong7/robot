from fastapi import APIRouter, Depends, Query

from src.api.admin_guard import require_admin
from src.api.auth import verify_api_token
from src.api.schemas import AdminWithdrawReject, ApiResponse, WxIdBody
from src.compliance_copy import settle_notify_message
from src.database import DatabaseManager
from src.services.order_sync_service import OrderSyncService
from src.services.wallet_service import WalletService
from config.config import COMMISSION_CONFIG

router = APIRouter(prefix='/v1/admin', tags=['admin'])
_db = DatabaseManager()
_wallet = WalletService(_db)
_order_sync = OrderSyncService(_db, wallet_service=_wallet)


@router.get('/withdrawals/pending', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def list_withdrawals(wxid: str = Query(...)):
    require_admin(wxid)
    return ApiResponse(success=True, message=_wallet.format_pending_withdrawals_message())


@router.post('/withdrawals/{withdraw_id}/approve', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def approve_withdraw(withdraw_id: int, body: WxIdBody):
    require_admin(body.wxid)
    result = _wallet.approve_withdraw(withdraw_id)
    if result['success']:
        message = (
            f"✅ 提现 #{withdraw_id} 已标记完成\n"
            f"用户: {result['wxid']}\n"
            f"金额: ¥{result['amount']:.2f}\n"
            f"请确认已完成线下转账"
        )
    else:
        message = f"❌ 操作失败: {result['message']}"
    return ApiResponse(success=result['success'], message=message, data=result)


@router.post('/withdrawals/{withdraw_id}/reject', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def reject_withdraw(withdraw_id: int, body: AdminWithdrawReject):
    require_admin(body.wxid)
    result = _wallet.reject_withdraw(withdraw_id, body.reason)
    if result['success']:
        message = (
            f"✅ 已拒绝提现 #{withdraw_id}，¥{result['amount']:.2f} 已退回用户余额\n"
            f"用户: {result['wxid']}"
        )
    else:
        message = f"❌ 操作失败: {result['message']}"
    return ApiResponse(success=result['success'], message=message, data=result)


@router.post('/orders/sync', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def sync_orders(body: WxIdBody):
    require_admin(body.wxid)
    result = await _order_sync.sync_once()
    if result.get('success'):
        st = result.get('stats', {})
        message = (
            f"✅ 联盟订单同步完成\n"
            f"拉取: {st.get('fetched', 0)} | 关联: {st.get('linked', 0)} | "
            f"结算: {st.get('settled', 0)} | 失效: {st.get('invalid', 0)}"
        )
    else:
        message = f"❌ 同步失败: {result.get('message', '')}"
    return ApiResponse(success=bool(result.get('success')), message=message, data=result)


@router.post('/orders/settle', response_model=ApiResponse, dependencies=[Depends(verify_api_token)])
async def settle_order(body: WxIdBody, order_no: str = Query(...)):
    require_admin(body.wxid)
    order_no = order_no.upper()
    result = _wallet.admin_settle_order(order_no)
    if result['success']:
        order = _db.get_order_by_no(order_no)
        if order:
            notify_msg = settle_notify_message(
                platform='taobao',
                product_title=result.get('product_title') or '',
                rebate=float(result.get('rebate', 0)),
                balance=float(result.get('balance', 0)),
                min_withdraw=float(COMMISSION_CONFIG.get('min_withdraw', 10)),
            )
            _db.add_pending_notification(order['wxid'], notify_msg)
        message = (
            f"✅ 订单 {result['order_no']} 已结算\n"
            f"发放推广奖励: ¥{result['rebate']:.2f}\n"
            f"用户可结算余额: ¥{result['balance']:.2f}"
        )
    else:
        message = f"❌ 结算失败: {result['message']}"
    return ApiResponse(success=result['success'], message=message, data=result)
