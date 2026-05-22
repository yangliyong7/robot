"""管理后台 Web 会话"""

from fastapi import HTTPException, Request

from config.config import ADMIN_PANEL_CONFIG


def panel_enabled() -> bool:
    return bool(ADMIN_PANEL_CONFIG.get('enabled', True))


def ensure_panel_enabled() -> None:
    if not panel_enabled():
        raise HTTPException(status_code=404, detail='管理后台未启用')


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get('admin_authenticated'))


def require_authenticated(request: Request) -> None:
    ensure_panel_enabled()
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail='未登录或会话已过期')


def login(request: Request, password: str) -> bool:
    ensure_panel_enabled()
    expected = (ADMIN_PANEL_CONFIG.get('password') or '').strip()
    if not expected or password != expected:
        return False
    request.session['admin_authenticated'] = True
    return True


def logout(request: Request) -> None:
    request.session.clear()
