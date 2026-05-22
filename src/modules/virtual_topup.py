"""
虚拟权益充值模块
支持话费、流量等全自动充值服务
"""

import logging
import requests
from config.config import DIGITAL_RIGHTS_CONFIG

logger = logging.getLogger(__name__)


class VirtualTopupService:
    def __init__(self):
        # 配置第三方平台信息（如极速数据、欧飞等）
        self.api_url = DIGITAL_RIGHTS_CONFIG.get('topup_provider_url', 'https://api.jisuapi.com/phonecharge/charge')
        self.app_key = DIGITAL_RIGHTS_CONFIG.get('topup_app_key', '')

    async def recharge_phone(self, phone: str, amount: int = 10) -> dict:
        """
        执行话费充值
        :param phone: 手机号
        :param amount: 充值面额 (10, 20, 30, 50, 100)
        :return: 充值结果字典
        """
        logger.info(f"正在为 {phone} 充值 {amount} 元话费...")

        if not self.app_key:
            return {'success': False, 'msg': '管理员未配置充值接口密钥'}

        try:
            params = {
                "appkey": self.app_key,
                "phoneno": phone,
                "amount": amount
            }
            response = requests.get(self.api_url, params=params, timeout=10)
            data = response.json()

            # 根据极速数据的返回格式处理
            if data.get("status") == "0":
                order_id = data.get("result", {}).get("orderno")
                return {
                    'success': True, 
                    'msg': f"✅ 充值提交成功！订单号：{order_id}\n通常 1-10 分钟内到账。",
                    'order_id': order_id
                }
            else:
                return {'success': False, 'msg': f"❌ 充值失败：{data.get('msg')}"}

        except Exception as e:
            logger.error(f"话费充值接口异常: {str(e)}")
            return {'success': False, 'msg': '服务器繁忙，请稍后再试'}

    async def get_price_list(self) -> str:
        """获取当前可充值的面额列表"""
        return (
            "📱 **话费充值价目表**\n"
            "━━━━━━━━━━━━━━━\n"
            "10元 - ¥9.8 (省0.2)\n"
            "30元 - ¥29.4 (省0.6)\n"
            "50元 - ¥49.0 (省1.0)\n"
            "100元 - ¥98.0 (省2.0)\n\n"
            "💬 回复【充值 手机号 金额】即可办理\n"
            "例如：充值 13800138000 50"
        )
