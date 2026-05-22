"""
面向用户的合规话术（淘宝客推广场景）
"""

SERVICE_NAME = '省钱导购助手'
DISCLAIMER_SHORT = '本服务为淘宝客导购工具，非淘宝/天猫/联盟官方。'
DISCLAIMER_SETTLE = '奖励来自推广佣金分成，以淘宝联盟最终结算为准。'
DISCLAIMER_ORDER = '请仅通过上方推广链接下单；退款、维权、失效订单不发放奖励。'


def link_success_notes() -> str:
    interval = 10
    try:
        from config.config import ORDER_SYNC_CONFIG
        interval = int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))
    except Exception:
        pass
    lines = [
        '',
        '✅ 请复制上方链接到淘宝/天猫 APP 下单',
        '📌 须通过本链接完成购买，方可参与奖励统计',
        f'📦 确认收货后，系统每 {interval} 分钟自动同步联盟订单并入账',
        '💡 入账后会通知您，也可回复【订单】【余额】查看',
        '',
        f'⚠️ {DISCLAIMER_SHORT}',
        f'⚠️ {DISCLAIMER_ORDER}',
    ]
    return '\n'.join(lines)


def estimated_reward_label() -> str:
    return '预估推广奖励（以联盟结算为准）'


def settle_notify_message(
    platform: str,
    product_title: str,
    rebate: float,
    balance: float,
    min_withdraw: float,
) -> str:
    title = (product_title or '商品')[:20]
    return (
        f'📬 订单状态更新（{SERVICE_NAME}）\n'
        f'━━━━━━━━━━━━━━━\n'
        f'平台：{platform}\n'
        f'商品：{title}\n'
        f'本次入账：¥{rebate:.2f}（推广奖励）\n'
        f'可结算余额：¥{balance:.2f}\n\n'
        f'💡 满 {min_withdraw:.0f} 元可回复【提现】申请结算\n'
        f'⚠️ {DISCLAIMER_SETTLE}'
    )


def help_message(min_withdraw: float) -> str:
    try:
        from config.config import ORDER_SYNC_CONFIG
        interval = int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))
    except Exception:
        interval = 10
    return f"""🤖 {SERVICE_NAME} 使用说明

📌 服务说明：
本工具帮助查询优惠并使用淘宝客推广链接导购。
奖励以联盟结算为准，无需您提交订单号或确认收货。

📌 使用流程：
1️⃣ 发送商品链接 → 获取推广购买链接
2️⃣ 通过推广链接下单
3️⃣ 收货后系统每 {interval} 分钟自动同步并入账（会通知您）

💬 常用指令：
• 【余额】【订单】【提现】【帮助】

🎯 直接发送淘宝/天猫商品链接或分享文案即可

⚠️ 须通过机器人推广链接下单；退款/维权订单不发放。
⚠️ {DISCLAIMER_SHORT}"""
