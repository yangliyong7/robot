"""
钱包服务：提现申请/审核、订单结算（主要由联盟定时同步触发）
"""

import logging
import re
from typing import Optional

from config.config import COMMISSION_CONFIG

logger = logging.getLogger(__name__)

ORDER_NO_PATTERN = re.compile(r'ORDER_[\w]+', re.IGNORECASE)


class WalletService:
    def __init__(self, db):
        self.db = db

    @property
    def min_withdraw(self) -> float:
        return float(COMMISSION_CONFIG.get('min_withdraw', 10.0))

    def extract_order_no(self, text: str) -> Optional[str]:
        """提取内部订单号（仅管理员指令使用）"""
        match = ORDER_NO_PATTERN.search(text or '')
        return match.group(0).upper() if match else None

    def apply_withdraw(self, wxid: str, payment_method: str = 'wechat', payment_account: str = '') -> dict:
        return self.db.apply_withdrawal(
            wxid=wxid,
            min_amount=self.min_withdraw,
            payment_method=payment_method,
            payment_account=payment_account or wxid,
        )

    def confirm_order_receipt(self, wxid: str, order_no: str) -> dict:
        return self.db.settle_order_on_receipt(order_no=order_no, wxid=wxid)

    def admin_settle_order(self, order_no: str) -> dict:
        return self.db.settle_order_on_receipt(order_no=order_no, wxid=None)

    def list_pending_withdrawals(self, limit: int = 20) -> list:
        return self.db.get_pending_withdrawals(limit=limit)

    def approve_withdraw(self, withdraw_id: int, remark: str = '') -> dict:
        return self.db.complete_withdrawal(withdraw_id, remark=remark)

    def reject_withdraw(self, withdraw_id: int, remark: str = '') -> dict:
        return self.db.reject_withdrawal(withdraw_id, remark=remark)

    def format_pending_withdrawals_message(self, limit: int = 20) -> str:
        rows = self.list_pending_withdrawals(limit)
        if not rows:
            return '📋 当前没有待审核的提现申请'

        msg = f'📋 待审核提现（共 {len(rows)} 条）\n━━━━━━━━━━━━━━━\n'
        for row in rows:
            msg += (
                f"#{row['id']} | ¥{row['amount']:.2f}\n"
                f"   用户: {row['wxid']}\n"
                f"   时间: {str(row['created_at'])[:16]}\n"
            )
        msg += (
            '\n操作指令：\n'
            '• 【通过提现 编号】审核通过（请线下转账后操作）\n'
            '• 【拒绝提现 编号 原因】拒绝并退回余额'
        )
        return msg
