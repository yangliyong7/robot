"""
多平台返利接口模块
支持淘宝、京东、拼多多、美团及扩展电商平台真实联盟 API 转链
"""

import re
import logging
import inspect

from config.config import COMMISSION_CONFIG
from src.compliance_copy import estimated_reward_label, link_success_notes
from src.platforms import (
    TaobaoClient,
    JDClient,
    PDDClient,
    MeituanClient,
    DouyinClient,
    VipshopClient,
    DangdangClient,
    KuaishouClient,
    XiaomiClient,
    YanxuanClient,
    BilibiliClient,
    SuningClient,
    XiaohongshuClient,
    XianyuClient,
    ElemeClient,
    WeixinStoreClient,
    CtripClient,
    TongchengClient,
    QunarClient,
    FliggyClient,
    TaopiaopiaoClient,
)

logger = logging.getLogger(__name__)

PLATFORM_NAMES = {
    'taobao': '淘宝/天猫',
    'jd': '京东',
    'pdd': '拼多多',
    'meituan': '美团外卖',
    'douyin': '抖音电商',
    'vipshop': '唯品会',
    'dangdang': '当当',
    'kuaishou': '快手',
    'bilibili': 'B站会员购',
    'xiaomi': '小米有品',
    'yanxuan': '网易严选',
    'suning': '苏宁',
    'xiaohongshu': '小红书',
    'xianyu': '闲鱼',
    'eleme': '饿了么',
    'weixin_store': '微信小店/推客',
    'ctrip': '携程',
    'tongcheng': '同程旅行',
    'qunar': '去哪儿',
    'fliggy': '飞猪旅行',
    'taopiaopiao': '淘票票',
}


