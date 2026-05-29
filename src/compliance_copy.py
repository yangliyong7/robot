"""
面向用户的合规话术（淘宝客推广场景）
"""

from __future__ import annotations

import re
from typing import Any

SERVICE_NAME = '省钱导购助手'
DISCLAIMER_SHORT = '本服务为淘宝客导购工具，非淘宝/天猫/联盟官方。'
DISCLAIMER_SETTLE = '奖励来自推广佣金分成，以各平台最终结算为准。'
DISCLAIMER_ORDER = '请仅通过上方推广链接下单；退款、维权、失效订单不发放奖励。'

# 复制链接下单提示中的 APP 名称（按用户链接所属平台）
PLATFORM_APP_NAMES: dict[str, str] = {
    'taobao': '淘宝',
    'jd': '京东',
    'pdd': '拼多多',
    'meituan': '美团',
    'douyin': '抖音',
    'vipshop': '唯品会',
    'dangdang': '当当',
    'kuaishou': '快手',
    'bilibili': 'B站',
    'xiaomi': '小米有品',
    'yanxuan': '网易严选',
    'suning': '苏宁',
    'xiaohongshu': '小红书',
    'xianyu': '闲鱼',
    'eleme': '饿了么',
    'weixin_store': '微信小店',
    'ctrip': '携程',
    'tongcheng': '同程旅行',
    'qunar': '去哪儿',
    'fliggy': '飞猪',
    'taopiaopiao': '淘票票',
}


def platform_app_name(platform: str | None) -> str:
    if not platform:
        return '对应平台'
    key = str(platform).strip().lower()
    return PLATFORM_APP_NAMES.get(key, '对应平台')


def estimated_reward_label() -> str:
    """兼容旧调用：返回奖励说明后缀。"""
    return '（以最终结算为准）'


def calc_user_rebate(result: dict[str, Any]) -> float:
    """预估返利奖励 = 联盟佣金 × 平台返利比例（COMMISSION_CONFIG）。"""
    platform = str(result.get('platform') or '').strip().lower()
    commission = float(result.get('commission') or 0)
    if commission <= 0:
        return float(result.get('user_rebate') or 0)
    try:
        from config.config import COMMISSION_CONFIG

        rate = float(COMMISSION_CONFIG.get(f'{platform}_rate', 0.7))
    except (TypeError, ValueError):
        rate = 0.7
    return round(commission * rate, 2)


def format_estimated_reward(rebate: float) -> str:
    if not rebate or rebate <= 0:
        return ''
    return f'💰 预估返利奖励 ¥{rebate:.2f}\n（以最终结算为准）'


def promo_footer_notes(platform: str | None = None) -> str:
    app = platform_app_name(platform)
    return '\n'.join([
        f'✅ 请复制链接到{app} APP 下单',
        '📦 确认收货后自动同步并入账',
    ])


def link_success_notes(platform: str | None = None) -> str:
    """查优惠/转链成功后的底部说明（含合规提示）。"""
    interval = 10
    try:
        from config.config import ORDER_SYNC_CONFIG
        interval = int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))
    except Exception:
        pass
    lines = [
        '',
        *promo_footer_notes(platform).split('\n'),
        f'💡 入账后会通知您，也可回复【订单】【余额】查看（约每 {interval} 分钟同步）',
        '',
        f'⚠️ {DISCLAIMER_SHORT}',
        f'⚠️ {DISCLAIMER_ORDER}',
    ]
    return '\n'.join(lines)


def extract_share_product_hint(text: str) -> str:
    """从分享文案中提取商品名（无推广时展示用）。"""
    text = (text or '').strip()
    if not text:
        return ''
    m = re.search(r'「([^」]{2,80})」', text)
    if m:
        return m.group(1).strip()
    for part in reversed(re.split(r'https?://\S+', text)):
        chunk = re.sub(r'【[^】]+】', ' ', part)
        chunk = re.sub(r'\s+', ' ', chunk).strip()
        chunk = re.sub(r'^(?:CZ|HU)\d+\s+', '', chunk, flags=re.I)
        if len(chunk) >= 3 and re.search(r'[\u4e00-\u9fff]', chunk):
            return chunk[:48]
    return ''


def build_compare_page_url(token: str) -> str:
    """生成全网比价页 URL（仅含服务端令牌，不含商品参数）。"""
    token = (token or '').strip()
    if not token:
        return ''

    base = ''
    try:
        from config.config import WECHAT_CONFIG

        base = (WECHAT_CONFIG.get('compare_public_base_url') or '').strip().rstrip('/')
    except Exception:
        pass
    if not base:
        try:
            from config.config import API_SERVER_CONFIG

            host = (API_SERVER_CONFIG.get('public_host') or API_SERVER_CONFIG.get('host') or '127.0.0.1')
            if host in ('0.0.0.0', '::'):
                host = '127.0.0.1'
            port = int(API_SERVER_CONFIG.get('port', 8765))
            base = f'http://{host}:{port}'
        except Exception:
            base = 'http://127.0.0.1:8765'

    return f'{base}/compare/{token}'


