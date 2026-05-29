"""
wxauto 微信机器人入口
用法: python -m src.main

默认会同时启动：
  - 管理后台: python -m src.api_server
  - 订单同步: python -m src.worker.order_sync_worker
  - 微信机器人: 本进程前台运行
"""

from __future__ import annotations

import argparse

from src.run_all import main as run_all
from src.utils import configure_utf8_io


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.main",
        description="启动返利机器人（默认启动：机器人 + 管理后台 + 订单同步）",
    )

    parser.add_argument(
        "--start",
        action="append",
        choices=["bot", "api", "worker"],
        help="指定要启动的进程，可重复传入。默认：bot/api/worker 全部启动。",
    )
    parser.add_argument("--no-bot", action="store_true", help="不启动微信机器人（只启动后台进程）")
    parser.add_argument("--no-api", action="store_true", help="不启动管理后台")
    parser.add_argument("--no-worker", action="store_true", help="不启动订单同步 worker")
    return parser.parse_args()


def main() -> None:
    configure_utf8_io()
    args = _parse_args()

    if args.start:
        start_bot = "bot" in args.start
        start_api = "api" in args.start
        start_worker = "worker" in args.start
    else:
        start_bot = True
        start_api = True
        start_worker = True

    # allow explicit disable flags to override
    if args.no_bot:
        start_bot = False
    if args.no_api:
        start_api = False
    if args.no_worker:
        start_worker = False

    run_all(start_api=start_api, start_worker=start_worker, start_bot=start_bot)


if __name__ == "__main__":
    main()
