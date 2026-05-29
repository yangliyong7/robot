"""
微信好友申请 / 群邀请自动通过（wxauto4 / wxautox4，按库能力探测）。
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

logger = logging.getLogger(__name__)

_FRIEND_FETCHERS: tuple[tuple[str, tuple[Any, ...], dict[str, Any]], ...] = (
    ('GetNewFriends', (), {'acceptable': True}),
    ('GetNewFriends', (), {}),
    ('GetNewFriend', (), {}),
)

_GROUP_FETCHERS: tuple[str, ...] = (
    'GetNewGroupInvites',
    'GetGroupInvites',
    'GetNewGroups',
    'GetGroupInvite',
)

_ACCEPT_ITEM_METHODS = ('accept', 'Accept', 'agree', 'Agree', 'pass_verify', 'PassVerify')
_ACCEPT_WX_METHODS = (
    ('AcceptFriend', ('friend', 'item', 'request')),
    ('AcceptNewFriend', ('friend', 'item', 'request')),
    ('AcceptGroupInvite', ('invite', 'item', 'group')),
    ('AcceptGroup', ('invite', 'item', 'group')),
)


def _config_flag(cfg: dict, key: str) -> bool:
    return bool(cfg.get(key))


def discover_capabilities(wx: Any) -> dict[str, bool]:
    caps = {
        'friend_fetch': any(callable(getattr(wx, name, None)) for name, _, _ in _FRIEND_FETCHERS),
        'group_fetch': any(callable(getattr(wx, name, None)) for name in _GROUP_FETCHERS),
        'switch_contact': callable(getattr(wx, 'SwitchContact', None)),
    }
    caps['friend'] = caps['friend_fetch'] or any(
        callable(getattr(wx, name, None)) for name, _ in _ACCEPT_WX_METHODS if 'Friend' in name
    )
    caps['group'] = caps['group_fetch'] or any(
        callable(getattr(wx, name, None)) for name, _ in _ACCEPT_WX_METHODS if 'Group' in name
    )
    return caps


def _call_wx(wx: Any, method: str, *args, **kwargs):
    fn = getattr(wx, method, None)
    if not callable(fn):
        return None
    try:
        return fn(*args, **kwargs)
    except TypeError:
        if kwargs:
            try:
                return fn(*args)
            except Exception:
                return None
        return None
    except Exception:
        return None


def _normalize_items(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, tuple):
        return list(raw)
    if isinstance(raw, dict):
        for key in ('data', 'list', 'items', 'friends', 'invites'):
            val = raw.get(key)
            if isinstance(val, list):
                return val
        return []
    return [raw]


def _item_label(item: Any) -> str:
    for key in ('name', 'nickname', 'remark', 'who', 'title', 'content', 'msg'):
        val = getattr(item, key, None) if not isinstance(item, dict) else item.get(key)
        if val:
            text = str(val).strip()
            if text:
                return text[:80]
    if isinstance(item, dict):
        return str(item)[:80]
    return type(item).__name__


def _item_kind(item: Any) -> str:
    for key in ('type', 'kind', 'category', 'request_type'):
        val = getattr(item, key, None) if not isinstance(item, dict) else item.get(key)
        if not val:
            continue
        text = str(val).lower()
        if 'group' in text or '群' in text:
            return 'group'
        if 'friend' in text or '好友' in text:
            return 'friend'
    text = _item_label(item).lower()
    if '邀请你加入群聊' in text or '群聊邀请' in text:
        return 'group'
    return 'friend'


def _fetch_friend_requests(wx: Any) -> list[Any]:
    for method, args, kwargs in _FRIEND_FETCHERS:
        raw = _call_wx(wx, method, *args, **kwargs)
        items = _normalize_items(raw)
        if items:
            return items
    return []


def _fetch_group_invites(wx: Any) -> list[Any]:
    for method in _GROUP_FETCHERS:
        raw = _call_wx(wx, method)
        items = _normalize_items(raw)
        if items:
            return items
    return []


def _accept_via_item(item: Any) -> bool:
    for meth in _ACCEPT_ITEM_METHODS:
        fn = getattr(item, meth, None)
        if callable(fn):
            fn()
            return True
    return False


def _accept_via_wx(wx: Any, item: Any, *, group: bool) -> bool:
    names = [n for n, _ in _ACCEPT_WX_METHODS if (group and 'Group' in n) or (not group and 'Friend' in n)]
    for name in names:
        fn = getattr(wx, name, None)
        if not callable(fn):
            continue
        for args in ((item,), (item, True), ()):
            try:
                if args:
                    fn(*args)
                else:
                    fn(item)
                return True
            except TypeError:
                continue
            except Exception:
                break
    return False


def _accept_one(wx: Any, item: Any, *, group: bool, dry_run: bool) -> tuple[bool, str]:
    label = _item_label(item)
    kind = 'group' if group else 'friend'
    if dry_run:
        return True, f'{kind}:{label}'

    if _accept_via_item(item):
        return True, f'{kind}:{label}'
    if _accept_via_wx(wx, item, group=group):
        return True, f'{kind}:{label}'
    return False, f'{kind}:{label}'


def preview_pending_accepts(wx: Any, cfg: dict | None = None) -> dict[str, Any]:
    """Dry-run：仅列出将要处理的好友/群邀请，不点击通过。"""
    cfg = cfg or {}
    caps = discover_capabilities(wx)
    pending: list[str] = []
    seen: set[int] = set()

    def _add(item: Any, *, group: bool) -> None:
        key = id(item)
        if key in seen:
            return
        seen.add(key)
        ok, label = _accept_one(wx, item, group=group, dry_run=True)
        if ok:
            pending.append(label)

    if _config_flag(cfg, 'auto_accept_friend') and caps['friend']:
        for item in _fetch_friend_requests(wx):
            if _item_kind(item) == 'group':
                continue
            _add(item, group=False)

    if _config_flag(cfg, 'auto_accept_group') and caps['group']:
        for item in _fetch_group_invites(wx):
            _add(item, group=True)
        if caps['friend_fetch'] and not caps['group_fetch']:
            for item in _fetch_friend_requests(wx):
                if _item_kind(item) == 'group':
                    _add(item, group=True)

    return {'capabilities': caps, 'pending': pending, 'count': len(pending)}


def process_auto_accepts(
    wx: Any,
    cfg: dict,
    *,
    dry_run: bool = False,
    log: logging.Logger | None = None,
) -> dict[str, int]:
    """处理待通过的好友申请与群邀请。返回统计 counters。"""
    log = log or logger
    caps = discover_capabilities(wx)
    stats = {'friend': 0, 'group': 0, 'failed': 0, 'skipped': 0}

    def _handle(items: Iterable[Any], *, group: bool) -> None:
        for item in items:
            ok, label = _accept_one(wx, item, group=group, dry_run=dry_run)
            if not ok:
                stats['failed'] += 1
                if not dry_run:
                    log.warning('自动通过失败: %s', label)
                continue
            key = 'group' if group else 'friend'
            stats[key] += 1
            if dry_run:
                log.info('[dry-run] 将通过: %s', label)
            else:
                log.info('已自动通过: %s', label)

    if _config_flag(cfg, 'auto_accept_friend'):
        if not caps['friend']:
            stats['skipped'] += 1
        else:
            for item in _fetch_friend_requests(wx):
                if _item_kind(item) == 'group':
                    continue
                _handle([item], group=False)

    if _config_flag(cfg, 'auto_accept_group'):
        if not caps['group']:
            stats['skipped'] += 1
        else:
            invites = _fetch_group_invites(wx)
            if invites:
                _handle(invites, group=True)
            elif caps['friend_fetch']:
                group_from_friends = [i for i in _fetch_friend_requests(wx) if _item_kind(i) == 'group']
                _handle(group_from_friends, group=True)

    return stats


class AutoAcceptWorker:
    """后台轮询：按 WECHAT_CONFIG 自动通过好友/群邀请。"""

    def __init__(self, log: logging.Logger | None = None):
        self._log = log or logger
        self._caps_logged = False
        self._unsupported_logged = False

    def tick(self, wx: Any, cfg: dict, *, dry_run: bool = False) -> None:
        if not (_config_flag(cfg, 'auto_accept_friend') or _config_flag(cfg, 'auto_accept_group')):
            return

        caps = discover_capabilities(wx)
        if not self._caps_logged:
            self._caps_logged = True
            self._log.info(
                '自动通过能力: friend=%s group=%s (SwitchContact=%s)',
                caps['friend'],
                caps['group'],
                caps['switch_contact'],
            )

        need_friend = _config_flag(cfg, 'auto_accept_friend')
        need_group = _config_flag(cfg, 'auto_accept_group')
        if (need_friend and not caps['friend']) or (need_group and not caps['group']):
            if not self._unsupported_logged:
                self._unsupported_logged = True
                self._log.warning(
                    '当前 wxauto 库不支持已启用的自动通过项（好友=%s 群邀请=%s），将跳过',
                    need_friend and not caps['friend'],
                    need_group and not caps['group'],
                )
            return

        try:
            stats = process_auto_accepts(wx, cfg, dry_run=dry_run, log=self._log)
        except Exception as exc:
            self._log.warning('自动通过轮询异常: %s', exc)
            return

        total = stats['friend'] + stats['group']
        if total and not dry_run:
            self._log.info(
                '自动通过完成: 好友 %d 群邀请 %d 失败 %d',
                stats['friend'],
                stats['group'],
                stats['failed'],
            )
