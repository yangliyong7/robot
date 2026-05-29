"""
wxauto 微信机器人：监听 PC 微信消息并自动回复。
需在 Windows 上登录微信客户端后运行: python -m src.main
"""

from __future__ import annotations

import hashlib
import random
import re
import sys
import threading
import time
from typing import Any

from config.config import ANTI_BAN_CONFIG, WECHAT_CONFIG
from config.settings_store import init_runtime_settings
from src.database import DatabaseManager
from src.message_handler import ChatContext, MessageHandler, run_handle
from src.message_router import has_product_intent
from src.utils import SensitiveWordFilter, configure_wxauto_logging, setup_logger
from src.wechat_auto_accept import AutoAcceptWorker

configure_wxauto_logging()

logger = setup_logger('WeChatBot')

SPECIAL_SESSIONS = frozenset({
    '公众号', '折叠的聊天', 'QQ邮箱提醒', '服务号', '微信团队', '文件传输助手',
})

SESSION_CLICK_WAIT = 0.55
SKIP_MESSAGE_TYPES = frozenset({
    'SystemMessage', 'TimeMessage', 'SelfTextMessage', 'SelfImageMessage',
    'SelfVideoMessage', 'SelfVoiceMessage', 'SelfFileMessage', 'SelfEmotionMessage',
})


def _import_wxauto():
    configure_wxauto_logging()
    last_exc = None
    # wxauto4: 免费版（通常仅支持到 Python 3.12）
    # wxautox4: Plus 版（支持到 Python 3.13）
    for mod_name in ('wxauto4', 'wxautox4', 'wxauto', 'wxautox'):
        try:
            mod = __import__(mod_name, fromlist=['WeChat'])
            WeChat = getattr(mod, 'WeChat')
            try:
                msgs_mod = __import__(f'{mod_name}.msgs', fromlist=['SelfMessage'])
                SelfMessage = getattr(msgs_mod, 'SelfMessage')
            except (ImportError, AttributeError):
                SelfMessage = type('SelfMessage', (), {})
            logger.info('使用微信自动化库: %s', mod_name)
            return WeChat, SelfMessage
        except ImportError as exc:
            last_exc = exc
            continue
    logger.error(
        '未安装 wxauto4/wxautox4，请执行其一:\n'
        '  pip install wxauto4   (免费版，通常仅支持到 Python 3.12)\n'
        '  pip install wxautox4  (Plus 版，支持到 Python 3.13)\n'
        '注意：需在 Windows 上运行，且 PC 微信已登录。'
    )
    raise SystemExit(1) from last_exc


def _connect_wechat(WeChat):
    return WeChat(ads=False)


