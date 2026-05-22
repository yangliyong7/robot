import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.admin_session import (
    ensure_panel_enabled,
    is_authenticated,
    login,
    logout,
    require_authenticated,
)
from config.schema_builder import build_settings_schema, build_settings_tree
from config.settings_store import (
    MASK_PLACEHOLDER,
    get_settings_store,
)
from config.config import COMMISSION_CONFIG
from src.compliance_copy import settle_notify_message
from src.database import DatabaseManager
from src.services.order_sync_service import OrderSyncService
from src.services.wallet_service import WalletService

router = APIRouter(tags=['admin-web'])
_db = DatabaseManager()
_wallet = WalletService(_db)
_order_sync = OrderSyncService(_db, wallet_service=_wallet)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'admin')


def _rows_to_list(rows) -> list:
    if not rows:
        return []
    return [{key: row[key] for key in row.keys()} for row in rows]


def _wrap_list_result(result: dict) -> dict:
    return {
        'total': result.get('total', 0),
        'items': _rows_to_list(result.get('items')),
    }


class LoginBody(BaseModel):
    password: str = Field(min_length=1)


class RejectBody(BaseModel):
    reason: str = Field(default='管理员拒绝', max_length=200)


class ApproveBody(BaseModel):
    remark: str = Field(default='管理员已线下转账', max_length=200)


class SettingsUpdateBody(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class ChangePasswordBody(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class SettleOrderBody(BaseModel):
    order_no: str = Field(min_length=1, max_length=64)


def require_admin_web(request: Request) -> None:
    require_authenticated(request)


@router.get('/admin')
async def admin_page():
    ensure_panel_enabled()
    index_path = os.path.join(_STATIC_DIR, 'index.html')
    return FileResponse(index_path, media_type='text/html; charset=utf-8')


@router.get('/admin/api/me')
async def admin_me(request: Request):
    ensure_panel_enabled()
    return {'authenticated': is_authenticated(request)}


@router.post('/admin/api/login')
async def admin_login(request: Request, body: LoginBody):
    if not login(request, body.password):
        return {'success': False, 'message': '密码错误'}
    return {'success': True, 'message': '登录成功'}


@router.post('/admin/api/logout')
async def admin_logout(request: Request):
    logout(request)
    return {'success': True}


@router.get('/admin/api/dashboard', dependencies=[Depends(require_admin_web)])
async def admin_dashboard():
    stats = _db.admin_dashboard_stats()
    return {
        'total_users': stats['total_users'],
        'total_orders': stats['total_orders'],
        'total_commission': float(stats['total_commission'] or 0),
        'pending_withdrawals': stats['pending_withdrawals'],
        'total_user_balance': stats['total_user_balance'],
    }


@router.get('/admin/api/users', dependencies=[Depends(require_admin_web)])
async def admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
):
    offset = (page - 1) * limit
    result = _db.admin_list_users(offset=offset, limit=limit, search=q)
    return _wrap_list_result(result)


@router.get('/admin/api/orders', dependencies=[Depends(require_admin_web)])
async def admin_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    wxid: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
):
    offset = (page - 1) * limit
    result = _db.admin_list_orders(
        offset=offset,
        limit=limit,
        status=status or None,
        wxid=wxid or None,
        platform=platform or None,
    )
    return _wrap_list_result(result)


@router.get('/admin/api/withdrawals', dependencies=[Depends(require_admin_web)])
async def admin_withdrawals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query('all'),
):
    offset = (page - 1) * limit
    result = _db.admin_list_withdrawals(offset=offset, limit=limit, status=status)
    return _wrap_list_result(result)


@router.get('/admin/api/transactions', dependencies=[Depends(require_admin_web)])
async def admin_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    wxid: Optional[str] = Query(None),
):
    offset = (page - 1) * limit
    result = _db.admin_list_transactions(offset=offset, limit=limit, wxid=wxid or None)
    return _wrap_list_result(result)


@router.get('/admin/api/users/{wxid}', dependencies=[Depends(require_admin_web)])
async def admin_user_detail(wxid: str):
    user = _db.get_user(wxid)
    if not user:
        return {'success': False, 'message': '用户不存在'}
    checkin_stats = _db.get_user_checkin_stats(wxid)
    last = checkin_stats.get('last_checkin')
    return {
        'success': True,
        'user': {key: user[key] for key in user.keys()},
        'checkin_stats': {
            'total_checkins': checkin_stats.get('total_checkins', 0),
            'total_reward': float(checkin_stats.get('total_reward') or 0),
            'continuous_days': checkin_stats.get('continuous_days', 0),
            'last_checkin': {key: last[key] for key in last.keys()} if last else None,
        },
        'orders': _wrap_list_result(_db.admin_list_orders(offset=0, limit=50, wxid=wxid)),
        'withdrawals': _wrap_list_result(
            _db.admin_list_withdrawals(offset=0, limit=50, status='all', wxid=wxid)
        ),
        'transactions': _wrap_list_result(_db.admin_list_transactions(offset=0, limit=50, wxid=wxid)),
        'checkins': _wrap_list_result(_db.admin_list_checkins(offset=0, limit=50, wxid=wxid)),
    }


