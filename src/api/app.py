from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

from config.settings_store import init_runtime_settings

init_runtime_settings()

from config.config import ADMIN_PANEL_CONFIG, API_SERVER_CONFIG, WECHAT_CONFIG
from src.api.auth import verify_api_token
from src.api.routes import admin, admin_web, bot_test, compare_web, convert, notifications, site_web, wallet

_session_secret = (
    (ADMIN_PANEL_CONFIG.get('session_secret') or '').strip()
    or API_SERVER_CONFIG.get('api_token', 'change-me')
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_runtime_settings()
    yield


app = FastAPI(title='Rebate Bot API', version='1.0.0', lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    session_cookie='rebate_admin_session',
    max_age=86400 * 7,
    same_site='lax',
    https_only=False,
)
app.include_router(site_web.router)
app.include_router(compare_web.router)
app.include_router(convert.router)
app.include_router(bot_test.router)
app.include_router(wallet.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(admin_web.router)


@app.get('/v1/health')
async def health():
    return {'status': 'ok', 'mode': 'api', 'bot_test': '/v1/bot/reply'}


@app.get('/v1/config/passive-mode', dependencies=[Depends(verify_api_token)])
async def passive_mode():
    return {
        'passive_mode': bool(WECHAT_CONFIG.get('passive_mode', True)),
    }
