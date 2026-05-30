"""微信侧文案（供 wxauto 机器人与 API 复用）"""

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
        f'⚠️ 余额以最终结算为准，退款/维权订单不发放'
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


def _parse_checkin_reward_map(raw) -> dict[int, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[int, float] = {}
    for days, reward in raw.items():
        try:
            out[int(days)] = float(reward)
        except (TypeError, ValueError):
            continue
    return out


def _next_checkin_milestone(rewards: dict[int, float], current: int) -> tuple[int, float] | None:
    for days in sorted(rewards):
        if days > current:
            return days, rewards[days]
    return None


def handle_checkin(db, wxid: str) -> str:
    stats = db.get_user_checkin_stats(wxid)
    total_before = int(stats.get('total_checkins') or 0) if stats else 0

    if db.has_checked_in_today(wxid):
        message = '⏰ 您今天已经签到过了哦~\n\n'
        message += f'累计签到：{total_before}天\n'
        message += '明天再来签到，继续累积连续天数吧！💪'
        return message

    from datetime import datetime

    now_hour = datetime.now().hour
    start_hour = int(CHECKIN_CONFIG.get('start_hour', 0))
    end_hour = int(CHECKIN_CONFIG.get('end_hour', 23))
    if start_hour <= end_hour:
        in_window = start_hour <= now_hour <= end_hour
    else:
        in_window = now_hour >= start_hour or now_hour <= end_hour
    if not in_window:
        return (
            f'⏰ 当前不在签到时间内哦~\n\n'
            f'签到开放时段：{start_hour:02d}:00 – {end_hour:02d}:59\n'
            f'请在开放时段内发送「签到」~'
        )

    continuous_days = db.get_continuous_days(wxid) + 1
    total_days = total_before + 1
    base_reward = float(CHECKIN_CONFIG.get('base_reward', 0.1))
    continuous_rewards = _parse_checkin_reward_map(CHECKIN_CONFIG.get('continuous_rewards'))
    total_rewards = _parse_checkin_reward_map(CHECKIN_CONFIG.get('total_rewards'))

    continuous_extra = continuous_rewards.get(continuous_days, 0.0)
    total_extra = total_rewards.get(total_days, 0.0)
    payout = base_reward + continuous_extra + total_extra

    db.add_checkin(wxid, payout, continuous_days)
    db.update_user_balance(wxid, payout)

    message = '✅ 签到成功！\n'
    message += '━━━━━━━━━━━━━━━\n'
    message += f'基础奖励：¥{base_reward:.2f}\n'
    if continuous_extra > 0:
        message += f'🎉 连续{continuous_days}天额外奖励：¥{continuous_extra:.2f}\n'
    if total_extra > 0:
        message += f'🏆 累计{total_days}天额外奖励：¥{total_extra:.2f}\n'
    message += f'本次获得：¥{payout:.2f}\n'
    message += f'连续签到：{continuous_days}天\n'
    message += f'累计签到：{total_days}天\n'

    tips: list[str] = []
    next_continuous = _next_checkin_milestone(continuous_rewards, continuous_days)
    if next_continuous:
        days_left, reward = next_continuous
        tips.append(f'再连续签{days_left - continuous_days}天可获得¥{reward:.2f}连续奖励')
    next_total = _next_checkin_milestone(total_rewards, total_days)
    if next_total:
        days_left, reward = next_total
        tips.append(f'再累计签{days_left - total_days}天可获得¥{reward:.2f}累计奖励')
    if tips:
        message += '\n🎯 ' + '；'.join(tips) + '！'
    message += '\n\n💡 坚持签到，奖励越来越多哦~'
    return message
