"""wechat_auto_accept 单元测试（无需安装 wxauto）。"""

import unittest
from unittest.mock import MagicMock

from src.wechat_auto_accept import (
    discover_capabilities,
    preview_pending_accepts,
    process_auto_accepts,
)


class _FakeRequest:
    def __init__(self, name: str, kind: str = 'friend'):
        self.name = name
        self.type = kind
        self.accepted = False

    def accept(self):
        self.accepted = True


class TestWechatAutoAccept(unittest.TestCase):
    def test_discover_capabilities(self):
        wx = MagicMock()
        wx.GetNewFriends = MagicMock()
        caps = discover_capabilities(wx)
        self.assertTrue(caps['friend_fetch'])
        self.assertTrue(caps['friend'])

    def test_preview_dry_run(self):
        wx = MagicMock()
        wx.GetNewFriends.return_value = [_FakeRequest('张三'), _FakeRequest('某群', 'group')]
        cfg = {'auto_accept_friend': True, 'auto_accept_group': True}
        result = preview_pending_accepts(wx, cfg)
        self.assertEqual(result['count'], 2)
        self.assertIn('friend:张三', result['pending'])

    def test_process_accepts_friend(self):
        wx = MagicMock()
        item = _FakeRequest('李四')
        wx.GetNewFriends.return_value = [item]
        stats = process_auto_accepts(wx, {'auto_accept_friend': True}, dry_run=False)
        self.assertEqual(stats['friend'], 1)
        self.assertTrue(item.accepted)


if __name__ == '__main__':
    unittest.main()