class WeChatBot:
    def __init__(self):
        init_runtime_settings()
        WeChat, SelfMessage = _import_wxauto()
        self._WeChat = WeChat
        self._SelfMessage = SelfMessage
        self.wx = None
        self.handler = MessageHandler()
        self.db = DatabaseManager()
        self.sensitive = SensitiveWordFilter()
        self._last_reply_at: dict[str, float] = {}
        self._running = False
        self._poll_warmup = True
        self._known_session_previews: set[str] = set()
        self._seen_msg_keys: set[str] = set()
        self._sender_info_cache: dict[str, dict] = {}
        self._auto_accept_worker = AutoAcceptWorker(logger)

    def _wx_capabilities(self) -> dict[str, bool]:
        wx = self.wx
        if wx is None:
            return {}
        return {
            'get_next_new_message': hasattr(wx, 'GetNextNewMessage'),
            'add_listen_chat': hasattr(wx, 'AddListenChat'),
            'keep_running': hasattr(wx, 'KeepRunning'),
            'get_session': hasattr(wx, 'GetSession'),
            'chat_info': hasattr(wx, 'ChatInfo'),
        }

    def start(self):
        if not WECHAT_CONFIG.get('enabled', True):
            logger.error('WECHAT_CONFIG.enabled=false，机器人未启动')
            return

        logger.info('正在连接 PC 微信（wxauto）…')
        self.wx = _connect_wechat(self._WeChat)
        if hasattr(self.db, 'upsert_health_status'):
            self.db.upsert_health_status('wxauto', 'ok', 'wxauto 已连接', {})
        caps = self._wx_capabilities()
        if not caps.get('add_listen_chat') or not caps.get('keep_running'):
            logger.info('当前库不支持 AddListenChat/KeepRunning，改用 GetSession 轮询')
            self.run_poll_loop()
            return

        self._running = True
        self._setup_listen_chats()
        threading.Thread(target=self._notification_loop, daemon=True).start()
        self._start_auto_accept_loop()

        logger.info('微信机器人已启动，等待消息…')
        try:
            self.wx.KeepRunning()
        except KeyboardInterrupt:
            logger.info('收到退出信号')
        finally:
            self._running = False

    def _setup_listen_chats(self):
        targets = self._listen_targets()
        if not targets:
            return
        for name in targets:
            try:
                self.wx.AddListenChat(nickname=name, callback=self._on_listen_message)
                logger.info('已添加监听: %s', name)
            except Exception as exc:
                logger.warning('添加监听失败 %s: %s', name, exc)

    def _listen_targets(self) -> list[str]:
        raw = WECHAT_CONFIG.get('listen_targets') or WECHAT_CONFIG.get('listen_whitelist') or []
        if isinstance(raw, str):
            raw = [x.strip() for x in raw.split(',') if x.strip()]
        return [str(x).strip() for x in raw if str(x).strip()]

    def _on_listen_message(self, msg, chat):
        try:
            self._process_message(msg, chat_name=self._chat_name(chat), chat_obj=chat)
        except Exception as exc:
            logger.error('处理监听消息失败: %s', exc, exc_info=True)

    def poll_once(self):
        """轮询新消息：优先 GetNextNewMessage，wxauto4 则走 GetSession。"""
        if self.wx is None:
            self.wx = _connect_wechat(self._WeChat)
        caps = self._wx_capabilities()
        if caps.get('get_next_new_message'):
            self._poll_get_next_new_message()
            return
        if caps.get('get_session'):
            self._poll_sessions_once()
            return
        logger.warning('当前 wxauto 库既无 GetNextNewMessage 也无 GetSession，无法收消息')

    def _poll_get_next_new_message(self):
        try:
            packet = self.wx.GetNextNewMessage(filter_mute=bool(WECHAT_CONFIG.get('filter_mute', False)))
        except TypeError:
            packet = self.wx.GetNextNewMessage()
        except Exception as exc:
            logger.debug('GetNextNewMessage: %s', exc)
            return

        if not packet:
            return

        chat_name = packet.get('chat_name') or packet.get('chatname') or ''
        chat_type = (packet.get('chat_type') or '').lower()
        is_group = chat_type == 'group' or self._looks_like_group(chat_name)
        msgs = packet.get('msg') or []
        for msg in msgs:
            self._process_message(msg, chat_name=chat_name, is_group=is_group)

    @staticmethod
    def _session_preview_key(session) -> str:
        try:
            info = session.info
        except Exception:
            info = {}
        if not isinstance(info, dict):
            info = {}
        return f"{info.get('time', '')}|{info.get('content', '')}"

    def _poll_sessions_once(self):
        try:
            sessions = self.wx.GetSession()
        except Exception as exc:
            logger.debug('GetSession: %s', exc)
            return

        if not sessions:
            return

        filter_mute = bool(WECHAT_CONFIG.get('filter_mute', False))
        current_previews: set[str] = set()

        for session in sessions:
            preview_key = self._session_preview_key(session)
            if not preview_key or preview_key == '|':
                continue
            current_previews.add(preview_key)

            try:
                info = session.info
            except Exception:
                info = {}
            if filter_mute and isinstance(info, dict) and info.get('ismute'):
                continue

            if self._poll_warmup:
                continue
            if preview_key in self._known_session_previews:
                continue

            self._open_session_and_process(session, preview_key)

        if self._poll_warmup:
            self._known_session_previews = current_previews
            self._poll_warmup = False
            logger.info('会话轮询基线已建立（%d 个会话），开始监听新消息', len(current_previews))
            return

        self._known_session_previews = current_previews

    def _open_session_and_process(self, session, preview_key: str):
        try:
            session.click()
        except Exception as exc:
            logger.debug('打开会话失败: %s', exc)
            return

        time.sleep(SESSION_CLICK_WAIT)
        chat_name, is_group = self._active_chat_meta()
        if not chat_name:
            logger.debug('无法识别当前会话: preview=%s', preview_key)
            return

        try:
            msgs = self.wx.GetAllMessage()
        except Exception as exc:
            logger.debug('GetAllMessage 失败 chat=%s: %s', chat_name, exc)
            return

        handled = 0
        for msg in msgs:
            if not self._is_incoming_message(msg):
                continue
            msg_key = self._message_key(chat_name, msg)
            if msg_key in self._seen_msg_keys:
                continue
            self._seen_msg_keys.add(msg_key)
            self._process_message(msg, chat_name=chat_name, is_group=is_group, wait_rate_limit=True)
            handled += 1

        if handled:
            logger.info('处理会话 %s 新消息 %d 条', chat_name, handled)

    def _active_chat_meta(self) -> tuple[str, bool]:
        if not hasattr(self.wx, 'ChatInfo'):
            return '', False
        try:
            info = self.wx.ChatInfo()
        except Exception:
            return '', False
        if not isinstance(info, dict):
            return '', False
        chat_name = str(info.get('chat_name') or '').strip()
        is_group = (info.get('chat_type') or '').lower() == 'group'
        return chat_name, is_group

    def _is_incoming_message(self, msg) -> bool:
        if isinstance(msg, self._SelfMessage):
            return False
        if type(msg).__name__ in SKIP_MESSAGE_TYPES:
            return False
        if getattr(msg, 'attr', '') in ('self', 'system'):
            return False
        sender = getattr(msg, 'sender', '')
        if sender in ('self', 'Self', '自己', 'system'):
            return False
        return bool(self._message_text(msg))

    @staticmethod
    def _message_key(chat_name: str, msg) -> str:
        sender = getattr(msg, 'sender', '') or ''
        content = getattr(msg, 'content', '') or str(msg)
        return f'{chat_name}|{sender}|{content}|{type(msg).__name__}'

    def run_poll_loop(self):
        if not WECHAT_CONFIG.get('enabled', True):
            logger.error('WECHAT_CONFIG.enabled=false，机器人未启动')
            return

        if self.wx is None:
            logger.info('正在连接 PC 微信（wxauto 轮询模式）…')
            self.wx = _connect_wechat(self._WeChat)
            if hasattr(self.db, 'upsert_health_status'):
                self.db.upsert_health_status('wxauto', 'ok', 'wxauto 已连接（轮询模式）', {})
        if not self._running:
            self._running = True
            threading.Thread(target=self._notification_loop, daemon=True).start()
            self._start_auto_accept_loop()

        caps = self._wx_capabilities()
        mode = 'GetNextNewMessage' if caps.get('get_next_new_message') else 'GetSession'
        interval = max(0.5, float(WECHAT_CONFIG.get('poll_interval_seconds', 1.0)))
        targets = self._listen_targets()
        if targets:
            logger.info(
                '微信机器人已启动（%s，间隔 %.1fs，群白名单: %s；私聊全部监听）',
                mode, interval, ', '.join(targets),
            )
        else:
            logger.info('微信机器人已启动（%s，间隔 %.1fs，私聊全部监听；未配置群白名单）', mode, interval)

        try:
            while self._running:
                self.poll_once()
                if hasattr(self.db, 'upsert_health_status'):
                    self.db.upsert_health_status('wxauto_heartbeat', 'ok', 'wxauto 心跳正常', {})
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info('收到退出信号')
        finally:
            self._running = False

    def _start_auto_accept_loop(self):
        if not (
            WECHAT_CONFIG.get('auto_accept_friend')
            or WECHAT_CONFIG.get('auto_accept_group')
        ):
            return
        threading.Thread(target=self._auto_accept_loop, daemon=True).start()

    def _auto_accept_loop(self):
        interval = max(
            5.0,
            float(WECHAT_CONFIG.get('poll_interval_seconds', 1.0)),
        )
        while self._running:
            if self.wx is not None:
                self._auto_accept_worker.tick(self.wx, WECHAT_CONFIG)
            time.sleep(interval)

    def _notification_loop(self):
        interval = max(5, int(WECHAT_CONFIG.get('notification_poll_seconds', 30)))
        while self._running:
            try:
                self._flush_pending_notifications()
            except Exception as exc:
                logger.warning('推送待通知失败: %s', exc)
            time.sleep(interval)

    def _flush_pending_notifications(self):
        rows = self.db.list_all_pending_notifications(limit=20)
        for row in rows:
            wxid = row['wxid']
            chat = self._chat_for_wxid(wxid)
            if not chat:
                continue
            try:
                self._send_reply(chat, row['message'])
                self.db.mark_notifications_delivered([row['id']])
                logger.info('已主动推送通知: wxid=%s', wxid)
                self._sleep_anti_ban(chat)
            except Exception as exc:
                logger.warning('推送通知失败 wxid=%s: %s', wxid, exc)

    def _chat_for_wxid(self, wxid: str) -> str:
        """wxid 即微信号，用于 ChatWith 发消息。"""
        return (wxid or '').strip()

    def _process_message(self, msg, chat_name: str = '', is_group: bool = False, chat_obj=None, wait_rate_limit: bool = False):
        if isinstance(msg, self._SelfMessage):
            return
        if getattr(msg, 'attr', '') == 'self' or getattr(msg, 'sender', '') in ('self', 'Self', '自己'):
            return

        text = self._message_text(msg)
        if not text:
            return

        chat_name = chat_name or self._chat_name(chat_obj) or 'unknown'
        if chat_name in SPECIAL_SESSIONS:
            return
        if not self._should_handle_chat(chat_name, is_group):
            return
        if is_group and not self._should_reply_in_group(text, msg):
            return
        if self.sensitive.contains_sensitive_word(text):
            logger.info('敏感词过滤: chat=%s', chat_name)
            return

        sender = self._sender_name(msg) or chat_name
        ctx = self._build_context(msg, chat_name, sender, is_group)
        if not ctx:
            return

        if not self._acquire_reply_slot(chat_name, is_group=is_group, wait=wait_rate_limit):
            logger.info('防封限流跳过: %s', chat_name)
            return

        reply = run_handle(self.handler, ctx, text)
        if not reply:
            return

        reply = self.sensitive.filter_text(reply)
        self._sleep_anti_ban(chat_name)
        self._send_reply(chat_name, reply, chat_obj=chat_obj, at_user=sender if is_group else None)
        if is_group:
            self.db.increment_group_msg_count(chat_name)
        logger.info('已回复 %s: %s…', chat_name, reply[:40].replace('\n', ' '))

    def _fetch_sender_info(self, msg) -> dict:
        """从 wxauto4 好友资料读取微信号（id 字段）；每条消息只能调一次 sender_info。"""
        cache_key = str(getattr(msg, 'id', '') or id(msg))
        if cache_key in self._sender_info_cache:
            return self._sender_info_cache[cache_key]

        info: dict = {}
        fetch = getattr(msg, 'sender_info', None)
        if callable(fetch):
            try:
                raw = fetch()
                if isinstance(raw, dict):
                    info = raw
            except Exception as exc:
                logger.debug('sender_info 失败: %s', exc)

        self._sender_info_cache[cache_key] = info
        return info

    def _build_context(self, msg, chat_name: str, sender: str, is_group: bool) -> ChatContext | None:
        info = self._fetch_sender_info(msg)
        resolved = self._resolve_user_wxid(msg, info, chat_name, sender, is_group)
        if not resolved:
            logger.info(
                '未识别到用户微信号，跳过消息: chat=%s sender=%s is_group=%s',
                chat_name, sender, is_group,
            )
            return None

        account, nick_hint = resolved
        nickname = str(
            info.get('display_name') or info.get('remark') or nick_hint or sender or ''
        ).strip() or sender or account

        if account.startswith('gmem_'):
            logger.debug('群成员使用内部标识: wxid=%s chat=%s sender=%s', account, chat_name, sender)

        return ChatContext(
            wxid=account,
            nickname=nickname,
            chat_name=chat_name,
            is_group=is_group,
            sender_name=sender,
        )

    def _resolve_user_wxid(
        self, msg, info: dict, chat_name: str, sender: str, is_group: bool
    ) -> tuple[str, str] | None:
        """群聊中 wxauto 常把 sender_info.id 返回为「群名|昵称」，不能整串当 wxid。"""
        candidates: list[str] = []
        for key in ('wxid', 'wechat_id', 'account'):
            val = str(info.get(key) or '').strip()
            if val:
                candidates.append(val)
        for key in ('wxid', 'sender_wxid', 'account'):
            val = str(getattr(msg, key, '') or '').strip()
            if val:
                candidates.append(val)
        raw_id = str(info.get('id') or '').strip()
        if raw_id:
            candidates.append(raw_id)

        for raw in candidates:
            wxid, nick = self._normalize_wxid(raw, chat_name, sender, is_group)
            if wxid:
                return wxid, nick

        if is_group and sender:
            return self._group_member_wxid(chat_name, sender), sender
        return None

    @staticmethod
    def _normalize_wxid(raw: str, chat_name: str, sender: str, is_group: bool) -> tuple[str | None, str]:
        raw = (raw or '').strip()
        if not raw:
            return None, ''

        member = raw
        for sep in ('|', '｜'):
            if sep in member:
                parts = [p.strip() for p in member.split(sep) if p.strip()]
                if len(parts) >= 2:
                    member = parts[-1]

        if WeChatBot._looks_like_group_identity(member, chat_name):
            return None, member
        if WeChatBot._looks_like_wechat_wxid(member):
            return member, member
        if not is_group:
            return member, member
        return None, member

    @staticmethod
    def _looks_like_group_identity(label: str, chat_name: str) -> bool:
        label = (label or '').strip()
        if not label:
            return True
        cn = (chat_name or '').strip()
        if cn and (label == cn or cn in label or label in cn):
            return True
        if '|' in label or '｜' in label:
            return True
        return bool('群' in label and len(label) <= 48)

    @staticmethod
    def _looks_like_wechat_wxid(value: str) -> bool:
        value = (value or '').strip()
        if not value or ' ' in value or '|' in value or '｜' in value:
            return False
        if value.startswith('wxid_'):
            return True
        return bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{5,31}', value))

    @staticmethod
    def _group_member_wxid(chat_name: str, sender: str) -> str:
        digest = hashlib.sha256(f'{chat_name}\x00{sender}'.encode('utf-8')).hexdigest()[:20]
        return f'gmem_{digest}'

    def _should_handle_chat(self, chat_name: str, is_group: bool) -> bool:
        blacklist = self._name_list('listen_blacklist')
        if chat_name in blacklist:
            return False

        if is_group:
            if not WECHAT_CONFIG.get('listen_groups', True):
                return False
            group_whitelist = self._listen_targets()
            if not group_whitelist or chat_name not in group_whitelist:
                return False
            return True

        if not WECHAT_CONFIG.get('listen_private', True):
            return False
        return True

    def _should_reply_in_group(self, text: str, msg) -> bool:
        mode = (WECHAT_CONFIG.get('group_reply_mode') or 'link_only').lower()
        if mode == 'all':
            return True
        if mode == 'at_me_only':
            return self._is_at_me(text, msg)
        # link_only：仅链接/口令/关键词意图
        return has_product_intent(text) or self.handler.decide(text).action == 'handle'

    def _is_at_me(self, text: str, msg) -> bool:
        names = self._name_list('bot_display_names') + self._name_list('my_nickname')
        if isinstance(names, str):
            names = [names]
        for name in names:
            if name and name in text:
                return True
        at_list = getattr(msg, 'at_list', None) or getattr(msg, 'at', None)
        if at_list:
            return True
        return bool(re.search(r'@\S+', text))

    def _name_list(self, key: str) -> list[str]:
        raw = WECHAT_CONFIG.get(key) or []
        if isinstance(raw, str):
            return [x.strip() for x in raw.split(',') if x.strip()]
        return [str(x).strip() for x in raw if str(x).strip()]

    def _acquire_reply_slot(self, chat_name: str, is_group: bool = False, wait: bool = False) -> bool:
        min_interval = float(ANTI_BAN_CONFIG.get('min_reply_interval_seconds', 2))
        max_per_minute = int(ANTI_BAN_CONFIG.get('max_replies_per_minute', 20))
        if is_group:
            max_group = int(ANTI_BAN_CONFIG.get('max_group_msgs_per_hour', 60))
            count = self.db.get_group_msg_count(chat_name)
            if count >= max_group:
                return False

        while True:
            now = time.time()
            last = self._last_reply_at.get(chat_name, 0)
            gap = now - last
            if gap < min_interval:
                if wait:
                    time.sleep(min_interval - gap)
                    continue
                return False

            window_key = f'{chat_name}:{int(now // 60)}'
            bucket = getattr(self, '_minute_bucket', {})
            bucket[window_key] = bucket.get(window_key, 0) + 1
            self._minute_bucket = {
                k: v for k, v in bucket.items()
                if int(k.rsplit(':', 1)[-1]) >= int(now // 60) - 1
            }
            if self._minute_bucket.get(window_key, 0) > max_per_minute:
                return False

            self._last_reply_at[chat_name] = time.time()
            return True

    def _rate_limit_ok(self, chat_name: str, is_group: bool = False) -> bool:
        return self._acquire_reply_slot(chat_name, is_group=is_group, wait=False)

    def _sleep_anti_ban(self, chat_name: str):
        lo = float(ANTI_BAN_CONFIG.get('random_delay_min', 0.5))
        hi = float(ANTI_BAN_CONFIG.get('random_delay_max', 1.5))
        if hi > 0:
            time.sleep(random.uniform(lo, max(lo, hi)))

    def _send_reply(self, who: str, text: str, chat_obj=None, at_user: str | None = None):
        at = [at_user] if at_user else None
        if chat_obj is not None and hasattr(chat_obj, 'SendMsg'):
            chat_obj.SendMsg(text, at=at)
            return
        self.wx.SendMsg(text, who=who, at=at)

    @staticmethod
    def _message_text(msg) -> str:
        content = getattr(msg, 'content', None)
        if content is None:
            content = str(msg)
        text = str(content).strip()
        if msg_type := getattr(msg, 'type', ''):
            if msg_type in ('image', 'video', 'voice', 'file') and not text:
                return ''
        return text

    @staticmethod
    def _sender_name(msg) -> str:
        for key in ('sender', 'sender_remark', 'nickname'):
            val = getattr(msg, key, None)
            if val and str(val).strip() not in ('', 'self', 'Self', '自己'):
                return str(val).strip()
        return ''

    @staticmethod
    def _chat_name(chat) -> str:
        if chat is None:
            return ''
        for key in ('who', 'nickname', 'name', 'chat_name'):
            val = getattr(chat, key, None)
            if val:
                return str(val).strip()
        return str(chat).strip()

    @staticmethod
    def _looks_like_group(name: str) -> bool:
        return bool(name and ('群' in name or 'Group' in name))


def main():
    if sys.platform != 'win32':
        logger.error('wxauto 模式仅支持 Windows，请在已登录 PC 微信的机器上运行')
        raise SystemExit(1)

    bot = WeChatBot()
    bot.run_poll_loop()


if __name__ == '__main__':
    main()
