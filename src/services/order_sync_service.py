"""
联盟订单同步服务：定时拉取联盟订单，确认收货/结算后按规则发放推广奖励
（等效于联盟订单回调，桌面端采用轮询方式）
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from config.config import ORDER_SYNC_CONFIG, COMMISSION_CONFIG
from src.platforms.alliance_orders import AllianceOrderFetcher
from src.compliance_copy import settle_notify_message

logger = logging.getLogger(__name__)

SETTLE_STATUSES = frozenset({'confirmed', 'settled'})


class OrderSyncService:
    def __init__(self, db, wallet_service=None, notify_callback=None):
        self.db = db
        self.fetcher = AllianceOrderFetcher()
        self.wallet = wallet_service
        self.notify_callback = notify_callback
        self.enabled = ORDER_SYNC_CONFIG.get('enabled', True)
        self.lookback_minutes = ORDER_SYNC_CONFIG.get('lookback_minutes', 120)
        self.settle_on_confirm = ORDER_SYNC_CONFIG.get('settle_on_confirm', True)

    async def sync_once(self) -> Dict:
        """执行一次全平台订单同步"""
        if not self.enabled:
            return {'success': False, 'message': '订单同步未启用'}

        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=self.lookback_minutes)
        last_sync = self.db.get_order_sync_time('all')
        if last_sync:
            try:
                start_time = max(start_time, datetime.fromisoformat(last_sync))
            except ValueError:
                pass

        platform_orders = await self.fetcher.fetch_all(start_time, end_time)
        stats = {
            'fetched': len(platform_orders),
            'linked': 0,
            'settled': 0,
            'invalid': 0,
            'skipped': 0,
            'notified': [],
        }

        for po in platform_orders:
            try:
                outcome = self._process_platform_order(po)
                stats[outcome] = stats.get(outcome, 0) + 1
            except Exception as e:
                logger.error('处理联盟订单失败: %s', e, exc_info=True)
                stats['skipped'] = stats.get('skipped', 0) + 1

        self.db.set_order_sync_time('all', end_time.isoformat())
        logger.info('联盟订单同步完成: %s', stats)
        return {'success': True, 'stats': stats}

    def _process_platform_order(self, po: Dict) -> str:
        platform = po['platform']
        platform_order_id = po['platform_order_id']
        wxid = po.get('wxid') or ''

        existing = self.db.get_order_by_platform(platform, platform_order_id)
        if existing:
            return self._update_existing_order(existing, po)

        internal = self._match_internal_order(po)
        if not internal:
            if wxid:
                logger.info(
                    '联盟订单无机器人转链记录，跳过返利: platform=%s oid=%s wxid=%s',
                    platform, platform_order_id, wxid,
                )
            return 'skipped'

        if not self.db.is_order_rebate_eligible(internal):
            logger.info('订单非 bot_convert 来源，跳过返利: %s', internal['order_no'])
            return 'skipped'

        self.db.link_platform_order(
            order_no=internal['order_no'],
            platform_order_id=platform_order_id,
            platform_item_id=po.get('platform_item_id'),
            platform_status=po.get('platform_status'),
            user_rebate=po.get('user_rebate'),
        )
        order_no = internal['order_no']
        wxid = internal['wxid']

        if po['norm_status'] == 'invalid':
            self.db.update_order_status(order_no, 'failed')
            return 'invalid'

        if po['norm_status'] == 'paid':
            self.db.update_order_status(order_no, 'paid')
            return 'linked'

        if self.settle_on_confirm and po['norm_status'] in SETTLE_STATUSES:
            result = self.db.settle_order_on_receipt(order_no, wxid=wxid)
            if result.get('success'):
                self._notify_user(wxid, result, po, order_no=order_no)
                return 'settled'
            if '已发放' in result.get('message', ''):
                return 'skipped'
        return 'linked'

    def _update_existing_order(self, existing: Dict, po: Dict) -> str:
        order_no = existing['order_no']
        wxid = existing['wxid']
        self.db.update_order_platform_status(order_no, po.get('platform_status'))

        if existing['order_status'] == 'settled':
            return 'skipped'
        if po['norm_status'] == 'invalid':
            self.db.update_order_status(order_no, 'failed')
            return 'invalid'
        if po['norm_status'] == 'paid' and existing['order_status'] == 'pending':
            self.db.update_order_status(order_no, 'paid')
            return 'linked'
        if self.settle_on_confirm and po['norm_status'] in SETTLE_STATUSES:
            result = self.db.settle_order_on_receipt(order_no, wxid=wxid)
            if result.get('success'):
                self._notify_user(wxid, result, po, order_no=order_no)
                return 'settled'
        return 'skipped'

    def _match_internal_order(self, po: Dict) -> Optional[Dict]:
        wxid = po.get('wxid')
        if not wxid:
            return None
        item_id = po.get('platform_item_id')
        return self.db.find_match_pending_order(
            wxid=wxid,
            platform=po['platform'],
            platform_item_id=item_id,
            within_days=ORDER_SYNC_CONFIG.get('match_within_days', 15),
        )

    def _notify_user(self, wxid: str, settle_result: Dict, po: Dict, order_no: str = None):
        if not self.notify_callback or not wxid:
            return
        msg = settle_notify_message(
            platform=po['platform'],
            product_title=settle_result.get('product_title') or po.get('title') or '',
            rebate=float(settle_result.get('rebate', 0)),
            balance=float(settle_result.get('balance', 0)),
            min_withdraw=float(COMMISSION_CONFIG.get('min_withdraw', 10)),
        )
        try:
            self.notify_callback(
                wxid,
                msg,
                order_no=order_no or settle_result.get('order_no'),
                notify_chat=settle_result.get('notify_chat'),
                notify_is_group=settle_result.get('notify_is_group'),
                user_nickname=settle_result.get('user_nickname'),
            )
            target = settle_result.get('notify_chat') or wxid
            logger.info('已通知返利到账: wxid=%s target=%s', wxid, target)
        except Exception as e:
            logger.warning('通知用户失败 %s: %s', wxid, e)
