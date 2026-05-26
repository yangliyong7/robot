"""
管理后台 / 调试 API 入口（可选）
用法: python -m src.api_server

微信机器人主程序: python -m src.main
"""

import uvicorn

from config.settings_store import init_runtime_settings

init_runtime_settings()

from config.config import API_SERVER_CONFIG
from src.utils import setup_logger

logger = setup_logger('ApiServer')


def main():
    host = API_SERVER_CONFIG.get('host', '127.0.0.1')
    port = int(API_SERVER_CONFIG.get('port', 8765))
    logger.info('启动管理后台 API: http://%s:%s', host, port)
    uvicorn.run(
        'src.api.app:app',
        host=host,
        port=port,
        reload=False,
        log_level='info',
    )


if __name__ == '__main__':
    main()
