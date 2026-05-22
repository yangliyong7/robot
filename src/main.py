"""
OpenClaw 模式入口（业务 API）
订单同步请另开终端: python -m src.worker.order_sync_worker
"""

from src.api_server import main

if __name__ == '__main__':
    main()