class RebateAPI:
    """多平台返利 API 统一入口"""

    def __init__(self):
        self.taobao = TaobaoClient()
        self.jd = JDClient()
        self.pdd = PDDClient()
        self.meituan = MeituanClient()
        self.douyin = DouyinClient()
        self.vipshop = VipshopClient()
        self.dangdang = DangdangClient()
        self.kuaishou = KuaishouClient()
        self.xiaomi = XiaomiClient()
        self.yanxuan = YanxuanClient()
        self.bilibili = BilibiliClient()
        self.suning = SuningClient()
        self.xiaohongshu = XiaohongshuClient()
        self.xianyu = XianyuClient()
        self.eleme = ElemeClient()
        self.weixin_store = WeixinStoreClient()
        self.ctrip = CtripClient()
        self.tongcheng = TongchengClient()
        self.qunar = QunarClient()
        self.fliggy = FliggyClient()
        self.taopiaopiao = TaopiaopiaoClient()

        self._core_handlers = {
            'taobao': self.taobao,
            'jd': self.jd,
            'pdd': self.pdd,
            'meituan': self.meituan,
            'xianyu': self.xianyu,
            'eleme': self.eleme,
            'weixin_store': self.weixin_store,
            'ctrip': self.ctrip,
            'tongcheng': self.tongcheng,
            'qunar': self.qunar,
            'fliggy': self.fliggy,
            'taopiaopiao': self.taopiaopiao,
        }
        self._extended_handlers = {
            'douyin': self.douyin,
            'vipshop': self.vipshop,
            'dangdang': self.dangdang,
            'kuaishou': self.kuaishou,
            'xiaomi': self.xiaomi,
            'yanxuan': self.yanxuan,
            'bilibili': self.bilibili,
            'suning': self.suning,
            'xiaohongshu': self.xiaohongshu,
        }

    def detect_platform(self, text):
        """检测商品链接所属平台"""
        if not text:
            return 'unknown'

        text_lower = text.lower()

        platform_rules = [
            (('store.weixin.qq.com', 'channels.weixin.qq.com'), 'weixin_store'),
            (('goofish.com', 'idle.taobao.com', '2.taobao.com/item.htm?'), 'xianyu'),
            (('ele.me', 'eleme.cn', 'h5.ele.me'), 'eleme'),
            (('ctrip.com', 'm.ctrip.com', 'u.ctrip.com'), 'ctrip'),
            (('fliggy.com', 'feizhu.com', 'alitrip.com', 'market.m.taobao.com/app/trip'), 'fliggy'),
            (('taopiaopiao.com', 'piao.cn', 'damai.cn', 'm.damai.cn'), 'taopiaopiao'),
            (('ly.com', 'elong.com', '17u.cn'), 'tongcheng'),
            (('qunar.com', 'touch.qunar.com'), 'qunar'),
            (('xiaohongshu.com', 'xhslink.com', 'xhs.cn', 'xhsurl.com'), 'xiaohongshu'),
            (('suning.com', 'm.suning.com', 'su.cn'), 'suning'),
            (('douyin.com', 'jinritemai.com', 'haohuo.jinritemai'), 'douyin'),
            (('vip.com', 'vipshop.com'), 'vipshop'),
            (('dangdang.com',), 'dangdang'),
            (('kuaishou.com', 'kwai.com', 'chenzhongkj.com'), 'kuaishou'),
            (('bilibili.com', 'b23.tv', 'show.bilibili.com'), 'bilibili'),
            (('mi.com', 'youpin.mi.com', 'xiaomi.com'), 'xiaomi'),
            (('you.163.com',), 'yanxuan'),
            (('taobao.com', 'tmall.com', 'tb.cn', 'm.tb.cn', 'e.tb.cn'), 'taobao'),
            (('jd.com', '3.cn', 'm.jd.com'), 'jd'),
            (('pinduoduo.com', 'yangkeduo.com', 'pdd.qq.com'), 'pdd'),
            (('meituan.com', 'mturl.cn', 'i.meituan.com', 'dianping.com'), 'meituan'),
        ]
        for keywords, platform in platform_rules:
            if any(k in text_lower for k in keywords):
                return platform

        if re.search(r'闲鱼|【闲鱼】', text):
            return 'xianyu'

        tb_tpword = r'【淘宝】.*?[￥¥Y]\w+[￥¥Y]'
        if re.search(tb_tpword, text, re.IGNORECASE):
            return 'taobao'
        jd_tpword = r'【京东】.*?[￥¥Y]\w+[￥¥Y]'
        if re.search(jd_tpword, text, re.IGNORECASE):
            return 'jd'

        keyword_platform = get_platform_from_keyword(text)
        if keyword_platform:
            return keyword_platform

        return 'unknown'

    async def convert_link(self, url, platform=None, wxid=None):
        """智能转换返利链接"""
        if not platform:
            platform = self.detect_platform(url)

        logger.info('开始转换链接: 平台=%s, URL=%s...', platform, (url or '')[:80])

        try:
            handler = self._core_handlers.get(platform) or self._extended_handlers.get(platform)
            if not handler:
                supported = '、'.join(PLATFORM_NAMES.values())
                return {
                    'success': False,
                    'message': f'暂不支持该平台。支持：{supported}',
                }

            convert_kwargs = {}
            if wxid and hasattr(handler, 'convert'):
                sig = inspect.signature(handler.convert)
                if 'wxid' in sig.parameters:
                    convert_kwargs['wxid'] = wxid
            result = await handler.convert(url, **convert_kwargs)

            if result.get('success') and 'commission' in result:
                rate_key = f'{platform}_rate'
                user_rate = COMMISSION_CONFIG.get(rate_key, 0.7)
                result['user_rebate'] = round(float(result.get('commission', 0)) * user_rate, 2)

            return result

        except Exception as e:
            logger.error('链接转换失败: %s', e, exc_info=True)
            return {'success': False, 'message': f'转换失败: {str(e)}'}

    async def convert_activity(self, platform: str, wxid: str = None, **kwargs):
        """活动页/口令类转链（饿了么红包、出行预订等）"""
        handler = self._core_handlers.get(platform)
        if not handler:
            return {'success': False, 'message': f'不支持的活动平台: {platform}'}

        if platform == 'eleme' and hasattr(handler, 'get_activity_link'):
            result = await handler.get_activity_link(wxid=wxid, **kwargs)
        elif platform == 'ctrip' and kwargs.get('city'):
            if kwargs.get('travel_type') == 'flight':
                result = await handler.get_flight_link(
                    kwargs.get('from_city', ''),
                    kwargs.get('to_city', kwargs.get('city', '')),
                    wxid=wxid,
                )
            else:
                result = await handler.get_hotel_link(
                    kwargs.get('city', ''),
                    wxid=wxid,
                    check_in=kwargs.get('check_in', ''),
                )
        elif platform in ('tongcheng', 'qunar') and kwargs.get('city'):
            result = await handler.get_hotel_link(kwargs.get('city', ''), wxid=wxid)
        elif platform == 'fliggy':
            result = await handler.get_activity_link(wxid=wxid, **kwargs)
        elif platform == 'taopiaopiao':
            if kwargs.get('keyword') or kwargs.get('city'):
                result = await handler.search_movies(
                    keyword=kwargs.get('keyword', ''),
                    city=kwargs.get('city'),
                )
            else:
                result = await handler.get_activity_link(wxid=wxid)
        else:
            result = await self.convert_link('', platform=platform, wxid=wxid)

        if result.get('success') and 'commission' in result:
            rate_key = f'{platform}_rate'
            user_rate = COMMISSION_CONFIG.get(rate_key, 0.7)
            result['user_rebate'] = round(float(result.get('commission', 0)) * user_rate, 2)
        return result

    def format_rebate_message(self, result):
        """格式化返利消息"""
        if not result['success']:
            return f"❌ {result['message']}"

        platform = result.get('platform', 'unknown')
        platform_name = PLATFORM_NAMES.get(platform, platform)

        message = f"🎯 {platform_name}优惠信息\n"
        message += "━━━━━━━━━━━━━━━\n"

        if result.get('title'):
            message += f"📦 商品：{result['title']}\n"
        if result.get('original_price'):
            message += f"💰 原价：¥{result['original_price']:.2f}\n"
        if result.get('coupon_amount') and result['coupon_amount'] > 0:
            message += f"🎫 优惠券：¥{result['coupon_amount']:.2f}\n"
        if result.get('final_price'):
            message += f"✨ 到手价：¥{result['final_price']:.2f}\n"
        if result.get('commission') and result['commission'] > 0:
            message += f"💵 预估佣金：¥{result['commission']:.2f}\n"
        if result.get('user_rebate') and result['user_rebate'] > 0:
            message += f"🎁 {estimated_reward_label()}：¥{result['user_rebate']:.2f}\n"

        message += f"\n🔗 推广购买链接：\n{result.get('rebate_url', result.get('original_url', ''))}\n"
        if result.get('tpwd'):
            message += f"\n📱 口令：{result['tpwd']}\n"
        message += link_success_notes()

        return message


