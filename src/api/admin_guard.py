"""管理员校验"""

from fastapi import HTTPException

from config.config import ADMIN_CONFIG, OTHER_CONFIG


def is_admin(wxid: str, nickname: str = '') -> bool:
    admin_ids = set()
    for item in (ADMIN_CONFIG.get('admin_wxids', '') or '').split(','):
        if item.strip():
            admin_ids.add(item.strip())
    legacy = (OTHER_CONFIG.get('admin_wechat', '') or '').strip()
    if legacy:
        admin_ids.add(legacy)
    if wxid in admin_ids:
        return True
    for kw in ADMIN_CONFIG.get('admin_nickname_keywords', []) or []:
        if kw and nickname and str(kw) in nickname:
            return True
    return False


def require_admin(wxid: str, nickname: str = '') -> None:
    if not is_admin(wxid, nickname):
        raise HTTPException(status_code=403, detail='需要管理员权限')
