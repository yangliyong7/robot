"""无推广商品比价令牌：商品信息仅存服务端，链接中不出现关键词。"""

from __future__ import annotations

import secrets
import time
from typing import Any

TOKEN_TTL_SECONDS = 3600
ALLOWED_SOURCE = 'no_promo'

_store: dict[str, dict[str, Any]] = {}


def _purge_expired() -> None:
    now = time.time()
    expired = [t for t, d in _store.items() if now - float(d.get('created_at', 0)) > TOKEN_TTL_SECONDS]
    for t in expired:
        _store.pop(t, None)


def issue_compare_token(*, wxid: str, keyword: str, platform: str) -> str:
    """仅在无推广场景签发；有推广商品不会生成令牌。"""
    _purge_expired()
    keyword = (keyword or '').strip()
    if not keyword:
        return ''
    token = secrets.token_urlsafe(18)
    _store[token] = {
        'wxid': str(wxid or ''),
        'keyword': keyword,
        'platform': (platform or '').strip(),
        'source': ALLOWED_SOURCE,
        'created_at': time.time(),
    }
    return token


def resolve_compare_token(token: str) -> dict[str, Any] | None:
    """读取并校验令牌（可多次打开，有效期内）。"""
    _purge_expired()
    data = _store.get((token or '').strip())
    if not data:
        return None
    if data.get('source') != ALLOWED_SOURCE:
        return None
    if time.time() - float(data.get('created_at', 0)) > TOKEN_TTL_SECONDS:
        _store.pop(token, None)
        return None
    return dict(data)
