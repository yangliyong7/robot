"""
OpenClaw 业务 API 入口
用法: python -m src.api_server
"""

import uvicorn

from config.settings_store import init_runtime_settings

init_runtime_settings()

from config.config import OPENCLAW_API_CONFIG
from src.utils import setup_logger

logger = setup_logger('ApiServer')


def main():
    host = OPENCLAW_API_CONFIG.get('host', '127.0.0.1')
    port = int(OPENCLAW_API_CONFIG.get('port', 8765))
    logger.info('启动 OpenClaw 业务 API: http://%s:%s', host, port)
    uvicorn.run(
        'src.api.app:app',
        host=host,
        port=port,
        reload=False,
        log_level='info',
    )


if __name__ == '__main__':
    main()