def format_no_promo_reply(
    result: dict[str, Any],
    *,
    raw_text: str = '',
    compare_url: str | None = None,
) -> str:
    """无联盟推广/无券无返利时：不展示优惠购买链接。"""
    platform = result.get('platform')
    app = platform_app_name(platform)
    title = (result.get('title') or extract_share_product_hint(raw_text) or '').strip()

    lines = ['😔 暂未找到可记录的推广优惠', '']
    if title:
        lines.append(f'📦 {title[:48]}')
        lines.append('')
    lines.append('💡 您可以：')
    lines.append(f'• 在{app} APP 用原分享链接直接购买')
    if compare_url:
        lines.append('')
        lines.append('🔍 全网比价（点此查看）：')
        lines.append(compare_url.strip())
    return '\n'.join(lines)


def _normalize_ai_advice(advice: str | None) -> str | None:
    if not advice or not str(advice).strip():
        return None
    text = str(advice).strip()
    for prefix in ('💡 AI 建议：', '💡 AI建议：', '💡 导购参考：', '💬 导购参考：'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return f'💡 AI 建议：{text}'


def format_promo_reply(result: dict[str, Any], ai_advice: str | None = None) -> str:
    """
    查优惠 / 转链成功后的统一回复样式。
    """
    platform = result.get('platform')
    lines = ['🛒 已为您找到优惠！', '']

    rebate_url = (result.get('rebate_url') or result.get('original_url') or '').strip()
    lines.append('📎 优惠购买链接：')
    lines.append(rebate_url or '[点击复制链接]')
    lines.append('')

    reward_block = format_estimated_reward(calc_user_rebate(result))
    if reward_block:
        lines.append(reward_block)
        lines.append('')

    advice_line = _normalize_ai_advice(ai_advice)
    if advice_line:
        lines.append(advice_line)
        lines.append('')

    lines.append(promo_footer_notes(platform))

    tpwd = result.get('tpwd')
    if tpwd:
        lines.extend(['', f'📱 口令：{tpwd}'])

    return '\n'.join(lines)


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


def order_event_notify_message(
    *,
    event: str,
    platform: str,
    product_title: str = '',
    rebate_delta: float | None = None,
    balance: float | None = None,
) -> str:
    """订单状态事件通知（下单/确认/退款/失效/返利调整等）。"""
    title = (product_title or '商品')[:20]
    ev = (event or '').strip().lower()
    event_label = {
        'paid': '下单成功',
        'confirmed': '确认收货',
        'invalid': '订单失效/退款',
        'refund_full': '订单已全额退款',
        'refund_partial': '订单发生部分退款',
        'rebate_adjust': '返利金额已调整',
    }.get(ev, event or '订单状态更新')

    lines = [
        f'📬 订单状态更新（{SERVICE_NAME}）',
        '━━━━━━━━━━━━━━━',
        f'事件：{event_label}',
        f'平台：{platform}',
        f'商品：{title}',
    ]
    if rebate_delta is not None:
        delta = float(rebate_delta)
        sign = '+' if delta >= 0 else '-'
        lines.append(f'返利变动：{sign}¥{abs(delta):.2f}')
    if balance is not None:
        lines.append(f'当前余额：¥{float(balance):.2f}')
    lines.extend(['', f'⚠️ {DISCLAIMER_SETTLE}'])
    return '\n'.join(lines)


def help_message(min_withdraw: float) -> str:
    try:
        from config.config import ORDER_SYNC_CONFIG
        interval = int(ORDER_SYNC_CONFIG.get('interval_minutes', 10))
    except Exception:
        interval = 10
    return f"""🤖 {SERVICE_NAME} 使用说明

📌 服务说明：
本工具帮助查询优惠并使用淘宝客推广链接导购。
奖励以最终结算为准，无需您提交订单号或确认收货。

📌 使用流程：
1️⃣ 发送商品链接 → 获取优惠购买链接
2️⃣ 通过推广链接下单
3️⃣ 收货后系统每 {interval} 分钟自动同步并入账（会通知您）

💬 常用指令：
• 【余额】【订单】【提现】【帮助】

🎯 直接发送淘宝/京东/拼多多等商品链接或分享文案即可

⚠️ 须通过机器人推广链接下单；退款/维权订单不发放。
⚠️ {DISCLAIMER_SHORT}"""