@router.get('/admin/api/checkins', dependencies=[Depends(require_admin_web)])
async def admin_checkins(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    wxid: Optional[str] = Query(None),
):
    offset = (page - 1) * limit
    result = _db.admin_list_checkins(offset=offset, limit=limit, wxid=wxid or None)
    return _wrap_list_result(result)


@router.post('/admin/api/orders/sync', dependencies=[Depends(require_admin_web)])
async def admin_sync_orders():
    result = await _order_sync.sync_once()
    if result.get('success'):
        st = result.get('stats', {})
        message = (
            f"同步完成：拉取 {st.get('fetched', 0)} | "
            f"关联 {st.get('linked', 0)} | 结算 {st.get('settled', 0)} | "
            f"失效 {st.get('invalid', 0)}"
        )
    else:
        message = result.get('message', '同步失败')
    return {'success': bool(result.get('success')), 'message': message, 'data': result}


@router.post('/admin/api/orders/settle', dependencies=[Depends(require_admin_web)])
async def admin_settle_order(body: SettleOrderBody):
    order_no = body.order_no.strip().upper()
    result = _wallet.admin_settle_order(order_no)
    if result.get('success'):
        order = _db.get_order_by_no(order_no)
        if order:
            notify_msg = settle_notify_message(
                platform=order.get('platform') or 'taobao',
                product_title=result.get('product_title') or order.get('product_title') or '',
                rebate=float(result.get('rebate', 0)),
                balance=float(result.get('balance', 0)),
                min_withdraw=float(COMMISSION_CONFIG.get('min_withdraw', 10)),
            )
            _db.add_pending_notification(order['wxid'], notify_msg)
        message = (
            f"订单 {result.get('order_no', order_no)} 已结算，"
            f"发放 ¥{float(result.get('rebate', 0)):.2f}"
        )
    else:
        message = result.get('message', '结算失败')
    return {'success': bool(result.get('success')), 'message': message, 'data': result}


@router.post('/admin/api/withdrawals/{withdraw_id}/approve', dependencies=[Depends(require_admin_web)])
async def admin_approve_withdraw(withdraw_id: int, body: ApproveBody):
    result = _wallet.approve_withdraw(withdraw_id, remark=body.remark)
    return _action_result(result, withdraw_id, 'approve')


@router.post('/admin/api/withdrawals/{withdraw_id}/reject', dependencies=[Depends(require_admin_web)])
async def admin_reject_withdraw(withdraw_id: int, body: RejectBody):
    result = _wallet.reject_withdraw(withdraw_id, body.reason)
    return _action_result(result, withdraw_id, 'reject')


def _action_result(result: dict, withdraw_id: int, action: str) -> dict[str, Any]:
    if result.get('success'):
        if action == 'approve':
            message = f'提现 #{withdraw_id} 已通过，请确认已完成线下转账'
        else:
            message = f'提现 #{withdraw_id} 已拒绝，余额已退回'
    else:
        message = result.get('message', '操作失败')
    return {'success': bool(result.get('success')), 'message': message, 'data': result}


@router.get('/admin/api/settings/schema', dependencies=[Depends(require_admin_web)])
async def settings_schema():
    store = get_settings_store()
    data = store.get_config_data()
    return {
        'sections': build_settings_schema(data),
        'tree': build_settings_tree(data),
    }


@router.get('/admin/api/settings', dependencies=[Depends(require_admin_web)])
async def settings_values():
    store = get_settings_store()
    meta = store.get_meta()
    return {
        'values': store.get_all_values(),
        'storage': meta.get('storage'),
        'meta': meta,
        'mask_placeholder': MASK_PLACEHOLDER,
    }


@router.put('/admin/api/settings/{section_id}', dependencies=[Depends(require_admin_web)])
async def settings_update(section_id: str, body: SettingsUpdateBody):
    store = get_settings_store()
    try:
        merged = store.update_section(section_id, body.values or {})
        return {'success': True, 'message': '配置已保存并生效', 'values': merged}
    except KeyError:
        return {'success': False, 'message': f'未知配置分组: {section_id}'}
    except (ValueError, json.JSONDecodeError) as e:
        return {'success': False, 'message': str(e)}


@router.post('/admin/api/settings/change-password', dependencies=[Depends(require_admin_web)])
async def settings_change_password(body: ChangePasswordBody):
    from config.config import ADMIN_PANEL_CONFIG

    if ADMIN_PANEL_CONFIG.get('password') != body.old_password:
        return {'success': False, 'message': '当前密码不正确'}
    store = get_settings_store()
    store.update_admin_password(body.new_password)
    return {'success': True, 'message': '管理密码已更新，请牢记新密码'}
