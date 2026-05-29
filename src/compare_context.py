"""按用户缓存最近一次无推广商品，供回复【全网比价】时使用。"""

from __future__ import annotations

from typing import Any

_pending: dict[str, dict[str, Any]] = {}


def set_pending_compare(wxid: str, *, keyword: str, platform: str) -> None:
    if not wxid:
        return
    _pending[str(wxid)] = {
        'keyword': (keyword or '').strip(),
        'platform': (platform or '').strip(),
    }


def pop_pending_compare(wxid: str) -> dict[str, Any] | None:
    if not wxid:
        return None
    return _pending.pop(str(wxid), None)
