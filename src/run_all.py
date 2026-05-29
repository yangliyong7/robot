"""
一键启动入口（Windows 推荐）

用法:
  python -m src.run_all

说明:
  - 管理后台、订单同步、微信机器人是三个独立进程
  - 本模块负责启动后台进程，并以前台方式运行机器人，便于查看日志与 Ctrl+C 停止
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import time
from typing import List, Optional


_children: List[subprocess.Popen] = []


def _utf8_env() -> dict:
    # 让子进程也统一 UTF-8 输出（比依赖控制台 codepage 更稳）
    env = dict(os.environ)
    env.setdefault('PYTHONUTF8', '1')
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    return env


def _spawn(module: str) -> subprocess.Popen:
    # 用同一个 python 解释器启动，避免环境不一致
    p = subprocess.Popen([sys.executable, "-m", module], env=_utf8_env())
    _children.append(p)
    return p


def _terminate_children() -> None:
    # Windows 下 terminate() 是最可控的退出方式
    for p in _children:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass


def _handle_signal(sig: int, frame: Optional[object]) -> None:
    _terminate_children()
    raise SystemExit(0)


def main(*, start_api: bool = True, start_worker: bool = True, start_bot: bool = True) -> None:
    # 先启动依赖后台进程
    if start_api:
        _spawn("src.api_server")
    if start_worker:
        _spawn("src.worker.order_sync_worker")

    atexit.register(_terminate_children)
    signal.signal(signal.SIGINT, _handle_signal)

    # 再启动机器人（前台阻塞）
    if start_bot:
        try:
            from src.utils import configure_wxauto_logging  # noqa: WPS433 (delayed import)
            from src.wechat_bot import main as bot_main  # noqa: WPS433 (delayed import)

            configure_wxauto_logging()
            bot_main()
            return
        except SystemExit:
            # 机器人启动失败（如未安装 wxauto/无微信客户端等），仍保持后台进程运行
            pass
        except Exception:
            # 不让机器人异常拖垮后台服务
            pass

    # 只启动后台：阻塞等待，便于 Ctrl+C 统一退出
    while True:
        alive = False
        for p in _children:
            if p.poll() is None:
                alive = True
                break
        if not alive:
            return
        time.sleep(0.5)


if __name__ == "__main__":
    main()

