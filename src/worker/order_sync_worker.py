"""
联盟订单同步 worker
结算通知写入 pending_notifications，由 wxauto 机器人推送或下次对话时附带。

用法: python -m src.worker.order_sync_worker
"""

import asyncio
import logging
import signal
import sys

from config.config import ORDER_SYNC_CONFIG
from config.settings_store import init_runtime_settings
from src.database import DatabaseManager
from src.services.order_sync_service import OrderSyncService
from src.services.wallet_service import WalletService
from src.utils import setup_logger

logger = setup_logger('OrderSyncWorker')
_running = True

async def run_loop():
    db = DatabaseManager()
    wallet = WalletService(db)

    def notify_callback(wxid, message, order_no=None, **kwargs):
        db.add_pending_notification(wxid, message)
        logger.info('结算通知已入队: wxid=%s order=%s', wxid, order_no)

    sync = OrderSyncService(db, wallet_service=wallet, notify_callback=notify_callback)
    logger.info('订单同步 worker 已启动')

    while _running:
        interval = max(1, int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))) * 60
        try:
            if ORDER_SYNC_CONFIG.get('enabled', True):
                result = await sync.sync_once()
                logger.info('同步结果: %s', result)
                if hasattr(db, 'upsert_health_status'):
                    db.upsert_health_status(
                        'order_sync_worker',
                        'ok',
                        '订单同步 worker 运行中',
                        {'interval_minutes': int(ORDER_SYNC_CONFIG.get('interval_minutes', 10) or 10)},
                    )
        except Exception as e:
            logger.error('同步失败: %s', e, exc_info=True)
            if hasattr(db, 'record_health_run'):
                db.record_health_run(
                    'order_sync_run',
                    success=False,
                    message=f'同步异常: {type(e).__name__}: {str(e)[:120]}',
                    detail_patch={},
                    fail_threshold=int(ORDER_SYNC_CONFIG.get('fail_threshold', 3) or 3),
                )
        await asyncio.sleep(interval)


def _stop(sig, frame):
    global _running
    logger.info('收到信号 %s，准备退出', sig)
    _running = False


def main():
    init_runtime_settings()
    signal.signal(signal.SIGINT, _stop)
    if sys.platform != 'win32':
        signal.signal(signal.SIGTERM, _stop)
    asyncio.run(run_loop())


if __name__ == '__main__':
    main()
