"""微信侧文案（从 wechat_bot 抽离，供 OpenClaw API 复用）"""

from config.config import CHECKIN_CONFIG, COMMISSION_CONFIG, ORDER_SYNC_CONFIG
from src.compliance_copy import help_message as compliance_help_message


def get_help_message() -> str:
    return compliance_help_message(COMMISSION_CONFIG.get('min_withdraw', 10))


def get_balance_message(db, wxid: str) -> str:
    user = db.get_user(wxid)
    if not user:
        return '未查询到您的账户信息，请先发送任意消息激活账户~'

    message = '💰 可结算余额（推广奖励）\n'
    message += '━━━━━━━━━━━━━━━\n'
    message += f"当前余额：¥{user['balance']:.2f}\n"
    message += f"累计入账：¥{user['total_earnings']:.2f}\n"
    message += f"服务记录：{user['total_orders']} 笔\n"
    message += (
        f"\n💡 满 {COMMISSION_CONFIG['min_withdraw']:.0f} 元可申请【提现】"
        f"（人工审核后转账）\n"
        f'⚠️ 余额以联盟结算为准，退款/维权订单不发放'
    )
    return message


def get_orders_message(db, wxid: str) -> str:
    orders = db.get_user_orders(wxid, limit=5)
    if not orders:
        return '📋 您还没有订单记录\n\n发送商品链接开始省钱吧~'

    message = '📋 最近 5 笔服务记录\n'
    message += '━━━━━━━━━━━━━━━\n'
    status_map = {
        'pending': '待确认收货',
        'paid': '已付款待收货',
        'settled': '已结算(奖励已入账)',
        'failed': '已失效',
    }
    for i, order in enumerate(orders, 1):
        status = status_map.get(order['order_status'], '未知')
        title = (order['product_title'] or '商品')[:24]
        message += f"{i}. {title}\n"
        message += (
            f"   参考价：¥{float(order['original_price'] or 0):.2f} | "
            f"预估奖励：¥{float(order['user_rebate'] or 0):.2f}\n"
        )
        message += f"   状态：{status} | 时间：{order['created_at'][:16]}\n\n"

    interval = int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))
    message += f'💡 收货后系统每 {interval} 分钟自动同步入账，无需发送订单号'
    return message


def get_stats_message(db, wxid: str) -> str:
    stats = db.get_user_stats(wxid)
    if not stats:
        return '暂无统计数据'

    message = '📊 推广奖励统计\n'
    message += '━━━━━━━━━━━━━━━\n'
    message += f"服务记录：{stats['total_orders']} 笔\n"
    message += f"累计入账：¥{stats['total_earnings']:.2f}\n"
    message += f"可结算余额：¥{stats['balance']:.2f}\n"
    message += f"加入时间：{stats['created_at'][:10]}\n"
    if stats['total_orders'] > 0:
        avg_rebate = stats['total_earnings'] / stats['total_orders']
        message += f'平均每笔：¥{avg_rebate:.2f}\n'
    message += '\n⚠️ 数据以联盟最终结算为准'
    return message


def handle_checkin(db, wxid: str) -> str:
    if db.has_checked_in_today(wxid):
        return '⏰ 您今天已经签到过了哦~\n\n明天再来签到，继续累积连续天数吧！💪'

    continuous_days_before = db.get_continuous_days(wxid)
    continuous_days = continuous_days_before + 1
    base_reward = CHECKIN_CONFIG['base_reward']
    extra_reward = 0
    for days, reward in CHECKIN_CONFIG['continuous_rewards'].items():
        if continuous_days == days:
            extra_reward = reward
            break

    total_reward = base_reward + extra_reward
    db.add_checkin(wxid, total_reward, continuous_days)
    db.update_user_balance(wxid, total_reward)

    message = '✅ 签到成功！\n'
    message += '━━━━━━━━━━━━━━━\n'
    message += f'基础奖励：¥{base_reward:.2f}\n'
    if extra_reward > 0:
        message += f'🎉 连续{continuous_days}天额外奖励：¥{extra_reward:.2f}\n'
    message += f'本次获得：¥{total_reward:.2f}\n'
    message += f'连续签到：{continuous_days}天\n'

    next_milestone = None
    for days in sorted(CHECKIN_CONFIG['continuous_rewards'].keys()):
        if days > continuous_days:
            next_milestone = days
            break
    if next_milestone:
        remaining = next_milestone - continuous_days
        milestone_reward = CHECKIN_CONFIG['continuous_rewards'][next_milestone]
        message += f'\n🎯 再签{remaining}天可获得¥{milestone_reward:.2f}额外奖励！'
    message += '\n\n💡 坚持签到，奖励越来越多哦~'
    return message
