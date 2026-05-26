"""
wxauto 微信机器人入口
用法: python -m src.main

管理后台另开终端: python -m src.api_server
订单同步另开终端: python -m src.worker.order_sync_worker
"""

from src.utils import configure_wxauto_logging

configure_wxauto_logging()

from src.wechat_bot import main

if __name__ == '__main__':
    main()
