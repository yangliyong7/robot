"""API Token 校验"""

from fastapi import Header, HTTPException

try:
    from config.config import OPENCLAW_API_CONFIG
except ImportError:
    OPENCLAW_API_CONFIG = {'api_token': '', 'enabled': True}


def verify_api_token(authorization: str = Header(default='')) -> None:
    if not OPENCLAW_API_CONFIG.get('enabled', True):
        return

    expected = (OPENCLAW_API_CONFIG.get('api_token') or '').strip()
    if not expected:
        raise HTTPException(status_code=503, detail='OPENCLAW_API_CONFIG.api_token 未配置')

    token = authorization.removeprefix('Bearer ').strip()
    if token != expected:
        raise HTTPException(status_code=401, detail='无效的 API Token')
