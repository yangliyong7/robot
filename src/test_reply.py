"""
无微信客户端的自动回复测试 CLI。

用法:
  py -m src.test_reply "余额"
  py -m src.test_reply --text "【淘宝】..." --wxid test_user
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from config.settings_store import init_runtime_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='模拟机器人自动回复（无需 wxauto）')
    parser.add_argument('text', nargs='?', default='', help='用户发送的文本')
    parser.add_argument('--text', dest='text_flag', default='', help='用户发送的文本（与位置参数二选一）')
    parser.add_argument('--wxid', default='test_wxid', help='测试用微信号')
    parser.add_argument('--nickname', default='测试用户', help='测试用昵称')
    parser.add_argument('--chat-name', default='', help='会话名（默认与昵称相同）')
    parser.add_argument('--group', action='store_true', help='模拟群聊')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    text = (args.text_flag or args.text or '').strip()
    if not text:
        print('请提供测试文本，例如: py -m src.test_reply "余额"', file=sys.stderr)
        return 2

    init_runtime_settings()
    from src.bot_simulator import simulate_bot_reply

    result = await simulate_bot_reply(
        text,
        wxid=args.wxid,
        nickname=args.nickname,
        chat_name=args.chat_name,
        is_group=args.group,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not result.get('error') else 1

    decision = result.get('decision') or {}
    print(f"路由: action={decision.get('action')} kind={decision.get('kind')}")
    if result.get('error'):
        print(f"错误: {result['error']}")
        return 1
    if result.get('replied'):
        print('--- 机器人回复 ---')
        print(result.get('reply') or '')
    else:
        print('(无回复 — 消息被忽略或未匹配)')
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == '__main__':
    main()
