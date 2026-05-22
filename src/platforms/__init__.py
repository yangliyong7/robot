"""各电商联盟平台真实 API 客户端"""

from src.platforms.taobao import TaobaoClient
from src.platforms.jd import JDClient
from src.platforms.pdd import PDDClient
from src.platforms.meituan import MeituanClient
from src.platforms.douyin import DouyinClient
from src.platforms.vipshop import VipshopClient
from src.platforms.dangdang import DangdangClient
from src.platforms.kuaishou import KuaishouClient
from src.platforms.xiaomi import XiaomiClient
from src.platforms.yanxuan import YanxuanClient
from src.platforms.bilibili import BilibiliClient
from src.platforms.suning import SuningClient
from src.platforms.xiaohongshu import XiaohongshuClient
from src.platforms.xianyu import XianyuClient
from src.platforms.eleme import ElemeClient
from src.platforms.weixin_store import WeixinStoreClient
from src.platforms.ctrip import CtripClient
from src.platforms.tongcheng import TongchengClient
from src.platforms.qunar import QunarClient
from src.platforms.fliggy import FliggyClient
from src.platforms.taopiaopiao import TaopiaopiaoClient

__all__ = [
    'TaobaoClient',
    'JDClient',
    'PDDClient',
    'MeituanClient',
    'DouyinClient',
    'VipshopClient',
    'DangdangClient',
    'KuaishouClient',
    'XiaomiClient',
    'YanxuanClient',
    'BilibiliClient',
    'SuningClient',
    'XiaohongshuClient',
    'XianyuClient',
    'ElemeClient',
    'WeixinStoreClient',
    'CtripClient',
    'TongchengClient',
    'QunarClient',
    'FliggyClient',
    'TaopiaopiaoClient',
]