# 兼容旧代码：TaobaoAPI / JDAPI 等别名
TaobaoAPI = TaobaoClient
JDAPI = JDClient
PDDAPI = PDDClient
MeituanAPI = MeituanClient


def extract_url_from_text(text):
    """从文本中提取 URL"""
    url_pattern = r'https?://[^\s<>\"\'\[\]]+|www\.[^\s<>\"\'\[\]]+'
    return re.findall(url_pattern, text)


def is_product_link(text):
    return len(extract_url_from_text(text)) > 0


def get_platform_from_keyword(text):
    text_lower = text.lower()
    mapping = [
        (['饿了么', 'eleme', '外卖红包', '饿了嘛'], 'eleme'),
        (['闲鱼', 'goofish', 'xianyu'], 'xianyu'),
        (['视频号', '微信小店', '推客', '小店商品'], 'weixin_store'),
        (['携程', 'ctrip'], 'ctrip'),
        (['同程', 'tongcheng', 'ly.com'], 'tongcheng'),
        (['去哪儿', 'qunar'], 'qunar'),
        (['飞猪', 'fliggy', 'feizhu'], 'fliggy'),
        (['淘票票', 'taopiaopiao', '电影票', '大麦'], 'taopiaopiao'),
        (['淘宝', '天猫', 'taobao'], 'taobao'),
        (['京东', 'jd'], 'jd'),
        (['拼多多', 'pdd', 'pinduoduo'], 'pdd'),
        (['美团', 'meituan'], 'meituan'),
        (['抖音', 'douyin'], 'douyin'),
        (['唯品会', 'vipshop'], 'vipshop'),
        (['苏宁', 'suning'], 'suning'),
        (['小红书', 'xhs', 'xiaohongshu'], 'xiaohongshu'),
    ]
    for keywords, platform in mapping:
        if any(kw in text_lower for kw in keywords):
            return platform
    return None
